# Verifier boundary Gate

> 這是 exact pilotfish v1.3.6 candidate 在原生 Claude Code 的單次
> reachability observation，不建立 activation frequency、品質、延遲或成本效率結論。

## 結果

兩個通過的 control 都使用 README 已公開的 opt-in：
`Use pilotfish and delegate eligible work to the named agents.`

| Control | 觀察到的 routing | Acceptance | Client-reported cost |
|---|---|---|---:|
| Schema migration | `plan-verifier` → 明確 approval stop → `executor` → primary tests → fresh `verifier` | `READY`；批准前零寫入；4/4 tests；只改 `store.mjs` 與 `store.test.mjs`；`CONFIRMED` | $1.33865765 |
| Routine docs | 只有 `mech-executor`；沒有 `plan-verifier` 或 outcome `verifier` | 1/1 test；只修指定的 README typo | $0.48368960 |

因此，exact candidate 在明確 agent opt-in 下到達 independent-review boundary
兩側：serialization change 有 Plan 與 outcome review，routine docs 則跳過兩個
review role。所有 Agent call 都未傳 invocation-level model override。Main
session route 是 Opus 5；`executor`／`mech-executor` 是 Sonnet 5；兩個 review
role 是 Opus 5。

這不是 cue-free 宣稱。這個 Claude Code account 有較高優先級的 operator
contract：使用者沒有明確要求時禁止 Agent call。因此 neutral schema prompt
直接修改 fixture，不能算 Gate evidence。該 run 成本為 $0.51322950，與先前
零成本 429 attempt 都保留在 [`results.json`](./results.json)。

## Exact inputs

| Input | SHA-256 |
|---|---|
| [`gate-snapshot/CLAUDE.md`](./gate-snapshot/CLAUDE.md) | `ae771c9b43ad985f7ad1e520cd6e021c69e13aac3bd6a60a8edacd1d386f0e82` |
| [`gate-snapshot/agents.json`](./gate-snapshot/agents.json) file bytes | `9aa5feb04d062400d414f9e7d31a6e882696f2f73ece01425fe06e74582122eb` |
| `agents.json` shell-normalized runtime input | `0953159df622bcb25c6f298a00d57dd2feea180d0b863e0b946547e5db107f42` |

Disposable baseline 在 [`fixture/`](./fixture/)；neutral 與 explicit prompts
在 [`prompts/`](./prompts/)；`results.json` 以 hash 綁定每個 prompt 與 raw
stream，並記錄 final artifact hash、route、cost、completion 與 acceptance。

## 重跑

分別把 `fixture/` 複製成 schema 與 routine 的 disposable Git repo，把
`gate-snapshot/CLAUDE.md` 放進各自 repo root 並提交 clean baseline，再執行：

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

Routine control 使用另一份全新 disposable copy、新 session ID、
`--max-budget-usd 4` 與
[`routine-docs-explicit.txt`](./prompts/routine-docs-explicit.txt)。
`--dangerously-skip-permissions` 只用於這些 disposable fixtures。
