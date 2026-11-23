# agy preview: delegation with and without `plugin-agy`

This run asks one question about the [Antigravity CLI port](../../plugin-agy/README.md): does installing it change what the main agent delegates, on one task where delegation should not happen and one where it should pay? It reuses two tasks from [`dispatch-brake`](../dispatch-brake/README.md) unchanged.

It is a small behavioral check, five runs per cell. It does not measure answer quality beyond each fixture's own tests, and it does not compare agy with Claude Code.

## Setup

| | |
|---|---|
| Date | 2026-11-23, Asia/Taipei |
| Host | macOS 27.0, Node.js v24.21.0 |
| agy | 1.5.15, headless (`agy -p`), consumer plan |
| Main model | `gemini-4-neon-high` |
| Plugin | The `plugin-agy` tree of the commit that adds this directory, without its `README.md`. `hooks/model-floor.sh` was hardened after the runs; its output for the two model names that occurred is unchanged |
| Runs | 2 tasks x 2 conditions x 5 = 20, four at a time, conditions interleaved |

- **brake**: [`dispatch-brake/task.md`](../dispatch-brake/task.md), an unknown bug on one coupled path. The policy says to keep it in the main agent.
- **research**: [`positive-controls/research/task.md`](../dispatch-brake/positive-controls/research/task.md), an audit of two disjoint surfaces. Delegating read-only discovery is expected.
- **plugin** condition: a fresh copy of the fixture with `plugin-agy` at `.agents/plugins/pilotfish`. **none** condition: the fixture alone. The user's global agy configuration applied to both; no pilotfish plugin was installed globally.

[`run.py`](./run.py) creates the workspaces, runs agy, counts `invoke_subagent` calls in the main transcript, records `git status`, and then runs `npm test`. Raw rows are in [`results.json`](./results.json).

```bash
python3 benchmarks/agy-preview/run.py --out /path/to/new-dir --reps 5
```

The command spends agy quota on 20 headless runs.

## Results

Every one of the 20 runs ended with status `SUCCESS` and a passing `npm test`.

| Task | Condition | Runs that delegated | Subagents launched | Subagent model |
|---|---|---|---|---|
| brake | none | 0 of 5 | none | n/a |
| brake | plugin | 0 of 5 | none | n/a |
| research | none | 4 of 5 | 2 built-in `research` each | `gemini-4-neon-high` |
| research | plugin | 5 of 5 | 2 `pilotfish-scout` each; one run added a `pilotfish-verifier` | scout: `gemini-4-hydrogen-tiered-high`; verifier: `gemini-4-neon-high` |

Subagent models were read from the subagent transcripts after the run; `run.py` does not record them.

| Task | Condition | Duration, seconds (sorted) | Main-conversation input, cached and uncached (sorted) |
|---|---|---|---|
| brake | none | 79, 97, 99, 122, 123 | 160k / 161k / 167k / 179k / 185k |
| brake | plugin | 77, 85, 92, 175, 178 | 167k / 169k / 170k / 171k / 195k |
| research | none | 215, 311, 337, 365, 395 | 228k / 286k / 304k / 406k / 438k |
| research | plugin | 238, 244, 259, 383, 445 | 292k / 357k / 416k / 419k / 525k |

The input column is `input_tokens + cache_read_tokens`. agy's `total_tokens` leaves cache reads out, so it mostly tracks the cache hit rate and is not used here.

## Reading

- **The brake held, and so did the baseline.** No run delegated the coupled bug in either condition. On this task the plugin changed nothing that was measured; agy on `gemini-4-neon-high` already kept it inline.
- **On the research task the plugin changed who did the discovery, not whether it was delegated.** Without the plugin the main agent used the built-in `research` subagent in four of five runs, on its own model. With the plugin it used `pilotfish-scout` in five of five, on the Hydrogen tier.
- **Duration and input size do not separate the conditions.** The ranges overlap in both tasks with five runs per cell.

## Not measured

- Whether `usage` in agy's JSON output includes subagent tokens. The token column is what agy reported for the main conversation and is not a cost figure.
- Cost. At list price Hydrogen costs less per token than Neon, but no per-run cost was computed.
- The quality of `REPORT.md` beyond the fixture's `npm test`.
- Any role other than `pilotfish-scout` and one `pilotfish-verifier` call; any risk-triggered path (Plan, approval, mandatory verifier); an interactive session; any other model, agy version or host.
- Run-to-run variance beyond five runs per cell.
