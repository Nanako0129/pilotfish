#!/usr/bin/env python3
"""Reproducible, resumable dispatch-rate experiment runner. Python 3 stdlib only.

See benchmarks/dispatch-rate/README.md for the study file schema, the safety
contract this file implements, and how to reproduce a run.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLASSIFY_PATH = REPO_ROOT / "benchmarks/spontaneous-dispatch/classify_stream.py"
AGENTS_BUILDER_PATH = REPO_ROOT / "benchmarks/baton-compatibility/build-agents-json.py"

REQUIRED_FIELDS = (
    "name", "prompt", "fixture", "agents_from", "model", "evidence_dir", "arms",
    "target_n", "per_run_cap_usd", "total_cap_usd",
    "max_retries_per_cell", "max_backoff_seconds", "seed",
)

DISPATCH_PREDICATE_TEXT = (
    "A run counts as dispatched when the classifier reports exactly one "
    "top-level Agent call with subagent_type: mech-executor, "
    "run_in_background: false, no invocation-level model override, and the "
    "child result collected. Anything else is direct."
)

RATE_LIMIT_KEYWORDS = ("rate_limit", "rate limit", "quota", "usage_limit", "429")


# --------------------------------------------------------------------------
# lazy-loaded sibling modules (hyphenated filename => can't `import` directly)
# --------------------------------------------------------------------------

def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_classify_mod = None
_agents_mod = None


def get_classify():
    global _classify_mod
    if _classify_mod is None:
        _classify_mod = _load_module(CLASSIFY_PATH, "dispatch_rate_classify_stream")
    return _classify_mod


def get_agents_builder():
    global _agents_mod
    if _agents_mod is None:
        _agents_mod = _load_module(AGENTS_BUILDER_PATH, "dispatch_rate_build_agents_json")
    return _agents_mod


def resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (REPO_ROOT / path)


# --------------------------------------------------------------------------
# study file
# --------------------------------------------------------------------------

def load_study(path: str) -> dict:
    study = json.loads(Path(path).read_text())
    missing = [f for f in REQUIRED_FIELDS if f not in study]
    if missing:
        raise SystemExit(f"study file missing required fields: {', '.join(missing)}")
    if "control" not in study["arms"]:
        raise SystemExit("study file arms must include a 'control' arm (composition base)")
    for arm, spec in study["arms"].items():
        scope = spec.get("scope", "project")
        if scope not in ("project", "user"):
            raise SystemExit(f"arm '{arm}': scope must be 'project' or 'user', got {scope!r}")
    return study


def arm_scope(study: dict, arm: str) -> str:
    return study["arms"][arm].get("scope", "project")


def real_config_root() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(env) if env else (Path.home() / ".claude")).resolve()


def guard_config_dir(candidate: Path) -> None:
    """Safety contract 4 (scope extension): a user-scope per-cell config dir
    must never be, or live inside, the real Claude Code configuration root."""
    real = real_config_root()
    candidate_r = candidate.resolve()
    inside = candidate_r == real
    if not inside:
        try:
            candidate_r.relative_to(real)
            inside = True
        except ValueError:
            inside = False
    if inside:
        raise SystemExit(
            f"refusing to use CLAUDE_CONFIG_DIR={candidate_r}: it is, or is inside, "
            f"the real configuration root {real}"
        )


def validate_paths(study: dict) -> None:
    checks = [resolve(study["prompt"]), resolve(study["fixture"]), resolve(study["agents_from"])]
    for spec in study["arms"].values():
        checks.append(resolve(spec["policy"]))
    missing = [str(p) for p in checks if not p.exists()]
    if missing:
        raise SystemExit("paths do not resolve: " + ", ".join(missing))


def resolve_evidence_dir(study: dict) -> Path:
    return resolve(study["evidence_dir"])


def _nearest_existing_ancestor(path: Path) -> Path:
    p = path
    while not p.exists():
        parent = p.parent
        if parent == p:  # hit filesystem root without finding anything
            break
        p = parent
    return p


def check_evidence_dir_git_ignored(evidence_dir: Path) -> str:
    """Safety contract 6: refuse to spawn anything unless the resolved
    evidence_dir is Git-ignored (streams carry local paths / session ids).
    Probes evidence_dir itself (its nearest existing ancestor if it doesn't
    exist yet) -- NOT REPO_ROOT, which is always the pilotfish checkout and
    would make the "not a Git work tree" branch unreachable and hard-refuse
    any evidence_dir living outside a work tree entirely. Returns a short
    status string; raises SystemExit if unignored. Never leaks raw `git`
    stderr -- every git call here is captured, and only this function's own
    constructed message reaches the operator."""
    probe_dir = _nearest_existing_ancestor(evidence_dir)
    probe = subprocess.run(
        ["git", "-C", str(probe_dir), "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True,
    )
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return "skipped: not a Git work tree"
    result = subprocess.run(
        ["git", "-C", str(probe_dir), "check-ignore", "-q", "--", str(evidence_dir)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        toplevel = subprocess.run(
            ["git", "-C", str(probe_dir), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
        try:
            root = Path(toplevel.stdout.strip()).resolve()
            # FIX C: no trailing slash -- `git check-ignore` does not match a
            # trailing-slash directory pattern against a path that does not
            # exist on disk yet (verified: `ev/` -> not matched, `ev` ->
            # matched), and evidence_dir is exactly that case here. Without
            # the slash the pattern still matches the directory once it
            # exists, and also matches sooner.
            suggested = evidence_dir.relative_to(root).as_posix()
        except (ValueError, OSError):
            suggested = str(evidence_dir)
        raise SystemExit(
            f"refusing to start: evidence_dir {evidence_dir} is not Git-ignored "
            f"(raw stream captures would land in a Git-visible path); add this "
            f"line to .gitignore: {suggested}"
        )
    return "ok"


def composed_policy_bytes(study: dict, arm: str) -> bytes:
    """control's own policy is the base; every other arm appends its file as a
    section onto that base (`bytes(base) + b"\\n" + bytes(section)`)."""
    base = resolve(study["arms"]["control"]["policy"]).read_bytes()
    if arm == "control":
        return base
    section = resolve(study["arms"][arm]["policy"]).read_bytes()
    return base + b"\n" + section


def fixture_tree_sha256(fixture_dir: Path) -> str:
    """Digest exactly the bytes `shutil.copytree(symlinks=False)` will deliver.

    `Path.rglob` does not descend into symlinked directories, but `copytree`
    materializes them, so a rglob-based digest silently excludes files that the
    fixture copy actually contains — content under such a link could then change
    between runs without tripping the drift gate. `os.walk(followlinks=True)`
    matches what is delivered, which is the only tree the digest may describe.
    """
    entries = []
    for dirpath, dirnames, filenames in os.walk(fixture_dir, followlinks=True):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for name in sorted(filenames):
            p = Path(dirpath) / name
            rel = p.relative_to(fixture_dir).as_posix()
            if ".git" in Path(rel).parts:
                continue
            entries.append(f"{rel}\0{hashlib.sha256(p.read_bytes()).hexdigest()}")
    entries.sort()
    return hashlib.sha256("\n".join(entries).encode()).hexdigest()


def build_schedule(study: dict) -> list[str]:
    cells = []
    for arm in sorted(study["arms"]):
        for i in range(1, study["target_n"] + 1):
            cells.append(f"{arm}#{i}")
    rng = random.Random(study["seed"])
    rng.shuffle(cells)
    return cells


def build_header(study: dict) -> dict:
    prompt_bytes = resolve(study["prompt"]).read_bytes()
    policies = {}
    for arm in study["arms"]:
        b = composed_policy_bytes(study, arm)
        policies[arm] = {
            "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
            "scope": arm_scope(study, arm),
        }
    return {
        "seed": study["seed"],
        "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        "fixture_tree_sha256": fixture_tree_sha256(resolve(study["fixture"])),
        "policies": policies,
    }


# --------------------------------------------------------------------------
# plan
# --------------------------------------------------------------------------

def cmd_plan(args: argparse.Namespace) -> int:
    study = load_study(args.study)
    validate_paths(study)
    schedule = build_schedule(study)
    header = build_header(study)
    print(json.dumps({"schedule": schedule, "header": header}, indent=2))
    return 0


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def ensure_evidence_dir(evidence_dir: Path) -> None:
    sentinel = evidence_dir / ".pilotfish-created"
    if evidence_dir.exists():
        # Known accepted gap (A5, deferred): an *empty* foreign directory is
        # silently accepted here because `any(evidence_dir.iterdir())` is
        # False for it, same as a directory this tool created. Not fixed --
        # narrow and low-severity (nothing has ever been written into it).
        if not sentinel.exists() and any(evidence_dir.iterdir()):
            raise SystemExit(
                f"refusing to use {evidence_dir}: it exists and was not created by this tool"
            )
    else:
        evidence_dir.mkdir(parents=True)
    sentinel.touch()


def save_state(state: dict, evidence_dir: Path) -> None:
    # unique per-process tmp name: two `run`s racing on a hardcoded name could
    # collide on os.replace (observed as a stray FileNotFoundError) even
    # though the run-level lock below is what actually prevents concurrency.
    tmp = evidence_dir / f"state.json.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, evidence_dir / "state.json")


def acquire_run_lock(evidence_dir: Path):
    """Safety contract extension (F1): only one `run` may operate on a given
    evidence_dir at a time -- concurrent runs each hold their own in-memory
    state and save_state()'s whole-file rewrite lets a later writer silently
    erase an earlier writer's reservations, defeating total_cap_usd. `plan`
    and `report` are read-only and don't need this lock."""
    lock_path = evidence_dir / ".lock"
    lock_file = open(lock_path, "a+")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.seek(0)
        holder = lock_file.read().strip()
        lock_file.close()
        raise SystemExit(
            f"refusing to start: another `run` already holds the lock on "
            f"{evidence_dir} (pid {holder or 'unknown'})"
        )
    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file  # caller holds this open for the whole run; closing
    # (including at process exit via signal) releases the OS-level flock


