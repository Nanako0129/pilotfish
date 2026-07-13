# Positive controls and rejected dispatch policies

The original state-clone benchmark proved that delegation can be wasteful. It could not prove the equally important claim that the brake still permits useful delegation. These controls test both sides of that boundary.

| Control | Intended decision | Acceptance gate |
|---|---|---|
| Small read-only research | Work inline unless the scan or latency is large enough to repay worker startup and synthesis | `REPORT.md` covers both surfaces with `file:line` evidence; `npm test` passes |
| Stable 12-file mechanical edit | Route to the cheap mechanical worker when the cost saving outweighs a modest latency penalty | All 12 tests pass; only adapter source files change |
| Tightly coupled unknown bug | Keep diagnosis and the first fix in one main-session reasoning chain; retain proportionate fresh verification | Both state-clone tests pass |

The exact fixtures and neutral prompts are in [`research/`](./research/) and [`mechanical/`](./mechanical/). Every completed and deliberately interrupted run is recorded in [`results.json`](./results.json); normalized tool sequences and Agent inputs are in [`traces.json`](./traces.json) and [`agent-calls.json`](./agent-calls.json). Raw stream hashes are published instead of raw streams because initialization events contain local paths, session identifiers, hooks, and plugin inventory.

## What failed before the balanced policy

| Policy iteration | Negative control | Mechanical positive control | Small research control | Decision |
|---|---|---|---|---|
| Direct-work hard veto | Good: tightly coupled work stayed inline | Bad: pilotfish stayed inline, so the cheap worker was suppressed | Direct | Rejected: direct execution being faster cannot be a universal veto |
| Broad net-benefit default | Regressed once in remora into scout → executor | Delegated | Bad: pilotfish spawned two scouts for about a dozen short files | Rejected: directory independence alone is not enough scale |
| Net benefit + single-bug guard | Good on both products | Good: pilotfish delegated to `mech-executor` | Still too subjective | Retained, then narrowed for read-only fan-out |
| Sized read-only gate | Not changed | Not changed | pilotfish completed inline with no Agent call | Shipped; remora interaction with an auto-loaded generic skill remains a disclosed limit |

The final decision model has two layers:

| Layer | Meaning |
|---|---|
| Hard blockers | Do not delegate while success conditions are unstable, the worker depends on evolving main-session evidence, writes overlap, or closure has no owner |
| Net benefit | Otherwise compare model cost, scarce context, elapsed time, isolation, and fresh independence against reconstruction, coordination, integration, and verification |

The result is intentionally not “delegate less.” Stable mechanical repetition remains an explicit positive path. Read-only repository fan-out is opt-in and needs substantial per-surface scanning, overlapable external/tool latency, or deliberately independent perspectives. Roughly a dozen short files default to one bounded main-session pass.

## Key measurements

| Run | Agent pattern | Wall time | Reported cost field | Result |
|---|---|---:|---:|---|
| pilotfish mechanical, hard veto | Inline | 128.24 s | $0.790263 | 12/12 pass |
| pilotfish mechanical, balanced | `mech-executor` foreground | 138.40 s | $0.505682 | 12/12 pass |
| pilotfish small research, broad fan-out | 2 scouts background | 261.52 s | $1.036893 | Pass |
| pilotfish small research, direct comparison | Inline | 234.10 s | $0.896864 | Pass |
| pilotfish small research, sized gate | Inline | 228.96 s | $0.918431 | Pass |
| pilotfish tightly coupled bug, balanced | Inline | 77.45 s | $0.365309 | 2/2 pass |
| remora tightly coupled bug, balanced | Inline diagnosis/fix → verifier foreground | 200.86 s | $0.817504 | 2/2 pass |

For the mechanical control, delegation reduced the reported cost field by 36.01% while adding 7.92% wall time. For the small research control, the overbroad two-scout policy increased wall time by 11.71% and the reported cost field by 15.61% relative to its direct comparison. These are single runs, not population estimates.

## Reproduce

Copy one fixture into a disposable directory, initialize it as a Git repository, verify the failing or clean baseline, and use the prompt from its adjacent `task.md`.

```bash
cp -R benchmarks/dispatch-brake/positive-controls/mechanical/fixture /tmp/pilotfish-mechanical
cd /tmp/pilotfish-mechanical
git init
git add .
git commit -m baseline
npm test

TASK="$(sed -n '/^```text$/,/^```$/p' \
  /path/to/pilotfish/benchmarks/dispatch-brake/positive-controls/mechanical/task.md \
  | sed '1d;$d')"

/usr/bin/time -p claude -p "$TASK" \
  --output-format stream-json \
  --verbose \
  --no-session-persistence \
  --dangerously-skip-permissions \
  --max-budget-usd 3 \
  --append-system-prompt-file /path/to/pilotfish/templates/claude-md.orchestration.md
```

> ⚠️ **Safety boundary:** bypass mode was used only in disposable copies of these published fixtures. Never reuse it in an untrusted or valuable checkout.

## Disclosed limits

| Limit | Consequence |
|---|---|
| One run per completed condition | Time and cost deltas show observed behavior, not stable expected values |
| Client-reported cost field | It is not a provider invoice |
| Claude quota approached exhaustion | No further pilotfish live repetitions were started; the completed sized-gate run was preserved |
| Co-installed [baton-dispatch v0.1.1](https://github.com/cablate/baton) | GPT-5.6 Sol auto-loaded the generic skill and still fanned out remora's small research fixture. Two follow-up probes were stopped once the decision violation was observable. An unverified precedence sentence was removed rather than shipped |
| Product/model asymmetry | A policy that works under Claude Opus is not automatically proven under GPT-5.6 Sol when later skill instructions are injected |

The remora/Baton interaction is therefore an open compatibility finding, not a claimed fix. The released policy improves the standalone routing contract and has positive/negative behavioral evidence, but it does not claim to dominate every independently installed orchestration skill.
