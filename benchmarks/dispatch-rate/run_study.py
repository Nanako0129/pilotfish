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

# Structural issue 1 (third review round): a hand-written list of "all the
# run-affecting inputs" has drifted twice before (total_cap_usd and
# per_run_cap_usd were both missing from the header). Instead of a second
# hand-written list, every REQUIRED_FIELDS entry is run-affecting UNLESS it
# is named here, with a reason -- and RUN_AFFECTING_HEADER_KEYS below (the
# single declared source build_header()/build_header_from_snapshot() must
# satisfy) is checked against this set at import time, so a future field
# added to REQUIRED_FIELDS without a decision either way fails the test
# suite immediately instead of waiting for a reviewer to notice.
NON_RUN_AFFECTING_FIELDS = frozenset({
    "name",          # a human label; never reaches the classifier or a spend decision
    "evidence_dir",  # where evidence is written, not an input to what gets run
})
RUN_AFFECTING_FIELDS = tuple(f for f in REQUIRED_FIELDS if f not in NON_RUN_AFFECTING_FIELDS)

# Declares, for every run-affecting field, the header key(s) that represent
# it. build_header() / build_header_from_snapshot() must emit every key
# listed here -- test_header_covers_every_run_affecting_field() in the test
# suite checks their actual output against this mapping.
RUN_AFFECTING_HEADER_KEYS = {
    "prompt": ("prompt_sha256",),
    "fixture": ("fixture_tree_sha256",),
    "agents_from": ("agents_sha256",),
    "model": ("model",),
    "arms": ("arms", "policies"),
    "target_n": ("target_n",),
    "per_run_cap_usd": ("per_run_cap_usd",),
    "total_cap_usd": ("total_cap_usd",),
    "max_retries_per_cell": ("max_retries_per_cell",),
    "max_backoff_seconds": ("max_backoff_seconds",),
    "seed": ("seed",),
}
assert set(RUN_AFFECTING_HEADER_KEYS) == set(RUN_AFFECTING_FIELDS), (
    "RUN_AFFECTING_HEADER_KEYS has drifted from REQUIRED_FIELDS -- add the "
    "new field's header key(s) here, or add the field to "
    "NON_RUN_AFFECTING_FIELDS with a reason, before shipping"
)

# The two spend ceilings ratchet instead of drift-refusing on ANY change like
# every other header field: LOWERING one only tightens an already-running
# study (it can never let it spend more than originally agreed), so it's
# allowed. RAISING one is refused outright on resume -- that is exactly the
# budget-ceiling bypass this field's presence in the header exists to catch
# (E2: resuming a study after editing total_cap_usd up must not restart a
# run that had already stopped at its hard ceiling). See cap_ratchet_diffs().
RATCHET_FIELDS = ("total_cap_usd", "per_run_cap_usd")

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
    # D7: .resolve() follows any symlink in the path (including evidence_dir
    # itself, or an ignored ancestor) to its real target BEFORE either the
    # Git-ignore check or any creation/write happens -- otherwise a symlink
    # living under an ignored path but pointing at a Git-visible directory
    # lets check_evidence_dir_git_ignored probe the ignored spelling while
    # ensure_evidence_dir and every stream write follow the link to the
    # visible target, passing the safety check while writing raw JSONL into
    # a visible directory. resolve() is safe on a path that doesn't exist yet
    # (Path.resolve() is non-strict by default).
    return resolve(study["evidence_dir"]).resolve()


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


# C1: the digest must ignore exactly what the fixture copy ignores, so the
# two can never drift apart. Every `shutil.copytree` of a fixture in this
# file passes this same ignore pattern.
FIXTURE_COPY_IGNORE = shutil.ignore_patterns(".git")


def fixture_tree_sha256(fixture_dir: Path) -> str:
    """Digest exactly the tree `shutil.copytree(fixture_dir, ..., symlinks=False,
    ignore=FIXTURE_COPY_IGNORE)` will deliver.

    `Path.rglob` does not descend into symlinked directories, but `copytree`
    materializes them, so a rglob-based digest silently excludes files that the
    fixture copy actually contains — content under such a link could then change
    between runs without tripping the drift gate. `os.walk(followlinks=True)`
    matches what is delivered, which is the only tree the digest may describe.

    Directory entries are included (as `"<rel>/\\0<dir>"` markers) so that
    adding or removing an empty directory moves the digest even though it
    contributes no file hash of its own -- `copytree` still delivers that
    directory.
    """
    entries = []
    for dirpath, dirnames, filenames in os.walk(fixture_dir, followlinks=True):
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        rel_dir = Path(dirpath).relative_to(fixture_dir).as_posix()
        if rel_dir != ".":
            entries.append(f"{rel_dir}/\0<dir>")
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