def digest_drift(stored_header: dict, fresh_header: dict) -> list[str]:
    """R8/FIX1: name every policy/prompt/fixture input whose bytes differ
    between the header recorded when this study began and what's on disk
    right now. Empty list means every input is still the same bytes."""
    diffs = []
    if stored_header.get("prompt_sha256") != fresh_header.get("prompt_sha256"):
        diffs.append(
            f"prompt: stored {stored_header.get('prompt_sha256')} vs "
            f"current {fresh_header.get('prompt_sha256')}"
        )
    if stored_header.get("fixture_tree_sha256") != fresh_header.get("fixture_tree_sha256"):
        diffs.append(
            f"fixture tree: stored {stored_header.get('fixture_tree_sha256')} vs "
            f"current {fresh_header.get('fixture_tree_sha256')}"
        )
    stored_policies = stored_header.get("policies", {})
    for arm, fresh_p in fresh_header.get("policies", {}).items():
        stored_p = stored_policies.get(arm)
        if stored_p is None:
            continue
        if stored_p.get("sha256") != fresh_p.get("sha256"):
            diffs.append(
                f"policy '{arm}': stored {stored_p.get('sha256')} "
                f"({stored_p.get('bytes')} bytes) vs current {fresh_p.get('sha256')} "
                f"({fresh_p.get('bytes')} bytes)"
            )
        # FIX B: scope is "the single variable across arms" per the spec --
        # changing it between runs (e.g. project -> user) silently mixes
        # setting-sources within one arm's attempts while the header still
        # claims a single scope. Bytes-only comparison above can't catch
        # this, so it's checked separately, same message shape as a digest
        # change.
        if stored_p.get("scope") != fresh_p.get("scope"):
            diffs.append(
                f"policy '{arm}' scope: stored {stored_p.get('scope')} vs "
                f"current {fresh_p.get('scope')}"
            )
    return diffs


