# pilotfish + Baton compatibility gate

## Contents

- [Purpose](#purpose)
- [Composition contract](#composition-contract)
- [Isolation and reproduction](#isolation-and-reproduction)
- [Exact prompts](#exact-prompts)
- [Final gate result](#final-gate-result)
- [Superseded and rejected harness runs](#superseded-and-rejected-harness-runs)
- [Limits and disclosure](#limits-and-disclosure)

## Purpose

This experiment tests whether [Baton](https://github.com/cablate/baton) and the phase-aware pilotfish v1.2.0 release candidate can complete a real plan-first lifecycle under native Claude routing. Baton owns the smallest useful delegation topology; pilotfish remains authoritative for named roles, role models, leaf-agent boundaries, approval, tool capabilities, and verifier vocabulary. The exact tested snapshot carries the earlier v1.1.6 candidate stamp; the change was reclassified as v1.2.0 before release, and the only policy-byte delta is that inert version comment.

> **Gate:** Discovery may happen before the implementation outcome is known, but writes wait for a main-session Plan and explicit approval. Plan review returns `READY` / `REVISE`; outcome review returns `CONFIRMED` / `REFUTED`.

The fixture is the [two-surface research control](../dispatch-brake/positive-controls/research/fixture) first published in pilotfish commit `5f027b8c`. The run used Claude Code 2.1.207, native first-party Claude authentication, the PR #10 candidate policy, and the installed Baton skill whose `SKILL.md` SHA-256 is recorded in [`results.json`](./results.json).

## Composition contract

```mermaid
flowchart TD
    REQUEST["User request"] --> DISCOVERY["Baton chooses Discovery topology"]
    DISCOVERY --> PLAN["Main session synthesizes Plan"]
    PLAN --> READINESS["Read-only plan-verifier: READY or REVISE"]
    READINESS --> APPROVAL["Explicit user approval"]
    APPROVAL --> EXECUTION["Approved execution contract"]
    EXECUTION --> OUTCOME["Fresh verifier: CONFIRMED or REFUTED"]
    OUTCOME --> FINAL["Main session final judgment"]
    PILOTFISH["pilotfish roles, models, leaf and safety gates"] --> DISCOVERY
    PILOTFISH --> READINESS
    PILOTFISH --> EXECUTION
    PILOTFISH --> OUTCOME
```

| Layer | Owns | Must not override |
|---|---|---|
| Baton | Questions, topology, worker count, ownership, sequence, budgets, stop conditions | Named-role models, approval, verifier capability, leaf boundary |
| pilotfish | Named roles, role models, tool allowlists, phase gates, approval contract, verifier vocabulary | Baton's topology judgment inside those gates |
| Main session | Evidence reconciliation, Plan synthesis, integration, final judgment | Required approval or independent verification |

## Isolation and reproduction

The test ran in a disposable Git repository. The exact final policy and eight-role session JSON are committed under [`final-gate-snapshot/`](./final-gate-snapshot/); [`build-agents-json.py`](./build-agents-json.py) converts the candidate role files to the injected `--agents` payload. This avoids overwriting the installed global pilotfish files and makes the tested working-tree snapshot auditable. User memory still stacks underneath the more-specific project candidate and is disclosed as a limit; session-scoped role definitions replace user role definitions for this run.

> ⚠️ **Safety boundary:** `--dangerously-skip-permissions` was used only in the disposable fixture. Do not reuse it in an untrusted or valuable checkout.

```bash
SOURCE=/path/to/pilotfish-pr10
ROOT="$(mktemp -d /tmp/pilotfish-baton-gate.XXXXXX)"
WORK="$ROOT/fixture"
SNAPSHOT="$SOURCE/benchmarks/baton-compatibility/final-gate-snapshot"

mkdir -p "$WORK"
cp -R "$SOURCE/benchmarks/dispatch-brake/positive-controls/research/fixture/." "$WORK/"
cp "$SNAPSHOT/CLAUDE.md" "$ROOT/CLAUDE.md"
git init -q "$WORK"
git -C "$WORK" add .
git -C "$WORK" -c user.name=pilotfish-gate \
  -c user.email=pilotfish-gate@example.invalid commit -qm baseline

AGENTS_JSON="$(cat "$SNAPSHOT/agents.json")"
SESSION_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
cd "$WORK"
```

The user setting source is intentional: Baton was installed under the user skill directory. Excluding `user` makes the Skill tool report `Unknown skill`. The project-level candidate policy is more specific than user memory, and session-scoped `--agents` definitions take precedence over user agent files.

```bash
claude --dangerously-skip-permissions \
  -p --output-format json --max-budget-usd 3 \
  --session-id "$SESSION_ID" --model best --effort high \
  --setting-sources user,project,local --strict-mcp-config \
  --agents "$AGENTS_JSON" \
  "$(cat "$SOURCE/benchmarks/baton-compatibility/prompts/turn-1.txt")"

claude --dangerously-skip-permissions \
  -p --output-format json --max-budget-usd 3 \
  --resume "$SESSION_ID" --model best --effort high \
  --setting-sources user,project,local --strict-mcp-config \
  --agents "$AGENTS_JSON" \
  "$(cat "$SOURCE/benchmarks/baton-compatibility/prompts/turn-2.txt")"
```

This gate exercises runtime policy composition and the exact final role definitions. [`final-gate-snapshot/CLAUDE.md`](./final-gate-snapshot/CLAUDE.md) hashes as stored; `agents.json` is read through shell command substitution, which strips its repository trailing newline before hashing and injection. The role definitions match the current templates exactly. The release policy matches the tested policy after normalizing its inert v1.1.6 → v1.2.0 version-stamp comment; [`results.json`](./results.json) records both raw policy hashes, and tests lock that sole delta. The Gate does not separately test global file discovery or the installer; those remain covered by the installer review path and policy contract tests.

## Exact prompts

| Turn | Prompt | Required stop |
|---|---|---|
| Discovery + Plan | [`prompts/turn-1.txt`](./prompts/turn-1.txt) | Baton loaded, no writes, read-only `plan-verifier` uses only `READY` / `REVISE`, then wait for approval |
| Approval + execution | [`prompts/turn-2.txt`](./prompts/turn-2.txt) | Only `REPORT.md`, tests pass, fresh outcome verifier returns `CONFIRMED` |

## Final gate result

| Turn | Wall time | Client-reported cost | API turns | Models | Result |
|---|---:|---:|---:|---|---|
| Discovery + Plan | 221.661 s | $1.763515 | 18 | Fable 5 + Opus 4.8 | Baton loaded; direct discovery; Git clean; read-only `plan-verifier` returned `READY` |
| Approved execution + verification | 226.487 s | $2.025533 | 4 | Fable 5 + Sonnet 5 + Opus 4.8 | `mech-executor` wrote only `REPORT.md`; `npm test` passed; outcome `verifier` returned `CONFIRMED` |
| Total | 448.148 s | $3.789048 | 22 | Fable 5 + Sonnet 5 + Opus 4.8 | Complete lifecycle passed without resend |

Baton chose direct main-session discovery, then delegated the stable one-file execution contract to `mech-executor`. That is the intended phase distinction: speculative discovery stayed direct, while approved mechanical writing took the cheap-worker route. The main session retained Plan synthesis, integration, tests, and final judgment.

| Agent call | Scheduling | Invocation `model` | Observed model | Verdict |
|---|---|---|---|---|
| `plan-verifier`: Plan readiness | Foreground | Omitted | `claude-opus-4-8` | `READY`; observed tools only `Glob` / `Read` |
| `mech-executor`: approved writing | Foreground | Omitted | `claude-sonnet-5` | `REPORT.md` only |
| `verifier`: outcome verification | Foreground | Omitted | `claude-opus-4-8` | `CONFIRMED` |

| Acceptance check | Result |
|---|---|
| Baton availability | Skill tool returned `Launching skill: baton-dispatch` |
| Writes before approval | None; Turn 1 ended with a clean Git tree |
| Plan ownership | Main session |
| Write scope | `REPORT.md` only; 36 lines, 7,071 bytes |
| Citation verification | 34 surface citations checked by the outcome verifier |
| Repository test | `REPORT.md covers both independent surfaces with file:line evidence` |
| Verifier vocabulary | Plan `READY`; outcome `CONFIRMED`; no cross-mode labels |
| Named-role routing | All three Agent calls omitted invocation-level `model`; Plan/outcome verification used Opus 4.8 and execution used Sonnet 5 |
| Startup resend | Not required; both turns created and grew their transcripts normally |

Machine-readable data is in [`results.json`](./results.json). The final raw transcript SHA-256 is `022871ac102442caeb6f902449442d8ccea5248617efafb4bb59dbce237c2569`.

The writer's `Write` tool was blocked twice by an environment protection against subagent report writes; within the explicitly approved one-file scope it fell back to a Bash heredoc. The final file still passed main-session tests and fresh verification. This is disclosed because it affected the trace even though it did not widen scope.

The Gate did not trigger a long-running process or invoke `security-reviewer`. Long-process behavior retains [@dromsak's four direct harness trials](https://github.com/Nanako0129/pilotfish/pull/10#issuecomment-4958570683) plus four-role contract tests; the security-reviewer boundary is verified by its positive tool allowlist and policy tests. No extra edge-case Claude run is presented as evidence.

## Superseded and rejected harness runs

An earlier complete Gate used one dual-mode `verifier` for both Plan and outcome review. It passed at the time (494.933 s, $3.906375, 12 turns), but Codex review found that its Plan and pre-approval security boundaries were prompt-only. It is now superseded by the capability-separated run above; its exact inputs remain in [`gate-snapshot/`](./gate-snapshot/) and its transcript hash remains in [`results.json`](./results.json).

The first isolation attempt was not counted as compatibility evidence. It used `--setting-sources project,local`, which hid the user-installed Baton skill. The remaining pilotfish gates still reached a clean `READY`, but the run did not test the requested composition and no approval turn was started.

| Evidence | Value |
|---|---:|
| Wall time | 213.558 s |
| Client-reported cost | $1.627875 |
| API turns | 17 |
| Git state | Clean |
| Disposition | Rejected before Turn 2 |
| Raw transcript SHA-256 | `64376ea52a4e67192df29d8595c180ddc5017638029759a8ac13aff87d5cca81` |

This rejection is published because a behavioral pass is not enough when the dependency under test never loaded.

## Limits and disclosure

> **Do not generalize one passing run into a universal performance claim.** The gate establishes one valid lifecycle and routing trace, not an expected topology, latency, or cost.

| Limit | Consequence |
|---|---|
| Single final run | Timing and cost are observations, not population estimates |
| Client-reported cost field | It is not a provider invoice |
| Small fixture | Baton chose direct discovery and one mechanical writer; larger tasks may choose bounded fan-out or direct writing |
| Dynamic role injection | Exact final snapshot definitions were tested, but global agent-file discovery was outside this runtime Gate |
| Unexercised security / long-process paths | Tool allowlists, policy tests, and dedicated contributor trials cover their contracts; this fixture does not claim runtime coverage |
| Candidate project memory stacked over user memory | The more specific candidate policy governed the fixture; managed policy or contradictory project instructions can still change behavior |
| Locally patched Claude binary | The provider route was native first-party Claude, but other Claude Code versions need their own smoke test |
| Raw transcript not committed | It contains absolute local paths and session metadata; prompts, normalized calls, content hashes, metrics, and verdicts are published instead |
