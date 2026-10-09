#!/usr/bin/env python3
"""Aider-polyglot style probe for pilotfish roles.

select  -> writes tasks.json (seeded sample of python+rust exercises)
sanity  -> grades each exercise's .meta example solution (grader self-check)
run     -> runs one claude -p per (task, config), hidden tests, then grades
"""
import json, os, random, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data/polyglot-benchmark"
OUT = HERE / "polyglot-out"
LANGS = {"python": 20, "rust": 20}
SEED = 20261009


def select():
    rng = random.Random(SEED)
    tasks = []
    for lang, n in LANGS.items():
        names = sorted(os.listdir(DATA / lang / "exercises/practice"))
        tasks += [{"lang": lang, "name": x} for x in sorted(rng.sample(names, n))]
    (HERE / "tasks.json").write_text(json.dumps(tasks, indent=1))
    print(len(tasks))


def src(t):
    return DATA / t["lang"] / "exercises/practice" / t["name"]


def cfg(t):
    return json.loads((src(t) / ".meta/config.json").read_text())


def prepare(t, work):
    """Copy exercise without tests and without .meta (holds the reference solution)."""
    s = src(t)
    tests = set(cfg(t)["files"]["test"])
    shutil.copytree(s, work, ignore=shutil.ignore_patterns(".meta"))
    for rel in tests:
        p = work / rel
        if p.exists():
            p.unlink()
    if t["lang"] == "rust":
        shutil.rmtree(work / "tests", ignore_errors=True)


def grade(t, work):
    """Restore the official tests and run them. Returns (passed, tail_of_output)."""
    s = src(t)
    for rel in cfg(t)["files"]["test"]:
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s / rel, work / rel)
    if t["lang"] == "python":
        cmd = ["uv", "run", "--quiet", "--with", "pytest", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider"]
    else:
        cmd = ["cargo", "test", "--quiet", "--", "--include-ignored"]
    try:
        r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=300)
        return r.returncode == 0, (r.stdout + r.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        return False, "grader timeout"


def sanity():
    tasks = json.loads((HERE / "tasks.json").read_text())
    bad = 0
    for t in tasks:
        with tempfile.TemporaryDirectory() as d:
            work = Path(d) / t["name"]
            prepare(t, work)
            for rel, ex in zip(cfg(t)["files"]["solution"], cfg(t)["files"]["example"]):
                (work / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src(t) / ex, work / rel)
            ok, tail = grade(t, work)
            if not ok:
                bad += 1
                print("SANITY FAIL", t, tail[-400:])
    print("sanity failures:", bad, "of", len(tasks))


def prompt(t):
    s = src(t)
    docs = (s / ".docs/instructions.md").read_text()
    app = s / ".docs/instructions.append.md"
    if app.exists():
        docs += "\n\n" + app.read_text()
    files = ", ".join(cfg(t)["files"]["solution"])
    return (
        f"Implement this {t['lang']} exercise in the current directory by editing {files}. "
        "Keep the existing function/struct names and signatures. The grader's test file is not provided; "
        "you may write and run your own checks, but do not create files the grader would collide with. "
        "When done, report what you implemented and how you checked it.\n\n" + docs
    )


def run_one(t, conf):
    model, effort, role = conf
    tag = f"{model}-{effort}-{role}"
    rec_path = OUT / tag / f"{t['lang']}-{t['name']}.json"
    if rec_path.exists():
        return json.loads(rec_path.read_text())
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    system = (HERE / f"role-{role}.md").read_text()
    with tempfile.TemporaryDirectory(prefix="pg-") as d:
        work = Path(d) / t["name"]
        prepare(t, work)
        t0 = time.time()
        try:
          r = subprocess.run(
            ["claude", "-p", prompt(t), "--model", model, "--effort", effort,
             "--system-prompt", system,
             "--disallowedTools", "Agent,Workflow,WebFetch,WebSearch",
             "--permission-mode", "acceptEdits", "--allowedTools", "Bash",
             "--setting-sources", "project", "--strict-mcp-config", "--no-session-persistence",
             "--output-format", "json"],
            cwd=work, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=1800)
        except subprocess.TimeoutExpired:
          r = subprocess.CompletedProcess([], 124, "", "agent timeout 1800s")
        dt = time.time() - t0
        try:
            j = json.loads(r.stdout)
        except Exception:
            j = {"is_error": True, "result": r.stdout[-2000:] + r.stderr[-2000:]}
        ok, tail = grade(t, work)
    mu = j.get("modelUsage", {})
    rec = {"task": t, "model": model, "effort": effort, "role": role, "passed": ok,
           "agent_error": bool(j.get("is_error")), "duration_s": round(dt, 1),
           "num_turns": j.get("num_turns"), "models_seen": list(mu),
           "output_tokens": sum(v.get("outputTokens", 0) for v in mu.values()),
           "input_tokens": sum(v.get("inputTokens", 0) + v.get("cacheReadInputTokens", 0) + v.get("cacheCreationInputTokens", 0) for v in mu.values()),
           "final_message": (j.get("result") or "")[-3000:], "grader_tail": tail}
    rec_path.write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    print(("PASS" if ok else "FAIL"), tag, t["lang"], t["name"], f"{dt:.0f}s", flush=True)
    return rec


def run(confs, workers):
    tasks = json.loads((HERE / "tasks.json").read_text())
    jobs = [(t, c) for c in confs for t in tasks]
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(lambda a: run_one(*a), jobs))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "select":
        select()
    elif cmd == "sanity":
        sanity()
    elif cmd == "run":
        confs = [tuple(c.split(":")) for c in sys.argv[3:]]
        run(confs, int(sys.argv[2]))