def load_or_init_state(study: dict, evidence_dir: Path, fresh_header: dict) -> dict:
    state_path = evidence_dir / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state.get("seed") != study["seed"]:
            raise SystemExit("resume refused: study seed changed since state was created")
        diffs = digest_drift(state["header"], fresh_header)
        if diffs:
            raise SystemExit(
                "resume refused: policy, prompt or fixture bytes changed since "
                "this study began -- this is no longer a single study. Start a "
                "new evidence_dir if you want to study the new bytes; there is "
                "no override.\n  " + "\n  ".join(diffs)
            )
        return state
    state = {
        "study_name": study.get("name"),
        "seed": study["seed"],
        "schedule": build_schedule(study),
        "header": fresh_header,
        "reservations": [],
        "cells": {},
        "backoff_seconds_used": 0.0,
        "stopped_reason": None,
    }
    save_state(state, evidence_dir)
    return state


def snapshot_run_inputs(study: dict) -> tuple[str, Path]:
    """FIX A: snapshot the prompt bytes and the fixture tree exactly once per
    `run` invocation, mirroring how policy bytes are already snapshotted at
    the top of _cmd_run_locked. Every spawn (spawn_cell) and every per-cell
    fixture copy (make_run_root) in this invocation must read from this
    snapshot rather than re-touching the source paths -- otherwise an edit to
    the prompt file or the fixture tree mid-run is picked up by later cells
    while the header (and every attempt's recorded digest) still names the
    original bytes, corrupting provenance undetectably. The caller owns
    cleanup via cleanup_run_root() once the run is done."""
    # Same TMPDIR-inside-real-config-root guard make_run_root applies, before
    # any filesystem creation.
    guard_config_dir(Path(tempfile.gettempdir()).resolve())
    # decode() rather than read_text(): read_text() applies universal newlines,
    # so a CRLF prompt file is delivered LF-normalized while build_header()
    # digests the raw bytes -- the recorded prompt_sha256 would then describe
    # bytes that were never sent.
    prompt_text = resolve(study["prompt"]).read_bytes().decode()
    snapshot_root = Path(tempfile.mkdtemp(prefix="pilotfish-dispatch-rate-snapshot-"))
    (snapshot_root / ".pilotfish-created").touch()
    fixture_snapshot = snapshot_root / "fixture"
    shutil.copytree(resolve(study["fixture"]), fixture_snapshot)
    return prompt_text, fixture_snapshot


