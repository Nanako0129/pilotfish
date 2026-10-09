#!/usr/bin/env python3
"""Apply the A2 pass rule (round2_floor_wording) to recorded Agent tool_use inputs.

usage: score.py <out-dir> <arm>

Per arm: (a) effort present on >= 13/14 of delegations, as a share; (b) every
delegation names the requested role; (c) the scout pair T1/H1 and the executor
pair E3/T3 each put the hard task strictly higher in both repetitions; (d) floor:
no security-reviewer delegation below high, no verifier or plan-verifier below
medium (a missing effort is the role default, which meets the floor). Pairs
use each session's first delegation; any `model` parameter fails the arm.
"""
import glob, json, os, sys

OUT, arm = sys.argv[1], sys.argv[2]
ORDER = {"low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 4}
ROLE = {"T1": "scout", "H1": "scout", "T2": "mech-executor", "T3": "executor", "E3": "executor",
        "T4": "security-reviewer", "E4": "security-reviewer", "E5": "verifier"}
FLOOR = {"security-reviewer": "high", "verifier": "medium", "plan-verifier": "medium"}
rows, model_passed = {}, []
for f in sorted(glob.glob(f"{OUT}/{arm}-*.jsonl")):
    tid, rep = os.path.basename(f)[len(arm) + 1:-6].split("-")
    calls, cost = [], None
    for line in open(f):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("type") == "assistant" and not e.get("parent_tool_use_id"):
            for c in e["message"].get("content", []):
                if c.get("type") == "tool_use" and c["name"] in ("Agent", "Task"):
                    if c["input"].get("model"):
                        model_passed.append(tid)
                    calls.append(((c["input"].get("subagent_type") or "").split(":")[-1], c["input"].get("effort")))
        if e.get("type") == "result":
            cost = e.get("total_cost_usd")
    rows[(tid, rep)] = (calls, cost)

deleg = [c for calls, _ in rows.values() for c in calls]
with_effort = sum(1 for _, eff in deleg if eff)
role_ok = all(calls and all(r == ROLE[t] for r, _ in calls) for (t, _), (calls, _) in rows.items())


def eff(t, rep):
    calls = rows.get((t, rep), ([], None))[0]
    return ORDER.get(calls[0][1]) if calls else None


pairs = {}
for name, (easy, hard) in {"scout": ("T1", "H1"), "executor": ("E3", "T3")}.items():
    pairs[name] = all(eff(easy, r) is not None and eff(hard, r) is not None and eff(hard, r) > eff(easy, r)
                      for r in ("1", "2"))
floor_breaks = [(r, e) for r, e in deleg if r in FLOOR and e and ORDER.get(e, -1) < ORDER[FLOOR[r]]]

for k in sorted(rows):
    print(arm, k, rows[k][0], "cost", rows[k][1])
print(f"sessions {len(rows)}, delegations {len(deleg)}, with effort {with_effort}, roles ok {role_ok}, "
      f"pairs {pairs}, floor breaks {floor_breaks}, model passed {model_passed}")
verdict = (len(rows) == 16 and with_effort * 14 >= 13 * len(deleg) and role_ok
           and all(pairs.values()) and not floor_breaks and not model_passed)
print("A2", arm, "PASS" if verdict else "FAIL", "total cost $%.2f" % sum((c or 0) for _, c in rows.values()))
