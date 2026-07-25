# Prompt compression Gate

## Scope and claim

This Gate binds the v1.3.4 prompt-compression candidate to exact source bytes,
static contracts, one runtime context census, and behavioral observations.
The candidate shortens the always-loaded orchestration policy and all eight
role bodies without changing role frontmatter.

> The byte and input-token reductions are measured. One small, explicitly
> directed lifecycle passed; the large lifecycle remained `REVISE`, so full
> behavioral parity is not claimed. Client cost fields are observations, not
> invoices or an efficiency A/B.

## Candidate identity

| Surface | Original | Candidate | Reduction |
|---|---:|---:|---:|
| Orchestration policy | 16,874 bytes | 12,714 bytes | 24.653% |
| Eight agent bodies + frontmatter | 15,686 bytes | 13,601 bytes | 13.292% |
| Combined templates | 32,560 bytes | 26,315 bytes | 19.180% |

The source baseline is
`ae5a7b55e7ac1eaa7ab31c66dba901be35ca7e26`. The candidate policy hashes to
`7657daa3…cbb31e`; the generated shell-normalized `--agents` payload hashes to
`cf262ac3…c35e`. Exact per-role hashes live in
[`results.json`](./results.json).

## Current Gate status

| Gate | Result | Cost field |
|---|---|---:|
| Static contracts | 29/29 passed; `git diff --check` passed | — |
| Haiku context census | 747 fewer input tokens in the one-run total | $0.0433408 |
| Candidate mechanical cell | 12/12 correctness; 0 dispatch | $0.713846 |
| Uncompressed v1.3.3 control | Same 0-dispatch session blocker | $0.5371145 |
| Candidate bug cell | 0 dispatch, one source file, 2/2 passed | $0.296559 |
| Explicit lifecycle | Baton + two scouts + three fresh Plan reviews; paused at `REVISE`, zero writes | $1.94195125 |
| Small explicit lifecycle | `READY` → approval → sole `mech-executor` writer → 12/12 → fresh `CONFIRMED` | $1.07153025 |
| **Campaign total** | **Completed under the $20 cap** | **$4.6043418** |

Claude Code 2.1.220 told both the compressed candidate and unchanged v1.3.3
control not to spawn unless the user prompt explicitly requested it. That
invalidates the cue-free topology claim for both inputs; it is not attributed
to compression. The explicit lifecycle proved named-role reachability, model
routing, background scouts, readiness output, and the two-`REVISE` stop, but
its large envelope did not reach `READY`.

A materially smaller Plan epoch then passed in two invocations on the exact
candidate bytes. One fresh Opus 5 `plan-verifier` returned `READY` before any
write. After approval, one Sonnet 5 `mech-executor` exclusively changed the 12
allowed adapter files, the main session wrote no source, `npm test` passed
12/12, and a fresh Opus 5 `verifier` returned `CONFIRMED`. This establishes
small-lifecycle compatibility for that input only. It does not establish
large-Plan convergence, spontaneous activation, remediation loops, security
behavior, or runtime coverage for `Explore`, `executor`, `security-reviewer`,
and `security-executor`.

## Reproduction

The small lifecycle reuses the repository-owned mechanical fixture and the
exact [`gate-snapshot`](./gate-snapshot/) inputs:

```bash
SOURCE=/path/to/pilotfish
ROOT="$(mktemp -d /tmp/pilotfish-small-lifecycle.XXXXXX)"
WORK="$ROOT/fixture"
SNAPSHOT="$SOURCE/benchmarks/prompt-compression/gate-snapshot"
SESSION_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"

cp -R "$SOURCE/benchmarks/dispatch-brake/positive-controls/mechanical/fixture" "$WORK"
cp "$SNAPSHOT/CLAUDE.md" "$WORK/CLAUDE.md"
git -C "$WORK" init -q
git -C "$WORK" add .
git -C "$WORK" -c user.name=pilotfish-gate \
  -c user.email=pilotfish-gate@example.invalid commit -qm baseline

cd "$WORK"
claude --dangerously-skip-permissions -p --output-format stream-json --verbose \
  --max-budget-usd 3 --session-id "$SESSION_ID" --model opus --effort high \
  --setting-sources project,local --strict-mcp-config \
  --agents "$(<"$SNAPSHOT/agents.json")" \
  "$(<"$SOURCE/benchmarks/prompt-compression/prompts/small-lifecycle-plan.txt")"

claude --dangerously-skip-permissions -p --output-format stream-json --verbose \
  --max-budget-usd 3 --resume "$SESSION_ID" --model opus --effort high \
  --setting-sources project,local --strict-mcp-config \
  --agents "$(<"$SNAPSHOT/agents.json")" \
  "$(<"$SOURCE/benchmarks/prompt-compression/prompts/small-lifecycle-approve.txt")"
```

The other exact prompts are under [`prompts/`](./prompts/).
[`results.json`](./results.json) records policy, payload, prompt, and raw-stream
hashes for every completed or stopped observation.

> `--dangerously-skip-permissions` is limited to the new disposable fixture.