def make_run_root(study: dict, arm: str, policy_bytes: bytes,
                   fixture_source: Path) -> tuple[Path, Path, Path | None, str]:
    scope = arm_scope(study, arm)
    # Guard BOTH scopes, before any filesystem creation (A1): the demonstrated
    # harm is not the scope-inherited config var, it's that run_root itself
    # (fixture copy, git repo, agents.json -- created below regardless of
    # scope) can land inside the real config root, e.g. via a TMPDIR pointed
    # there. mkdtemp always creates its directory under tempfile.gettempdir(),
    # so guarding that base directory bounds every possible run_root.
    guard_config_dir(Path(tempfile.gettempdir()).resolve())

    run_root = Path(tempfile.mkdtemp(prefix="pilotfish-dispatch-rate-"))
    (run_root / ".pilotfish-created").touch()
    fixture_copy = run_root / "fixture"
    # FIX A: copy from the run's frozen snapshot, never from the source path
    # on disk again -- the source could have been edited since the snapshot
    # was taken at the top of _cmd_run_locked.
    shutil.copytree(fixture_source, fixture_copy)

    config_dir: Path | None = None
    if scope == "project":
        (fixture_copy / "CLAUDE.md").write_bytes(policy_bytes)
        setting_sources = "project,local"
    else:  # "user" -- validated by load_study
        config_dir = run_root / "user-config"
        guard_config_dir(config_dir)  # belt-and-braces on top of the base-dir guard above
        config_dir.mkdir()
        (config_dir / "CLAUDE.md").write_bytes(policy_bytes)
        setting_sources = "user,project,local"

    subprocess.run(["git", "init", "-q"], cwd=fixture_copy, check=True)
    subprocess.run(["git", "add", "."], cwd=fixture_copy, check=True)
    subprocess.run(
        ["git", "-c", "user.name=pilotfish-benchmark",
         "-c", "user.email=pilotfish-benchmark@example.invalid",
         "commit", "-q", "-m", "baseline"],
        cwd=fixture_copy, check=True,
    )
    agents = get_agents_builder().build_agents(resolve(study["agents_from"]))
    (run_root / "agents.json").write_text(json.dumps(agents, separators=(",", ":")))
    return run_root, fixture_copy, config_dir, setting_sources


def spawn_cell(study: dict, fixture_copy: Path, run_root: Path, config_dir: Path | None,
               setting_sources: str, stream_path: Path, err_path: Path,
               prompt_text: str) -> None:
    # FIX A: prompt_text is the run's frozen snapshot (see
    # snapshot_run_inputs), never re-read from disk here -- a mid-run edit to
    # the prompt file must not reach a later spawn while the header still
    # names the original bytes.
    agents_json = (run_root / "agents.json").read_text()
    cmd = [
        "claude", "-p", prompt_text,
        "--model", study["model"],
        "--setting-sources", setting_sources,
        "--strict-mcp-config",
        "--output-format", "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--dangerously-skip-permissions",
        "--max-budget-usd", str(study["per_run_cap_usd"]),
        "--agents", agents_json,
    ]
    env = dict(os.environ)
    if config_dir is not None:
        env["CLAUDE_CONFIG_DIR"] = str(config_dir)
    with open(stream_path, "wb") as out, open(err_path, "wb") as err:
        subprocess.run(cmd, cwd=fixture_copy, stdout=out, stderr=err, env=env)


