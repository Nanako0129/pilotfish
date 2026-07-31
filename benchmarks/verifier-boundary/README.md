# Verifier-boundary Gate

> One native Claude Code reachability observation for the exact pilotfish
> v1.3.6 candidate. It does not establish activation frequency, quality,
> latency, or cost efficiency.

## Result

Both passing controls used the README-documented opt-in:
`Use pilotfish and delegate eligible work to the named agents.`

| Control | Observed routing | Acceptance | Client-reported cost |
|---|---|---|---:|
| Schema migration | `plan-verifier` → explicit approval stop → `executor` → primary tests → fresh `verifier` | `READY`; no pre-approval writes; 4/4 tests; only `store.mjs` and `store.test.mjs`; `CONFIRMED` | $1.33865765 |
| Routine docs | `mech-executor` only; no `plan-verifier` or outcome `verifier` | 1/1 test; only the requested README typo changed | $0.48368960 |

The exact candidate therefore reached both sides of the independent-review
boundary under explicit agent opt-in: the serialization change received Plan
and outcome review, while routine docs skipped both review roles. Every Agent
call omitted an invocation-level model override. The main session resolved to
Opus 5, `executor` and `mech-executor` resolved to Sonnet 5, and both review
roles resolved to Opus 5.

This is not a cue-free claim. On this tested Claude Code account, a
higher-priority operator contract prohibited Agent calls unless the user
requested them. A neutral schema prompt therefore edited the fixture directly
and was rejected as Gate evidence. The run cost $0.51322950 and is retained in
[`results.json`](./results.json), along with the earlier zero-cost 429 attempt.

## Exact inputs

| Input | SHA-256 |
|---|---|
| [`gate-snapshot/CLAUDE.md`](./gate-snapshot/CLAUDE.md) | `ae771c9b43ad985f7ad1e520cd6e021c69e13aac3bd6a60a8edacd1d386f0e82` |
| [`gate-snapshot/agents.json`](./gate-snapshot/agents.json), file bytes | `9aa5feb04d062400d414f9e7d31a6e882696f2f73ece01425fe06e74582122eb` |
| `agents.json`, shell-normalized runtime input | `0953159df622bcb25c6f298a00d57dd2feea180d0b863e0b946547e5db107f42` |

The disposable baseline is under [`fixture/`](./fixture/). Exact neutral and
explicit prompts are under [`prompts/`](./prompts/). `results.json` binds every
prompt and raw stream by hash and records the final artifact hashes, route,
cost, completion, and acceptance evidence.

## Reproduction

Create separate disposable Git copies of `fixture/` for the schema and routine
controls, copy `gate-snapshot/CLAUDE.md` into each repository root, and commit
the clean baseline. Then run:

```bash
claude --dangerously-skip-permissions \
  -p --output-format stream-json --verbose --max-budget-usd 6 \
  --session-id "$SESSION_ID" --model opus --effort high \
  --setting-sources project,local --strict-mcp-config \
  --agents "$(<gate-snapshot/agents.json)" \
  "$(<prompts/schema-turn-1-explicit.txt)"

claude --dangerously-skip-permissions \
  -p --output-format stream-json --verbose --max-budget-usd 6 \
  --resume "$SESSION_ID" --model opus --effort high \
  --setting-sources project,local --strict-mcp-config \
  --agents "$(<gate-snapshot/agents.json)" \
  "$(<prompts/schema-turn-2-explicit.txt)"
```

Run the routine control in a fresh disposable copy with a new session ID,
`--max-budget-usd 4`, and
[`routine-docs-explicit.txt`](./prompts/routine-docs-explicit.txt).
`--dangerously-skip-permissions` is limited to these disposable fixtures.