def _agents_payload_bytes(agents_from: Path) -> bytes:
    """The canonical byte form of a built `--agents` payload -- sort_keys so
    the digest doesn't depend on directory-listing order, used both to hash
    and to write the payload every place it's produced."""
    payload = get_agents_builder().build_agents(agents_from)
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def build_header(study: dict) -> dict:
    """Restructure (D1/D2/D3): the run header is the COMPLETE set of
    run-affecting inputs -- seed, target_n, model, the arm set, and the
    digests of prompt/fixture/agents/every arm's policy -- enumerated in this
    one place. Adding a new run-affecting input means adding one key here;
    digest_drift() below then protects it automatically, with no second edit
    anywhere else."""
    prompt_bytes = resolve(study["prompt"]).read_bytes()
    policies = {}
    for arm in study["arms"]:
        b = composed_policy_bytes(study, arm)
        policies[arm] = {
            "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
            "scope": arm_scope(study, arm),
        }
    agents_bytes = _agents_payload_bytes(resolve(study["agents_from"]))
    return {
        "seed": study["seed"],
        "target_n": study.get("target_n"),
        "model": study.get("model"),
        "arms": sorted(study["arms"]),
        "prompt_sha256": hashlib.sha256(prompt_bytes).hexdigest(),
        "fixture_tree_sha256": fixture_tree_sha256(resolve(study["fixture"])),
        "agents_sha256": hashlib.sha256(agents_bytes).hexdigest(),
        "policies": policies,
        # E2 / structural issue 1: these two were missing from the header,
        # so raising either on a resumed `run` silently restarted a study
        # that had already stopped at its hard ceiling. See RATCHET_FIELDS.
        "total_cap_usd": study.get("total_cap_usd"),
        "per_run_cap_usd": study.get("per_run_cap_usd"),
        "max_retries_per_cell": study.get("max_retries_per_cell"),
        "max_backoff_seconds": study.get("max_backoff_seconds"),
    }


