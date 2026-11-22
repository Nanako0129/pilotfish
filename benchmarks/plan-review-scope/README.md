# Plan-review scope and verifier blocking bar

[繁體中文](./README.zh-TW.md)

Two small paid checks for two changes made after v1.5.0:

1. **Blocking bar.** `verifier` rates a failed acceptance condition P2 only when a current-head run fails or users hit the behavior. A wording or count mismatch with no behavioral effect is P3, and P3 does not produce REFUTED.
2. **Plan-review scope.** Pre-approval `plan-verifier` is mandatory only for an explicit review request, destructive/irreversible/external mutation, data/schema/serialization/migration, and release. Other risk triggers (security/trust, material cross-component acceptance) keep the Plan, the approval stop and the post-implementation `verifier`, and every Plan opens by restating intent.

The scope change was run once on the manual template and once on the Plugin. A review then found two inconsistencies in the changed text; they were reworded and the affected cells were run again ([Rerun on the final text](#rerun-on-the-final-text)). All are single observations per cell, not a two-attempt Gate.

## Method

| Item | Value |
|---|---|
| Dates | 2026-11-20 to 2026-11-22 |
| Client | Claude Code 2.1.325; `--model opus --effort high`, resolved to `claude-opus-5-5` |
| Isolation | `--setting-sources project,local --strict-mcp-config`, each cell in a disposable Git copy of `benchmarks/verifier-boundary/fixture` with the policy template as `CLAUDE.md` and roles passed by `--agents` |
| Counting | Only top-level stream events. In `scope` and `plugin`, a required role counts only when its call returned without error; `blocking-bar` did not check that, and its captures hold no failed top-level tool result |
| Role models | Child messages in the captures report `claude-opus-5-5` for `verifier` and `plan-verifier` and `claude-sonnet-5-5` for `mech-executor`, so no subagent model override was active (read from the uncommitted raw streams, like the failed-result count above) |
| Cost | `total_cost_usd` from each result line. A resumed turn reports its session's cumulative total, so each session is counted once. The `DONE spent=` lines in the first three `run.log` files added every turn and overstate the spend |

Exact input hashes are in `inputs.sha256` in each of [`blocking-bar/`](./blocking-bar/), [`scope/`](./scope/), [`plugin/`](./plugin/) and [`rerun/`](./rerun/). Per-cell values are in [`results.json`](./results.json).

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

No call passed an invocation `model` or ran in the background, and no cell moved `HEAD`. The `cross` Plan opens with what the user gets and what stays unchanged: [`scope/outputs/cross-t1.final.txt`](./scope/outputs/cross-t1.final.txt).

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

- `verifier` defined CONFIRMED as evidence for every required condition, while a condition failing only at P3 also ended in CONFIRMED. The definition now reads "sufficient for every required acceptance condition, or its only shortfall rates P3/P4 (report)".
- Policy lines 36, 37 and 40 mentioned readiness for every unit, although only `plan-verifier` returns READY. Line 40 now opens with "Plan-review units:", line 37 says "After any required readiness", line 36 says "any readiness review". The Plugin's compressed rule opens with `*:`.

The cells were run again in one script, on policy SHA-256 `bd907c31...2ec5` and `sessionstart.txt` SHA-256 `62751a24...70fa`. Log: [`rerun/run.log`](./rerun/run.log). Spent USD 2.74 of a 4.00 cap.

| Cell | Path | Result |
|---|---|---|
| `v1` | template | `verifier` REFUTED |
| `v2` | template | `verifier` CONFIRMED, count mismatch reported as P3 |
| `cross` | template | No Agent call, no write, Plan, stop; then `mech-executor`, `verifier` CONFIRMED; the six scoped files; tests pass |
| `schema` | template | `plan-verifier` READY, no write, stop; then `mech-executor`, `verifier` CONFIRMED; `store.mjs`, `store.test.mjs`; tests pass |
| `routine` | template | Main session edit, no Agent call; `README.md`; tests pass |
| `p-preflight` | Plugin | Hook text and `pilotfish:` roles present |
| `p-cross` | Plugin | Same as `cross`, with `pilotfish:` roles |
| `p-schema` | Plugin | Same as `schema`, with `pilotfish:` roles |

In `p-schema` the edits went to `pilotfish:mech-executor` this time; in the earlier Plugin run the main session wrote them. The outcomes equal the earlier ones, so the rerun shows no regression. It does not show the rewording works: `cross` already stopped without `plan-verifier` and `v2` was already CONFIRMED on the earlier text, so no cell distinguishes the two wordings.

`v2base`, `plancap` and `plancapbase` were not repeated. `v2base` and `plancapbase` use `main`'s roles. `plancap` used the candidate roles under `main`'s policy and failed the same way as `plancapbase`; it has not been run on the final text.

`REPO-STATUS-BEFORE` and `-AFTER` differ in this log because the `rerun/` folder was added to the working tree while the script ran. No cell wrote there.

## Limits

- One attempt per cell.
- In `scope` and `plugin` the scripts check which roles were called, writes, changed files and tests. They do not check verdicts or call order: the CONFIRMED and READY entries above were read from `outputs/`.
- The blocking-bar comparison covers one kind of failed condition, a count mismatch in a README. A failed condition of another kind that breaks no run and reaches no user, such as a required test that was not added, is also below P2 under the new wording and was not observed.
- Three weaknesses in the final wording were found after the rerun and are not fixed, because a fix changes the text the rerun is bound to:
  - In the `verifier` CONFIRMED definition, "its only shortfall" can be read as missing evidence rated P3, not only as an evaluated condition that failed at P3. The role's INCONCLUSIVE rule for unevaluated conditions says otherwise two lines later.
  - Policy line 40 puts "Plan-review units:" before the whole rule, so the sentences about shared blockers and cosmetic splits also read as limited to those units.
  - The Plugin's compressed rule opens with `*:`, while `*` is defined 23 lines earlier as a suffix marker on triggers.
- Whether `--max-budget-usd` on a resumed call counts the session's earlier spend was not checked. Each resumed turn finished under its cap.
- The `cross` prompt names its risk class. The cell tests trigger-to-role routing, not whether the model classifies the risk itself.
- Every prompt opts in to pilotfish explicitly.
- The Plugin run has no `routine` cell and no blocking-bar cells.
- Security/trust, release, and destructive/external triggers were not run.
- Raw stream captures are not committed. `streams.sha256` in each folder lists their digests; `outputs/` holds each Agent result and final answer, with the local work path replaced by `<workdir>`.

## Reproduce

Each call is paid. Copy one campaign folder (`blocking-bar`, `scope`, `plugin` or `rerun`) to a scratch directory and run its script from there, so the repository is only read:

```bash
cp -R benchmarks/plan-review-scope/scope /tmp/plan-review-scope
SRC="$PWD" bash /tmp/plan-review-scope/run-copy/run.sh
```

The committed scripts are records of what ran and are not maintained as shared tooling, which is why they repeat each other. Three edits were made: `SRC` was an absolute path; `blocking-bar/run-copy/run.sh` took its base roles from `main`, now pinned to `40d170e`; and the spend total in each checker added every turn of a resumed session, now counted once per session. `plugin/run-copy/run.sh` reads its `cross` fixture and prompt from `scope/` in the repository. They have not been rerun since those edits; `rerun/run-copy/run.sh` is as it ran. `blocking-bar/run-copy/run2.sh` adds the two `main` controls and reuses the inputs frozen by `run.sh`.
