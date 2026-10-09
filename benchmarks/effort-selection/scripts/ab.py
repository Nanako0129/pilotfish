#!/usr/bin/env python3
"""A/B: fixed role effort (A) vs main-agent-chosen effort (B), through the real
pilotfish plugin. The main session (default model) must delegate exactly once to
the named role; grading is identical to the earlier probes.

usage: ab.py polyglot <workers> | ab.py swe <workers>
"""
import importlib.util, json, os, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
# The recorded A/B used plugin/ from a12b57a, before the shipped effort clause existed;
# pointing this at a newer plugin/ gives arm A conflicting instructions.
PLUGIN = os.environ["PILOTFISH_PLUGIN"]
RULE = (HERE / "ab-rule-B.md").read_text()
FIXED = "Do not pass the Agent tool's `effort` parameter; let each role use its own configured effort."
OUT = HERE / "ab-out"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pg = load("pg", HERE / "polyglot.py")
ar = load("ar", HERE / "agent_run.py")

WRAP = ("Delegate this task exactly once to {role} and wait for it in the foreground. "
        "Do not read, edit or run anything yourself and do not delegate again; "
        "when it returns, report its result.\n\n--- task for {role} ---\n{task}")


def parse(stdout, role, arm):
    calls, child, main_tools, res = [], {}, [], None
    for line in stdout.splitlines():
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("type") == "assistant":
            m = e["message"]
            p = e.get("parent_tool_use_id")
            for c in m.get("content", []):
                if c.get("type") == "tool_use":
                    if c["name"] in ("Agent", "Task") and not p:
                        calls.append({"id": c["id"], "role": c["input"].get("subagent_type"),
                                      "effort": c["input"].get("effort"), "model": c["input"].get("model")})
                    elif not p:
                        main_tools.append(c["name"])
            if p:
                child.setdefault(p, set()).add(m.get("model"))
        elif e.get("type") == "result":
            res = e
    for c in calls:
        c["child_models"] = sorted(child.get(c["id"], []))
    # A run counts only if it received its arm's treatment: one delegation to the
    # requested role, with no effort in arm A and an explicit effort in arm B.
    valid = (res is not None and not res.get("is_error") and len(calls) == 1 and not main_tools
             and calls[0]["role"] == role and (calls[0]["effort"] is None) == (arm == "A"))
    mu = (res or {}).get("modelUsage", {})
    return {
        "valid": valid, "delegations": calls, "main_tools": main_tools,
        "total_cost_usd": (res or {}).get("total_cost_usd"),
        "cost_by_model": {k: v.get("costUSD") for k, v in mu.items()},
        "output_tokens_by_model": {k: v.get("outputTokens") for k, v in mu.items()},
        "thinking_tokens_by_model": {k: v.get("thinkingTokens") for k, v in mu.items()},
        "duration_s": round((res or {}).get("duration_ms", 0) / 1000, 1),
        "agent_error": bool((res or {}).get("is_error", True)),
        "final_message": ((res or {}).get("result") or "")[-2000:],
    }


def claude(prompt, cwd, arm):
    extra = RULE if arm == "B" else FIXED
    try:
        r = subprocess.run(
            ["claude", "-p", prompt, "--append-system-prompt", extra, "--plugin-dir", PLUGIN,
             "--permission-mode", "acceptEdits", "--allowedTools", "Bash",
             "--setting-sources", "project", "--strict-mcp-config", "--no-session-persistence",
             "--output-format", "stream-json", "--verbose"],
            cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=3600,
            env={k: v for k, v in os.environ.items() if k not in ("CLAUDE_EFFORT", "CLAUDE_CODE_EFFORT_LEVEL")})
        return r.stdout
    except subprocess.TimeoutExpired as e:
        return (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")


def run_polyglot(t, arm):
    path = OUT / f"polyglot-{arm}" / f"{t['lang']}-{t['name']}.json"
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ab-") as d:
        work = Path(d) / t["name"]
        pg.prepare(t, work)
        rec = parse(claude(WRAP.format(role="pilotfish:mech-executor", task=pg.prompt(t)), work, arm),
                    "pilotfish:mech-executor", arm)
        rec["passed"], rec["grader_tail"] = pg.grade(t, work)
    rec["task"] = t
    path.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    print("polyglot", arm, t["name"], "PASS" if rec["passed"] else "FAIL",
          [c["effort"] for c in rec["delegations"]], rec["total_cost_usd"], flush=True)


def run_swe(inst, arm):
    iid = inst["instance_id"]
    path = OUT / f"swe-{arm}" / f"{iid}.json"
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tag = f"ab-{arm}"
    wd = ar.WORK / tag / iid
    shutil.rmtree(wd, ignore_errors=True)
    wd.parent.mkdir(parents=True, exist_ok=True)
    cont = f"ab-{arm}-{iid}".replace(".", "-").replace("_", "-")[:120]
    ar.sh(["docker", "rm", "-f", cont])
    tmp = cont + "-cp"
    ar.sh(["docker", "create", "--platform", "linux/amd64", "--name", tmp, inst["image"]])
    ar.sh(["docker", "cp", f"{tmp}:/testbed", str(wd)])
    ar.sh(["docker", "rm", "-f", tmp])
    started = ar.sh(["docker", "run", "-d", "--platform", "linux/amd64", "--name", cont,
                     "-v", f"{wd}:/testbed", inst["image"], "sleep", "infinity"])
    if started.returncode != 0 or not (wd / ".git").exists():
        raise RuntimeError(f"{iid}: container or /testbed copy failed; not starting a paid session")
    (wd / "envrun").write_text(ar.ENVRUN.format(cont=cont))
    (wd / "envrun").chmod(0o755)
    with open(wd / ".git/info/exclude", "a") as f:
        f.write("\nenvrun\n")
    rec = parse(claude(WRAP.format(role="pilotfish:executor", task=ar.prompt(inst)), wd, arm),
                "pilotfish:executor", arm)
    rec["patch"] = ar.diff_with_new_files(wd)
    rec["instance_id"] = iid
    ar.sh(["docker", "rm", "-f", cont])
    shutil.rmtree(wd, ignore_errors=True)
    path.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    print("swe", arm, iid, [c["effort"] for c in rec["delegations"]], rec["total_cost_usd"], flush=True)


if __name__ == "__main__":
    suite, workers = sys.argv[1], int(sys.argv[2])
    if suite == "polyglot":
        items = json.loads((HERE / "tasks.json").read_text())
        fn = run_polyglot
    else:
        items = json.load(open(HERE / "med20.json"))
        fn = run_swe
    jobs = [(i, arm) for i in items for arm in ("A", "B")]
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(lambda a: fn(*a), jobs))
    if suite == "swe":
        records = {(i["instance_id"], arm): json.loads((OUT / f"swe-{arm}" / f"{i['instance_id']}.json").read_text())
                   for i in items for arm in ("A", "B")}
        invalid = sorted(k for k, r in records.items() if not r.get("valid"))
        if invalid:
            # Rerunning is a paid decision; stop instead of grading runs that missed their treatment.
            raise SystemExit(f"invalid runs, delete their records and rerun before exporting: {invalid}")
        for arm in ("A", "B"):
            preds = [{"instance_id": i["instance_id"], "model_name_or_path": f"ab-{arm}",
                      "model_patch": json.loads((OUT / f"swe-{arm}" / f"{i['instance_id']}.json").read_text())["patch"]}
                     for i in items]
            (HERE / f"preds-ab-{arm}.json").write_text(json.dumps(preds))