def build_header_from_snapshot(study: dict, prompt_text: str, fixture_snapshot: Path,
                                policy_bytes: dict, agents_bytes: bytes) -> dict:
    """C8/D2: same shape as build_header(), but every digest is derived from
    already-frozen bytes (prompt_text, fixture_snapshot, policy_bytes,
    agents_bytes) instead of re-reading live source paths. Used by `run`,
    which must call this only after snapshot_run_inputs() and the
    policy_bytes read have both already happened -- see _cmd_run_locked."""
    policies = {}
    for arm, b in policy_bytes.items():
        policies[arm] = {
            "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
            "scope": arm_scope(study, arm),
        }
    return {
        "seed": study["seed"],
        "target_n": study.get("target_n"),
        "model": study.get("model"),
        "arms": sorted(policy_bytes),
        "prompt_sha256": hashlib.sha256(prompt_text.encode()).hexdigest(),
        "fixture_tree_sha256": fixture_tree_sha256(fixture_snapshot),
        "agents_sha256": hashlib.sha256(agents_bytes).hexdigest(),
        "policies": policies,
        "total_cap_usd": study.get("total_cap_usd"),
        "per_run_cap_usd": study.get("per_run_cap_usd"),
        "max_retries_per_cell": study.get("max_retries_per_cell"),
        "max_backoff_seconds": study.get("max_backoff_seconds"),
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


def digest_drift(stored_header: dict, fresh_header: dict, _path: str = "",
                  skip: frozenset = frozenset()) -> list[str]:
    """Restructure (requirement 2): a generic structural diff over the WHOLE
    header, not a hand-picked subset of fields -- every key present in either
    header (seed, target_n, model, arms, every digest, every arm's policy
    sub-dict...) is compared. A field added to build_header()/
    build_header_from_snapshot() is drift-protected the moment it exists
    here; nothing in this function names an individual field. Nested dicts
    (e.g. "policies") recurse so a single changed leaf (one arm's sha256, or
    its scope) is still named precisely. Empty list means every recorded
    input is still the same bytes.

    `skip` names top-level keys (only meaningful at the top level, hence
    `not _path`) excluded from this plain-equality comparison -- used for
    RATCHET_FIELDS, which have their own asymmetric (increase-refused,
    decrease-allowed) comparison in cap_ratchet_diffs() instead."""
    diffs = []
    for key in sorted(set(stored_header) | set(fresh_header)):
        if not _path and key in skip:
            continue
        label = f"{_path}{key}"
        stored_v, fresh_v = stored_header.get(key), fresh_header.get(key)
        if isinstance(stored_v, dict) and isinstance(fresh_v, dict):
            diffs.extend(digest_drift(stored_v, fresh_v, _path=f"{label}."))
        elif stored_v != fresh_v:
            diffs.append(f"{label}: stored {stored_v!r} vs current {fresh_v!r}")
    return diffs


def cap_ratchet_diffs(stored_header: dict, fresh_header: dict) -> list[str]:
    """E2: total_cap_usd / per_run_cap_usd may only shrink across a resume.
    Raising either is refused with the same "no override" shape digest_drift
    uses for every other input, naming both values."""
    diffs = []
    for key in RATCHET_FIELDS:
        old, new = stored_header.get(key), fresh_header.get(key)
        if old is None or new is None or new <= old:
            continue
        diffs.append(
            f"{key}: stored {old!r} vs current {new!r} (increase refused -- "
            "raising a spend ceiling on resume would restart a study that "
            "already stopped at its ceiling; lowering it is allowed)"
        )
    return diffs


def load_or_init_state(study: dict, evidence_dir: Path, fresh_header: dict) -> dict:
    state_path = evidence_dir / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state.get("seed") != study["seed"]:
            raise SystemExit("resume refused: study seed changed since state was created")
        diffs = digest_drift(state["header"], fresh_header, skip=frozenset(RATCHET_FIELDS))
        diffs += cap_ratchet_diffs(state["header"], fresh_header)
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


def snapshot_run_inputs(study: dict) -> tuple[str, Path, bytes]:
    """FIX A / D2: snapshot the prompt bytes, the fixture tree, AND the
    agents payload exactly once per `run` invocation, mirroring how policy
    bytes are already snapshotted at the top of _cmd_run_locked. Every spawn
    (spawn_cell) and every per-cell fixture copy (make_run_root) in this
    invocation must read from this snapshot rather than re-touching the
    source paths -- otherwise an edit to the prompt file, the fixture tree,
    or agents_from mid-run is picked up by later cells while the header (and
    every attempt's recorded digest) still names the original bytes,
    corrupting provenance undetectably -- and for agents_from specifically,
    letting one arm's cells mix mech-executor definitions within a single
    run/denominator. The caller owns cleanup via cleanup_run_root() once the
    run is done."""
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
    shutil.copytree(resolve(study["fixture"]), fixture_snapshot, ignore=FIXTURE_COPY_IGNORE)
    agents_bytes = _agents_payload_bytes(resolve(study["agents_from"]))
    return prompt_text, fixture_snapshot, agents_bytes


def make_run_root(study: dict, arm: str, policy_bytes: bytes,
                   fixture_source: Path, agents_bytes: bytes) -> tuple[Path, Path, Path | None, str]:
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
    shutil.copytree(fixture_source, fixture_copy, ignore=FIXTURE_COPY_IGNORE)

    config_dir: Path | None = None
    if scope == "project":
        (fixture_copy / "CLAUDE.md").write_bytes(policy_bytes)
        setting_sources = "project,local"
    else:  # "user" -- validated by load_study
        # C6: single-variable violation guard. A fixture that already ships a
        # CLAUDE.md is fine at project scope (the arm's policy simply
        # overwrites it), but at user scope the policy instead lands outside
        # the fixture entirely -- leaving the fixture's own CLAUDE.md in place
        # would make both the per-cell user policy AND the fixture's project
        # policy visible to the run, violating the spec's scope table ("fixture
        # CLAUDE.md absent" for user scope) and the single-variable-across-arms
        # contract. Refused rather than silently deleted (see README).
        existing = fixture_copy / "CLAUDE.md"
        if existing.exists():
            cleanup_run_root(run_root)  # nothing was spawned yet; don't leak the temp copy
            raise SystemExit(
                f"refusing user-scope arm '{arm}': fixture already contains "
                f"CLAUDE.md ({existing}); user scope requires the fixture to "
                f"carry no project-level policy -- remove it from the fixture "
                f"or run this arm at project scope"
            )
        config_dir = run_root / "user-config"
        guard_config_dir(config_dir)  # belt-and-braces on top of the base-dir guard above
        config_dir.mkdir()
        (config_dir / "CLAUDE.md").write_bytes(policy_bytes)
        setting_sources = "user,project,local"

    subprocess.run(["git", "init", "-q"], cwd=fixture_copy, check=True)
    subprocess.run(["git", "add", "."], cwd=fixture_copy, check=True)
    subprocess.run(
        # E3: --allow-empty -- a user-scope arm writes no CLAUDE.md into the
        # fixture copy (the policy lands in the per-cell CLAUDE_CONFIG_DIR
        # instead), so a fixture that is itself empty or contains only empty
        # directories leaves nothing staged; without this flag the baseline
        # commit fails with "nothing to commit" after budget was already
        # reserved and before any spawn. Harmless when there IS something
        # staged -- it only lifts the "nothing to commit" refusal, it never
        # forces an empty commit over real staged content.
        ["git", "-c", "user.name=pilotfish-benchmark",
         "-c", "user.email=pilotfish-benchmark@example.invalid",
         "commit", "-q", "--allow-empty", "-m", "baseline"],
        cwd=fixture_copy, check=True,
    )
    # D2: write the run's frozen agents snapshot -- never rebuild from the
    # live agents_from directory here. Every cell of every arm in this `run`
    # invocation gets exactly these bytes, the same bytes hashed into the
    # header's agents_sha256.
    (run_root / "agents.json").write_bytes(agents_bytes)
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


def _stream_looks_complete(stream_path: Path) -> bool:
    """E5: an interrupted attempt is recoverable only if the stream file the
    spawned `claude` process wrote is itself complete -- carries a terminal
    `type: "result"` event -- meaning the process had already finished
    (successfully or not) before this runner was killed, and only the local
    persistence step (evaluate_stream + save_state) never ran. A stream
    truncated mid-write (the far more common kill shape: the process itself
    was still running) has no terminal event and is NOT recoverable -- it
    must still be retried."""
    if not stream_path.exists():
        return False
    for line in stream_path.read_bytes().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result":
            return True
    return False


def evaluate_stream(stream_path: Path, err_path: Path) -> dict:
    err_text = err_path.read_text(errors="replace") if err_path.exists() else ""
    try:
        verdict = get_classify().classify(stream_path)
    except Exception:
        # A stray non-JSON line on stdout (e.g. a "Warning:" line) must not
        # abort the study -- record it as an invalid, retryable run instead
        # of crashing (which would leave the cell in_progress forever and
        # burn per_run_cap_usd on every resume with zero observations).
        #
        # C4: this early return must not hardcode rate_limited: false. A
        # rejection that ALSO emits a stray non-JSON line (a noisy quota
        # rejection) still needs to trigger the bounded-backoff path, so
        # detect rate limiting from the raw stdout/stderr text directly,
        # independently of whether the stream as a whole could be parsed.
        raw_bytes = stream_path.read_bytes() if stream_path.exists() else b""
        raw_text = raw_bytes.decode(errors="replace")
        haystack = f"{raw_text} {err_text}".lower()
        rate_limited = any(k in haystack for k in RATE_LIMIT_KEYWORDS)
        # D4: the stream file was still written and the attempt was charged
        # and retried even though it couldn't be parsed -- compute the
        # digest directly from those bytes (same hashlib.sha256(raw).hexdigest()
        # classify_stream.py itself would have produced) so these are exactly
        # the failures a human can still bind back to their captured JSONL.
        raw_sha256 = hashlib.sha256(raw_bytes).hexdigest() if raw_bytes else None
        return {
            "valid": False, "rate_limited": rate_limited, "dispatched": False,
            "subagent_type": None, "foreground": None, "collected": False,
            "cost_usd": None, "raw_stream_sha256": raw_sha256,
            "observed_main_model": None, "client_version": None,
            "terminal_subtype": None, "reason": "unparseable_stream",
        }
    terminal_subtype = None
    terminal_result_text = None
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
            terminal_result_text = event.get("result")

    valid = bool(verdict["model_costs_usd"]) and terminal_subtype == "success"
    rate_limited = False
    reason = None
    if not valid:
        # D5: a rejection can carry a generic terminal subtype while its own
        # `result` text is the actual quota/usage-limit message (empty
        # stderr) -- checking subtype+stderr alone missed exactly that case,
        # so the terminal event's own text is part of the haystack too.
        haystack = f"{terminal_subtype or ''} {terminal_result_text or ''} {err_text}".lower()
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
    # C8/D2: snapshot every live input exactly once, BEFORE anything is
    # derived from it -- prompt, fixture tree, AND (D2) the agents payload.
    # The header (FIX1: recomputed every run, never read back from state),
    # the drift check, and every spawn all read this one frozen snapshot --
    # never the source paths again -- so an edit landing in this startup
    # window, or later mid-run, can no longer make later cells run bytes the
    # header never recorded.
    policy_bytes = {arm: composed_policy_bytes(study, arm) for arm in study["arms"]}
    prompt_text, fixture_snapshot, agents_bytes = snapshot_run_inputs(study)
    # D6: everything from here on can raise (load_or_init_state refuses on
    # drift) -- the snapshot created just above must be cleaned up on EVERY
    # exit path, not only the one _run_cells reaches, or a refused resume
    # leaves a full fixture copy under the temp directory forever.
    try:
        fresh_header = build_header_from_snapshot(
            study, prompt_text, fixture_snapshot, policy_bytes, agents_bytes
        )
        state = load_or_init_state(study, evidence_dir, fresh_header)
        state["evidence_dir_git_ignore_check"] = git_ignore_status
        return _run_cells(study, evidence_dir, state, fresh_header, policy_bytes,
                           prompt_text, fixture_snapshot, agents_bytes, keep_run_roots)
    finally:
        cleanup_run_root(fixture_snapshot.parent)


def _run_cells(study: dict, evidence_dir: Path, state: dict, fresh_header: dict,
               policy_bytes: dict, prompt_text: str, fixture_snapshot: Path,
               agents_bytes: bytes, keep_run_roots: bool) -> int:
    streams_dir = evidence_dir / "streams"
    for cell in state["schedule"]:
        info = state["cells"].setdefault(cell, {"status": "pending", "attempts": []})
        if info["status"] in ("complete", "exhausted"):
            continue
        arm = cell.split("#", 1)[0]

        while True:
            # E5: the runner can be killed after `claude` finished writing a
            # COMPLETE stream but before this attempt's evidence was
            # persisted -- the pre-spawn placeholder is still "interrupted"
            # even though a valid (possibly paid) run actually happened. A
            # naive resume treats that as unevaluated, spawns attempt N+1,
            # and drops the completed run from the denominator while
            # spending again. Recover it in place instead of respawning
            # whenever the last recorded attempt is "interrupted" AND its
            # stream file actually reached a terminal event.
            last = info["attempts"][-1] if info["attempts"] else None
            recovered_stream_path = None
            if last is not None and last.get("status") == "interrupted":
                candidate_path = streams_dir / f"{cell.replace('#', '-')}-attempt{last['attempt']}.jsonl"
                if _stream_looks_complete(candidate_path):
                    recovered_stream_path = candidate_path

            if recovered_stream_path is not None:
                attempt_no = last["attempt"]
                stream_path = recovered_stream_path
                err_path = streams_dir / f"{cell.replace('#', '-')}-attempt{attempt_no}.err"
                reservation = next(
                    r for r in state["reservations"]
                    if r["cell"] == cell and r["attempt"] == attempt_no
                )
                scope = arm_scope(study, arm)
                setting_sources = "project,local" if scope == "project" else "user,project,local"
                run_root = None  # unknown: never persisted before the crash (see comment below)
                extra_fields = {
                    # The run root that produced this stream was created
                    # (and possibly already cleaned up) by a process that
                    # was killed before it ever saved that path to state --
                    # it cannot be recovered here. Not needed for validity
                    # or the tally, only for forensic inspection of an
                    # attempt that has already been fully evaluated.
                    "changed_files": None, "run_root": None, "config_dir": None,
                    "scope": scope, "setting_sources": setting_sources,
                    "recovered_from_interrupted": True,
                }
            else:
                # attempt_no (for numbering/filenames) counts every recorded
                # attempt including interrupted placeholders, so a resume
                # never reuses a filename (A3). The retry budget only counts
                # attempts that actually got evaluated -- an interrupted
                # (hard-killed, unrecoverable) attempt was never observed, so
                # it shouldn't burn retry budget.
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
                        study, arm, policy_bytes[arm], fixture_snapshot, agents_bytes
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

                extra_fields = {
                    "changed_files": git_changed_files(fixture_copy),
                    "run_root": str(run_root),
                    "scope": arm_scope(study, arm),
                    "setting_sources": setting_sources,
                    "config_dir": str(config_dir) if config_dir is not None else None,
                }

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
                **extra_fields,
            })

            if evidence["valid"]:
                reservation["charged_usd"] = (
                    evidence["cost_usd"] if evidence["cost_usd"] is not None
                    else study["per_run_cap_usd"]
                )
            reservation["status"] = "done"
            evidence["reservation_charged_usd"] = reservation["charged_usd"]
            info["attempts"][-1] = evidence  # replace the pre-spawn placeholder (A3)
            # C7: an interrupted (hard-killed) attempt was never observed and
            # must not consume retry budget -- the pre-spawn check above
            # already excludes it via evaluated_attempts. The cutoffs and
            # backoff index below must use the same count, recomputed now
            # that this attempt's placeholder has been replaced with real
            # evidence, or a prior interrupted placeholder still inflates
            # attempt_no and exhausts the budget early.
            evaluated_attempts = sum(
                1 for a in info["attempts"] if a.get("status") != "interrupted"
            )

            # FIX3: clean up the disposable run root once its evidence is
            # written out. Only for valid attempts -- an invalid one is
            # exactly what a human will want to inspect, so it's left in
            # place (as is anything killed mid-flight: that path never
            # reaches here at all). run_root is None for a recovered
            # attempt (E5) -- its path was never persisted, so there is
            # nothing this process can clean up.
            if evidence["valid"] and not keep_run_roots and run_root is not None:
                cleanup_run_root(run_root)

            if evidence["valid"]:
                info["status"] = "complete"
                save_state(state, evidence_dir)
                break

            save_state(state, evidence_dir)

            if evidence["rate_limited"]:
                if evaluated_attempts >= 1 + study["max_retries_per_cell"]:
                    info["status"] = "exhausted"
                    state["stopped_reason"] = (
                        f"{cell}: retries exhausted after rate-limit rejection "
                        f"({evaluated_attempts} evaluated attempts)"
                    )
                    save_state(state, evidence_dir)
                    print(state["stopped_reason"])
                    return 2
                remaining = study["max_backoff_seconds"] - state["backoff_seconds_used"]
                backoff = min(2 ** (evaluated_attempts - 1), remaining)
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
            if evaluated_attempts >= 1 + study["max_retries_per_cell"]:
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

