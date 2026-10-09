#!/usr/bin/env python3
"""Run one claude -p agent per (SWE-bench instance, config) and collect predictions.

The agent edits a host copy of the image's /testbed (bind-mounted back into a
container of the same image), and can run commands in the instance's conda env
via ./envrun. Hidden FAIL_TO_PASS tests are never shown. Output: preds-<tag>.json
for swebench.harness.run_evaluation, plus per-instance records.
"""
import json, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROLE = HERE.parent / "role-executor.md"
OUT = HERE / "agent-out"
WORK = HERE / "work"

ENVRUN = """#!/bin/sh
# Run a command inside the task's test environment (repo at /testbed, conda env 'testbed').
exec docker exec -w /testbed {cont} bash -lc "source /opt/miniconda3/bin/activate testbed && $*"
"""


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, **kw)


def diff_with_new_files(wd):
    """Tracked changes plus files the agent created (envrun is excluded via info/exclude)."""
    sh(["git", "add", "--intent-to-add", "--all"], cwd=wd)
    return sh(["git", "-c", "core.fileMode=false", "diff", "--no-color"], cwd=wd).stdout


def prompt(inst):
    return (
        "Resolve the following GitHub issue in the repository in the current directory "
        f"({inst['repo']}). Make the minimal source change that fixes it. "
        "Run commands in the project's test environment with `./envrun <command>` "
        "(for example `./envrun python -m pytest path/to/test.py -x -q`); plain shell commands "
        "run on the host, which lacks the project's dependencies. Do not commit. "
        "Do not modify or add test files unless needed to check your change locally; "
        "the grader uses its own hidden tests. Report what you changed and how you verified it.\n\n"
        "<issue>\n" + inst["problem_statement"] + "\n</issue>"
    )


def run_one(inst, conf):
    model, effort = conf
    tag = f"{model}-{effort}"
    iid = inst["instance_id"]
    rec_path = OUT / tag / f"{iid}.json"
    if rec_path.exists():
        return json.loads(rec_path.read_text())
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    wd = WORK / tag / iid
    shutil.rmtree(wd, ignore_errors=True)
    wd.parent.mkdir(parents=True, exist_ok=True)
    cont = f"probe-{tag}-{iid}".replace(".", "-").replace("_", "-")[:120]
    sh(["docker", "rm", "-f", cont])
    # Copy /testbed (with its built artifacts) out of the image.
    tmp = f"{cont}-cp"
    sh(["docker", "create", "--platform", "linux/amd64", "--name", tmp, inst["image"]])
    sh(["docker", "cp", f"{tmp}:/testbed", str(wd)])
    sh(["docker", "rm", "-f", tmp])
    sh(["docker", "run", "-d", "--platform", "linux/amd64", "--name", cont,
        "-v", f"{wd}:/testbed", inst["image"], "sleep", "infinity"])
    (wd / "envrun").write_text(ENVRUN.format(cont=cont))
    (wd / "envrun").chmod(0o755)
    # Keep the helper out of the diff.
    with open(wd / ".git/info/exclude", "a") as f:
        f.write("\nenvrun\n")
    t0 = time.time()
    try:
        r = subprocess.run(
            ["claude", "-p", prompt(inst), "--model", model, "--effort", effort,
             "--system-prompt", ROLE.read_text(),
             "--disallowedTools", "Agent,Workflow,WebFetch,WebSearch",
             "--permission-mode", "acceptEdits", "--allowedTools", "Bash",
             "--setting-sources", "project", "--strict-mcp-config", "--no-session-persistence",
             "--output-format", "json"],
            cwd=wd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=3600)
        out = r.stdout
    except subprocess.TimeoutExpired:
        out = ""
    dt = time.time() - t0
    try:
        j = json.loads(out)
    except Exception:
        j = {"is_error": True, "result": out[-2000:]}
    diff = diff_with_new_files(wd)
    sh(["docker", "rm", "-f", cont])
    mu = j.get("modelUsage", {})
    rec = {"instance_id": iid, "model": model, "effort": effort,
           "agent_error": bool(j.get("is_error")), "duration_s": round(dt, 1),
           "num_turns": j.get("num_turns"), "models_seen": list(mu),
           "output_tokens": sum(v.get("outputTokens", 0) for v in mu.values()),
           "input_tokens": sum(v.get("inputTokens", 0) + v.get("cacheReadInputTokens", 0) + v.get("cacheCreationInputTokens", 0) for v in mu.values()),
           "patch": diff, "final_message": (j.get("result") or "")[-3000:]}
    rec_path.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    shutil.rmtree(wd, ignore_errors=True)
    print("done", tag, iid, f"{dt:.0f}s", "patch_lines", diff.count("\n"), flush=True)
    return rec


def main():
    workers = int(sys.argv[1])
    insts = json.load(open(HERE / "pick20.json"))
    confs = [tuple(c.split(":")) for c in sys.argv[2:]]
    jobs = [(i, c) for c in confs for i in insts]
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(lambda a: run_one(*a), jobs))
    for c in confs:
        tag = f"{c[0]}-{c[1]}"
        preds = [{"instance_id": i["instance_id"], "model_name_or_path": tag,
                  "model_patch": json.loads((OUT / tag / f"{i['instance_id']}.json").read_text())["patch"]}
                 for i in insts]
        (HERE / f"preds-{tag}.json").write_text(json.dumps(preds))


if __name__ == "__main__":
    main()
