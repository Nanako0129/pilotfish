# Positive controls and rejected dispatch policies

The original state-clone benchmark proved that delegation can be wasteful. It could not prove the equally important claim that the brake still permits useful delegation. These controls test both sides of that boundary.

| Control | Intended decision | Acceptance gate |
|---|---|---|
| Small task-local read-only research | Compare direct inspection with bounded fan-out for this fixture; do not infer a complete plan-first lifecycle | `REPORT.md` covers both surfaces with `file:line` evidence; `npm test` passes |
| Stable 12-file mechanical edit | Route to the cheap mechanical worker when the cost saving outweighs a modest latency penalty | All 12 tests pass; only adapter source files change |
| Tightly coupled unknown bug | Keep diagnosis and the first fix in one main-session reasoning chain; retain proportionate fresh verification | Both state-clone tests pass |

The exact fixtures and neutral prompts are in [`research/`](./research/) and [`mechanical/`](./mechanical/). Every completed and deliberately interrupted run is recorded in [`results.json`](./results.json); normalized tool sequences and Agent inputs are in [`traces.json`](./traces.json) and [`agent-calls.json`](./agent-calls.json). Raw stream hashes are published instead of raw streams because initialization events contain local paths, session identifiers, hooks, and plugin inventory.

## What failed before the balanced policy

| Policy iteration | Negative control | Mechanical positive control | Small research control | Decision |
|---|---|---|---|---|
| Direct-work hard veto | Good: tightly coupled work stayed inline | Bad: pilotfish stayed inline, so the cheap worker was suppressed | Direct | Rejected: direct execution being faster cannot be a universal veto |
| Broad net-benefit default | Regressed once in remora into scout → executor | Delegated | Two scouts had higher overhead than direct work on this fixture | Rejected as a task-local default; not tested as part of a larger Plan |
| Net benefit + single-bug guard | Good on both products | Good: pilotfish delegated to `mech-executor` | Still too subjective | Retained, then narrowed for read-only fan-out |
| Sized read-only gate | Not changed | Not changed | pilotfish completed inline with no Agent call | Retained as a task-local default; the historical Baton probe was incomplete, then a separate lifecycle Gate closed that question |

The release decision model is phase-aware:

| Phase | Meaning |
|---|---|
| Discovery | A stable question, scope, evidence format, and stop condition can be delegated read-only before the implementation outcome is known |
| Plan and approval | Main session synthesizes one Plan; material work waits for explicit approval before source writes or implementation briefs |
| Execution | Stable scope, exclusive ownership, done criteria, integration, and verification are required before writing agents start |
| Net benefit | Within each phase's safety boundary, compare model cost, scarce context, elapsed time, isolation, and fresh independence against reconstruction, coordination, integration, and verification |

The result is intentionally not “delegate less.” Stable mechanical repetition remains an explicit positive path. A task-local bounded scan defaults to one main-session pass, while read-only discovery can still fan out when substantial independent surfaces, overlapable external/tool latency, or independently gathered evidence materially reduces Plan uncertainty.

## Key measurements

| Run | Agent pattern | Wall time | Reported cost field | Result |
|---|---|---:|---:|---|
| pilotfish mechanical, hard veto | Inline; no outcome verifier | 128.24 s | $0.790263 | 12/12 pass |
| pilotfish mechanical, balanced | `mech-executor` foreground; no outcome verifier | 138.40 s | $0.505682 | 12/12 pass |
| pilotfish small research, broad fan-out | 2 scouts background | 261.52 s | $1.036893 | Pass |
| pilotfish small research, direct comparison | Inline | 234.10 s | $0.896864 | Pass |
| pilotfish small research, sized gate | Inline | 228.96 s | $0.918431 | Pass |
| pilotfish tightly coupled bug, balanced | Inline | 77.45 s | $0.365309 | 2/2 pass |
| remora tightly coupled bug, balanced | Inline diagnosis/fix → verifier foreground | 200.86 s | $0.817504 | 2/2 pass |

