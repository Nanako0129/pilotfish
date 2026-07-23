# Prompt-neutral Baton activation and dispatch matrix

This behavioral matrix asks two separate questions: is Baton invoked when merely available on a bounded task, and do Baton invocation plus a complete delegated topology appear under the current pilotfish policy when a substantial cross-surface user prompt never names Baton or agents?

> **Result:** the bounded availability observation remained inline, but the substantial v1.3.1 Gate passed. An exact post-PR-19 release-payload replay passed the same activation, four-scout dispatch, ownership, collection, and final-byte correctness boundaries with agents SHA `0b42c137…9723c`.

## What was tested

| Cell | Prompt and fixture | Policy | Result |
|---|---|---|---|
| Small control | Two-surface research task; Baton absent | Earlier v1.3.1 candidate | 0 `Skill`, 0 `Agent`, correctness pass |
| Small treatment | Same task; project-scoped Baton 0.1.1 visible | Same earlier candidate | 0 `Skill`, 0 `Agent`, correctness pass |
| Large Gate | Four substantial domains; project-scoped Baton 0.1.1 visible | v1.3.1 release policy, SHA `17d272b6…b39bf` | 1 Baton `Skill`, 4 completed background `scout` calls, ownership/collection/correctness pass |
| Release-payload replay | Same substantial prompt and pinned fixture | Policy SHA `17d272b6…b39bf`; post-PR-19 agents SHA `0b42c137…9723c` | Same 1 Skill / 4 completed scouts topology; in-session and independent final-byte tests pass |

Both prompt files pass a case-insensitive scan for Baton, agent, subagent, worker, role, skill, delegation, orchestration, parallelism, and fan-out vocabulary. This is a prompt property only. Both fixtures contain orchestration material; the small ordered pair is therefore retained as an availability observation, and the substantial Gate establishes prompt-neutral policy reachability rather than a fully cue-free causal experiment. The separate [`spontaneous-dispatch`](../spontaneous-dispatch/README.md) matrix scans both its user prompts and task fixtures for cue-free topology claims.

## Large Gate contract

| Input | Pinned value |
|---|---|
| Client | Claude Code 2.1.218 for final `large-v131-4`; attempts 1–3 used 2.1.217 |
| Requested / observed main model | `opus` / `claude-opus-4-8` |
| Settings | `project,local`; strict MCP; no session persistence |
| Baton | 0.1.1, commit `77f12e6`, `SKILL.md` SHA `48b1e573…3d67` |
| Historical attempt role payload | Eight pilotfish roles, SHA `e901e16a…c61` |
| Release-replay role payload | Eight pilotfish roles, SHA `0b42c137…9723c`; `executor` changed from Opus to Sonnet after #18 |
| Policy | v1.3.1 release policy, SHA `17d272b6…b39bf` |
| Prompt | [`prompts/large-audit.txt`](./prompts/large-audit.txt), SHA `c0cebdce…ffba` |
| Fixture baseline | Commit `34ebabe2…245f`, tree `3773149b…2574`; 45 domain files / 3,032 lines |
| Budget | $5 maximum per attempt |

The disposable fixture mapped four repository surfaces into `domain-a` through `domain-d`, copied the current policy to `CLAUDE.md`, installed the pinned Baton dependency as a project skill, and added the shape-only [`verify-audit.mjs`](./large-fixture/verify-audit.mjs) harness.

## Attempt matrix

| Attempt | Baton / agents | Ownership and collection | Outcome |
|---|---:|---|---|
| `large-v131-1` | 1 / 2 completed | Failed: main duplicated active domain-c/domain-d reconnaissance | `AUDIT.md` and test passed, but Gate failed |
| `large-v131-2` | 1 / 2 completed | Failed: one mixed-scope Bash read active `domain-c/VERSION` | `AUDIT.md` and test passed, but Gate failed |
| `large-v131-3` | 1 / 4 launched, 2 completed | No overlap observed | Two scouts hit the session limit; no report; Gate failed |
| `large-v131-4` | 1 / 4 completed | Passed: all results arrived before cross-domain work | `AUDIT.md` only; `npm test` passed; Gate passed |

The failed runs remain first-class evidence in [`results.json`](./results.json). They drove two concrete policy changes: an active agent-owned read scope is temporarily exclusive, including every path inside a mixed Bash command; and a selected multi-agent batch must be launched back-to-back before the main session continues disjoint work.

## Final trace

```text
Bash → Read → Bash → Skill(baton-dispatch)
  → Agent(domain-a, background)
  → Agent(domain-b, background)
  → Agent(domain-c, background)
  → Agent(domain-d, background)
  → collect all four results
  → post-collection spot-check → Write → npm test → Edit
```

| Gate dimension | Evidence | Status |
|---|---|---|
| Activation | Baton listed at init and invoked before dispatch | Pass |
| Topology | Four `scout` calls; all background; invocation-level `model` omitted | Pass |
| Ownership | No main content read or analysis touched an agent-owned domain while active | Pass |
| Collection | Completion events 199, 236, 252, and 258 precede spot-check event 280 | Pass |
| Correctness boundary | The in-session test at event 313 preceded a final edit at event 320; an independent post-run `npm test` rerun against final SHA `1a23459c…4969` passed with only `AUDIT.md` changed | Pass |

The final run took 400.00 seconds wall time and reported $1.8456953 in the client cost field. Parallel agent API time was 655.635 seconds and can exceed wall time. A fresh verifier rejected the original completed claim; follow-up inspection found that the in-session test ran before the final edit. The final bytes were therefore retested independently, that rerun passed, and its evidence was recorded at `2026-07-23T02:01:06Z`. Raw streams are not committed because initialization events include local paths and session metadata; [`results.json`](./results.json) binds every stream and report by SHA-256, while [`traces.json`](./traces.json) and [`agent-calls.json`](./agent-calls.json) publish normalized evidence.

## Exact release-payload replay

The replay used Claude Code 2.1.218, the same committed fixture baseline and prompt-neutral user request, exact current policy SHA `17d272b6…b39bf`, and generated agents SHA `0b42c137…9723c`. Baton appeared in the init inventory and was invoked before four background `scout` calls launched back-to-back without invocation-level model overrides. Completion events 278, 320, 348, and 360 all preceded the first cross-domain sanity check at event 394.

Only `AUDIT.md` was added. The single write at event 402 preceded the in-session `npm test` at event 405, and an independent rerun passed against identical final SHA `92a111dd…17a`. The replay completed in 168.156 seconds of client duration, reported $1.6609134 in the client cost field, and is stored additively under `release_payload_replay`; it does not rewrite the historical attempts.

## Claim boundary

| Established | Not established |
|---|---|
| The substantial prompt-neutral request activated Baton in the final Gate and again with the exact release payload | A fully cue-free environment, or activation frequency and reliability across a representative sample |
| Baton invocation was followed by four completed named-role calls | A causal comparison against a no-Baton large control |
| The final run respected exclusive discovery ownership and collected every result | Lower latency, lower cost, or better efficiency |
| The generated artifact passed the repository-owned shape test | Semantic correctness of every audit claim |
| The final Gate passed on Claude Code 2.1.218 | That policy changes alone explain differences from attempts 1–3, which used 2.1.217 |

The earlier [`baton-compatibility`](../baton-compatibility/README.md) Gate remains the approval-lifecycle record for its exact historical policy bytes. This matrix tests the newer policy bytes at the activation, dispatch, ownership, collection, and output-shape boundary.

> ⚠️ Permission bypass was used only inside fresh disposable fixtures.