def cleanup_run_root(run_root: Path) -> None:
    """FIX3: remove a cell's disposable run root once its evidence has been
    written out, so an unattended study doesn't accumulate one fixture+git
    copy per attempt in $TMPDIR forever. Only ever removes a directory this
    tool created -- guarded by the .pilotfish-created sentinel make_run_root
    writes -- never a foreign path."""
    if (run_root / ".pilotfish-created").exists():
        shutil.rmtree(run_root, ignore_errors=True)


def git_changed_files(fixture_copy: Path) -> list[str]:
    out = subprocess.run(
        ["git", "status", "--porcelain"], cwd=fixture_copy,
        capture_output=True, text=True,
    )
    return sorted({line[3:].strip() for line in out.stdout.splitlines() if line.strip()})


def evaluate_stream(stream_path: Path, err_path: Path) -> dict:
    try:
        verdict = get_classify().classify(stream_path)
    except Exception:
        # A stray non-JSON line on stdout (e.g. a "Warning:" line) must not
        # abort the study -- record it as an invalid, retryable run instead
        # of crashing (which would leave the cell in_progress forever and
        # burn per_run_cap_usd on every resume with zero observations).
        return {
            "valid": False, "rate_limited": False, "dispatched": False,
            "subagent_type": None, "foreground": None, "collected": False,
            "cost_usd": None, "raw_stream_sha256": None,
            "observed_main_model": None, "client_version": None,
            "terminal_subtype": None, "reason": "unparseable_stream",
        }
    terminal_subtype = None
    for line in stream_path.read_bytes().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            terminal_subtype = event.get("subtype")
    err_text = err_path.read_text(errors="replace") if err_path.exists() else ""

    valid = bool(verdict["model_costs_usd"]) and terminal_subtype == "success"
    rate_limited = False
    reason = None
    if not valid:
        haystack = f"{terminal_subtype or ''} {err_text}".lower()
        rate_limited = any(k in haystack for k in RATE_LIMIT_KEYWORDS)
        # name the actual defect: a "success" terminal subtype with empty
        # model_costs_usd (the source study's contamination shape) is not a
        # success -- reporting reason="success" would be forensically
        # misleading, so empty cost data always takes priority.
        if not verdict["model_costs_usd"]:
            reason = "empty_model_costs_usd"
        else:
            reason = terminal_subtype or "empty_model_costs_usd"

    matching = [
        c for c in verdict["agent_calls"]
        if c.get("subagent_type") == "mech-executor"
        and c.get("run_in_background") is False
        and not c.get("invocation_model_present")
    ]
    dispatched = (
        valid
        and len(verdict["agent_calls"]) == 1
        and len(matching) == 1
        and verdict["subagent_result_collected"]
    )

    return {
        "valid": valid,
        "rate_limited": rate_limited,
        "dispatched": dispatched,
        "subagent_type": matching[0]["subagent_type"] if dispatched else None,
        "foreground": (not matching[0]["run_in_background"]) if dispatched else None,
        "collected": bool(verdict["subagent_result_collected"]) if dispatched else False,
        "cost_usd": verdict["client_reported_cost_usd"],
        "raw_stream_sha256": verdict["raw_stream_sha256"],
        "observed_main_model": verdict["observed_main_model"],
        "client_version": verdict["client_version"],
        "terminal_subtype": terminal_subtype,
        "reason": reason,
    }


def cmd_run(args: argparse.Namespace) -> int:
    study = load_study(args.study)
    validate_paths(study)
    evidence_dir = resolve_evidence_dir(study)
    git_ignore_status = check_evidence_dir_git_ignored(evidence_dir)  # before any filesystem creation (F2)
    ensure_evidence_dir(evidence_dir)  # creates it (with sentinel) if needed, refuses a foreign dir
    lock_file = acquire_run_lock(evidence_dir)  # held for the whole run (F1)
    try:
        return _cmd_run_locked(study, evidence_dir, git_ignore_status, args.keep_run_roots)
    finally:
        lock_file.close()  # releases the flock; also happens automatically on any signal kill