In the mechanical control's execution-only segment, delegation reduced the reported cost field by 36.01% while adding 7.92% wall time. Neither mechanical run performed the release policy's required outcome-verifier pass, so this demonstrates that the cheap execution route remains reachable; it does **not** establish full-lifecycle savings. For the small research control, the two-scout run increased wall time by 11.71% and the reported cost field by 15.61% relative to its direct comparison. These are single task-local runs, not population estimates, and the research comparison did not include downstream Plan synthesis or execution.

## Reproduce

To replay the published balanced mechanical harness with byte-identical policy and role inputs, fetch the full pinned commit (required for a shallow release checkout) and attach it as a temporary worktree. The current checkout supplies only the generic JSON builder; both the policy and all six role definitions come from the pinned snapshot and are injected explicitly, so no global pilotfish install is required. The main session is pinned to the recorded Opus 4.8 model; generated output, timing, and cost remain single-run observations rather than deterministic bytes.

```bash
HARNESS=/path/to/current/pilotfish
SNAPSHOT=/tmp/pilotfish-dispatch-863b117
PINNED=863b117b9da42179c5bb77a05158920fbc092ee2

git -C "$HARNESS" fetch --depth 1 origin "$PINNED"
git -C "$HARNESS" worktree add --detach "$SNAPSHOT" "$PINNED"
cp -R "$SNAPSHOT/benchmarks/dispatch-brake/positive-controls/mechanical/fixture" \
  /tmp/pilotfish-mechanical
cd /tmp/pilotfish-mechanical
git init -q
git add .
git -c user.name=pilotfish-benchmark \
  -c user.email=pilotfish-benchmark@example.invalid commit -qm baseline
npm test

TASK="$(sed -n '/^```text$/,/^```$/p' \
  "$SNAPSHOT/benchmarks/dispatch-brake/positive-controls/mechanical/task.md" \
  | sed '1d;$d')"
AGENTS_JSON="$(python3 \
  "$HARNESS/benchmarks/baton-compatibility/build-agents-json.py" \
  "$SNAPSHOT/templates/agents")"

/usr/bin/time -p claude -p "$TASK" \
  --output-format stream-json \
  --verbose \
  --no-session-persistence \
  --dangerously-skip-permissions \
  --max-budget-usd 3 \
  --model claude-opus-4-8 \
  --setting-sources project,local \
  --strict-mcp-config \
  --agents "$AGENTS_JSON" \
  --append-system-prompt-file "$SNAPSHOT/templates/claude-md.orchestration.md"

git -C "$HARNESS" worktree remove "$SNAPSHOT"
```

> ⚠️ **Safety boundary:** bypass mode was used only in disposable copies of these published fixtures. Never reuse it in an untrusted or valuable checkout.

## Disclosed limits

| Limit | Consequence |
|---|---|
| One run per completed condition | Time and cost deltas show observed behavior, not stable expected values |
| Client-reported cost field | It is not a provider invoice |
| Historical Baton probes | GPT-5.6 Sol auto-loaded [baton-dispatch v0.1.1](https://github.com/cablate/baton) and selected two read-only discovery calls. Both probes stopped before Plan synthesis, approval, execution, or verification, so those runs alone did not evaluate the complete composition |
| Product/model asymmetry | A decision observed under Claude Opus is not automatically proven under GPT-5.6 Sol with a planning skill active |
| Complete lifecycle | The later, now-historical [pilotfish + Baton compatibility gate](../../baton-compatibility/README.md) completed the native-Claude two-turn lifecycle for its exact recorded bytes; it is a separate single-run gate, not a reinterpretation of these probes |

The historical remora/Baton observation remains a composition probe, not a standalone compatibility finding. Baton selected a plausible discovery topology and remora supplied the named roles and GPT model routing, but the probes stopped before closure. End-to-end compatibility evidence is published separately so the earlier observations keep their original scope.
