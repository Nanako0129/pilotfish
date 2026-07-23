# Cue-free Baton dispatch-effect pair

This paired behavioral test asks a narrower question than the compatibility Gate: does making Baton available, without naming it in the task, cause spontaneous skill activation or change the Agent topology?

> **Result:** no dispatch effect was observed. The treatment exposed `baton-dispatch` in the initialization skill inventory, but Opus emitted no `Skill` call and no `Agent` call. Both cells completed inline and passed the fixture test.

## Paired contract

| Factor | Control | Treatment |
|---|---|---|
| Task prompt | Exact same bytes | Exact same bytes |
| Fixture | Exact same research fixture | Exact same research fixture |
| Pilotfish policy and roles | Exact same v1.3.1 bytes | Exact same v1.3.1 bytes |
| Main model | `claude-opus-4-8` | `claude-opus-4-8` |
| Setting sources | `project,local` | `project,local` |
| Baton | Absent | Project-scoped Baton 0.1.1 at commit `77f12e6` |
| Maximum client budget | $3 | $3 |

The prompt in [`prompts/task.txt`](./prompts/task.txt) contains no case-insensitive match for `baton`, `agent`, `subagent`, `worker`, standalone `role`, `policy`, `skill`, `delegat`, `orchestrat`, `parallel`, `independent`, or `fan-out`. It does not tell either cell to optimize topology or use a planning layer.

## Observed result

| Observation | Control | Treatment | Effect gate |
|---|---:|---:|---|
| Baton listed during init | No | Yes | Capability injection passed |
| `Skill` calls | 0 | 0 | Spontaneous activation failed |
| `Agent` calls | 0 | 0 | Topology delta failed |
| Execution shape | Inline | Inline | No dispatch effect observed |
| Fixture test | Pass | Pass | Correctness control passed |
| Wall time | 129.27 s | 130.17 s | Single observations only |
| Client-reported cost | $0.718764 | $0.741686 | Not a provider invoice |

[`results.json`](./results.json) preserves exact hashes, metrics, and the failed effect gate. [`traces.json`](./traces.json) and [`agent-calls.json`](./agent-calls.json) publish normalized tool evidence. Raw streams are not committed because initialization events contain local paths and session metadata; their SHA-256 hashes remain recorded.

## Reproduce

The treatment copies the pinned local Baton dependency into its project skill directory before committing the disposable baseline. The control omits that directory. Both cells exclude user settings so unrelated user memory and skills do not become an A/B variable.

```bash
SOURCE=/path/to/pilotfish
BATON=/path/to/baton-at-77f12e600406065a6e62a22a66347355e278a9d7
PAIR_ROOT="$(mktemp -d /tmp/pilotfish-baton-effect.XXXXXX)"

for CELL in control treatment; do
  WORK="$PAIR_ROOT/$CELL"
  mkdir -p "$WORK"
  cp -R "$SOURCE/benchmarks/dispatch-brake/positive-controls/research/fixture/." "$WORK/"
  cp "$SOURCE/templates/claude-md.orchestration.md" "$WORK/CLAUDE.md"

  if [ "$CELL" = treatment ]; then
    mkdir -p "$WORK/.claude/skills/baton-dispatch"
    cp "$BATON/SKILL.md" "$WORK/.claude/skills/baton-dispatch/SKILL.md"
    cp -R "$BATON/references" "$WORK/.claude/skills/baton-dispatch/references"
  fi

  git -C "$WORK" init -q
  git -C "$WORK" add .
  git -C "$WORK" -c user.name=pilotfish-benchmark \
    -c user.email=pilotfish-benchmark@example.invalid commit -qm baseline
done

TASK="$(<"$SOURCE/benchmarks/baton-dispatch-effect/prompts/task.txt")"
AGENTS_JSON="$(python3 \
  "$SOURCE/benchmarks/baton-compatibility/build-agents-json.py" \
  "$SOURCE/templates/agents")"

for CELL in control treatment; do
  cd "$PAIR_ROOT/$CELL"
  claude -p "$TASK" \
    --model opus \
    --setting-sources project,local \
    --strict-mcp-config \
    --output-format stream-json \
    --verbose \
    --no-session-persistence \
    --dangerously-skip-permissions \
    --max-budget-usd 3 \
    --agents "$AGENTS_JSON" >"$PAIR_ROOT/$CELL-stream.jsonl"
done
```

> ⚠️ **Safety boundary:** permission bypass is limited to fresh disposable copies of the repository-owned fixture.

## Claim boundary

| Limit | Consequence |
|---|---|
| One ordered pair | The result is an observed failure to activate, not a population rate |
| Availability is not activation | Seeing Baton in the init inventory does not prove the model read or followed it |
| Same correctness, different reports | Report wording and size are nondeterministic and do not establish an effect |
| No Agent calls in either cell | This test provides no evidence that Baton dispatch affected topology |
| No performance experiment | Timing and cost deltas must not be interpreted as Baton overhead |

The earlier [`baton-compatibility`](../baton-compatibility/README.md) Gate remains valid for lifecycle composition. This pair closes a different evidence gap and fails it honestly: compatibility did not imply spontaneous Baton activation.
