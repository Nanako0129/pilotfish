# Verifier-boundary Gate

> One native Claude Code reachability observation for the exact pilotfish
> v1.3.6 candidate. It does not establish activation frequency, quality,
> latency, or cost efficiency.

## Result

Both passing controls used the README-documented opt-in:
`Use pilotfish and delegate eligible work to the named agents.`

| Control | Observed routing | Acceptance | Client-reported cost |
|---|---|---|---:|
| Schema migration (2 of 2 attempts after the approval-gate wording fix; 2 of 4 before — see `determinism`) | `plan-verifier` → explicit approval stop → `executor` → primary tests → fresh `verifier` | `READY`; no pre-approval writes; only `store.mjs` and `store.test.mjs`; `CONFIRMED` | $2.20320000 |
| Routine docs | Direct main-session edit; no Agent call | 1/1 test; only the requested README typo changed | $0.25540000 |
| Post-cap Plan control | `plan-verifier` × 3 | `REVISE` → `REVISE` → material ownership fix/new epoch → closing `READY`; zero writes | $1.13100000 |

The exact candidate therefore reached both sides of the independent-review
boundary under explicit agent opt-in: the serialization change received Plan
and outcome review, routine docs stayed direct, and a user-directed three-turn
Plan control stopped after two `REVISE` verdicts before one closing check.
Every Agent call omitted an invocation-level model override. The main session
and both review roles resolved to Opus 5; `executor` resolved to Sonnet 5.

The current passing controls reported $3.589600 against the v1.3.7 compressed policy. The schema cell is not deterministic: it reproduced on one of two attempts against byte-identical inputs, and the non-reproducing attempt is recorded under `failed_attempts`. Including the earlier candidate Gate, the disclosed
operator-policy failure, the zero-cost quota failure, the non-reproducing schema
attempt, and the diagnostic that the weekly limit truncated, the full campaign
reported $15.70; `results.json` carries the breakdown.

This is not a cue-free claim. On this tested Claude Code account, a
higher-priority operator contract prohibited Agent calls unless the user
requested them. A neutral schema prompt therefore edited the fixture directly
and was rejected as Gate evidence. The run cost $0.51322950 and is retained in
[`results.json`](./results.json), along with the earlier zero-cost 429 attempt.

## Exact inputs

| Input | SHA-256 |
|---|---|
| [`gate-snapshot-v2/CLAUDE.md`](./gate-snapshot-v2/CLAUDE.md) | `8cec947e72844a689942cb00386b37147adcc4edf2fb2952c6917d207e31b549` |
| [`gate-snapshot-v2/agents.json`](./gate-snapshot-v2/agents.json), file bytes | `e6257911a02c805147d7d8923eae14877cc8e29089e85ac93b544f5afb73ea3f` |
| `agents.json`, shell-normalized runtime input | `b5dc352f526f0c6f1985c67799f547c3368b2b72e77be1738a8789c542ae7bfc` |

The disposable baseline is under [`fixture/`](./fixture/). Exact neutral and
explicit prompts are under [`prompts/`](./prompts/). `results.json` binds every
prompt and raw stream by hash and records the final artifact hashes, route,
cost, completion, and acceptance evidence.

[`gate-snapshot/`](./gate-snapshot/) preserves the first passing candidate
before the follow-up verifier prompt correction. It remains historical evidence
and is not the current installable payload.

## Reproduction

Create separate disposable Git copies of `fixture/` for the schema and routine
controls, copy `gate-snapshot-v2/CLAUDE.md` into each repository root, and commit
the clean baseline. Then run:

```bash
SOURCE="$(git rev-parse --show-toplevel)"
SNAPSHOT="$SOURCE/benchmarks/verifier-boundary/gate-snapshot-v2"
PROMPTS="$SOURCE/benchmarks/verifier-boundary/prompts"
SESSION_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
cd /absolute/path/to/disposable/schema

claude --dangerously-skip-permissions \
  -p --output-format stream-json --verbose --max-budget-usd 6 \
  --session-id "$SESSION_ID" --model opus --effort high \
  --setting-sources project,local --strict-mcp-config \
  --agents "$(<"$SNAPSHOT/agents.json")" \
  "$(<"$PROMPTS/schema-turn-1-explicit.txt")"

claude --dangerously-skip-permissions \
  -p --output-format stream-json --verbose --max-budget-usd 6 \
  --resume "$SESSION_ID" --model opus --effort high \
  --setting-sources project,local --strict-mcp-config \
  --agents "$(<"$SNAPSHOT/agents.json")" \
  "$(<"$PROMPTS/schema-turn-2-explicit.txt")"
```

Run the routine control in a fresh disposable copy with a new session ID,
`--max-budget-usd 4`, and
[`routine-docs-explicit.txt`](./prompts/routine-docs-explicit.txt).
Run the three `plan-cap-turn-*.txt` prompts in order in another clean copy,
using one new session ID, then `--resume` for turns 2 and 3.
`--dangerously-skip-permissions` is limited to these disposable fixtures.
