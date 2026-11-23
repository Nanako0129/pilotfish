#!/usr/bin/env python3
"""Run the dispatch-brake task and its research control under agy, with and
without plugin-agy, and record what the main agent did.

    python3 benchmarks/agy-preview/run.py --out /path/to/new-dir [--reps 5]

Each run gets a fresh workspace (fixture copy + one base commit). The "plugin"
condition adds plugin-agy as a workspace plugin; "none" adds nothing. The
user's global agy configuration applies to both conditions alike.
Spends agy quota: tasks x 2 conditions x reps headless runs.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRAKE = ROOT / "benchmarks" / "dispatch-brake"
TASKS = {
    # name: (task file, fixture). brake = delegation should not happen;
    # research = two disjoint surfaces, delegation is expected to pay.
    "brake": (BRAKE / "task.md", BRAKE / "fixture"),
    "research": (
        BRAKE / "positive-controls" / "research" / "task.md",
        BRAKE / "positive-controls" / "research" / "fixture",
    ),
}
BRAIN = Path.home() / ".gemini" / "antigravity-cli" / "brain"
GIT = ["git", "-c", "user.name=bench", "-c", "user.email=bench@example.invalid"]


def prompt_of(task_md: Path) -> str:
    return re.search(r"```text\n(.*?)\n```", task_md.read_text(encoding="utf-8"), re.S).group(1)


def subagent_calls(transcript: str) -> list[str]:
    """TypeName of every invoke_subagent call, "?" when a call names none."""
    starts = [m.end() for m in re.finditer(r'"name":"invoke_subagent","args":\{', transcript)]
    names = []
    for start, end in zip(starts, [*starts[1:], len(transcript)]):
        # A prompt may contain braces, so search the call's whole span, not up to the first "}".
        m = re.search(r'"TypeName":"([^"]+)"', transcript[start:end])
        names.append(m.group(1) if m else "?")
    return names


def run_one(task: str, cond: str, rep: int, out: Path, model: str) -> dict:
    task_md, fixture = TASKS[task]
    name = f"{task}-{cond}-{rep}"
    ws = out / name
    shutil.copytree(fixture, ws)  # raises if the workspace exists: never reuse one
    if cond == "plugin":
        shutil.copytree(ROOT / "plugin-agy", ws / ".agents" / "plugins" / "pilotfish")
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    subprocess.run(["git", "add", "-A", "."], cwd=ws, check=True)
    subprocess.run([*GIT, "commit", "-qm", "base"], cwd=ws, check=True)

    row: dict = {"task": task, "condition": cond, "rep": rep}
    try:
        proc = subprocess.run(
            ["agy", "--model", model, "--print-timeout", "560s", "--output-format", "json",
             "-p=" + prompt_of(task_md)],
            cwd=ws, capture_output=True, text=True, timeout=620,
        )
        (out / f"{name}.json").write_text(proc.stdout, encoding="utf-8")
        (out / f"{name}.err").write_text(proc.stderr, encoding="utf-8")
        result = json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        result = {"status": "TIMEOUT"}
    except json.JSONDecodeError:
        result = {"status": "NO_JSON"}
    row["status"] = result.get("status")
    row["duration_seconds"] = result.get("duration_seconds")
    row["usage"] = result.get("usage")  # as agy reports it for the main conversation

    transcript = BRAIN / str(result.get("conversation_id")) / ".system_generated" / "logs" / "transcript_full.jsonl"
    if transcript.is_file():
        body = transcript.read_text(encoding="utf-8", errors="replace")
        row["subagent_calls"] = subagent_calls(body)
    else:
        row["subagent_calls"] = None  # unknown, not zero

    # Before the tests, so files a test run writes are not counted as the agent's.
    status = subprocess.run(["git", "status", "--short"], cwd=ws, capture_output=True, text=True, check=True)
    row["changed"] = status.stdout.splitlines()
    try:
        test = subprocess.run(["npm", "test"], cwd=ws, capture_output=True, text=True, timeout=300)
        row["tests_pass"] = test.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        row["tests_pass"] = None  # unknown
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--model", default="gemini-4-neon-high")
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()
    args.out.mkdir(parents=True)  # raises if it exists: results are never overwritten

    # rep outermost so the conditions interleave in time
    jobs = [(t, c, r) for r in range(1, args.reps + 1) for t in TASKS for c in ("plugin", "none")]
    rows = []
    with cf.ThreadPoolExecutor(args.jobs) as pool:
        futures = {pool.submit(run_one, t, c, r, args.out, args.model): (t, c, r) for t, c, r in jobs}
        for done in cf.as_completed(futures):
            try:
                row = done.result()
            except Exception as exc:  # keep the other runs; record this one as failed
                t, c, r = futures[done]
                row = {"task": t, "condition": c, "rep": r, "status": f"ERROR: {exc!r}"}
            rows.append(row)
            print(json.dumps(row), flush=True)
            (args.out / "results.json").write_text(json.dumps(
                {"model": args.model, "rows": sorted(rows, key=lambda x: (x["task"], x["condition"], x["rep"]))},
                indent=2) + "\n", encoding="utf-8")
    print(f"DONE {len(rows)}/{len(jobs)} runs", flush=True)


if __name__ == "__main__":
    main()
