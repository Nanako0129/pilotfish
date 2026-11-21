# Plan-review scope and verifier blocking bar

[繁體中文](./README.zh-TW.md)

Two small paid checks for two changes made after v1.5.0:

1. **Blocking bar.** `verifier` rates a failed acceptance condition P2 only when a current-head run fails or users hit the behavior. A wording or count mismatch with no behavioral effect is P3, and P3 does not produce REFUTED.
2. **Plan-review scope.** Pre-approval `plan-verifier` is mandatory only for an explicit review request, destructive/irreversible/external mutation, data/schema/serialization/migration, and release. Other risk triggers (security/trust, material cross-component acceptance) keep the Plan, the approval stop and the post-implementation `verifier`, and every Plan opens by restating intent.

Both are single observations per cell, not a two-attempt Gate.

## Method

| Item | Value |
|---|---|
| Dates | 2026-11-20 and 2026-11-21 |
| Client | Claude Code 2.1.325; `--model opus --effort high`, resolved to `claude-opus-5-5` |
| Isolation | `--setting-sources project,local --strict-mcp-config`, each cell in a disposable Git copy of `benchmarks/verifier-boundary/fixture` with the policy template as `CLAUDE.md` and roles passed by `--agents` |
| Counting | Only top-level stream events. A required role counts only when its call returned without error |
| Cost | `total_cost_usd` from each result line |

Exact input hashes are in [`blocking-bar/inputs.sha256`](./blocking-bar/inputs.sha256) and [`scope/inputs.sha256`](./scope/inputs.sha256). Per-cell values are in [`results.json`](./results.json).

## Blocking bar

Prompt: [`blocking-bar/prompts/verify.txt`](./blocking-bar/prompts/verify.txt). States: [`blocking-bar/states/`](./blocking-bar/states/). Log: [`blocking-bar/run.log`](./blocking-bar/run.log). Spent USD 3.63 of a 6.00 cap.

| Cell | Roles | State under review | Verdict |
|---|---|---|---|
| `v1` | changed `verifier` | Version 1 payloads decode without `id`; tests pass | REFUTED |
| `v2` | changed `verifier` | Code correct; README says 3 tests, the suite has 4 | CONFIRMED, mismatch reported as P3 |
| `v2base` | `main` at `40d170e` | Same as `v2` | REFUTED |
| `plancap` | changed roles | Existing three-turn Plan-cap prompts | REVISE, REVISE, REVISE |
| `plancapbase` | `main` at `40d170e` | Same | REVISE, REVISE, REVISE |

`v2` against `v2base` is the one old-versus-new observation behind the blocking-bar change. `v1` shows a behavioral defect still blocks.

The Plan-cap prompts expect READY on turn 3. Both role sets returned REVISE there, so that expectation does not hold on `claude-opus-5-5` with or without this change. The `plan-verifier` wording tried in the changed set showed no difference from `main` and was dropped; the committed `plan-verifier` equals `main`.

## Plan-review scope

Prompts: [`scope/prompts/cross-turn-1.txt`](./scope/prompts/cross-turn-1.txt) and the existing explicit schema and routine prompts in `benchmarks/verifier-boundary/prompts/`. Extra fixture files: [`scope/xfix/`](./scope/xfix/). Log: [`scope/run.log`](./scope/run.log). Spent USD 1.74 of a 5.00 cap.

| Cell | Before approval | After approval | Files changed | `npm test` |
|---|---|---|---|---|
| `cross` (cross-component, reversible) | No Agent call, no write, Plan presented, stop | `mech-executor`, then `verifier` CONFIRMED | The six scoped files | Pass |
| `schema` (payload migration) | `plan-verifier` READY, no write, stop | `mech-executor`, then `verifier` CONFIRMED | `store.mjs`, `store.test.mjs` | Pass |
| `routine` (README typo) | Not applicable | Main session edit, no Agent call | `README.md` | Pass |

No call passed an invocation `model` or ran in the background, and no cell moved `HEAD`. The `cross` Plan opens with what the user gets and what stays unchanged: [`scope/outputs/cross-t1.final.txt`](./scope/outputs/cross-t1.final.txt).

## Limits

- One attempt per cell.
- The `cross` prompt names its risk class. The cell tests trigger-to-role routing, not whether the model classifies the risk itself.
- Every prompt opts in to pilotfish explicitly.
- The policy ran as the manual template in `CLAUDE.md`. The Plugin's compressed SessionStart text was not run.
- Security/trust, release, and destructive/external triggers were not run.
- Raw stream captures are not committed. `streams.sha256` in each folder lists their digests; `outputs/` holds each Agent result and final answer, with the local work path replaced by `<workdir>`.

## Reproduce

Each call is paid. Copy one campaign folder to a scratch directory and run its script from there, so the repository is only read:

```bash
cp -R benchmarks/plan-review-scope/scope /tmp/plan-review-scope
SRC="$PWD" bash /tmp/plan-review-scope/run-copy/run.sh
```

The committed scripts are the ones that ran, with one edit: `SRC` was an absolute path. They have not been rerun since that edit. `blocking-bar/run-copy/run2.sh` adds the two `main` controls and reuses the inputs frozen by `run.sh`.
