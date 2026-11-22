#!/usr/bin/env python3
"""Summarize one `claude -p --output-format stream-json` capture.

usage: parse.py STREAM.jsonl ROLE EXPECT_REGEX   -> prints one RESULT line, exit 0 pass / 1 fail
       parse.py --spent STREAMS_DIR              -> prints summed total_cost_usd of all captures

Only top-level events (parent_tool_use_id null/absent) count as main-session
events; child-agent events are ignored for routing and write checks.
"""
import json
import pathlib
import re
import sys

WRITE_TOOLS = {"Write", "Edit", "NotebookEdit"}
VERDICTS = re.compile(r"\b(CONFIRMED|REFUTED|INCONCLUSIVE|READY|REVISE)\b")
VERDICT_LINE = re.compile(
    r"(?m)^[\s*_#>`-]*(?:verdict[\s*_:`-]*)?(CONFIRMED|REFUTED|INCONCLUSIVE|READY|REVISE)\b",
    re.IGNORECASE,
)


def verdict_of(body):
    """Verdict stated at the start of a line; else the only verdict word used; else None."""
    lines = {m.group(1).upper() for m in VERDICT_LINE.finditer(body) if m.group(1).isupper()}
    if len(lines) == 1:
        return lines.pop()
    if lines:
        return None
    words = set(VERDICTS.findall(body))
    return words.pop() if len(words) == 1 else None


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
        if e.get("type") == "result":
            return e
    return None


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(x.get("text", "") for x in content if isinstance(x, dict))
    return ""


def spent(directory):
    # A resumed call reports its session's cumulative total_cost_usd, so count each
    # session once, at its largest value.
    latest = {}
    for p in sorted(pathlib.Path(directory).glob("*.jsonl")):
        r = result_of(load(p))
        if r is None:
            # A capture without a result line has unknown cost: refuse to guess.
            print(f"UNKNOWN-COST {p.name}", file=sys.stderr)
            return None
        session = r.get("session_id") or p.name
        latest[session] = max(latest.get(session, 0.0), float(r.get("total_cost_usd") or 0.0))
    return sum(latest.values())


def main():
    if sys.argv[1] == "--spent":
        s = spent(sys.argv[2])
        if s is None:
            sys.exit(2)
        print(f"{s:.6f}")
        return
    path, role, expect = sys.argv[1], sys.argv[2], sys.argv[3]
    events = load(path)
    calls, results, writes, version, model = [], {}, [], None, None
    for e in events:
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
    r = result_of(events) or {}
    stem = pathlib.Path(path).with_suffix("")
    verdict = None
    types = []
    for i, c in enumerate(calls):
        inp = c.get("input") or {}
        types.append(inp.get("subagent_type"))
        body = results.get(c.get("id"), "")
        pathlib.Path(f"{stem}.agent{i}.txt").write_text(body, encoding="utf-8")
        if i == 0:
            verdict = verdict_of(body)
    overrides = [bool((c.get("input") or {}).get("model")) for c in calls]
    background = [bool((c.get("input") or {}).get("run_in_background")) for c in calls]
    ok = (
        r.get("subtype") == "success"
        and not r.get("is_error")
        and types == [role]
        and not any(overrides)
        and not any(background)
        and not writes
        and verdict is not None
        and re.fullmatch(expect, verdict) is not None
    )
    print(
        f"RESULT {'PASS' if ok else 'FAIL'} {pathlib.Path(path).name} agents={types} "
        f"verdict={verdict} expect={expect} main_writes={writes} model_override={any(overrides)} "
        f"background={any(background)} subtype={r.get('subtype')} is_error={r.get('is_error')} "
        f"cost={r.get('total_cost_usd')} client={version} main_model={model}"
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
