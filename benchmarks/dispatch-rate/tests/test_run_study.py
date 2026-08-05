#!/usr/bin/env python3
"""Free acceptance checks for run_study.py, driven entirely by the shipped
`claude` stub in this directory. Spends nothing; never invokes a real model.

Run with: python3 benchmarks/dispatch-rate/tests/test_run_study.py
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
DISPATCH_RATE_DIR = HERE.parent
REPO_ROOT = DISPATCH_RATE_DIR.parent.parent
RUN_STUDY = DISPATCH_RATE_DIR / "run_study.py"

sys.path.insert(0, str(DISPATCH_RATE_DIR))
import run_study  # noqa: E402


def stub_env(**overrides) -> dict:
    env = dict(os.environ)
    env["PATH"] = f"{HERE}{os.pathsep}{env.get('PATH', '')}"
    for k, v in overrides.items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = str(v)
    return env


def make_study(tmp_evidence: Path, **overrides) -> Path:
    study = {
        "name": "test-study",
        "prompt": "benchmarks/spontaneous-dispatch/prompts/mechanical.txt",
        "fixture": "benchmarks/dispatch-brake/positive-controls/mechanical/fixture",
        "agents_from": "templates/agents",
        "model": "opus",
        "target_n": 1,
        "per_run_cap_usd": 1.0,
        "total_cap_usd": 100.0,
        "max_retries_per_cell": 0,
        "max_backoff_seconds": 10,
        "seed": 1,
        "evidence_dir": str(tmp_evidence),
        "arms": {
            "control": {"policy": "templates/claude-md.orchestration.md"},
            "candidate": {"policy": "benchmarks/dispatch-rate/policies/candidate.md"},
            "placebo": {"policy": "benchmarks/dispatch-rate/policies/placebo.md"},
        },
    }
    study.update(overrides)
    path = tmp_evidence.parent / f"{tmp_evidence.name}.study.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(study))
    return path


def new_evidence_dir(label: str) -> Path:
    # inside the repo, under the gitignored dispatch-rate evidence tree, so
    # test 7 (git-ignore + fixture-copy cleanliness) exercises the real rule.
    return REPO_ROOT / ".agent-local" / "dispatch-rate" / f"test-{label}-{uuid.uuid4().hex[:8]}"


def run_cli(args: list[str], env: dict, timeout: float = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUN_STUDY), *args],
        env=env, capture_output=True, text=True, timeout=timeout,
    )


def kill_after_reservation(cmd_args: list[str], env: dict, state_path: Path) -> None:
    proc = subprocess.Popen(
        [sys.executable, str(RUN_STUDY), *cmd_args],
        env=env, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text())
            except json.JSONDecodeError:
                state = {}
            if state.get("reservations"):
                break
        time.sleep(0.05)
    else:
        proc.kill()
        raise AssertionError("reservation never appeared before timeout")
    time.sleep(0.2)  # let the child stub actually start hanging
    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


# --------------------------------------------------------------------------

def test_1_plan_stable_and_resolves():
    out1 = subprocess.run(
        [sys.executable, str(RUN_STUDY), "plan", str(DISPATCH_RATE_DIR / "study.example.json")],
        capture_output=True, text=True, check=True,
    )
    out2 = subprocess.run(
        [sys.executable, str(RUN_STUDY), "plan", str(DISPATCH_RATE_DIR / "study.example.json")],
        capture_output=True, text=True, check=True,
    )
    assert out1.stdout == out2.stdout, "schedule not stable under fixed seed"
    schedule = json.loads(out1.stdout)["schedule"]
    assert len(schedule) == 30
    assert set(c.split("#")[0] for c in schedule) == {"control", "candidate", "placebo"}


def test_2_reservation_survives_kill_and_blocks():
    evidence = new_evidence_dir("kill")
    study_path = make_study(
        evidence, target_n=1, per_run_cap_usd=1.0, total_cap_usd=100.0,
        max_retries_per_cell=0, arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    env = stub_env(CLAUDE_STUB_MODE="hang")
    state_path = evidence / "state.json"
    kill_after_reservation(["run", str(study_path)], env, state_path)

    state = json.loads(state_path.read_text())
    assert len(state["reservations"]) == 1, state["reservations"]
    r = state["reservations"][0]
    assert r["charged_usd"] == 1.0, "reservation must stay charged after a hard kill"
    cell = r["cell"]
    assert state["cells"][cell]["status"] == "in_progress"

    # re-invoke with a cap that the already-charged reservation exhausts
    study2_path = make_study(
        evidence, target_n=1, per_run_cap_usd=1.0, total_cap_usd=1.0,
        max_retries_per_cell=0, arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    result = run_cli(["run", str(study2_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "refusing" in result.stdout and "blocking reservation" in result.stdout, result.stdout

    shutil.rmtree(evidence, ignore_errors=True)


def test_3_rate_limit_retries_then_stops_without_spinning():
    evidence = new_evidence_dir("ratelimit")
    study_path = make_study(
        evidence, target_n=1, per_run_cap_usd=0.5, total_cap_usd=100.0,
        max_retries_per_cell=2, max_backoff_seconds=10, seed=2,
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="rate_limit"))
    assert result.returncode == 2, result.stdout + result.stderr

    state = json.loads((evidence / "state.json").read_text())
    attempted_cells = [c for c, info in state["cells"].items() if info["attempts"]]
    assert len(attempted_cells) == 1, "must stop without spinning through further cells"
    cell = attempted_cells[0]
    info = state["cells"][cell]
    assert len(info["attempts"]) == 3, "1 initial + max_retries_per_cell(2) retries"
    assert all(a["rate_limited"] and not a["valid"] for a in info["attempts"])
    assert info["status"] == "exhausted"
    assert 0 < state["backoff_seconds_used"] <= 10

    report = run_cli(["report", str(study_path)], stub_env())
    parsed = json.loads(report.stdout)
    arm = cell.split("#")[0]
    assert parsed["arms"][arm]["attempts"] == 0, "invalid runs must never enter the tally (R4)"
    assert "refused" in parsed

    shutil.rmtree(evidence, ignore_errors=True)


def test_4_resume_completes_only_missing_cells():
    evidence = new_evidence_dir("resume")
    study_path = make_study(evidence, target_n=1, seed=3)
    study = run_study.load_study(str(study_path))
    schedule = run_study.build_schedule(study)
    cell1, cell2 = schedule[0], schedule[1]

    counter_file = evidence.parent / f"{evidence.name}.counter"
    counter_file.parent.mkdir(parents=True, exist_ok=True)
    state_path = evidence / "state.json"

    env = stub_env(
        CLAUDE_STUB_MODE="success",
        CLAUDE_STUB_COUNTER_FILE=str(counter_file),
        CLAUDE_STUB_HANG_ON_CALL=2,
    )
    proc = subprocess.Popen(
        [sys.executable, str(RUN_STUDY), "run", str(study_path)],
        env=env, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        if state_path.exists():
            state = json.loads(state_path.read_text())
            if state.get("cells", {}).get(cell1, {}).get("status") == "complete" and \
               state.get("cells", {}).get(cell2, {}).get("status") == "in_progress":
                break
        time.sleep(0.05)
    else:
        proc.kill()
        raise AssertionError("cell1 never completed / cell2 never started before timeout")
    time.sleep(0.2)
    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass

    stream_dir = evidence / "streams"
    cell1_stream = stream_dir / f"{cell1.replace('#', '-')}-attempt1.jsonl"
    before = cell1_stream.read_bytes()
    before_sha = json.loads(state_path.read_text())["cells"][cell1]["attempts"][0]["raw_stream_sha256"]

    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr

    after = cell1_stream.read_bytes()
    assert before == after, "an already-complete cell's stream must never be rewritten"
    state = json.loads(state_path.read_text())
    assert state["cells"][cell1]["attempts"][0]["raw_stream_sha256"] == before_sha
    assert all(info["status"] == "complete" for info in state["cells"].values())

    shutil.rmtree(evidence, ignore_errors=True)


def test_5_report_refuses_before_target_n():
    evidence = new_evidence_dir("shortfall")
    study_path = make_study(evidence, target_n=5, seed=4)
    evidence.mkdir(parents=True, exist_ok=True)
    fake_state = {
        "study_name": "test", "seed": 4, "schedule": ["control#1"],
        "header": {}, "reservations": [], "backoff_seconds_used": 0.0, "stopped_reason": None,
        "cells": {
            "control#1": {"status": "complete", "attempts": [{"valid": True, "dispatched": True}]},
        },
    }
    (evidence / "state.json").write_text(json.dumps(fake_state))

    result = run_cli(["report", str(study_path)], stub_env())
    parsed = json.loads(result.stdout)
    assert parsed.get("comparisons") is None
    assert "refused" in parsed and "target_n=5" in parsed["refused"]
    assert parsed["arms"]["control"]["attempts"] == 1

    shutil.rmtree(evidence, ignore_errors=True)


def test_6_legacy_report_reproduces_tracked_synthetic_fixture():
    # C3: this must pass on a clean clone with zero local state. The real
    # study's results.json lives under the Git-ignored
    # .agent-local/dispatch-rate-study/ and is exercised separately, only
    # when present, by test_6b below -- this test instead round-trips a
    # small tracked fixture shipped alongside the suite so the free
    # acceptance suite the README advertises actually is runnable by anyone.
    legacy = DISPATCH_RATE_DIR / "tests" / "fixtures" / "legacy-results.sample.json"
    assert legacy.exists(), "tracked legacy fixture is missing"
    result = subprocess.run(
        [sys.executable, str(RUN_STUDY), "report", "--legacy", str(legacy)],
        capture_output=True, text=True, check=True,
    )
    parsed = json.loads(result.stdout)
    assert parsed["arms"]["control"] == {"dispatched": 2, "attempts": 5}
    assert parsed["arms"]["placebo"] == {"dispatched": 1, "attempts": 5}
    assert parsed["arms"]["candidate"]["dispatched"] == 4
    assert parsed["arms"]["candidate"]["attempts"] == 5
    c = parsed["comparisons"]
    assert c["candidate_vs_control"]["fisher_two_sided_p"] == 0.52381
    assert c["candidate_vs_placebo"]["fisher_two_sided_p"] == 0.20635
    assert c["placebo_vs_control"]["fisher_two_sided_p"] == 1.0
    assert "dispatch_predicate" in parsed


def test_6b_legacy_report_reproduces_source_study():
    # Real-study reproduction. Skipped (not failed) when the Git-ignored
    # local evidence file isn't present -- e.g. any clone other than the one
    # that ran the original 2026-08-06 study.
    legacy = REPO_ROOT / ".agent-local" / "dispatch-rate-study" / "results.json"
    if not legacy.exists():
        print(f"SKIP test_6b_legacy_report_reproduces_source_study: {legacy} not present locally")
        return
    result = subprocess.run(
        [sys.executable, str(RUN_STUDY), "report", "--legacy", str(legacy)],
        capture_output=True, text=True, check=True,
    )
    parsed = json.loads(result.stdout)
    assert parsed["arms"]["control"] == {"dispatched": 3, "attempts": 10}
    assert parsed["arms"]["placebo"] == {"dispatched": 1, "attempts": 10}
    assert parsed["arms"]["candidate"]["dispatched"] == 8
    assert parsed["arms"]["candidate"]["attempts"] == 8
    c = parsed["comparisons"]
    assert c["candidate_vs_control"]["fisher_two_sided_p"] == 0.00402
    assert c["candidate_vs_placebo"]["fisher_two_sided_p"] == 0.00041
    assert c["placebo_vs_control"]["fisher_two_sided_p"] == 0.58204
    assert "dispatch_predicate" in parsed


def test_7_no_committed_jsonl_no_agents_json_in_fixture():
    evidence = new_evidence_dir("clean")
    study_path = make_study(
        evidence, target_n=1, seed=5,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    result = run_cli(["run", "--keep-run-roots", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr

    status = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    rel_evidence = evidence.relative_to(REPO_ROOT).as_posix()
    assert not any(
        line for line in status.splitlines() if rel_evidence in line and line.strip().endswith(".jsonl")
    ), "raw streams must never be visible to git status (gitignore must cover them)"

    state = json.loads((evidence / "state.json").read_text())
    cell = next(iter(state["cells"]))
    run_root = Path(state["cells"][cell]["attempts"][0]["run_root"])
    fixture_copy = run_root / "fixture"

    others = subprocess.run(
        ["git", "-C", str(fixture_copy), "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert others == "", f"fixture copy has untracked files: {others!r}"
    assert not (fixture_copy / "agents.json").exists(), "agents payload must never be copied into the fixture"

    shutil.rmtree(evidence, ignore_errors=True)
    shutil.rmtree(run_root, ignore_errors=True)


def test_9_scope_handling():
    # project scope: policy in the fixture copy, --setting-sources project,local
    evidence_p = new_evidence_dir("scope-project")
    argv_p = evidence_p.parent / f"{evidence_p.name}.argv.json"
    study_p = make_study(
        evidence_p, target_n=1, seed=6,
        arms={"control": {"policy": "templates/claude-md.orchestration.md", "scope": "project"}},
    )
    result = run_cli(
        ["run", "--keep-run-roots", str(study_p)],
        stub_env(CLAUDE_STUB_MODE="success", CLAUDE_STUB_ARGV_FILE=str(argv_p)),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    state_p = json.loads((evidence_p / "state.json").read_text())
    cell_p = next(iter(state_p["cells"]))
    attempt_p = state_p["cells"][cell_p]["attempts"][0]
    assert attempt_p["scope"] == "project"
    assert attempt_p["setting_sources"] == "project,local"
    assert attempt_p["config_dir"] is None
    run_root_p = Path(attempt_p["run_root"])
    assert (run_root_p / "fixture" / "CLAUDE.md").exists()
    argv_data = json.loads(argv_p.read_text())
    assert "--setting-sources" in argv_data["argv"]
    assert argv_data["argv"][argv_data["argv"].index("--setting-sources") + 1] == "project,local"
    assert "--agents" in argv_data["argv"]
    assert argv_data["CLAUDE_CONFIG_DIR"] is None
    shutil.rmtree(evidence_p, ignore_errors=True)
    shutil.rmtree(run_root_p, ignore_errors=True)

    # user scope: policy in a per-cell CLAUDE_CONFIG_DIR, fixture copy untouched
    evidence_u = new_evidence_dir("scope-user")
    argv_u = evidence_u.parent / f"{evidence_u.name}.argv.json"
    study_u = make_study(
        evidence_u, target_n=1, seed=7,
        arms={"control": {"policy": "templates/claude-md.orchestration.md", "scope": "user"}},
    )
    # isolate real_config_root() from this machine's actual ~/.claude for the test
    fake_home = evidence_u.parent / f"{evidence_u.name}.fakehome"
    fake_home.mkdir(parents=True, exist_ok=True)
    env_u = stub_env(CLAUDE_STUB_MODE="success", CLAUDE_STUB_ARGV_FILE=str(argv_u))
    env_u["HOME"] = str(fake_home)
    env_u.pop("CLAUDE_CONFIG_DIR", None)
    result = run_cli(["run", "--keep-run-roots", str(study_u)], env_u)
    assert result.returncode == 0, result.stdout + result.stderr
    state_u = json.loads((evidence_u / "state.json").read_text())
    user_cell = next(iter(state_u["cells"]))
    attempt_u = state_u["cells"][user_cell]["attempts"][0]
    assert attempt_u["scope"] == "user"
    assert attempt_u["setting_sources"] == "user,project,local"
    config_dir = Path(attempt_u["config_dir"])
    assert (config_dir / "CLAUDE.md").exists()
    run_root_u = Path(attempt_u["run_root"])
    assert not (run_root_u / "fixture" / "CLAUDE.md").exists()
    argv_data_u = json.loads(argv_u.read_text())
    assert argv_data_u["argv"][argv_data_u["argv"].index("--setting-sources") + 1] == "user,project,local"
    assert "--agents" in argv_data_u["argv"]
    assert argv_data_u["CLAUDE_CONFIG_DIR"] == str(config_dir)
    shutil.rmtree(evidence_u, ignore_errors=True)
    shutil.rmtree(fake_home, ignore_errors=True)
    for cell, info in state_u["cells"].items():
        for a in info["attempts"]:
            shutil.rmtree(a["run_root"], ignore_errors=True)

    # refusal: a CLAUDE_CONFIG_DIR that is (or is inside) the real config root must be rejected
    real_root = run_study.real_config_root()
    try:
        run_study.guard_config_dir(real_root)
        raise AssertionError("guard_config_dir must refuse the real config root itself")
    except SystemExit:
        pass
    try:
        run_study.guard_config_dir(real_root / "nested")
        raise AssertionError("guard_config_dir must refuse a path inside the real config root")
    except SystemExit:
        pass
    run_study.guard_config_dir(evidence_p.parent / "unrelated-safe-dir")  # must not raise


def test_10_concurrent_run_refuses():
    # F1: a second `run` against the same evidence_dir while a first `run`
    # holds it must refuse immediately instead of racing state.json writes.
    evidence = new_evidence_dir("lock")
    study_path = make_study(
        evidence, target_n=1, per_run_cap_usd=1.0, total_cap_usd=100.0,
        max_retries_per_cell=0, arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    env = stub_env(CLAUDE_STUB_MODE="hang")
    procA = subprocess.Popen(
        [sys.executable, str(RUN_STUDY), "run", str(study_path)],
        env=env, start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    lock_path = evidence / ".lock"
    deadline = time.time() + 20
    while time.time() < deadline and not lock_path.exists():
        time.sleep(0.05)
    else:
        if not lock_path.exists():
            procA.kill()
            raise AssertionError("lock file never appeared before timeout")
    time.sleep(0.2)

    resultB = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert resultB.returncode != 0, resultB.stdout + resultB.stderr
    assert "holds the lock" in (resultB.stdout + resultB.stderr), resultB.stdout + resultB.stderr

    os.killpg(os.getpgid(procA.pid), signal.SIGKILL)
    try:
        procA.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    shutil.rmtree(evidence, ignore_errors=True)


def test_11_evidence_dir_must_be_git_ignored():
    # F2: refuse before any spawn unless the resolved evidence_dir is
    # Git-ignored, even though the dispatch-rate directory itself is
    # currently untracked (that's not the same thing as ignored).
    evidence = DISPATCH_RATE_DIR / "tests" / f"not-ignored-{uuid.uuid4().hex[:8]}"
    check = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", "--", str(evidence)]
    )
    assert check.returncode != 0, "test setup bug: path is unexpectedly git-ignored"

    study_path = make_study(
        evidence, target_n=1, arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode != 0, result.stdout + result.stderr
    assert "not Git-ignored" in result.stdout + result.stderr, result.stdout + result.stderr
    assert not evidence.exists(), "refused evidence_dir must not be created"
    study_path.unlink(missing_ok=True)


def test_12_unparseable_stream_does_not_abort_study():
    # F3: a stray non-JSON stdout line must be a bounded, retried invalid
    # observation, not a crash that leaves the cell stuck in_progress.
    evidence = new_evidence_dir("noise")
    study_path = make_study(
        evidence, target_n=1, max_retries_per_cell=1, seed=8,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="noise"))
    assert result.returncode == 0, result.stdout + result.stderr

    state = json.loads((evidence / "state.json").read_text())
    cell = next(iter(state["cells"]))
    info = state["cells"][cell]
    assert info["status"] == "exhausted"
    assert len(info["attempts"]) == 2, "1 initial + max_retries_per_cell(1) retries"
    assert all(a["reason"] == "unparseable_stream" and not a["valid"] for a in info["attempts"])

    shutil.rmtree(evidence, ignore_errors=True)


def _config_root_env(evidence: Path, label: str) -> tuple[dict, Path]:
    fake_home = evidence.parent / f"{evidence.name}.{label}.fakehome"
    fake_home.mkdir(parents=True, exist_ok=True)
    fake_config_root = fake_home / ".claude"
    fake_config_root.mkdir()
    env = stub_env(CLAUDE_STUB_MODE="success")
    env["HOME"] = str(fake_home)
    env["TMPDIR"] = str(fake_config_root)
    env.pop("CLAUDE_CONFIG_DIR", None)
    return env, fake_config_root


def test_13_run_root_guarded_against_real_config_root_project_scope():
    # F4 / A1: a project-scope arm still must not let run_root (fixture copy,
    # git repo, agents.json) land inside the real config root just because
    # TMPDIR points there -- and the guard must fire before any of that is
    # created.
    evidence = new_evidence_dir("cfgroot")
    study_path = make_study(
        evidence, target_n=1, seed=9,
        arms={"control": {"policy": "templates/claude-md.orchestration.md", "scope": "project"}},
    )
    env, fake_config_root = _config_root_env(evidence, "t13")
    result = run_cli(["run", str(study_path)], env)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "real configuration root" in result.stdout + result.stderr, result.stdout + result.stderr
    assert list(fake_config_root.rglob("*")) == [], "guard must fire before any filesystem creation"

    shutil.rmtree(evidence, ignore_errors=True)
    shutil.rmtree(fake_config_root.parent, ignore_errors=True)


def test_14_reservation_released_on_guard_refusal():
    # A2: a cell refused by the config-root guard before spawn must not keep
    # a charged reservation -- otherwise repeated retries could exhaust
    # total_cap_usd having spent nothing.
    evidence = new_evidence_dir("guardrefund")
    study_path = make_study(
        evidence, target_n=1, seed=10, max_retries_per_cell=0,
        arms={"control": {"policy": "templates/claude-md.orchestration.md", "scope": "project"}},
    )
    env, fake_config_root = _config_root_env(evidence, "t14")
    result = run_cli(["run", str(study_path)], env)
    assert result.returncode != 0, result.stdout + result.stderr

    # FIX A / C8: snapshot_run_inputs applies the same TMPDIR-inside-real-
    # config-root guard, and (as of C8) runs before state.json is ever
    # written at all -- the frozen snapshot the header is derived from must
    # be taken before anything else happens, including state creation. So a
    # refusal this early may legitimately leave no state.json on disk;
    # if one exists regardless (e.g. a resumed evidence_dir), it must show
    # no charged reservation and no phantom attempt on any cell.
    state_path = evidence / "state.json"
    if state_path.exists():
        state = json.loads(state_path.read_text())
        assert state["reservations"] == [], "guard-refused cell must not leave a charged reservation"
        assert all(
            not info["attempts"] for info in state["cells"].values()
        ), "guard-refused run must not leave a phantom attempt on any cell"

    shutil.rmtree(evidence, ignore_errors=True)
    shutil.rmtree(fake_config_root.parent, ignore_errors=True)


def test_15_interrupted_attempt_never_overwritten_on_resume():
    # A3: a hard-killed attempt's raw stream must survive resume, and the
    # retry must use a new attempt number rather than reusing (and
    # overwriting) the interrupted attempt's filename.
    evidence = new_evidence_dir("noverwrite")
    study_path = make_study(
        evidence, target_n=1, per_run_cap_usd=1.0, total_cap_usd=100.0,
        max_retries_per_cell=1, seed=11,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    env = stub_env(CLAUDE_STUB_MODE="hang")
    state_path = evidence / "state.json"
    kill_after_reservation(["run", str(study_path)], env, state_path)

    stream1 = evidence / "streams" / "control-1-attempt1.jsonl"
    before = stream1.read_bytes()

    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr

    after = stream1.read_bytes()
    assert before == after, "interrupted attempt's raw stream must never be overwritten"
    stream2 = evidence / "streams" / "control-1-attempt2.jsonl"
    assert stream2.exists(), "resume must advance to a new attempt number, not reuse attempt 1"

    state = json.loads(state_path.read_text())
    attempts = state["cells"]["control#1"]["attempts"]
    assert attempts[0]["status"] == "interrupted" and attempts[0]["valid"] is False
    assert attempts[1]["valid"] is True

    shutil.rmtree(evidence, ignore_errors=True)


def test_16_reason_names_actual_defect_not_success():
    # A4: subtype "success" with empty modelUsage (the source study's
    # contamination shape) must not be recorded with the misleading reason
    # "success".
    evidence = new_evidence_dir("reason")
    study_path = make_study(
        evidence, target_n=1, max_retries_per_cell=0, seed=12,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    result = run_cli(
        ["run", str(study_path)],
        stub_env(CLAUDE_STUB_MODE="empty_costs", CLAUDE_STUB_DISPATCH="1"),
    )
    assert result.returncode == 0, result.stdout + result.stderr

    state = json.loads((evidence / "state.json").read_text())
    cell = next(iter(state["cells"]))
    attempt = state["cells"][cell]["attempts"][0]
    assert attempt["valid"] is False
    assert attempt["terminal_subtype"] == "success"
    assert attempt["reason"] == "empty_model_costs_usd", attempt["reason"]

    shutil.rmtree(evidence, ignore_errors=True)


def test_17_digest_drift_refuses_resume():
    # FIX1: a resumed `run` must recompute policy/prompt/fixture digests from
    # disk and refuse to start if any changed since the header was written --
    # never silently keep going while recording the stale digest.
    evidence = new_evidence_dir("drift")
    policy_path = evidence.parent / f"{evidence.name}.policy.md"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text("control policy, original bytes.\n")
    orig_bytes = len(policy_path.read_bytes())
    study_path = make_study(
        evidence, target_n=1, seed=13,
        arms={"control": {"policy": str(policy_path)}},
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr

    state_before = json.loads((evidence / "state.json").read_text())
    stored_sha = state_before["header"]["policies"]["control"]["sha256"]

    # drift the policy file on disk -- same path, different bytes
    policy_path.write_text("control policy, COMPLETELY DIFFERENT drifted bytes now.\n")
    new_bytes = len(policy_path.read_bytes())
    assert new_bytes != orig_bytes

    result2 = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result2.returncode != 0, "resume must refuse once inputs have drifted"
    out = result2.stdout + result2.stderr
    assert "no longer a single study" in out, out
    assert "policies.control" in out and "control" in out, out
    assert stored_sha in out, "must name the stored digest"
    assert str(orig_bytes) in out and str(new_bytes) in out, "must name both byte counts"
    assert "no override" in out, "must state that no override flag is offered"

    # state must be untouched by the refused resume
    state_after = json.loads((evidence / "state.json").read_text())
    assert state_after == state_before, "a refused resume must not mutate state"

    shutil.rmtree(evidence, ignore_errors=True)
    policy_path.unlink(missing_ok=True)


def test_18_git_ignore_check_probes_evidence_dir_not_repo_root():
    # FIX2: the probe must target evidence_dir (its nearest existing
    # ancestor), not REPO_ROOT -- otherwise the documented "skipped: not a
    # Git work tree" branch is unreachable and an out-of-work-tree
    # evidence_dir is hard-refused with leaked git stderr and a nonsensical
    # in-repo .gitignore suggestion.
    import tempfile
    outside = Path(tempfile.mkdtemp()) / "pilotfish-outside-worktree-evidence"
    assert run_study._nearest_existing_ancestor(outside).exists()
    check = subprocess.run(
        ["git", "-C", str(outside.parent), "rev-parse", "--is-inside-work-tree"],
        capture_output=True, text=True,
    )
    assert check.returncode != 0 or check.stdout.strip() != "true", (
        "test setup bug: chosen path is unexpectedly inside a Git work tree"
    )

    status = run_study.check_evidence_dir_git_ignored(outside)
    assert status == "skipped: not a Git work tree", status
    assert not outside.exists(), "the probe itself must not create the evidence_dir"

    # the in-repo, not-ignored refusal path must still work (unchanged behaviour)
    in_repo_unignored = DISPATCH_RATE_DIR / "tests" / f"not-ignored-{uuid.uuid4().hex[:8]}"
    try:
        run_study.check_evidence_dir_git_ignored(in_repo_unignored)
        raise AssertionError("must still refuse an in-repo, non-ignored evidence_dir")
    except SystemExit as exc:
        msg = str(exc)
        assert "not Git-ignored" in msg
        assert "fatal" not in msg.lower(), "must never leak raw git stderr"

    shutil.rmtree(outside.parent, ignore_errors=True)


def test_19_run_root_cleaned_up_after_valid_attempt_kept_for_invalid():
    # FIX3: a cell's disposable run root is removed once its evidence is
    # written out for a valid attempt, left in place for an invalid one (a
    # human will want to inspect it), and --keep-run-roots suppresses
    # cleanup entirely. cleanup_run_root() itself must refuse to touch a
    # directory lacking the .pilotfish-created sentinel.
    evidence = new_evidence_dir("cleanup-valid")
    study_path = make_study(
        evidence, target_n=1, seed=14,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr
    state = json.loads((evidence / "state.json").read_text())
    run_root = Path(state["cells"]["control#1"]["attempts"][0]["run_root"])
    assert not run_root.exists(), "a valid attempt's run root must be cleaned up by default"
    shutil.rmtree(evidence, ignore_errors=True)

    evidence2 = new_evidence_dir("cleanup-invalid")
    study_path2 = make_study(
        evidence2, target_n=1, max_retries_per_cell=0, seed=15,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    result2 = run_cli(["run", str(study_path2)], stub_env(CLAUDE_STUB_MODE="empty_costs"))
    assert result2.returncode == 0, result2.stdout + result2.stderr
    state2 = json.loads((evidence2 / "state.json").read_text())
    run_root2 = Path(state2["cells"]["control#1"]["attempts"][0]["run_root"])
    assert run_root2.exists(), "an invalid attempt's run root must be left for inspection"
    shutil.rmtree(evidence2, ignore_errors=True)
    shutil.rmtree(run_root2, ignore_errors=True)

    evidence3 = new_evidence_dir("cleanup-kept")
    study_path3 = make_study(
        evidence3, target_n=1, seed=16,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    result3 = run_cli(["run", "--keep-run-roots", str(study_path3)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result3.returncode == 0, result3.stdout + result3.stderr
    state3 = json.loads((evidence3 / "state.json").read_text())
    run_root3 = Path(state3["cells"]["control#1"]["attempts"][0]["run_root"])
    assert run_root3.exists(), "--keep-run-roots must suppress cleanup"
    shutil.rmtree(evidence3, ignore_errors=True)
    shutil.rmtree(run_root3, ignore_errors=True)

    # never delete anything the tool didn't create
    foreign = evidence.parent / f"{evidence.name}.foreign-dir"
    foreign.mkdir(parents=True, exist_ok=True)
    (foreign / "not-mine.txt").write_text("do not delete me")
    run_study.cleanup_run_root(foreign)
    assert foreign.exists(), "cleanup_run_root must refuse a directory without the sentinel"
    shutil.rmtree(foreign, ignore_errors=True)


def test_20_fix_a_snapshot_immune_to_mid_run_edit():
    # FIX A: the prompt and fixture tree must be frozen once per `run`
    # invocation (snapshot_run_inputs); a later cell's make_run_root and
    # spawn_cell must read from that frozen snapshot, never re-touch the
    # source paths again -- otherwise an edit to either mid-run reaches a
    # later spawn while the header (computed once, at the top of the run)
    # still names the original bytes, corrupting provenance undetectably.
    tmp = REPO_ROOT / ".agent-local" / "dispatch-rate" / f"test-fixa-{uuid.uuid4().hex[:8]}"
    tmp.mkdir(parents=True)
    prompt_path = tmp / "prompt.txt"
    prompt_path.write_text("original prompt text\n")
    fixture_dir = tmp / "fixture"
    fixture_dir.mkdir()
    (fixture_dir / "marker.txt").write_text("original fixture content\n")

    study = {
        "prompt": str(prompt_path),
        "fixture": str(fixture_dir),
        "agents_from": "templates/agents",
        "model": "opus",
        "per_run_cap_usd": 1.0,
        "arms": {"control": {"policy": "templates/claude-md.orchestration.md", "scope": "project"}},
    }

    prompt_text, fixture_snapshot, agents_bytes = run_study.snapshot_run_inputs(study)
    assert prompt_text == "original prompt text\n"
    assert (fixture_snapshot / "marker.txt").read_text() == "original fixture content\n"

    # simulate a mid-run edit of both inputs, on the same source paths the
    # study references, after the snapshot above was taken
    prompt_path.write_text("EDITED prompt text -- must not reach a later spawn\n")
    (fixture_dir / "marker.txt").write_text("EDITED fixture content -- must not reach a later spawn\n")

    run_root, fixture_copy, config_dir, setting_sources = run_study.make_run_root(
        study, "control", b"policy bytes", fixture_snapshot, agents_bytes
    )
    old_environ = dict(os.environ)
    try:
        assert (fixture_copy / "marker.txt").read_text() == "original fixture content\n", (
            "make_run_root must copy from the frozen snapshot, not re-read "
            "the (now-edited) source fixture"
        )

        argv_path = tmp / "argv.json"
        os.environ["PATH"] = f"{HERE}{os.pathsep}{os.environ.get('PATH', '')}"
        os.environ["CLAUDE_STUB_MODE"] = "success"
        os.environ["CLAUDE_STUB_ARGV_FILE"] = str(argv_path)
        run_study.spawn_cell(
            study, fixture_copy, run_root, config_dir, setting_sources,
            tmp / "stream.jsonl", tmp / "stream.err", prompt_text,
        )
        argv_data = json.loads(argv_path.read_text())
        prompt_arg = argv_data["argv"][argv_data["argv"].index("-p") + 1]
        assert prompt_arg == "original prompt text\n", (
            "spawn_cell must use the frozen prompt snapshot, not re-read "
            "the (now-edited) source prompt file"
        )
    finally:
        os.environ.clear()
        os.environ.update(old_environ)
        run_study.cleanup_run_root(run_root)
        run_study.cleanup_run_root(fixture_snapshot.parent)
    shutil.rmtree(tmp, ignore_errors=True)


def test_21_digest_drift_refuses_on_scope_change():
    # FIX B: `scope` is "the single variable across arms" -- changing an
    # arm's scope between runs must be refused by the resume drift gate just
    # like a changed digest, even though the policy bytes are unchanged.
    evidence = new_evidence_dir("scopedrift")
    study_path = make_study(
        evidence, target_n=1, seed=17,
        arms={"control": {"policy": "templates/claude-md.orchestration.md", "scope": "project"}},
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr

    study = json.loads(study_path.read_text())
    study["arms"]["control"]["scope"] = "user"
    study_path.write_text(json.dumps(study))

    result2 = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result2.returncode != 0, "resume must refuse once an arm's scope has changed"
    out = result2.stdout + result2.stderr
    assert "scope" in out and "control" in out, out
    assert "project" in out and "user" in out, out

    shutil.rmtree(evidence, ignore_errors=True)


def test_22_gitignore_suggestion_matches_nonexistent_dir():
    # FIX C: the suggested pattern must match `git check-ignore` for a path
    # that does not exist on disk yet -- a trailing-slash directory pattern
    # (the old suggestion) does not, so an operator who copied it verbatim
    # was refused again on the very next invocation.
    import tempfile
    # .resolve() matters on macOS: /var/folders/... is a symlink into
    # /private/var/folders/..., and `git rev-parse --show-toplevel` reports
    # the resolved form -- an unresolved evidence_dir would fail
    # relative_to(root) here for a reason unrelated to the fix under test.
    outside = Path(tempfile.mkdtemp(prefix="pilotfish-fixc-")).resolve()
    subprocess.run(["git", "init", "-q"], cwd=outside, check=True)
    evidence = outside / "ev"
    assert not evidence.exists()
    try:
        run_study.check_evidence_dir_git_ignored(evidence)
        raise AssertionError("must refuse a non-ignored evidence_dir")
    except SystemExit as exc:
        msg = str(exc)
    marker = "add this line to .gitignore: "
    assert marker in msg, msg
    suggested = msg.split(marker, 1)[1].strip()
    (outside / ".gitignore").write_text(suggested + "\n")
    check = subprocess.run(
        ["git", "-C", str(outside), "check-ignore", "-q", "--", str(evidence)]
    )
    assert check.returncode == 0, (
        f"suggested gitignore pattern {suggested!r} does not match a "
        f"not-yet-existing path (rc={check.returncode})"
    )
    shutil.rmtree(outside, ignore_errors=True)


def test_23_report_round_trips_through_legacy():
    # FIX D: report's own results.json must carry the header (seed, prompt
    # and fixture digests, client, per-arm scope) and a per-arm policy block
    # -- R8 requires provenance to travel with the numbers -- and feeding
    # that file back through `report --legacy` must reproduce identical
    # dispatched/attempts numbers.
    evidence = new_evidence_dir("roundtrip")
    study_path = make_study(
        evidence, target_n=1, seed=18,
        arms={
            "control": {"policy": "templates/claude-md.orchestration.md"},
            "candidate": {"policy": "benchmarks/dispatch-rate/policies/candidate.md"},
            "placebo": {"policy": "benchmarks/dispatch-rate/policies/placebo.md"},
        },
    )
    result = run_cli(
        ["run", str(study_path)],
        stub_env(CLAUDE_STUB_MODE="success", CLAUDE_STUB_DISPATCH="1"),
    )
    assert result.returncode == 0, result.stdout + result.stderr

    report1 = run_cli(["report", str(study_path)], stub_env())
    parsed1 = json.loads(report1.stdout)
    assert parsed1.get("seed") == 18
    assert parsed1.get("prompt_sha256")
    assert parsed1.get("fixture_tree_sha256")
    for arm in ("control", "candidate", "placebo"):
        assert parsed1["arms"][arm]["scope"] == "project"
        assert parsed1["arms"][arm]["policy"]["sha256"]

    results_path = evidence / "results.json"
    legacy = run_cli(["report", "--legacy", str(results_path)], stub_env())
    parsed2 = json.loads(legacy.stdout)
    for arm in ("control", "candidate", "placebo"):
        assert parsed2["arms"][arm]["dispatched"] == parsed1["arms"][arm]["dispatched"]
        assert parsed2["arms"][arm]["attempts"] == parsed1["arms"][arm]["attempts"]

    shutil.rmtree(evidence, ignore_errors=True)



def test_24_prompt_digest_matches_delivered_bytes_for_crlf():
    """snapshot_run_inputs must deliver the bytes build_header digested.

    Load-bearing: this drives run_study.snapshot_run_inputs and run_study.build_header
    directly. Reimplementing the decode inside the test would make the assertion
    tautological and let a revert to read_text() -- which applies universal newlines
    and so delivers a CRLF prompt LF-normalized under a digest describing the raw
    file -- ship green.
    """
    import hashlib
    import tempfile

    d = Path(tempfile.mkdtemp(prefix="pilotfish-test24-"))
    try:
        prompt = d / "prompt.txt"
        prompt.write_bytes(b"Line one.\r\nLine two.\r\n")
        fixture = d / "fixture"
        fixture.mkdir()
        (fixture / "a.txt").write_text("x")

        study = {
            "prompt": str(prompt),
            "fixture": str(fixture),
            "agents_from": "templates/agents",
            "model": "opus",
            "arms": {"control": {"policy": str(prompt), "scope": "project"}},
            "seed": 1,
        }
        header = run_study.build_header(study)
        prompt_text, fixture_snapshot, _agents_bytes = run_study.snapshot_run_inputs(study)
        try:
            delivered = hashlib.sha256(prompt_text.encode()).hexdigest()
            assert delivered == header["prompt_sha256"], (
                "snapshot_run_inputs delivered bytes whose digest "
                f"({delivered[:16]}) differs from the recorded prompt_sha256 "
                f"({header['prompt_sha256'][:16]})"
            )
        finally:
            run_study.cleanup_run_root(fixture_snapshot)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_25_fixture_digest_covers_symlinked_directories():
    """The digest must describe exactly what copytree(symlinks=False) delivers.

    Path.rglob does not descend into symlinked directories but copytree
    materializes them, so content under such a link sat outside both the
    digest and the drift gate and could be swapped between runs unnoticed.
    """
    import os, tempfile
    base = Path(tempfile.mkdtemp())
    fx = base / "fixture"; fx.mkdir()
    (fx / "real.txt").write_text("hello")
    outside = base / "outside"; outside.mkdir()
    (outside / "deep.txt").write_text("original")
    os.symlink(outside, fx / "link-dir")
    os.symlink(fx / "real.txt", fx / "link-file.txt")

    src_digest = run_study.fixture_tree_sha256(fx)
    copy = base / "copy"
    shutil.copytree(fx, copy, symlinks=False)
    assert run_study.fixture_tree_sha256(copy) == src_digest, (
        "digest of the delivered fixture copy must equal the digest of its source"
    )

    (outside / "deep.txt").write_text("SECRETLY CHANGED")
    assert run_study.fixture_tree_sha256(fx) != src_digest, (
        "a change under a symlinked directory must move the digest"
    )
    shutil.rmtree(base, ignore_errors=True)


def test_26_fixture_digest_matches_delivered_copy_with_empty_dir_and_git():
    # C1: reproduces the drift the review flagged -- a rglob/file-only digest
    # stays unchanged when an empty directory is added/removed even though
    # copytree delivers it, and previously didn't ignore .git even though the
    # digest did. The copy and the digest must now agree exactly.
    import tempfile
    base = Path(tempfile.mkdtemp(prefix="pilotfish-test26-"))
    try:
        fx = base / "fixture"
        fx.mkdir()
        (fx / "a.txt").write_text("hello")
        (fx / "empty-dir").mkdir()
        git_dir = fx / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

        src_digest = run_study.fixture_tree_sha256(fx)

        copy = base / "copy"
        shutil.copytree(fx, copy, ignore=run_study.FIXTURE_COPY_IGNORE)
        assert not (copy / ".git").exists(), "copy must not deliver .git (matches the digest's ignore)"
        assert (copy / "empty-dir").is_dir(), "copy must still deliver the empty directory"
        copy_digest = run_study.fixture_tree_sha256(copy)
        assert copy_digest == src_digest, (
            "digest of source must equal digest of the delivered copy"
        )

        # reproduction: removing the empty directory must move the digest --
        # a file-only digest would miss this entirely.
        shutil.rmtree(fx / "empty-dir")
        assert run_study.fixture_tree_sha256(fx) != src_digest, (
            "removing an empty directory must change the digest"
        )
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_27_report_refuses_target_n_drift():
    # C2: safety contract 7's pre-registration guard must not be editable
    # after the fact by lowering target_n in the study file. Reproduces the
    # review's exact scenario: a study whose header recorded target_n=10 (one
    # valid run per arm so far, an original shortfall) must still refuse a
    # pooled comparison after the study file's target_n is edited down to 1
    # -- not silently emit Fisher comparisons against the edited value.
    evidence = new_evidence_dir("targetndrift")
    study_path = make_study(evidence, target_n=10, seed=19)
    evidence.mkdir(parents=True, exist_ok=True)
    fake_state = {
        "study_name": "test", "seed": 19, "schedule": ["control#1"],
        "header": {"target_n": 10}, "reservations": [],
        "backoff_seconds_used": 0.0, "stopped_reason": None,
        "cells": {
            "control#1": {"status": "complete", "attempts": [{"valid": True, "dispatched": True}]},
        },
    }
    (evidence / "state.json").write_text(json.dumps(fake_state))

    # reproduction, pre-fix shape: the true shortfall (1 of 10) is refused...
    report_before = run_cli(["report", str(study_path)], stub_env())
    parsed_before = json.loads(report_before.stdout)
    assert parsed_before.get("comparisons") is None
    assert "refused" in parsed_before and "target_n=10" in parsed_before["refused"]

    # ...lower target_n in the study file after the fact...
    study = json.loads(study_path.read_text())
    study["target_n"] = 1
    study_path.write_text(json.dumps(study))

    # ...must now be refused outright, not quietly emit comparisons at n=1.
    report_after = run_cli(["report", str(study_path)], stub_env())
    assert report_after.returncode != 0, report_after.stdout + report_after.stderr
    out = report_after.stdout + report_after.stderr
    assert "target_n drifted" in out, out
    assert "recorded 10" in out and "now says 1" in out, out

    shutil.rmtree(evidence, ignore_errors=True)


def test_28_report_uses_recorded_scope_not_live_study_scope():
    # C5: report must publish the scope actually run (recorded in the
    # header), not whatever the study file currently says -- editing the
    # study file's scope after a run must not corrupt the published record.
    evidence = new_evidence_dir("scopereport")
    study_path = make_study(
        evidence, target_n=1, seed=20,
        arms={"control": {"policy": "templates/claude-md.orchestration.md", "scope": "project"}},
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr

    # reproduction: edit the study file's scope after the run completed
    study = json.loads(study_path.read_text())
    study["arms"]["control"]["scope"] = "user"
    study_path.write_text(json.dumps(study))

    report = run_cli(["report", str(study_path)], stub_env())
    assert report.returncode == 0, report.stdout + report.stderr
    parsed = json.loads(report.stdout)
    assert parsed["arms"]["control"]["scope"] == "project", (
        "report must publish the scope that was actually run (recorded in "
        "the header), not the study file's edited-after-the-fact value"
    )

    shutil.rmtree(evidence, ignore_errors=True)


def test_29_user_scope_refuses_fixture_with_existing_claude_md():
    # C6: single-variable violation guard. A user-scope arm whose fixture
    # already ships a CLAUDE.md must be refused rather than silently running
    # with both the per-cell user policy AND the fixture's project policy
    # visible at once.
    import tempfile
    fixture_dir = Path(tempfile.mkdtemp(prefix="pilotfish-test29-fixture-"))
    try:
        (fixture_dir / "CLAUDE.md").write_text("pre-existing fixture policy\n")
        evidence = new_evidence_dir("userscopeclaudemd")
        study_path = make_study(
            evidence, target_n=1, seed=21,
            fixture=str(fixture_dir),
            arms={"control": {"policy": "templates/claude-md.orchestration.md", "scope": "user"}},
        )
        fake_home = evidence.parent / f"{evidence.name}.fakehome"
        fake_home.mkdir(parents=True, exist_ok=True)
        env = stub_env(CLAUDE_STUB_MODE="success")
        env["HOME"] = str(fake_home)
        env.pop("CLAUDE_CONFIG_DIR", None)

        result = run_cli(["run", str(study_path)], env)
        assert result.returncode != 0, result.stdout + result.stderr
        out = result.stdout + result.stderr
        assert "already contains" in out and "CLAUDE.md" in out, out

        state = json.loads((evidence / "state.json").read_text())
        assert state["reservations"] == [], "refused cell must not leave a charged reservation"

        shutil.rmtree(evidence, ignore_errors=True)
        shutil.rmtree(fake_home, ignore_errors=True)
    finally:
        shutil.rmtree(fixture_dir, ignore_errors=True)


def test_30_noisy_rate_limit_still_triggers_backoff():
    # C4: reproduces the review's exact scenario -- a rejection that is both
    # a rate limit AND emits a stray non-JSON line, so classify() raises and
    # the old code took the unparseable-stream early return with
    # rate_limited hardcoded False. That must no longer treat the run as an
    # ordinary invalid attempt with no global stop.
    evidence = new_evidence_dir("noisyratelimit")
    study_path = make_study(
        evidence, target_n=1, per_run_cap_usd=0.5, total_cap_usd=100.0,
        max_retries_per_cell=2, max_backoff_seconds=10, seed=22,
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="noise_rate_limit"))
    assert result.returncode == 2, (
        "a noisy rate-limit rejection must still hit the bounded-backoff "
        f"global-stop path (rc=2), got {result.returncode}: {result.stdout + result.stderr}"
    )

    state = json.loads((evidence / "state.json").read_text())
    attempted_cells = [c for c, info in state["cells"].items() if info["attempts"]]
    assert len(attempted_cells) == 1, "must stop without spinning through further cells"
    cell = attempted_cells[0]
    info = state["cells"][cell]
    for a in info["attempts"]:
        assert a["reason"] == "unparseable_stream"
        assert a["rate_limited"] is True, "rate_limited must not be hardcoded False for a noisy rejection"
        assert a["valid"] is False
    assert info["status"] == "exhausted"
    assert 0 < state["backoff_seconds_used"] <= 10

    shutil.rmtree(evidence, ignore_errors=True)


def test_31_interrupted_attempt_does_not_consume_retry_budget():
    # C7: an interrupted (hard-killed) attempt must not count against
    # max_retries_per_cell -- only evaluated attempts may. Reproduces the
    # review's scenario: one interrupted placeholder followed by rate-limit
    # rejections must exhaust only after the initial attempt plus
    # max_retries_per_cell EVALUATED rejections, not after attempt_no
    # (which includes the interrupted placeholder) reaches that count.
    evidence = new_evidence_dir("interruptretry")
    study_path = make_study(
        evidence, target_n=1, per_run_cap_usd=1.0, total_cap_usd=100.0,
        max_retries_per_cell=2, max_backoff_seconds=30, seed=23,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    env = stub_env(CLAUDE_STUB_MODE="hang")
    state_path = evidence / "state.json"
    kill_after_reservation(["run", str(study_path)], env, state_path)

    state = json.loads(state_path.read_text())
    cell = next(iter(state["cells"]))
    assert state["cells"][cell]["attempts"][0]["status"] == "interrupted"

    # resume with rate-limit rejections: 1 interrupted + up to (1 + 2)
    # evaluated attempts must all still be spent before exhaustion --
    # a pre-fix implementation keying off attempt_no would exhaust after
    # only 2 more (since attempt_no already counts the interrupted one).
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="rate_limit"))
    assert result.returncode == 2, result.stdout + result.stderr

    state = json.loads(state_path.read_text())
    info = state["cells"][cell]
    evaluated = [a for a in info["attempts"] if a.get("status") != "interrupted"]
    assert len(evaluated) == 3, (
        "1 initial + max_retries_per_cell(2) retries must all be evaluated "
        f"despite the earlier interrupted attempt, got {len(evaluated)}"
    )
    assert info["status"] == "exhausted"

    shutil.rmtree(evidence, ignore_errors=True)


def test_32_evidence_dir_symlink_resolved_before_ignore_check():
    # D7: evidence_dir is a symlink living under a Git-ignored path (e.g.
    # .agent-local/) but pointing at a Git-visible directory in the
    # worktree. Pre-fix, check_evidence_dir_git_ignored probed the ignored
    # symlink spelling and passed, while ensure_evidence_dir and every
    # stream write followed the symlink to the visible target -- raw JSONL
    # landed in a visible directory with the safety check green.
    # resolve_evidence_dir must resolve the symlink before either the check
    # or creation, so the refusal fires against the real (visible) target.
    visible_target = DISPATCH_RATE_DIR / "tests" / f"symlink-target-{uuid.uuid4().hex[:8]}"
    visible_target.mkdir()
    try:
        check = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", "--", str(visible_target)]
        )
        assert check.returncode != 0, "test setup bug: visible target is unexpectedly git-ignored"

        ignored_parent = REPO_ROOT / ".agent-local" / "dispatch-rate"
        ignored_parent.mkdir(parents=True, exist_ok=True)
        symlink_path = ignored_parent / f"test-symlink-{uuid.uuid4().hex[:8]}"
        os.symlink(visible_target, symlink_path)
        try:
            assert subprocess.run(
                ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", "--", str(symlink_path)]
            ).returncode == 0, "test setup bug: symlink spelling must itself be git-ignored"

            study_path = make_study(
                symlink_path, target_n=1,
                arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
            )
            result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
            assert result.returncode != 0, result.stdout + result.stderr
            assert "not Git-ignored" in result.stdout + result.stderr, result.stdout + result.stderr
            assert not any(visible_target.iterdir()), (
                "refused run must not have written anything into the symlink target"
            )
        finally:
            symlink_path.unlink(missing_ok=True)
    finally:
        shutil.rmtree(visible_target, ignore_errors=True)


def test_33_digest_drift_is_generic_over_header_shape():
    # Requirement 2: digest_drift must compare the WHOLE header generically,
    # not a hand-picked subset of named fields. Proven with a key
    # digest_drift has never heard of -- if it were hand-picking fields
    # (the pre-restructure shape), an unknown key would be silently ignored
    # no matter how much it drifted.
    stored = {
        "seed": 1, "target_n": 1,
        "totally_new_future_field": "original-value",
        "policies": {"control": {"bytes": 10, "sha256": "aaa", "scope": "project"}},
    }
    fresh = {
        "seed": 1, "target_n": 1,
        "totally_new_future_field": "DRIFTED-value",
        "policies": {"control": {"bytes": 10, "sha256": "aaa", "scope": "project"}},
    }
    diffs = run_study.digest_drift(stored, fresh)
    assert any("totally_new_future_field" in d for d in diffs), diffs
    assert any("original-value" in d and "DRIFTED-value" in d for d in diffs), diffs
    # unrelated, unchanged fields (including nested ones) must not appear
    assert not any("seed" in d for d in diffs), diffs
    assert not any("policies" in d for d in diffs), diffs


def test_34_report_uses_recorded_arms_not_live_study_arms():
    # D1: removing (or adding) an arm in study.json after a run must not
    # change which arms `report` computes over -- it must use the arm set
    # recorded in state["header"], not the live study file's arms dict, or
    # real evidence silently drops out of results.json / a shortfall gets
    # invented for an arm that was never run.
    evidence = new_evidence_dir("armsdrift")
    study_path = make_study(
        evidence, target_n=1, seed=24,
        arms={
            "control": {"policy": "templates/claude-md.orchestration.md"},
            "candidate": {"policy": "benchmarks/dispatch-rate/policies/candidate.md"},
        },
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr

    # remove 'candidate' from the live study file after the run completed
    study = json.loads(study_path.read_text())
    del study["arms"]["candidate"]
    study_path.write_text(json.dumps(study))

    report = run_cli(["report", str(study_path)], stub_env())
    assert report.returncode == 0, report.stdout + report.stderr
    parsed = json.loads(report.stdout)
    assert "candidate" in parsed["arms"], (
        "report must still show the candidate arm's real evidence even "
        "though the study file no longer lists it"
    )
    assert parsed["arms"]["candidate"]["attempts"] == 1
    assert "refused" not in parsed, (
        "no shortfall should be invented for an arm the study file no "
        f"longer lists but that was actually run at target_n: {parsed}"
    )

    shutil.rmtree(evidence, ignore_errors=True)


def test_35_agents_payload_frozen_within_single_run():
    # D2: snapshot_run_inputs must freeze the agents payload once (like
    # prompt/fixture), and every cell's make_run_root in that run must use
    # those frozen bytes -- an edit to agents_from mid-run must not reach a
    # later spawn, or one arm's denominator could mix mech-executor
    # definitions.
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="pilotfish-test35-"))
    try:
        agents_dir = tmp / "agents"
        agents_dir.mkdir()
        (agents_dir / "mech-executor.md").write_text(
            "---\nname: mech-executor\ndescription: original\nmodel: sonnet\neffort: low\n---\n\noriginal\n"
        )
        fixture_dir = tmp / "fixture"
        fixture_dir.mkdir()
        (fixture_dir / "marker.txt").write_text("x")
        prompt_path = tmp / "prompt.txt"
        prompt_path.write_text("prompt\n")

        study = {
            "prompt": str(prompt_path), "fixture": str(fixture_dir),
            "agents_from": str(agents_dir), "model": "opus",
            "per_run_cap_usd": 1.0, "seed": 1,
            "arms": {"control": {"policy": "templates/claude-md.orchestration.md", "scope": "project"}},
        }

        prompt_text, fixture_snapshot, agents_bytes = run_study.snapshot_run_inputs(study)
        original_bytes = agents_bytes

        # simulate a mid-run edit of agents_from, on the same path the study references
        (agents_dir / "mech-executor.md").write_text(
            "---\nname: mech-executor\ndescription: DRIFTED\nmodel: sonnet\neffort: low\n---\n\nDRIFTED\n"
        )

        run_root, fixture_copy, config_dir, setting_sources = run_study.make_run_root(
            study, "control", b"policy bytes", fixture_snapshot, agents_bytes
        )
        try:
            delivered = (run_root / "agents.json").read_bytes()
            assert delivered == original_bytes, (
                "make_run_root must write the run's frozen agents snapshot, "
                "not re-read the (now-edited) agents_from directory"
            )
            assert b"DRIFTED" not in delivered
        finally:
            run_study.cleanup_run_root(run_root)
            run_study.cleanup_run_root(fixture_snapshot.parent)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_36_model_drift_refuses_resume_and_report():
    # D3: editing the study's `model` after some cells have completed must
    # be refused by the resume drift gate (it's now part of the header, and
    # digest_drift compares the whole header), and `report` must refuse to
    # publish pooled rates against a study whose model changed underneath it.
    evidence = new_evidence_dir("modeldrift")
    study_path = make_study(
        evidence, target_n=1, seed=26, model="opus",
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr

    study = json.loads(study_path.read_text())
    study["model"] = "sonnet"
    study_path.write_text(json.dumps(study))

    result2 = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result2.returncode != 0, "resume must refuse once model has drifted"
    out2 = result2.stdout + result2.stderr
    assert "model" in out2 and "opus" in out2 and "sonnet" in out2, out2

    result3 = run_cli(["report", str(study_path)], stub_env())
    assert result3.returncode != 0, "report must refuse once model has drifted"
    out3 = result3.stdout + result3.stderr
    assert "model" in out3 and "drifted" in out3, out3

    shutil.rmtree(evidence, ignore_errors=True)


def test_37_unparseable_stream_records_digest():
    # D4: an unparseable stream must still have raw_stream_sha256 computed
    # from the bytes actually written and charged/retried -- not None -- so
    # a human can bind the recorded evidence back to its capture.
    import hashlib
    evidence = new_evidence_dir("noisehash")
    study_path = make_study(
        evidence, target_n=1, max_retries_per_cell=0, seed=27,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="noise"))
    assert result.returncode == 0, result.stdout + result.stderr

    state = json.loads((evidence / "state.json").read_text())
    cell = next(iter(state["cells"]))
    attempt = state["cells"][cell]["attempts"][0]
    assert attempt["reason"] == "unparseable_stream"
    assert attempt["raw_stream_sha256"] is not None

    stream_path = evidence / "streams" / f"{cell.replace('#', '-')}-attempt1.jsonl"
    expected = hashlib.sha256(stream_path.read_bytes()).hexdigest()
    assert attempt["raw_stream_sha256"] == expected

    shutil.rmtree(evidence, ignore_errors=True)


def test_38_rate_limit_detected_from_terminal_result_text():
    # D5: a terminal event with a generic subtype but a result message that
    # says "quota" (and empty stderr) must still be classified rate_limited,
    # triggering the bounded-backoff global stop -- checking subtype+stderr
    # alone missed exactly this case.
    evidence = new_evidence_dir("resulttextratelimit")
    study_path = make_study(
        evidence, target_n=1, per_run_cap_usd=0.5, total_cap_usd=100.0,
        max_retries_per_cell=2, max_backoff_seconds=10, seed=28,
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="rate_limit_result_text"))
    assert result.returncode == 2, (
        "a rate-limit message carried only in the terminal event's own "
        f"result text must still hit the bounded-backoff global stop, got "
        f"rc={result.returncode}: {result.stdout + result.stderr}"
    )

    state = json.loads((evidence / "state.json").read_text())
    attempted_cells = [c for c, info in state["cells"].items() if info["attempts"]]
    assert len(attempted_cells) == 1, "must stop without spinning through further cells"
    cell = attempted_cells[0]
    info = state["cells"][cell]
    for a in info["attempts"]:
        assert a["terminal_subtype"] == "error_during_execution"
        assert a["rate_limited"] is True, (
            "must detect rate limiting from the terminal event's own result text"
        )
        assert a["valid"] is False
    assert info["status"] == "exhausted"
    assert 0 < state["backoff_seconds_used"] <= 10

    shutil.rmtree(evidence, ignore_errors=True)


def test_39_snapshot_cleaned_up_on_refused_resume():
    # D6: a resume refused by the drift gate in load_or_init_state must not
    # leave the fixture snapshot behind under the temp directory -- the
    # cleanup try/finally must cover snapshot creation through state
    # loading, not only the cells loop that runs after it.
    import tempfile
    evidence = new_evidence_dir("snapcleanup")
    policy_path = evidence.parent / f"{evidence.name}.policy.md"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text("original policy bytes\n")
    study_path = make_study(
        evidence, target_n=1, seed=29,
        arms={"control": {"policy": str(policy_path)}},
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr

    policy_path.write_text("DRIFTED policy bytes\n")

    tmp_root = Path(tempfile.gettempdir())
    before = {p for p in tmp_root.glob("pilotfish-dispatch-rate-snapshot-*")}

    result2 = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result2.returncode != 0, "resume must refuse once the policy has drifted"

    after = {p for p in tmp_root.glob("pilotfish-dispatch-rate-snapshot-*")}
    leftover = after - before
    assert leftover == set(), (
        f"a refused resume must not leave a fixture snapshot behind: {leftover}"
    )

    shutil.rmtree(evidence, ignore_errors=True)
    policy_path.unlink(missing_ok=True)


def test_40_header_covers_every_run_affecting_field():
    # Structural issue 1 (third review round): the header's input set must
    # be derived from a single declared source, not a hand-written list --
    # that's exactly what let total_cap_usd and per_run_cap_usd both go
    # missing twice before. RUN_AFFECTING_HEADER_KEYS.keys() ==
    # RUN_AFFECTING_FIELDS is asserted at import time (module load); this
    # test additionally checks build_header()'s ACTUAL output against the
    # same declared mapping, so a bug in build_header itself (declared here
    # but not actually emitted) is caught by the suite too.
    study = run_study.load_study(str(DISPATCH_RATE_DIR / "study.example.json"))
    header = run_study.build_header(study)
    for field, header_keys in run_study.RUN_AFFECTING_HEADER_KEYS.items():
        for key in header_keys:
            assert key in header, (
                f"required field {field!r} maps to header key {key!r}, "
                f"which is missing from build_header()'s output"
            )
    # the two caps specifically, since that's the exact omission the review found
    assert header["total_cap_usd"] == study["total_cap_usd"]
    assert header["per_run_cap_usd"] == study["per_run_cap_usd"]
    assert header["max_retries_per_cell"] == study["max_retries_per_cell"]
    assert header["max_backoff_seconds"] == study["max_backoff_seconds"]


def test_41_total_cap_increase_on_resume_refused():
    # E2: raising total_cap_usd on resume must not restart a study that
    # already stopped at its ceiling -- the budget-ceiling bypass.
    evidence = new_evidence_dir("capraise")
    study_path = make_study(
        evidence, target_n=1, per_run_cap_usd=1.0, total_cap_usd=1.0,
        max_retries_per_cell=0, seed=40,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr

    study = json.loads(study_path.read_text())
    study["total_cap_usd"] = 100.0
    study_path.write_text(json.dumps(study))

    result2 = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result2.returncode != 0, "raising total_cap_usd on resume must be refused"
    out2 = result2.stdout + result2.stderr
    assert "total_cap_usd" in out2 and "increase refused" in out2, out2
    assert "1.0" in out2 and "100.0" in out2, out2

    shutil.rmtree(evidence, ignore_errors=True)


def test_41b_per_run_cap_increase_on_resume_refused():
    # E2, same ratchet on the other cap.
    evidence = new_evidence_dir("perruncapraise")
    study_path = make_study(
        evidence, target_n=1, per_run_cap_usd=1.0, total_cap_usd=100.0,
        max_retries_per_cell=0, seed=41,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr

    study = json.loads(study_path.read_text())
    study["per_run_cap_usd"] = 50.0
    study_path.write_text(json.dumps(study))

    result2 = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result2.returncode != 0, "raising per_run_cap_usd on resume must be refused"
    out2 = result2.stdout + result2.stderr
    assert "per_run_cap_usd" in out2 and "increase refused" in out2, out2

    shutil.rmtree(evidence, ignore_errors=True)


def test_42_cap_decrease_on_resume_allowed():
    # Lowering a cap only tightens an already-running study -- it must not
    # be refused the way any other header drift is.
    evidence = new_evidence_dir("capdecrease")
    study_path = make_study(
        evidence, target_n=1, per_run_cap_usd=1.0, total_cap_usd=100.0,
        max_retries_per_cell=0, seed=42,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr

    study = json.loads(study_path.read_text())
    study["total_cap_usd"] = 0.5
    study["per_run_cap_usd"] = 0.5
    study_path.write_text(json.dumps(study))

    result2 = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result2.returncode == 0, (
        f"lowering caps on resume must be allowed: {result2.stdout + result2.stderr}"
    )

    shutil.rmtree(evidence, ignore_errors=True)


def test_43_interrupted_attempt_with_complete_stream_recovered_not_respawned():
    # E5: killed after `claude` finished writing a COMPLETE stream but
    # before the runner persisted its evidence -- state still shows
    # "interrupted". On resume this must be classified and persisted in
    # place, not treated as unevaluated and retried (which would drop a
    # completed, possibly paid, run from the denominator and spend again).
    evidence = new_evidence_dir("recoverinterrupted")
    study_path = make_study(
        evidence, target_n=1, per_run_cap_usd=1.0, total_cap_usd=100.0,
        max_retries_per_cell=1, seed=43,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    study = run_study.load_study(str(study_path))
    schedule = run_study.build_schedule(study)
    cell = schedule[0]

    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / ".pilotfish-created").touch()
    (evidence / "streams").mkdir(exist_ok=True)
    stream_path = evidence / "streams" / f"{cell.replace('#', '-')}-attempt1.jsonl"
    stream_path.write_text(
        json.dumps({"type": "system", "subtype": "init", "model": "claude-stub-5",
                    "claude_code_version": "0.0.0-stub"}) + "\n"
        + json.dumps({"type": "assistant", "parent_tool_use_id": None,
                      "message": {"content": [{"type": "tool_use", "id": "t1",
                                                "name": "Write", "input": {}}]}}) + "\n"
        + json.dumps({"type": "result", "subtype": "success", "total_cost_usd": 0.07,
                      "modelUsage": {"claude-stub-5": {"costUSD": 0.07}}}) + "\n"
    )
    (evidence / "streams" / f"{cell.replace('#', '-')}-attempt1.err").write_text("")

    fresh_header = run_study.build_header(study)
    state = {
        "study_name": study.get("name"), "seed": study["seed"], "schedule": schedule,
        "header": fresh_header,
        "reservations": [
            {"cell": cell, "attempt": 1, "charged_usd": study["per_run_cap_usd"], "status": "reserved"},
        ],
        "cells": {cell: {"status": "in_progress", "attempts": [
            {"attempt": 1, "valid": False, "status": "interrupted"},
        ]}},
        "backoff_seconds_used": 0.0, "stopped_reason": None,
    }
    (evidence / "state.json").write_text(json.dumps(state))

    counter_file = evidence.parent / f"{evidence.name}.counter"
    result = run_cli(
        ["run", str(study_path)],
        stub_env(CLAUDE_STUB_MODE="success", CLAUDE_STUB_COUNTER_FILE=str(counter_file)),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not counter_file.exists(), (
        "the stub must never have been invoked -- a recoverable attempt must not respawn"
    )
    stream2 = evidence / "streams" / f"{cell.replace('#', '-')}-attempt2.jsonl"
    assert not stream2.exists(), "recovering attempt1 must not create a new attempt"

    state_after = json.loads((evidence / "state.json").read_text())
    info = state_after["cells"][cell]
    assert info["status"] == "complete"
    assert len(info["attempts"]) == 1
    attempt = info["attempts"][0]
    assert attempt["valid"] is True
    assert attempt["cost_usd"] == 0.07
    assert attempt.get("status") != "interrupted"
    reservation = state_after["reservations"][0]
    assert reservation["charged_usd"] == 0.07, "reservation must reconcile to the recovered cost"
    assert reservation["status"] == "done"

    shutil.rmtree(evidence, ignore_errors=True)


def test_43b_interrupted_attempt_with_truncated_stream_still_retried():
    # E5's counterpart: an interrupted attempt whose stream never reached a
    # terminal event (the far more common kill shape -- the process was
    # still running) must NOT be treated as recoverable; it must still be
    # retried as a new attempt, exactly like before this fix.
    evidence = new_evidence_dir("truncatedinterrupt")
    study_path = make_study(
        evidence, target_n=1, per_run_cap_usd=1.0, total_cap_usd=100.0,
        max_retries_per_cell=1, seed=44,
        arms={"control": {"policy": "templates/claude-md.orchestration.md"}},
    )
    study = run_study.load_study(str(study_path))
    schedule = run_study.build_schedule(study)
    cell = schedule[0]

    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / ".pilotfish-created").touch()
    (evidence / "streams").mkdir(exist_ok=True)
    stream_path = evidence / "streams" / f"{cell.replace('#', '-')}-attempt1.jsonl"
    stream_path.write_text(
        json.dumps({"type": "system", "subtype": "init", "model": "claude-stub-5",
                    "claude_code_version": "0.0.0-stub"}) + "\n"
        # no terminal "result" event -- truncated mid-run
    )

    fresh_header = run_study.build_header(study)
    state = {
        "study_name": study.get("name"), "seed": study["seed"], "schedule": schedule,
        "header": fresh_header,
        "reservations": [
            {"cell": cell, "attempt": 1, "charged_usd": study["per_run_cap_usd"], "status": "reserved"},
        ],
        "cells": {cell: {"status": "in_progress", "attempts": [
            {"attempt": 1, "valid": False, "status": "interrupted"},
        ]}},
        "backoff_seconds_used": 0.0, "stopped_reason": None,
    }
    (evidence / "state.json").write_text(json.dumps(state))

    result = run_cli(["run", str(study_path)], stub_env(CLAUDE_STUB_MODE="success"))
    assert result.returncode == 0, result.stdout + result.stderr

    stream2 = evidence / "streams" / f"{cell.replace('#', '-')}-attempt2.jsonl"
    assert stream2.exists(), "a truncated interrupted stream must still be retried as a new attempt"

    shutil.rmtree(evidence, ignore_errors=True)


def test_44_user_scope_empty_fixture_baseline_commit_succeeds():
    # E3: an empty (or empty-dirs-only) fixture at user scope writes no
    # CLAUDE.md into the fixture copy (the policy goes to the per-cell
    # CLAUDE_CONFIG_DIR instead), so `git commit` had nothing to commit and
    # failed after budget was already reserved and before any spawn.
    import tempfile
    fixture_dir = Path(tempfile.mkdtemp(prefix="pilotfish-test44-fixture-"))
    try:
        (fixture_dir / "empty-subdir").mkdir()
        evidence = new_evidence_dir("emptyfixture")
        fake_home = evidence.parent / f"{evidence.name}.fakehome"
        fake_home.mkdir(parents=True, exist_ok=True)
        study_path = make_study(
            evidence, target_n=1, seed=45,
            fixture=str(fixture_dir),
            arms={"control": {"policy": "templates/claude-md.orchestration.md", "scope": "user"}},
        )
        env = stub_env(CLAUDE_STUB_MODE="success")
        env["HOME"] = str(fake_home)
        env.pop("CLAUDE_CONFIG_DIR", None)

        result = run_cli(["run", str(study_path)], env)
        assert result.returncode == 0, result.stdout + result.stderr
        state = json.loads((evidence / "state.json").read_text())
        assert state["cells"]["control#1"]["status"] == "complete"
        assert state["reservations"][0]["status"] == "done"

        shutil.rmtree(evidence, ignore_errors=True)
        shutil.rmtree(fake_home, ignore_errors=True)
    finally:
        shutil.rmtree(fixture_dir, ignore_errors=True)


def test_45_report_refuses_pooled_comparisons_on_mixed_client_version():
    # E1: attempts observed under different client_version values must not
    # be silently pooled into one label -- refuse pooled comparisons and
    # name the distinct values, while still printing per-arm counts.
    evidence = new_evidence_dir("mixedclient")
    study_path = make_study(evidence, target_n=1, seed=46)
    evidence.mkdir(parents=True, exist_ok=True)
    study = run_study.load_study(str(study_path))
    header = run_study.build_header(study)

    def attempt(client_version, model):
        return {
            "valid": True, "dispatched": True, "cost_usd": 0.05,
            "client_version": client_version, "observed_main_model": model,
        }

    fake_state = {
        "study_name": "test", "seed": 46, "schedule": ["control#1", "candidate#1", "placebo#1"],
        "header": header, "reservations": [], "backoff_seconds_used": 0.0, "stopped_reason": None,
        "cells": {
            "control#1": {"status": "complete", "attempts": [attempt("2.1.100", "claude-stub-5")]},
            "candidate#1": {"status": "complete", "attempts": [attempt("2.1.220", "claude-stub-5")]},
            "placebo#1": {"status": "complete", "attempts": [attempt("2.1.100", "claude-stub-5")]},
        },
    }
    (evidence / "state.json").write_text(json.dumps(fake_state))

    result = run_cli(["report", str(study_path)], stub_env())
    assert result.returncode == 0, result.stdout + result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["comparisons"] is None
    assert "refused" in parsed and "mixed observed conditions" in parsed["refused"], parsed
    assert "client_version" in parsed["refused"], parsed["refused"]
    assert parsed["arms"]["control"]["attempts"] == 1, "per-arm counts must still be printed"
    assert sorted(parsed["observed_conditions"]["client_version"]) == ["2.1.100", "2.1.220"]

    shutil.rmtree(evidence, ignore_errors=True)


def test_46_report_refuses_pooled_comparisons_on_mixed_observed_main_model():
    # E4: the report must not ignore observed_main_model in favor of the
    # requested `model` -- a model alias resolving differently across
    # attempts must refuse pooling too, even with a single client_version.
    evidence = new_evidence_dir("mixedmodel")
    study_path = make_study(evidence, target_n=1, seed=47)
    evidence.mkdir(parents=True, exist_ok=True)
    study = run_study.load_study(str(study_path))
    header = run_study.build_header(study)

    def attempt(model):
        return {
            "valid": True, "dispatched": True, "cost_usd": 0.05,
            "client_version": "2.1.100", "observed_main_model": model,
        }

    fake_state = {
        "study_name": "test", "seed": 47, "schedule": ["control#1", "candidate#1", "placebo#1"],
        "header": header, "reservations": [], "backoff_seconds_used": 0.0, "stopped_reason": None,
        "cells": {
            "control#1": {"status": "complete", "attempts": [attempt("claude-opus-5")]},
            "candidate#1": {"status": "complete", "attempts": [attempt("claude-opus-5-1")]},
            "placebo#1": {"status": "complete", "attempts": [attempt("claude-opus-5")]},
        },
    }
    (evidence / "state.json").write_text(json.dumps(fake_state))

    result = run_cli(["report", str(study_path)], stub_env())
    assert result.returncode == 0, result.stdout + result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["comparisons"] is None
    assert "refused" in parsed and "observed_main_model" in parsed["refused"], parsed
    assert parsed["model"] == "opus", "the requested model field is unaffected"

    shutil.rmtree(evidence, ignore_errors=True)


def test_47_report_pools_normally_when_conditions_uniform():
    # Sanity check on the new gate: uniform observed conditions across all
    # valid attempts must still pool and reproduce a Fisher p-value, exactly
    # as before this change.
    evidence = new_evidence_dir("uniformconditions")
    study_path = make_study(evidence, target_n=1, seed=48)
    evidence.mkdir(parents=True, exist_ok=True)
    study = run_study.load_study(str(study_path))
    header = run_study.build_header(study)

    def attempt(dispatched):
        return {
            "valid": True, "dispatched": dispatched, "cost_usd": 0.05,
            "client_version": "2.1.100", "observed_main_model": "claude-stub-5",
        }

    fake_state = {
        "study_name": "test", "seed": 48, "schedule": ["control#1", "candidate#1", "placebo#1"],
        "header": header, "reservations": [], "backoff_seconds_used": 0.0, "stopped_reason": None,
        "cells": {
            "control#1": {"status": "complete", "attempts": [attempt(False)]},
            "candidate#1": {"status": "complete", "attempts": [attempt(True)]},
            "placebo#1": {"status": "complete", "attempts": [attempt(False)]},
        },
    }
    (evidence / "state.json").write_text(json.dumps(fake_state))

    result = run_cli(["report", str(study_path)], stub_env())
    assert result.returncode == 0, result.stdout + result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["comparisons"] is not None, parsed
    assert "refused" not in parsed, parsed
    assert parsed["client"] == "2.1.100"

    shutil.rmtree(evidence, ignore_errors=True)


TESTS = [
    test_1_plan_stable_and_resolves,
    test_2_reservation_survives_kill_and_blocks,
    test_3_rate_limit_retries_then_stops_without_spinning,
    test_4_resume_completes_only_missing_cells,
    test_5_report_refuses_before_target_n,
    test_6_legacy_report_reproduces_tracked_synthetic_fixture,
    test_6b_legacy_report_reproduces_source_study,
    test_7_no_committed_jsonl_no_agents_json_in_fixture,
    test_9_scope_handling,
    test_10_concurrent_run_refuses,
    test_11_evidence_dir_must_be_git_ignored,
    test_12_unparseable_stream_does_not_abort_study,
    test_13_run_root_guarded_against_real_config_root_project_scope,
    test_14_reservation_released_on_guard_refusal,
    test_15_interrupted_attempt_never_overwritten_on_resume,
    test_16_reason_names_actual_defect_not_success,
    test_17_digest_drift_refuses_resume,
    test_18_git_ignore_check_probes_evidence_dir_not_repo_root,
    test_19_run_root_cleaned_up_after_valid_attempt_kept_for_invalid,
    test_20_fix_a_snapshot_immune_to_mid_run_edit,
    test_21_digest_drift_refuses_on_scope_change,
    test_22_gitignore_suggestion_matches_nonexistent_dir,
    test_23_report_round_trips_through_legacy,
    test_24_prompt_digest_matches_delivered_bytes_for_crlf,
    test_25_fixture_digest_covers_symlinked_directories,
    test_26_fixture_digest_matches_delivered_copy_with_empty_dir_and_git,
    test_27_report_refuses_target_n_drift,
    test_28_report_uses_recorded_scope_not_live_study_scope,
    test_29_user_scope_refuses_fixture_with_existing_claude_md,
    test_30_noisy_rate_limit_still_triggers_backoff,
    test_31_interrupted_attempt_does_not_consume_retry_budget,
    test_32_evidence_dir_symlink_resolved_before_ignore_check,
    test_33_digest_drift_is_generic_over_header_shape,
    test_34_report_uses_recorded_arms_not_live_study_arms,
    test_35_agents_payload_frozen_within_single_run,
    test_36_model_drift_refuses_resume_and_report,
    test_37_unparseable_stream_records_digest,
    test_38_rate_limit_detected_from_terminal_result_text,
    test_39_snapshot_cleaned_up_on_refused_resume,
    test_40_header_covers_every_run_affecting_field,
    test_41_total_cap_increase_on_resume_refused,
    test_41b_per_run_cap_increase_on_resume_refused,
    test_42_cap_decrease_on_resume_allowed,
    test_43_interrupted_attempt_with_complete_stream_recovered_not_respawned,
    test_43b_interrupted_attempt_with_truncated_stream_still_retried,
    test_44_user_scope_empty_fixture_baseline_commit_succeeds,
    test_45_report_refuses_pooled_comparisons_on_mixed_client_version,
    test_46_report_refuses_pooled_comparisons_on_mixed_observed_main_model,
    test_47_report_pools_normally_when_conditions_uniform,
]


def _sweep_test_leftovers() -> None:
    base = REPO_ROOT / ".agent-local" / "dispatch-rate"
    if not base.exists():
        return
    for p in base.glob("test-*"):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            p.unlink(missing_ok=True)


def main() -> int:
    _sweep_test_leftovers()  # clean any debris from a prior interrupted run
    failed = []
    for test in TESTS:
        name = test.__name__
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            failed.append(name)
            print(f"FAIL {name}: {exc}")
        else:
            print(f"PASS {name}")
    _sweep_test_leftovers()
    print(f"\n{len(TESTS) - len(failed)}/{len(TESTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