def _cmd_run_locked(study: dict, evidence_dir: Path, git_ignore_status: str,
                     keep_run_roots: bool = False) -> int:
    streams_dir = evidence_dir / "streams"
    streams_dir.mkdir(exist_ok=True)
    fresh_header = build_header(study)  # FIX1: recomputed every run, never read back from state
    state = load_or_init_state(study, evidence_dir, fresh_header)
    state["header"]["evidence_dir_git_ignore_check"] = git_ignore_status
    policy_bytes = {arm: composed_policy_bytes(study, arm) for arm in study["arms"]}
    # FIX A: freeze the prompt and fixture tree once, right after the
    # drift-checked header above is computed, exactly like policy_bytes.
    # Every cell below reads from this snapshot, never from the source paths
    # again, so a mid-run edit to either can't reach a later spawn while the
    # header still names the original bytes.
    prompt_text, fixture_snapshot = snapshot_run_inputs(study)

    try:
        return _run_cells(study, evidence_dir, state, fresh_header, policy_bytes,
                           prompt_text, fixture_snapshot, keep_run_roots)
    finally:
        cleanup_run_root(fixture_snapshot.parent)


def _run_cells(study: dict, evidence_dir: Path, state: dict, fresh_header: dict,
               policy_bytes: dict, prompt_text: str, fixture_snapshot: Path,
               keep_run_roots: bool) -> int:
    streams_dir = evidence_dir / "streams"
    for cell in state["schedule"]:
        info = state["cells"].setdefault(cell, {"status": "pending", "attempts": []})
        if info["status"] in ("complete", "exhausted"):
            continue
        arm = cell.split("#", 1)[0]

        while True:
            # attempt_no (for numbering/filenames) counts every recorded
            # attempt including interrupted placeholders, so a resume never
            # reuses a filename (A3). The retry budget only counts attempts
            # that actually got evaluated -- an interrupted (hard-killed)
            # attempt was never observed, so it shouldn't burn retry budget.
            attempt_no = len(info["attempts"]) + 1
            evaluated_attempts = sum(
                1 for a in info["attempts"] if a.get("status") != "interrupted"
            )
            if evaluated_attempts >= 1 + study["max_retries_per_cell"]:
                info["status"] = "exhausted"
                save_state(state, evidence_dir)
                break

            cumulative = sum(r["charged_usd"] for r in state["reservations"])
            if cumulative + study["per_run_cap_usd"] > study["total_cap_usd"]:
                blocking = state["reservations"][-1] if state["reservations"] else None
                msg = (
                    f"refusing {cell} attempt {attempt_no}: cumulative charged "
                    f"${cumulative:.4f} + reservation ${study['per_run_cap_usd']:.4f} "
                    f"would exceed total_cap_usd ${study['total_cap_usd']:.4f}"
                )
                if blocking is not None:
                    msg += (
                        f"; blocking reservation: cell={blocking['cell']} "
                        f"attempt={blocking['attempt']} charged=${blocking['charged_usd']:.4f}"
                    )
                print(msg)
                save_state(state, evidence_dir)
                return 1

            reservation = {
                "cell": cell, "attempt": attempt_no,
                "charged_usd": study["per_run_cap_usd"], "status": "reserved",
            }
            state["reservations"].append(reservation)
            info["status"] = "in_progress"
            # Record the attempt itself before spawn too (A3): if the process
            # is killed mid-spawn, len(info["attempts"]) must already reflect
            # this attempt, or a resume recomputes the same attempt_no and
            # overwrites this attempt's raw stream file with the retry's.
            info["attempts"].append({"attempt": attempt_no, "valid": False, "status": "interrupted"})
            save_state(state, evidence_dir)  # persisted before spawn: survives a hard kill

            try:
                run_root, fixture_copy, config_dir, setting_sources = make_run_root(
                    study, arm, policy_bytes[arm], fixture_snapshot
                )
            except SystemExit:
                # Refused before any spawn happened (F4 guard) -- A2: don't
                # leave a charged reservation or a phantom attempt behind for
                # zero spend, or repeated retries could exhaust
                # total_cap_usd having spent nothing.
                state["reservations"].pop()
                info["attempts"].pop()
                info["status"] = "in_progress" if info["attempts"] else "pending"
                save_state(state, evidence_dir)
                raise

            stream_path = streams_dir / f"{cell.replace('#', '-')}-attempt{attempt_no}.jsonl"
            err_path = streams_dir / f"{cell.replace('#', '-')}-attempt{attempt_no}.err"
            spawn_cell(study, fixture_copy, run_root, config_dir, setting_sources,
                       stream_path, err_path, prompt_text)

            evidence = evaluate_stream(stream_path, err_path)
            evidence.update({
                "attempt": attempt_no,
                "arm": arm,
                "cell": cell,
                "schedule_position": state["schedule"].index(cell),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "policy_sha256": fresh_header["policies"][arm]["sha256"],
                "prompt_sha256": fresh_header["prompt_sha256"],
                "fixture_tree_sha256": fresh_header["fixture_tree_sha256"],
                "changed_files": git_changed_files(fixture_copy),
                "run_root": str(run_root),
                "scope": arm_scope(study, arm),
                "setting_sources": setting_sources,
                "config_dir": str(config_dir) if config_dir is not None else None,
            })

            if evidence["valid"]:
                reservation["charged_usd"] = (
                    evidence["cost_usd"] if evidence["cost_usd"] is not None
                    else study["per_run_cap_usd"]
                )
            reservation["status"] = "done"
            evidence["reservation_charged_usd"] = reservation["charged_usd"]
            info["attempts"][-1] = evidence  # replace the pre-spawn placeholder (A3)

            # FIX3: clean up the disposable run root once its evidence is
            # written out. Only for valid attempts -- an invalid one is
            # exactly what a human will want to inspect, so it's left in
            # place (as is anything killed mid-flight: that path never
            # reaches here at all).
            if evidence["valid"] and not keep_run_roots:
                cleanup_run_root(run_root)

            if evidence["valid"]:
                info["status"] = "complete"
                save_state(state, evidence_dir)
                break

            save_state(state, evidence_dir)

            if evidence["rate_limited"]:
                if attempt_no >= 1 + study["max_retries_per_cell"]:
                    info["status"] = "exhausted"
                    state["stopped_reason"] = (
                        f"{cell}: retries exhausted after rate-limit rejection "
                        f"({attempt_no} attempts)"
                    )
                    save_state(state, evidence_dir)
                    print(state["stopped_reason"])
                    return 2
                remaining = study["max_backoff_seconds"] - state["backoff_seconds_used"]
                backoff = min(2 ** (attempt_no - 1), remaining)
                if backoff <= 0:
                    info["status"] = "exhausted"
                    state["stopped_reason"] = (
                        f"{cell}: backoff budget exhausted "
                        f"({state['backoff_seconds_used']:.1f}s used of "
                        f"{study['max_backoff_seconds']:.1f}s cap)"
                    )
                    save_state(state, evidence_dir)
                    print(state["stopped_reason"])
                    return 2
                time.sleep(backoff)
                state["backoff_seconds_used"] += backoff
                save_state(state, evidence_dir)
                continue  # retry same cell

            # non-rate-limit invalid run: bounded retry, no backoff, no global stop
            if attempt_no >= 1 + study["max_retries_per_cell"]:
                info["status"] = "exhausted"
                save_state(state, evidence_dir)
                break
            continue

    complete = sum(1 for c in state["cells"].values() if c["status"] == "complete")
    print(f"run: {complete}/{len(state['schedule'])} cells complete")
    return 0


