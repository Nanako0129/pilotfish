# Spontaneous-dispatch behavior gate

This gate asks whether Pilotfish chooses the intended execution topology from an ordinary task request. The prompts contain no instruction to delegate, avoid delegation, or consult an orchestration policy.

| Cell | Expected topology | Behavioral acceptance |
|---|---|---|
| Stable 12-file mechanical edit | Exactly one foreground `mech-executor` | The main session performs no source mutation; the worker is the sole mutation path; exactly 12 adapter files change; 12/12 tests pass |
| One unknown tightly coupled bug | Main session owns diagnosis and the first minimal fix | No discovery or implementation agent runs before the main session changes the fix and observes the focused 2/2 pass; a closing `verifier` remains allowed |

The exact prompts are in [`prompts/`](./prompts/). Recorded outcomes, normalized tool traces, and observable Agent calls are in [`results.json`](./results.json), [`traces.json`](./traces.json), and [`agent-calls.json`](./agent-calls.json). Raw streams are not committed because initialization events contain local paths, session identifiers, hooks, and plugin inventory; their SHA-256 hashes are retained instead.

## Input contract

| Control | Rule |
|---|---|
| Prompt vocabulary | Reject case-insensitive matches for `agent`, `subagent`, `worker`, `role`, `policy`, `baton`, `parallel`, `independent`, `delegat`, `orchestrat`, or `fan-out` |
| Fixture vocabulary | Apply the same scan to both the mechanical and tightly coupled bug fixtures |
| Model attribution | Record the model from the stream initialization event; a requested alias is not proof of the observed model |
| Role attribution | Require an observable `Agent` call with `subagent_type: mech-executor`; reject an invocation-level model override |
| Mutation attribution | Reject top-level `Edit` or `Write`; classify every top-level Bash command conservatively and reject redirection or commands capable of source writes |
| Isolation | Run only in a fresh disposable copy with a clean committed baseline |

The strict Bash classifier treats uncertainty as a failure. A correct final diff does not prove worker ownership when the main session had any unclassified write-capable command.

## Baseline result

| Run | Observed model | Correctness | Topology | Disposition |
|---|---|---|---|---|
| Fable 5, v1.3.0 mechanical | `claude-fable-5` | Not executed | Not observed | `usage_credits_required`; no behavioral or cost claim |
| Opus 4.8, v1.3.0 mechanical | `claude-opus-4-8` | 12/12 | No Agent call; main rewrote all files | Correctness pass, topology fail |

The Opus run completed in one disposable fixture and cannot establish a delegation frequency or a performance expectation. It establishes only that the tested v1.3.0 policy failed this topology gate on that run.

## Candidate result

| Run | Main topology | Source owner | Correctness | Gate |
|---|---|---|---|---|
| Opus 4.8, v1.3.1 candidate 1 mechanical | Read-only triage → one foreground `mech-executor` → main acceptance | `mech-executor` only | 12/12 | Pass |
| Opus 4.8, v1.3.1 candidate 1 bug | Main diagnosis → main minimal fix → main test and identity probe | Main session | 2/2 | Pass |

The mechanical Agent invocation omitted `model`, leaving model routing to the named role definition. Its nested trace contains all source-writing tools; the main trace contains no `Edit`, `Write`, redirection, or write-capable Bash command. The bug trace contains no Agent call before or after its main-owned fix and 2/2 pass.

## Exact release-payload replay

After PR #19 and PR #20 merged into the release branch, both cells were rerun on Claude Code 2.1.218 with policy SHA `17d272b6…b39bf` and generated agents SHA `0b42c137…9723c`.

| Run | Observable topology | Correctness | Gate |
|---|---|---|---|
| Mechanical | Opus main → one foreground `mech-executor`; invocation omitted `model`; nested model resolved to `claude-sonnet-5`; worker was the only source-mutation path | In-session 12/12; independent post-run 12/12 | Pass |
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

## Claim limits

| Limit | Consequence |
|---|---|
| One observation per recorded cell | Outcomes are behavioral examples, not rates |
| Client-reported cost field | It is not a provider invoice |
| Fable usage-credit gate | No Fable behavior, correctness, or efficiency comparison is available |
| Opus-only candidate evaluation | A passing Opus gate does not prove identical routing by another model |
| Policy iteration count | Candidate 1 passed both cells; the later exact release-payload replay retested the same cells after the executor frontmatter change |
| Normalized evidence | Raw-stream hashes support identity checks, while published traces intentionally exclude sensitive local metadata |

This gate is additive. It does not overwrite the earlier [`dispatch-brake`](../dispatch-brake/README.md) or [`baton-compatibility`](../baton-compatibility/README.md) evidence.