# Structural issue 2: fields whose value is OBSERVED per attempt rather than
# declared up front -- they can't be frozen into the header like a policy
# digest, because they're outputs of running, not inputs to it (a Claude
# Code upgrade or a model alias resolving differently mid-study are both
# outside this tool's control). Pooling silently assumes every attempt saw
# the same one; declared once, generically, so a future observed field is
# covered by adding it here rather than writing a second special case.
OBSERVED_CONDITION_FIELDS = ("client_version", "observed_main_model")


def _observed_conditions(state: dict, arms) -> dict[str, list]:
    """Distinct non-null values seen for each OBSERVED_CONDITION_FIELDS entry
    across every valid attempt in the given arms. More than one distinct
    value for a field means attempts were pooled from heterogeneous
    conditions (E1 / E4) -- the caller must refuse pooled comparisons."""
    arms = set(arms)
    conditions: dict[str, list] = {}
    for field in OBSERVED_CONDITION_FIELDS:
        conditions[field] = sorted({
            a[field]
            for cell, info in state["cells"].items()
            if cell.split("#", 1)[0] in arms
            for a in info["attempts"]
            if a.get("valid") and a.get(field)
        })
    return conditions


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

    # FIX D: carry the header and a per-arm policy digest block, same shape
    # as the preserved source study, so this file can itself be fed through
    # `report --legacy` (R8 -- provenance must travel with the numbers).
    header = state.get("header", {})
    policies = header.get("policies", {})

    # C2: target_n is pre-registered (safety contract 7). Editing the study
    # file after the fact must not change what `report` refuses against --
    # use the value recorded in the header when the study began, and refuse
    # outright if the study file has since drifted from it (the same way a
    # policy digest drift is refused, just surfaced here instead of at
    # `run` since `report` never calls load_or_init_state). A state written
    # before target_n was recorded in the header has no recorded value; fall
    # back to the study file's value rather than refusing against nothing.
    recorded_target_n = header.get("target_n")
    if recorded_target_n is not None and recorded_target_n != study["target_n"]:
        raise SystemExit(
            f"refusing report: target_n drifted since this study began "
            f"(recorded {recorded_target_n}, study file now says "
            f"{study['target_n']}) -- no override"
        )
    target_n = recorded_target_n if recorded_target_n is not None else study["target_n"]

    # D3: model is a run-affecting input like any other -- a study that
    # finished remaining cells on a different model than it started must not
    # get pooled into one report as if nothing changed. Same shape as the
    # target_n check above.
    recorded_model = header.get("model")
    live_model = study.get("model")
    if recorded_model is not None and recorded_model != live_model:
        raise SystemExit(
            f"refusing report: model drifted since this study began "
            f"(recorded {recorded_model!r}, study file now says {live_model!r}) "
            f"-- no override"
        )
    model = recorded_model if recorded_model is not None else live_model

    # D1: the arm set to report over is the one actually run (recorded in
    # the header), never the live study file's `arms` dict -- editing
    # study.json after the run (removing an arm, adding one) must not drop
    # real evidence from results.json or invent a zero-attempt shortfall.
    recorded_arms = header.get("arms")
    arms = recorded_arms if recorded_arms is not None else sorted(study["arms"])

    tally: dict[str, tuple[int, int]] = {}
    for arm in arms:
        valid = [
            a for cell, info in state["cells"].items()
            if cell.split("#", 1)[0] == arm
            for a in info["attempts"] if a["valid"]
        ]
        dispatched = sum(1 for a in valid if a["dispatched"])
        tally[arm] = (dispatched, len(valid) - dispatched)

    # E1 / E4 (structural issue 2): aggregate the observed conditions across
    # every valid attempt in the reported arms, BEFORE deciding whether to
    # emit a pooled comparison -- see OBSERVED_CONDITION_FIELDS.
    observed = _observed_conditions(state, tally.keys())
    mixed_conditions = {field: values for field, values in observed.items() if len(values) > 1}
    client_versions = observed["client_version"]
    client_version = (
        client_versions[0] if len(client_versions) == 1
        else (client_versions if client_versions else None)
    )

    result = {
        "dispatch_predicate": DISPATCH_PREDICATE_TEXT,
        "seed": header.get("seed"),
        "target_n": target_n,
        "model": model,
        "prompt_sha256": header.get("prompt_sha256"),
        "fixture_tree_sha256": header.get("fixture_tree_sha256"),
        "agents_sha256": header.get("agents_sha256"),
        "client": client_version,
        "observed_conditions": observed,
        "arms": {
            # C5: scope is provenance too -- use the value recorded in the
            # header when the run happened, not the study file's current
            # value, or an edit to the study file after the fact could make
            # this report claim a scope that was never actually run.
            a: {
                "dispatched": d, "attempts": d + f,
                "scope": policies.get(a, {}).get("scope") or arm_scope(study, a),
                "policy": {
                    "bytes": policies.get(a, {}).get("bytes"),
                    "sha256": policies.get(a, {}).get("sha256"),
                },
            }
            for a, (d, f) in tally.items()
        },
    }

    shortfall = {
        a: target_n - (d + f) for a, (d, f) in tally.items()
        if (d + f) < target_n
    }
    if shortfall:
        result["comparisons"] = None
        result["refused"] = (
            f"pooled comparisons refused: target_n={target_n} not yet reached "
            f"for {shortfall}"
        )
    elif mixed_conditions:
        # E1 / E4: valid attempts disagree on an observed condition (e.g. a
        # Claude Code upgrade or a model alias resolving differently
        # mid-study) -- pooling them under one label would average over
        # different implementations. Refuse the pooled p-values; the
        # per-arm counts above (and observed_conditions) are still printed.
        result["comparisons"] = None
        result["refused"] = (
            "pooled comparisons refused: mixed observed conditions across "
            f"valid attempts (not run-affecting inputs, so not caught at "
            f"resume): {mixed_conditions}"
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
