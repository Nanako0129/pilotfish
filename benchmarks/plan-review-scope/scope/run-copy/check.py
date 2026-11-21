#!/usr/bin/env python3
"""Routing check for one `claude -p --output-format stream-json` capture.

usage: check.py STREAM.jsonl --require ROLE[,ROLE] --allow ROLE[,ROLE]
       check.py --spent STREAMS_DIR

PASS needs: a result line with subtype success and is_error false; every
--require role called at least once at top level; every top-level Agent/Task
call's subagent_type inside require+allow; no invocation `model`; no
run_in_background; no top-level Write/Edit/NotebookEdit when --no-main-writes.
Only top-level events (parent_tool_use_id null/absent) are counted.
"""
import argparse
import json
import pathlib
import sys

WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}


def load(path):
    events = []
    for line in pathlib.Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def result_of(events):
    for e in reversed(events):
        if isinstance(e, dict) and e.get("type") == "result":
            return e
    return None


def spent(directory):
    total = 0.0
    for p in sorted(pathlib.Path(directory).glob("*.jsonl")):
        r = result_of(load(p))
        if r is None:
            print(f"UNKNOWN-COST {p.name}", file=sys.stderr)
            return None
        total += float(r.get("total_cost_usd") or 0.0)
    return total


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(x.get("text", "") for x in content if isinstance(x, dict))
    return ""


def roles(value):
    return [x for x in value.split(",") if x]


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--spent":
        s = spent(sys.argv[2])
        if s is None:
            sys.exit(2)
        print(f"{s:.6f}")
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("stream")
    ap.add_argument("--require", type=roles, default=[])
    ap.add_argument("--allow", type=roles, default=[])
    ap.add_argument("--no-main-writes", action="store_true")
    a = ap.parse_args()
    events = load(a.stream)
    calls, results, failed, writes, version, model = [], {}, set(), [], None, None
    for e in events:
        if not isinstance(e, dict):
            continue
        if e.get("type") == "system" and e.get("subtype") == "init":
            version, model = e.get("claude_code_version"), e.get("model")
        if e.get("parent_tool_use_id"):
            continue
        content = (e.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for x in content:
            if not isinstance(x, dict):
                continue
            if e.get("type") == "assistant" and x.get("type") == "tool_use":
                if x.get("name") in ("Agent", "Task"):
                    calls.append(x)
                elif x.get("name") in WRITE_TOOLS:
                    writes.append(x.get("name"))
            if e.get("type") == "user" and x.get("type") == "tool_result":
                results[x.get("tool_use_id")] = text_of(x.get("content"))
                if x.get("is_error"):
                    failed.add(x.get("tool_use_id"))
    r = result_of(events) or {}
    stem = pathlib.Path(a.stream).with_suffix("")
    types = []
    for i, c in enumerate(calls):
        inp = c.get("input") or {}
        types.append(inp.get("subagent_type"))
        pathlib.Path(f"{stem}.agent{i}.txt").write_text(results.get(c.get("id"), ""), encoding="utf-8")
    pathlib.Path(f"{stem}.final.txt").write_text(str(r.get("result") or ""), encoding="utf-8")
    permitted = set(a.require) | set(a.allow)
    overrides = any((c.get("input") or {}).get("model") for c in calls)
    background = any((c.get("input") or {}).get("run_in_background") for c in calls)
    problems = []
    if r.get("subtype") != "success" or r.get("is_error"):
        problems.append(f"result={r.get('subtype')}/{r.get('is_error')}")
    completed = [
        (c.get("input") or {}).get("subagent_type")
        for c in calls
        if c.get("id") in results and c.get("id") not in failed
    ]
    for role in a.require:
        if role not in completed:
            problems.append(f"missing-or-failed:{role}")
    for t in types:
        if t not in permitted:
            problems.append(f"unexpected:{t}")
    if overrides:
        problems.append("model-override")
    if background:
        problems.append("background")
    if a.no_main_writes and writes:
        problems.append(f"main-writes:{writes}")
    print(
        f"RESULT {'PASS' if not problems else 'FAIL'} {pathlib.Path(a.stream).name} agents={types} "
        f"problems={problems} main_writes={writes} cost={r.get('total_cost_usd')} "
        f"client={version} main_model={model}"
    )
    sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()
