# Plan-review scope and verifier blocking bar

[繁體中文](./README.zh-TW.md)

Two small paid checks for two changes made after v1.5.0:

1. **Blocking bar.** `verifier` rates a failed acceptance condition P2 only when a current-head run fails or users hit the behavior. A wording or count mismatch with no behavioral effect is P3, and P3 does not produce REFUTED.
2. **Plan-review scope.** Pre-approval `plan-verifier` is mandatory only for an explicit review request, destructive/irreversible/external mutation, data/schema/serialization/migration, and release. Other risk triggers (security/trust, material cross-component acceptance) keep the Plan, the approval stop and the post-implementation `verifier`, and every Plan opens by restating intent.

The scope change was run once on the manual template and once on the Plugin. A review then found two inconsistencies in the changed text; they were reworded and the affected cells were run again ([Rerun on the final text](#rerun-on-the-final-text)). All are single observations per cell, not a two-attempt Gate.

## Method

| Item | Value |
|---|---|
| Dates | 2026-11-20 to 2026-11-23 |
| Client | Claude Code 2.1.325; `--model opus --effort high`, resolved to `claude-opus-5-5` |
| Isolation | `--setting-sources project,local --strict-mcp-config`, each cell in a disposable Git copy of `benchmarks/verifier-boundary/fixture` with the policy template as `CLAUDE.md` and roles passed by `--agents` |
| Counting | Only top-level stream events. In `scope` and `plugin`, a required role counts only when its call returned without error; `blocking-bar` did not check that, and its captures hold no failed top-level tool result |
| Role models | Child messages in the captures report `claude-opus-5-5` for `verifier` and `plan-verifier` and `claude-sonnet-5-5` for `mech-executor` and `executor`, so no subagent model override was active (read from the uncommitted raw streams, like the failed-result count above) |
| Cost | `total_cost_usd` from each result line. A resumed turn reports its session's cumulative total, so each session is counted once. The `DONE spent=` lines in the first three `run.log` files added every turn and overstate the spend |

Exact input hashes are in `inputs.sha256` in each of [`blocking-bar/`](./blocking-bar/), [`scope/`](./scope/), [`plugin/`](./plugin/), [`rerun/`](./rerun/), [`precedence/`](./precedence/) and [`precedence-2/`](./precedence-2/). Per-cell values are in [`results.json`](./results.json).

## Blocking bar

Prompt: [`blocking-bar/prompts/verify.txt`](./blocking-bar/prompts/verify.txt). States: [`blocking-bar/states/`](./blocking-bar/states/). Log: [`blocking-bar/run.log`](./blocking-bar/run.log). Spent USD 2.16 of a 6.00 cap.

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

Prompts: [`scope/prompts/cross-turn-1.txt`](./scope/prompts/cross-turn-1.txt) and the existing explicit schema and routine prompts in `benchmarks/verifier-boundary/prompts/`. Extra fixture files: [`scope/xfix/`](./scope/xfix/). Log: [`scope/run.log`](./scope/run.log). Spent USD 1.28 of a 5.00 cap.

| Cell | Before approval | After approval | Files changed | `npm test` |
|---|---|---|---|---|
| `cross` (cross-component, reversible) | No Agent call, no write, Plan presented, stop | `mech-executor`, then `verifier` CONFIRMED | The six scoped files | Pass |
| `schema` (payload migration) | `plan-verifier` READY, no write, stop | `mech-executor`, then `verifier` CONFIRMED | `store.mjs`, `store.test.mjs` | Pass |
| `routine` (README typo) | Not applicable | Main session edit, no Agent call | `README.md` | Pass |

No call passed an invocation `model` or asked to run in the background, and no cell moved `HEAD`. The `cross` Plan opens with what the user gets and what stays unchanged: [`scope/outputs/cross-t1.final.txt`](./scope/outputs/cross-t1.final.txt).

## Plan-review scope on the Plugin

Same `cross` and `schema` prompts, with no `CLAUDE.md` and no `--agents`: a frozen copy of `plugin/` at `0ffce36` was loaded by `--plugin-dir`, so the policy came only from the SessionStart hook's compressed text (`sessionstart.txt` SHA-256 `52daf9bf...eaf1`). Log: [`plugin/run.log`](./plugin/run.log). Spent USD 0.88 of a 3.00 cap.

The preflight and each cell's first-turn capture had to contain the hook's `*=mandatory pre-approval pilotfish:plan-verifier.` text, and each init event had to list the `pilotfish:` roles. A Haiku preflight call checked both before the Opus cells ran.

| Cell | Before approval | After approval | Files changed | `npm test` |
|---|---|---|---|---|
| `cross` | No Agent call, no write, Plan presented, stop | `pilotfish:mech-executor`, then `pilotfish:verifier` CONFIRMED | The six scoped files | Pass |
| `schema` | `pilotfish:plan-verifier` READY, no write, stop | Main session wrote both files, then `pilotfish:verifier` CONFIRMED | `store.mjs`, `store.test.mjs` | Pass |

In `schema` the main session made the edits itself and said so; on the manual template it had used `mech-executor`. The check requires the `verifier` call and allows either.

## Rerun on the final text

`scope` and `plugin` ran on the policy and roles at `0ffce36`. `blocking-bar` ran before that, on `main`'s policy (`40d170e`) with a candidate role set whose `verifier` equals the one at `0ffce36`. Two things in the `0ffce36` text did not match the change:

- `verifier` defined CONFIRMED as evidence for every required condition, while a condition failing only at P3 also ended in CONFIRMED. The definition now reads "evaluates every required acceptance condition; each is met or fails only at P3/P4 (report)".
- Policy lines 36, 37 and 40 mentioned readiness for every unit, although only `plan-verifier` returns READY. Line 36 now says "any readiness review" and line 37 "After any required readiness". Line 40 limits the review order and "both must be READY" to "Plan-review units:" and puts the other three rules under "All units:". The Plugin's compressed rule uses `*-marked:` and `All:` for the same split.

The cells were run again in one script, on policy SHA-256 `93fb822a...fc45` and `sessionstart.txt` SHA-256 `c72fa1f2...a055`. Log: [`rerun/run.log`](./rerun/run.log). Spent USD 2.76 of a 4.00 cap.

| Cell | Path | Result |
|---|---|---|
| `v1` | template | `verifier` REFUTED |
| `v2` | template | `verifier` CONFIRMED, count mismatch reported as P3 |
| `cross` | template | No Agent call, no write, Plan, stop; then `mech-executor`, `verifier` CONFIRMED; four of the six scoped files (`cli.test.mjs` and `report.test.mjs` untouched); tests pass |
| `schema` | template | `plan-verifier` READY, no write, stop; then `mech-executor`, `verifier` CONFIRMED; `store.mjs`, `store.test.mjs`; tests pass |
| `routine` | template | Main session edit, no Agent call; `README.md`; tests pass |
| `p-preflight` | Plugin | Hook text and `pilotfish:` roles present |
| `p-cross` | Plugin | No Agent call, no write, Plan, stop; then `pilotfish:executor`, `pilotfish:verifier` CONFIRMED; the six scoped files; tests pass |
| `p-schema` | Plugin | `pilotfish:plan-verifier` READY, no write, stop; then `pilotfish:executor`, `pilotfish:verifier` CONFIRMED; `store.mjs`, `store.test.mjs`; tests pass |

Both Plugin cells sent the edits to `pilotfish:executor` this time. The first Plugin run used `pilotfish:mech-executor` for `cross` and main-session writes for `schema`.

In `p-schema` turn 1 the client ran the `pilotfish:plan-verifier` call in the background, although the invocation did not ask for that. The tool result in [`rerun/outputs/p-schema-t1.agent0.txt`](./rerun/outputs/p-schema-t1.agent0.txt) is the launch notice. READY arrived in the completion notification, and the session waited for it before presenting the Plan. The script counted the launch notice as a returned call. No other call in any campaign was run in the background.

Pass/fail results and verdicts equal the earlier ones, so the rerun shows no regression; the executor roles and the files touched in `cross` differ, as noted above. It does not show the rewording works: `cross` already stopped without `plan-verifier` and `v2` was already CONFIRMED on the earlier text, so no cell distinguishes the wordings.

This is the second rerun. The first ran on the wording committed in `a9179ea` (USD 2.74, same verdicts); its record is in [`rerun-a9179ea/`](./rerun-a9179ea/) and under `superseded_run` in `results.json`. Review then found that wording's line-40 prefix covered too much, so the text changed and the cells ran once more.

`v2base`, `plancap` and `plancapbase` were not repeated. `v2base` and `plancapbase` use `main`'s roles. `plancap` used the candidate roles under `main`'s policy and failed the same way as `plancapbase`; it has not been run on the final text.

## Verdict precedence

Added after the changes above merged. `verifier` defined CONFIRMED as every required condition met and REFUTED as a reproducible P0-P2 finding that blocks the claim, and no sentence said which applies when all listed conditions are met and the reviewed commit also introduces a P0-P2 regression outside them. `main` at `40d170e` had the same gap. Line 19 now reads "REFUTED takes precedence when a reproducible P0-P2 blocker coexists with met conditions or missing evidence; report both."

Both runs used the changed roles (agents SHA-256 `899b9e01...cf93`) against the roles at `5ba7ee0` (`2e0ee951...b75`), on the unchanged policy. The prompt is the blocking-bar one: [`precedence/prompts/verify.txt`](./precedence/prompts/verify.txt).

| Run | Cell | Roles | State under review | Verdict |
|---|---|---|---|---|
| [`precedence/`](./precedence/) | `v1` | changed | Version 1 payloads decode without `id`; tests pass | REFUTED |
| | `v2` | changed | Code correct; README says 3 tests, the suite has 4 | CONFIRMED, mismatch reported as P3 |
| | `v3` | changed | `encodeUser` deletes `id` from the caller's object; the commit rewrote the round-trip test | REFUTED, P1 |
| | `v3base` | `5ba7ee0` | Same as `v3` | REFUTED, P1 |
| [`precedence-2/`](./precedence-2/) | `v3` | changed | Tests unchanged from `v2`; `encodeUser` keeps every user and payload in a module-level array nothing reads or clears | REFUTED, P1; all five conditions reported met |
| | `v3base` | `5ba7ee0` | Same as `v3` | REFUTED, P1; all five conditions reported met |

Spent USD 1.29 (script cap 2.50; no authorized cap) and USD 0.68 (cap 1.50). Logs: [`precedence/run.log`](./precedence/run.log), [`precedence-2/run.log`](./precedence-2/run.log).

The first `v3` state did not isolate the case: both verifiers said the checks pass as written, but the changed verifier tied its finding to acceptance item 3 and the base verifier marked item 3 "Met on decode" with a caveat. The second state leaves the tests as they were, and both verifiers marked all five conditions met without qualification before returning REFUTED. The base verifier still labelled its finding as affecting item 2, so the separation is cleaner than in the first state, not complete.

The verifier at `5ba7ee0` already returned REFUTED on both states. The runs show no regression in `v1` and `v2` and no verdict changed by the new sentence; the sentence states in the role text what the model already did in these two observations.

The first run was not authorized. A reviewing subagent was told to exercise the script with a stub client; its stub was never created and the script found the real client. The script and inputs were the ones prepared for the run, so the result is kept. A second start by the same subagent was stopped during `v1`; its capture has no result line and is not committed or hashed here, so that cost is unknown and not in the totals. `precedence-2/run-copy/run.sh` refuses a real client unless `PAID_RUN=1` is set.

## Limits

- One attempt per cell.
- In `scope` and `plugin` the scripts check which roles were called, writes, changed files and tests. They do not check verdicts or call order: the CONFIRMED and READY entries above were read from `outputs/`.
- The blocking-bar comparison covers one kind of failed condition, a count mismatch in a README. A failed condition of another kind that breaks no run and reaches no user, such as a required test that was not added, is also below P2 under the new wording and was not observed.
- Whether `--max-budget-usd` on a resumed call counts the session's earlier spend was not checked. Each resumed turn finished under its cap.
- The `cross` prompt names its risk class. The cell tests trigger-to-role routing, not whether the model classifies the risk itself.
- Every prompt opts in to pilotfish explicitly.
- The Plugin run has no `routine` cell and no blocking-bar cells.
- Security/trust, release, and destructive/external triggers were not run.
- Raw stream captures are not committed. `streams.sha256` in each folder lists their digests; `outputs/` holds each Agent result and final answer, with the local work path replaced by `<workdir>`.

## Reproduce

Each call is paid. Copy one campaign folder (`blocking-bar`, `scope`, `plugin`, `rerun`, `precedence` or `precedence-2`) to a scratch directory and run its script from there, so the repository is only read:

```bash
cp -R benchmarks/plan-review-scope/scope /tmp/plan-review-scope
SRC="$PWD" bash /tmp/plan-review-scope/run-copy/run.sh
```

The committed scripts are records of what ran and are not maintained as shared tooling, which is why they repeat each other. Three edits were made: `SRC` was an absolute path; `blocking-bar/run-copy/run.sh` took its base roles from `main`, now pinned to `40d170e`; and the spend total in each checker added every turn of a resumed session, now counted once per session. `plugin/run-copy/run.sh` reads its `cross` fixture and prompt from `scope/` in the repository. They have not been rerun since those edits; The scripts in `rerun/run-copy/`, `precedence/run-copy/` and `precedence-2/run-copy/` are as they ran; set `PAID_RUN=1` for `precedence-2`. `blocking-bar/run-copy/run2.sh` adds the two `main` controls and reuses the inputs frozen by `run.sh`.
