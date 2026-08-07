# Spontaneous-dispatch behavior gate

This gate asks whether Pilotfish chooses the intended execution topology from an ordinary task request. In the two cells below and in the cue-free arm of the [v1.3.7 paired opt-in matrix](#v137-paired-opt-in-matrix), the prompts contain no instruction to delegate, avoid delegation, or consult an orchestration policy. The one exception is that matrix's explicitly directed arm, whose prompts state the instruction on purpose — it is the intervention being compared against, and its observations are not evidence of spontaneous dispatch.

| Cell | Expected topology | Behavioral acceptance |
|---|---|---|
| Stable 12-file mechanical edit | Exactly one foreground `mech-executor` | The stream contains one matching completed Agent result; exactly 12 adapter files change; 12/12 tests pass |
| One unknown tightly coupled bug | Main session owns diagnosis and the first minimal fix | No discovery or implementation agent runs before the main session changes the fix and observes the focused 2/2 pass; a closing `verifier` remains allowed |

The exact prompts are in [`prompts/`](./prompts/). Recorded outcomes, normalized tool traces, and observable Agent calls are in [`results.json`](./results.json), [`traces.json`](./traces.json), and [`agent-calls.json`](./agent-calls.json). The corrected issue #29 retrospective is in [`issue-29-topology.json`](./issue-29-topology.json), produced with [`classify_stream.py`](./classify_stream.py). Raw streams are not committed because initialization events contain local paths, session identifiers, and plugin inventory; their SHA-256 hashes are retained instead.

## Input contract

| Control | Rule |
|---|---|
| Prompt vocabulary | Reject case-insensitive matches for `agent`, `subagent`, `worker`, `role`, `policy`, `baton`, `parallel`, `independent`, `delegat`, `orchestrat`, or `fan-out` |
| Fixture vocabulary | Apply the same scan to both the mechanical and tightly coupled bug fixtures |
| Model attribution | Record the model from the stream initialization event; a requested alias is not proof of the observed model |
| Role attribution | Require an observable `Agent` call with `subagent_type: mech-executor`; reject an invocation-level model override |
| Evidence boundary | Use `parent_tool_use_id` to separate main and child tools and require the matching completed Agent result. Record modified paths and tests as separate final-state observations; do not infer causal filesystem ownership |
| Isolation | Run only in a fresh disposable copy with a clean committed baseline |

The classifier records dispatch reachability, not shell side effects. A correct final diff and a collected worker result do not prove which process caused each mutation.

## Baseline result

| Run | Observed model | Correctness | Topology | Disposition |
|---|---|---|---|---|
| Fable 5, v1.3.0 mechanical | `claude-fable-5` | Not executed | Not observed | `usage_credits_required`; no behavioral or cost claim |
| Opus 4.8, v1.3.0 mechanical | `claude-opus-4-8` | 12/12 | No Agent call; main rewrote all files | Correctness pass, topology fail |

The Opus run completed in one disposable fixture and cannot establish a delegation frequency or a performance expectation. It establishes only that the tested v1.3.0 policy failed this topology gate on that run.

## Candidate result

| Run | Main topology | Observed source-tool scope | Correctness | Gate |
|---|---|---|---|---|
| Opus 4.8, v1.3.1 candidate 1 mechanical | Main triage → one foreground `mech-executor` → main acceptance | Source-targeted tools appear in the worker trace | 12/12 | Pass |
| Opus 4.8, v1.3.1 candidate 1 bug | Main diagnosis → main minimal fix → main test and identity probe | Main session | 2/2 | Pass |

The mechanical Agent invocation omitted `model`, leaving model routing to the named role definition. Its nested trace contains the source-targeted tool calls and the main trace does not. This is stream evidence, not causal filesystem ownership. The bug trace contains no Agent call before or after its main-owned fix and 2/2 pass.

## Exact release-payload replay

After PR #19 and PR #20 merged into the release branch, both cells were rerun on Claude Code 2.1.218 with policy SHA `17d272b6…b39bf` and generated agents SHA `0b42c137…9723c`.

| Run | Observable topology | Correctness | Gate |
|---|---|---|---|
| Mechanical | Opus main → one foreground `mech-executor`; invocation omitted `model`; nested model resolved to `claude-sonnet-5`; source-targeted tools appear in the worker trace | In-session 12/12; independent post-run 12/12 | Pass |
| Bug | Opus main owned diagnosis, first minimal fix, and post-fix test; zero Agent calls | In-session 2/2; independent post-run 2/2 | Pass |

These additive replay records are named `opus-v1.3.1-release-payload-mechanical` and `opus-v1.3.1-release-payload-bug` in the JSON evidence. They establish both sides of the routing boundary for these two exact inputs and show that Claude Code accepted the post-[#18](https://github.com/Nanako0129/pilotfish/issues/18) generated payload. The mechanical role is `mech-executor`, not the separately defined `executor` changed by #18; this replay does not live-exercise that role or establish a dispatch frequency.

## Reproduce

Set `HARNESS` to this checkout. The commands below create disposable repositories, inject the repository policy and installed role definitions explicitly, and leave the source checkout untouched.

```bash
HARNESS=/path/to/pilotfish
RUN_ROOT="$(mktemp -d /tmp/pilotfish-spontaneous.XXXXXX)"
FIXTURE="$RUN_ROOT/fixture"

cp -R "$HARNESS/benchmarks/dispatch-brake/positive-controls/mechanical/fixture" "$FIXTURE"
cp "$HARNESS/templates/claude-md.orchestration.md" "$FIXTURE/CLAUDE.md"
git -C "$FIXTURE" init -q
git -C "$FIXTURE" add .
git -C "$FIXTURE" -c user.name=pilotfish-benchmark \
  -c user.email=pilotfish-benchmark@example.invalid commit -qm baseline

TASK="$(<"$HARNESS/benchmarks/spontaneous-dispatch/prompts/mechanical.txt")"
AGENTS_JSON="$(python3 \
  "$HARNESS/benchmarks/baton-compatibility/build-agents-json.py" \
  "$HARNESS/templates/agents")"

cd "$FIXTURE"
claude -p "$TASK" \
  --model opus \
  --setting-sources project,local \
  --strict-mcp-config \
  --output-format stream-json \
  --verbose \
  --no-session-persistence \
  --dangerously-skip-permissions \
  --max-budget-usd 3 \
  --agents "$AGENTS_JSON" >"$RUN_ROOT/stream.jsonl"
```

For the negative cell, copy `benchmarks/dispatch-brake/fixture`, read [`prompts/bug.txt`](./prompts/bug.txt), and otherwise use the same invocation.

> ⚠️ **Safety boundary:** permission bypass is used only in newly created disposable copies of repository-owned fixtures. Never run this command in a valuable or untrusted checkout.

## v1.3.7 paired opt-in matrix

Recorded under `v1_3_7_paired_opt_in_matrix` in [`results.json`](./results.json). It answers the open Gate item on [#29](https://github.com/Nanako0129/pilotfish/issues/29): the cue-free and the explicitly-directed lifecycle as separate cells, each carrying account plan, client build, model route and Agent call count.

It holds two comparisons, not one.

| Comparison | Cells | Result |
|---|---|---|
| Cue vs no cue, both on Pro | cue-free schema ×2, explicit schema ×2, routine control ×1 each | Cue-free dispatched nothing on either attempt; explicit reached `plan-verifier`, `mech-executor` and `verifier` on both. Routine dispatched nothing in either arm, as its contract requires |
| Pro vs Max, both prompt-cue-free | schema ×2 and routine ×1 on each plan | One of two Max attempts dispatched `plan-verifier` and then `verifier` with no instruction to delegate in the prompt and none in the four fixture files, which pass the cue scan. Neither Pro attempt did |

The dispatching Max attempt reached the policy lifecycle unprompted: a program envelope with a stable slice ID, acceptance and rollback sent to `plan-verifier`, which returned bare `READY`; the migration implemented in the main session with no executor dispatched; then an outcome `verifier` given the exact five-part claim, which returned `CONFIRMED`.

One of two is not a rate. Two attempts cannot separate a plan effect from run-to-run variance, and they cannot separate it from the tree that changed alongside the plan: the Pro cells tracked a copy of `agents.json` that the Max cells did not, the only blob difference between the two baselines. Account plan and repository tree moved together, so the matrix records reachability and ranks no causes. Settling it would need Pro re-run on the Max tree, which is no longer available on an upgraded account. Recorded in `cue_free.tree_difference_between_plans`, including the monotonicity argument an earlier revision made and then withdrew.

That limitation reaches the plan comparison only. The cue-vs-no-cue comparison is paired: both Pro arms ran from the identical baseline tree `fd81141c…`, `agents.json` included, so the file is a shared constant there and the delegation sentence remains the sole intervention. Both explicit attempts are bound to that tree, not only the first. Note that [`../verifier-boundary/README.md`](../verifier-boundary/README.md) documents a recipe that passes `agents.json` externally; the recorded runs tracked it instead, and that README now says so. Details in `cue_free.pro_arms_share_one_tree`.

Five of the six schema attempts converged on the same `store.mjs`, `6aa2e259…` — both explicit attempts, both Max cue-free attempts and Pro cue-free attempt a. Only Pro cue-free attempt b differs. Every attempt's test file differs from every other's. So the same implementation was reached by the main session alone, by a main session that dispatched two review roles, and by a three-role explicit lifecycle.

One term needs care. `cue_free` marks the arm whose prompts carry no delegation instruction — prompt-cue-free. The stricter whole-context definition in `input_contract.why` is not met by any cell here: the Pro cells tracked `agents.json`, which does not pass the cue scan, and every cell had an untracked stream capture in its directory. The Pro cells record zero dispatch with that vocabulary present in the repository; no ranking against a hypothetical clean-context run is drawn, because that would need the same monotonicity assumption withdrawn above. The Max fixture passes the scan, with `CLAUDE.md` and the untracked capture as the named remaining context. `cue_free.classification` states what each arm satisfies.

Every run in this matrix also wrote its own stream capture into the run directory as an untracked file, so the committed baseline tree is not quite the whole context the session could see. In the sole dispatching run no captured tool call read those bytes — `ls -la`, `git status` and `git ls-files --others` surface the filenames, nothing reads the contents — but the `plan-verifier` subagent's own tool calls are not captured in the parent stream, so the same cannot be shown for it. The presence is symmetric across both arms and both plans. Recorded in `input_contract.tree_binding.untracked_stream_captures`, along with the fix for future runs: write captures outside the disposable repository.

Its prompts live in [`../verifier-boundary/prompts/`](../verifier-boundary/prompts/), not in this benchmark's local `prompts/`, and its fixture is [`../verifier-boundary/fixture`](../verifier-boundary/fixture) bound by the digest recorded in the matrix. The schema cell is two turns and needs a resumed session, so it does not use `--no-session-persistence` like the older cells above.

### Reproduction

Reuse `$HARNESS` from the [Reproduce](#reproduce) block above rather than deriving the checkout from the working directory: that block leaves the shell inside `$FIXTURE`, which is itself a Git repository, so `git rev-parse --show-toplevel` would resolve to the disposable copy and every path below would be missing.

```bash
HARNESS=/path/to/pilotfish
SNAPSHOT="$HARNESS/benchmarks/verifier-boundary/gate-snapshot-v2"
PROMPTS="$HARNESS/benchmarks/verifier-boundary/prompts"
WORK="$(mktemp -d /tmp/pilotfish-cue-free.XXXXXX)"

cp -R "$HARNESS/benchmarks/verifier-boundary/fixture/." "$WORK/"
cp "$SNAPSHOT/CLAUDE.md" "$WORK/CLAUDE.md"
git -C "$WORK" init -q && git -C "$WORK" add -A
git -C "$WORK" -c user.name=pilotfish-gate   -c user.email=pilotfish-gate@example.invalid commit -qm baseline

SESSION_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
cd "$WORK"

# turn 1 — cue-free
claude --dangerously-skip-permissions   -p --output-format stream-json --verbose --max-budget-usd 6   --session-id "$SESSION_ID" --model opus --effort high   --setting-sources project,local --strict-mcp-config   --agents "$(<"$SNAPSHOT/agents.json")"   "$(<"$PROMPTS/schema-turn-1.txt")"

# turn 2 — cue-free, resumed
claude --dangerously-skip-permissions   -p --output-format stream-json --verbose --max-budget-usd 6   --resume "$SESSION_ID" --model opus --effort high   --setting-sources project,local --strict-mcp-config   --agents "$(<"$SNAPSHOT/agents.json")"   "$(<"$PROMPTS/schema-turn-2.txt")"
```

The role definitions are passed to `--agents` from the snapshot and never copied into `$WORK`, matching the [verifier-boundary](../verifier-boundary/README.md) recipe. Committing `agents.json` into the fixture would add a tracked file that names all five roles, changing the task context the run observes.

**This block is the corrected shape for new runs, not an exact reproduction of any recorded cell.** It differs from every recorded run in two ways, both deliberate:

| Delta | Recorded runs | This block |
|---|---|---|
| `agents.json` | Tracked in the Pro cells, baseline tree `fd81141c…`; absent from the Max cells, `d31e2096…` | Never copied in; builds `d31e2096…` |
| Stream captures | Written into the run directory, so `t1.jsonl` and `t2.jsonl` were visible in the working tree | Not redirected; nothing cue-bearing is created inside `$WORK` |

To recreate a recorded task context rather than start a clean one, apply the matching deltas. For the Pro cells, add `cp "$SNAPSHOT/agents.json" "$WORK/agents.json"` before the commit. For a recorded schema cell, redirect the two invocations into the run directory as `>"$WORK/t1.jsonl"` and `>"$WORK/t2.jsonl"`; for a recorded routine control, the single invocation goes to `>"$WORK/stream.jsonl"`. The filenames are part of the recorded context, since they are what a directory listing shows. Do both only to re-examine what was recorded; neither belongs in a new run. `cue_free.tree_difference_between_plans` and `input_contract.tree_binding.untracked_stream_captures` record what each difference does and does not license.

Run the routine control in a fresh disposable copy with a new session ID, `--max-budget-usd 4`, and [`routine-docs.txt`](../verifier-boundary/prompts/routine-docs.txt). For the explicit arm, use the `-explicit` variants of the same three prompts; that arm's per-cell evidence is recorded in [`../verifier-boundary/results.json`](../verifier-boundary/results.json) under `passing_gate`.

Recompute the fixture digest with:

Run this from the source checkout, not from `$WORK` — the preceding block leaves the shell inside the disposable copy, where the relative path finds no files and prints the digest of an empty manifest:

```bash
cd "$HARNESS"
python3 - <<'EOF'
import hashlib, pathlib
fx = pathlib.Path("benchmarks/verifier-boundary/fixture")
files = sorted(p for p in fx.rglob("*") if p.is_file())
manifest = "".join(
    f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(fx).as_posix()}\n"
    for p in files
)
print(hashlib.sha256(manifest.encode()).hexdigest())
EOF
```

`--dangerously-skip-permissions` is limited to these disposable fixtures.

## v1.3.7 Max prompt baseline

Recorded under `v1_3_7_max_prompt_baseline` in [`results.json`](./results.json). It is the reference point for the prompt work tracked on [#29](https://github.com/Nanako0129/pilotfish/issues/29): what the shipped v1.3.7 policy does on a Max account across positive and negative cells together, so a candidate policy can be measured against it rather than against an impression.

| Cell | Expected | a | b |
|---|---|---|---|
| Mechanical, 12 files | one foreground `mech-executor`, no main-session mutation | **FAIL** — 0 Agent calls, main rewrote all 12 | **FAIL** — 0 Agent calls, main rewrote all 12 by shell redirection |
| Tightly coupled bug | negative: main owns diagnosis and first fix | PASS — 0 Agent calls, one `Edit` | PASS — 0 Agent calls, one `Edit` |
| Schema lifecycle | `plan-verifier`, implement, `verifier` | PASS — 2 Agent calls | **FAIL** — 0 Agent calls, approval gate skipped |
| Routine docs | negative: zero Agent calls | PASS | PASS |

**Positive attempts: 1 of 4. Negative attempts: 4 of 4. Correctness: every cell passed its tests.** Every failure is a routing failure, never a wrong result. The negative side has headroom and the positive side does not, which is the shape a candidate has to improve without disturbing.

The mechanical cell is the sharpest comparison available: the same prompt and fixture passed 2 of 2 on Opus 4.8 with clients 2.1.217 and 2.1.218, recorded above as `opus-v1.3.1-candidate-1-mechanical` and `opus-v1.3.1-release-payload-mechanical`. It now fails 2 of 2. The observable capability regressed, but the model, the client and the policy version all differ between those records and this one, so the baseline is a starting point, not an attribution.

This baseline is the first set of runs to fix both contamination sources found in review: `agents.json` is passed to `--agents` and never copied in, and every capture is written outside the disposable repository. `git ls-files --others --exclude-standard` is empty in all five newly run directories. The three attempts reused from the paired matrix — schema a and b, routine a — predate the capture fix and each says so.

## Issue #29 reachability correction

Closed PR #45 reported zero dispatch passes in twenty mechanical attempts. Its extractor included child-agent events in `top_level_tools`; the corrected classifier separates those scopes and matches completed Agent results without trying to parse shell side effects.

| Corrected configuration | Dispatch reachability |
|---|---|
| Candidate 3, Opus 5, client 2.1.220 | 2/2 pass |
| v1.3.1 and v1.3.7 policies, Opus 4.8, client 2.1.218, current roles | 4/4 pass |
| Full v1.3.1 reproduction with release roles | 1/2 pass |
| Remaining configurations | 0/12 pass |

The corrected total is **7/20**, with all twenty attempts still at 12/12 correctness and the same twelve final modified paths. A pass means exactly one foreground, collected `mech-executor` call without an invocation-level model override. The tool stream, final diff, and test result are separate observations: they do not prove causal filesystem ownership or establish a dispatch rate. Client 2.1.218 also ran at default effort while 2.1.220 ran at high effort, so the comparison does not isolate the client.

Historical Candidate 3 is evidence for the wording direction, not a release candidate: its mechanical dispatch reachability passed 2/2, but it exceeded the prompt-density budget and skipped the approval gate in both schema attempts. A compressed candidate must pass fresh mechanical, bug, routine, and schema gates before its snapshot hashes move.

## Issue #29 opt-in recovery

The recorded Gate candidate passed the corrected matrix with this explicit opt-in. After post-review corrections restored the independent-review qualifier and defined the background exception for a mechanical worker that may need a long command, the exact v1.3.8 release policy repeated the same matrix and passed every cell:

```text
Use pilotfish. Follow its dispatch brake: keep direct work in the main session and call the named agents only when the policy selects delegation.
```

| Cell | Blocking contract | Result |
|---|---|---|
| Routine docs | Direct main-session edit; zero Agent calls | 2/2 pass |
| Single unknown bug | Main session owns diagnosis and first minimal fix; zero Agent calls | 2/2 pass |
| Stable 12-file repetition | One foreground, collected `mech-executor`; exactly twelve final modified paths | 2/2 pass, 12/12 tests each |
| Schema lifecycle | `plan-verifier` → approval stop → implementation → primary tests → `verifier`; implementation owner follows the brake | 2/2 pass; both direct implementations ended `CONFIRMED` |

Schema review and implementation routing are separate decisions. Serialization makes Plan and outcome review mandatory; it does not make a two-file implementation delegation mandatory. Mechanical delegation has its own positive cell. Treating an execution-agent hop as a schema blocker would contradict the policy's net-benefit brake and previously caused a one-line docs task to over-delegate.

[`issue-29-recovery.json`](./issue-29-recovery.json) binds the repository policy, injection method, generated agents payload, prompts, costs, and raw-stream hashes for both the earlier Gate candidate and the release replay. The release replay ran ten completed invocations under an `$8` hard cap and reported `$3.89565485`. Claude Code updated from 2.1.220 to 2.1.221 between the two mechanical attempts; both passed, and the remaining cells ran on 2.1.221. The client transcripts observe the expected fixture `CLAUDE.md` sizes but do not expose a digest of the bytes incorporated into the runtime system prompt, so this is not an exact-loaded-policy causal claim. Stream and final-state evidence are not used to claim causal mutation ownership.

## Adaptive interaction routing Gate

The 18,500-byte candidate adds `execute`, `explore_then_plan`, and `co_discover` before the existing risk, lifecycle, and worker-routing decisions. It repeated the same explicit-opt-in matrix on 2026-08-07: routine and single-bug controls stayed direct `2/2`, mechanical delegation passed `2/2`, and both schema lifecycles completed `plan-verifier READY` → approval stop → direct implementation and primary tests → `verifier CONFIRMED`. Ten completed invocations reported `$4.101095` under an `$8` hard cap. Claude Code updated from 2.1.223 to 2.1.224 between Schema B turns; the resumed lifecycle still passed.

The machine-readable record is `adaptive_interaction_routing_gate` in [`issue-29-recovery.json`](./issue-29-recovery.json). The previous v1.3.8 policy is frozen in [`v1.3.8-policy-snapshot/CLAUDE.md`](./v1.3.8-policy-snapshot/CLAUDE.md), so later template changes cannot rewrite the older release or TUI evidence. This Gate establishes compatibility with the existing topology boundaries, not an A/B quality gain or a mode-selection rate; Routine A explicitly reported `execute`, while the remaining cells were judged by their observable routing and approval contracts.

## Calico TUI diagnostic

The later cue-free candidate tried to express delegation as a standing user instruction inside `CLAUDE.md`. Four mechanical cells on Claude Code or Calico 2.1.223, Opus 5, high effort made zero Agent calls, changed all twelve adapters in the main session, and passed 12/12 tests. The experiment stopped there; correctness did not satisfy the required ownership topology.

The final cell used a persistent interactive Calico TUI with its existing full tool-output patch enabled. All four thinking blocks were readable. Their bounded summary is that the model treated a higher-priority system instruction as overriding the candidate's AgentTool permission; it separately printed `dispatch: direct — 12 identical one-shot edits, mechanical but faster inline than briefing a worker.` The TUI showed six Bash calls, no `Agent` or `Task` call, and complete command/output rows.

[`cue-free-tui.json`](./cue-free-tui.json) binds the reconstructable policy delta, prompt, fixture, generated agents payload, patched client binary, transcript hash, observable tools, final paths, tests, and approximately `$2.6381705` campaign cost. The raw thinking is not committed. This is evidence of the model's stated decision basis, not the exact active system-prompt bytes; it closes this `CLAUDE.md` candidate, not cue-free delegation as a product goal.

## Claim limits

| Limit | Consequence |
|---|---|
| One observation per recorded cell in the baseline, candidate, and release-payload sections; two attempts per cell in the Issue #29 recovery matrix | Outcomes are behavioral examples, not rates |
| Three observed cells in the v1.3.7 matrix, not a full matrix — Pro has both arms, Max has the cue-free arm only, two schema attempts and one routine attempt in each | Still not a rate. The one dispatching Max attempt out of two is a reachability example; two attempts cannot separate a plan effect from run-to-run variance or from the tree difference that changed with the plan |
| Client-reported cost field | It is not a provider invoice |
| Fable usage-credit gate | No Fable behavior, correctness, or efficiency comparison is available |
| Opus-only candidate evaluation | A passing Opus gate does not prove identical routing by another model |
| Policy iteration count | Candidate 1 passed both cells; the later exact release-payload replay retested the same cells after the executor frontmatter change |
| Normalized evidence | Raw-stream hashes support identity checks, while published traces intentionally exclude sensitive local metadata |
| Stream plus final state | A collected worker call, modified paths, and passing tests do not establish causal filesystem ownership |

This gate is additive. It does not overwrite the earlier [`dispatch-brake`](../dispatch-brake/README.md) or [`baton-compatibility`](../baton-compatibility/README.md) evidence.