# --------------------------------------------------------------------------
# fisher exact (two-sided), pure stdlib
# --------------------------------------------------------------------------

def fisher_exact_two_sided(table: list[list[int]]) -> float:
    (a, b), (c, d) = table
    n = a + b + c + d
    row1, row2, col1 = a + b, c + d, a + c

    def hyper(x: int) -> float:
        y, z = row1 - x, col1 - x
        w = row2 - z
        return math.comb(row1, x) * math.comb(row2, z) / math.comb(n, col1)

    p_obs = hyper(a)
    total = 0.0
    lo, hi = max(0, col1 - row2), min(row1, col1)
    for x in range(lo, hi + 1):
        p = hyper(x)
        if p <= p_obs * (1 + 1e-9):
            total += p
    return total


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def _comparisons(control: tuple[int, int], placebo: tuple[int, int],
                  candidate: tuple[int, int]) -> dict:
    def frac(pair: tuple[int, int]) -> str:
        d, f = pair
        return f"{d}/{d + f}"

    return {
        "candidate_vs_control": {
            "a": frac(candidate), "b": frac(control),
            "fisher_two_sided_p": round(fisher_exact_two_sided([list(candidate), list(control)]), 5),
        },
        "candidate_vs_placebo": {
            "a": frac(candidate), "b": frac(placebo),
            "fisher_two_sided_p": round(fisher_exact_two_sided([list(candidate), list(placebo)]), 5),
        },
        "placebo_vs_control": {
            "a": frac(placebo), "b": frac(control),
            "fisher_two_sided_p": round(fisher_exact_two_sided([list(placebo), list(control)]), 5),
        },
    }


