# Verifier boundary Gate

> 這是 exact pilotfish v1.3.6 candidate 在原生 Claude Code 的單次
> reachability observation，不建立 activation frequency、品質、延遲或成本效率結論。

## 結果

兩個通過的 control 都使用 README 已公開的 opt-in：
`Use pilotfish and delegate eligible work to the named agents.`

| Control | 觀察到的 routing | Acceptance | Client-reported cost |
|---|---|---|---:|
| Schema migration | `plan-verifier` → 明確 approval stop → `executor` → primary tests → fresh `verifier` | `READY`；批准前零寫入；5/5 tests；只改 `store.mjs` 與 `store.test.mjs`；`CONFIRMED` | $1.49902485 |
| Routine docs | Main session 直接修改；沒有 Agent call | 1/1 test；只修指定的 README typo | $0.32835250 |
| Post-cap Plan control | `plan-verifier` × 3 | `REVISE` → `REVISE` → ownership fix／new epoch → closing `READY`；零寫入 | $0.99777300 |

因此，exact candidate 在明確 agent opt-in 下到達 independent-review boundary
兩側：serialization change 有 Plan 與 outcome review，routine docs 維持直接
處理，user-directed 三回合 Plan control 則在兩次 `REVISE` 後停止，接著只做
一次 closing check。所有 Agent call 都未傳 invocation-level model
override。Main session 與兩個 review role 是 Opus 5；`executor` 是 Sonnet 5。

目前 passing controls reported $2.82515035。加上較早的 candidate Gate、公開的
operator-policy failure 與零成本 quota failure，完整 campaign reported
$5.16072710。

這不是 cue-free 宣稱。這個 Claude Code account 有較高優先級的 operator
contract：使用者沒有明確要求時禁止 Agent call。因此 neutral schema prompt
直接修改 fixture，不能算 Gate evidence。該 run 成本為 $0.51322950，與先前
零成本 429 attempt 都保留在 [`results.json`](./results.json)。

## Exact inputs

| Input | SHA-256 |
|---|---|
| [`gate-snapshot-v2/CLAUDE.md`](./gate-snapshot-v2/CLAUDE.md) | `ae771c9b43ad985f7ad1e520cd6e021c69e13aac3bd6a60a8edacd1d386f0e82` |
| [`gate-snapshot-v2/agents.json`](./gate-snapshot-v2/agents.json) file bytes | `8df823840683dc65c6528ce568d35d0c14deee5a0290db532bdca63b3885a0a7` |
| `agents.json` shell-normalized runtime input | `e5e7fa1595c2231f6954f86720c734ab064ce901ab141c3e6431d07dd4335123` |

Disposable baseline 在 [`fixture/`](./fixture/)；neutral 與 explicit prompts
在 [`prompts/`](./prompts/)；`results.json` 以 hash 綁定每個 prompt 與 raw
stream，並記錄 final artifact hash、route、cost、completion 與 acceptance。

[`gate-snapshot/`](./gate-snapshot/) 保留 follow-up verifier prompt 修正前的第一份
passing candidate；它是 historical evidence，不是目前 installable payload。

## 重跑

分別把 `fixture/` 複製成 schema 與 routine 的 disposable Git repo，把
`gate-snapshot-v2/CLAUDE.md` 放進各自 repo root 並提交 clean baseline，再執行：

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

Routine control 使用另一份全新 disposable copy、新 session ID、
`--max-budget-usd 4` 與
[`routine-docs-explicit.txt`](./prompts/routine-docs-explicit.txt)。
另一份 clean copy 依序執行三個 `plan-cap-turn-*.txt` prompt；turn 1 使用新
session ID，turn 2／3 使用 `--resume`。
`--dangerously-skip-permissions` 只用於這些 disposable fixtures。