def cmd_report_legacy(path: str) -> int:
    data = json.loads(Path(path).read_text())
    arms = data["arms"]
    for required in ("control", "placebo"):
        if required not in arms:
            raise SystemExit(f"legacy results.json missing '{required}' arm")
    candidate_key = next(
        (k for k in ("candidate", "candidate_full") if k in arms),
        None,
    ) or next((k for k in sorted(arms) if k.startswith("candidate")), None)
    if candidate_key is None:
        raise SystemExit("legacy results.json has no candidate arm")

    def pair(name: str) -> tuple[int, int]:
        a = arms[name]
        return a["dispatched"], a["attempts"] - a["dispatched"]

    control, placebo, candidate = pair("control"), pair("placebo"), pair(candidate_key)

    out = {
        "dispatch_predicate": DISPATCH_PREDICATE_TEXT,
        "source": "legacy",
        "arms": {
            "control": {"dispatched": control[0], "attempts": control[0] + control[1]},
            "placebo": {"dispatched": placebo[0], "attempts": placebo[0] + placebo[1]},
            "candidate": {
                "dispatched": candidate[0], "attempts": candidate[0] + candidate[1],
                "source_arm": candidate_key,
            },
        },
        "comparisons": _comparisons(control, placebo, candidate),
    }
    print(json.dumps(out, indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    if args.legacy:
        return cmd_report_legacy(args.path)

    study = load_study(args.path)
    evidence_dir = resolve_evidence_dir(study)
    state_path = evidence_dir / "state.json"
    if not state_path.exists():
        print(json.dumps({"dispatch_predicate": DISPATCH_PREDICATE_TEXT, "arms": {}}, indent=2))
        return 0
    state = json.loads(state_path.read_text())

    arms = sorted(study["arms"])
    tally: dict[str, tuple[int, int]] = {}
    client_version = None
    for arm in arms:
        valid = [
            a for cell, info in state["cells"].items()
            if cell.split("#", 1)[0] == arm
            for a in info["attempts"] if a["valid"]
        ]
        dispatched = sum(1 for a in valid if a["dispatched"])
        tally[arm] = (dispatched, len(valid) - dispatched)
        if client_version is None:
            client_version = next((a["client_version"] for a in valid if a.get("client_version")), None)

    # FIX D: carry the header and a per-arm policy digest block, same shape
    # as the preserved source study, so this file can itself be fed through
    # `report --legacy` (R8 -- provenance must travel with the numbers).
    header = state.get("header", {})
    policies = header.get("policies", {})
    result = {
        "dispatch_predicate": DISPATCH_PREDICATE_TEXT,
        "seed": header.get("seed"),
        "prompt_sha256": header.get("prompt_sha256"),
        "fixture_tree_sha256": header.get("fixture_tree_sha256"),
        "client": client_version,
        "arms": {
            a: {
                "dispatched": d, "attempts": d + f,
                "scope": arm_scope(study, a),
                "policy": {
                    "bytes": policies.get(a, {}).get("bytes"),
                    "sha256": policies.get(a, {}).get("sha256"),
                },
            }
            for a, (d, f) in tally.items()
        },
    }

    shortfall = {
        a: study["target_n"] - (d + f) for a, (d, f) in tally.items()
        if (d + f) < study["target_n"]
    }
    if shortfall:
        result["comparisons"] = None
        result["refused"] = (
            f"pooled comparisons refused: target_n={study['target_n']} not yet reached "
            f"for {shortfall}"
        )
    elif {"control", "placebo", "candidate"} <= tally.keys():
        result["comparisons"] = _comparisons(tally["control"], tally["placebo"], tally["candidate"])

    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0


# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_study.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan")
    p_plan.add_argument("study")
    p_plan.set_defaults(func=cmd_plan)

    p_run = sub.add_parser("run")
    p_run.add_argument("study")
    p_run.add_argument(
        "--keep-run-roots", action="store_true",
        help="don't remove a cell's disposable run root after its evidence is written; for debugging",
    )
    p_run.set_defaults(func=cmd_run)

    p_report = sub.add_parser("report")
    p_report.add_argument("path", help="study.json, or a legacy results.json with --legacy")
    p_report.add_argument("--legacy", action="store_true")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
