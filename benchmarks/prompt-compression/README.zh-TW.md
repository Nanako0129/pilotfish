# Prompt 壓縮 Gate

## 範圍與主張

這組 Gate 把 v1.3.4 prompt 壓縮 candidate 綁定到精確 source bytes、靜態
contract、一次 runtime context census 與行為觀察。Candidate 縮短每個
session 都會載入的 orchestration policy，以及八個角色 body；角色
frontmatter 不變。

> Byte 與 input-token 降幅是實測值。一個明確要求的小型 lifecycle 已通過；
> 大型 lifecycle 仍停在 `REVISE`，因此不主張完整行為等價。Client cost
> field 是觀察值，不是 invoice，也不是效率 A/B。

## Candidate 身分

| Surface | 原始 | Candidate | 降幅 |
|---|---:|---:|---:|
| Orchestration policy | 16,874 bytes | 12,714 bytes | 24.653% |
| 八個 agent body + frontmatter | 15,686 bytes | 13,601 bytes | 13.292% |
| Templates 合計 | 32,560 bytes | 26,315 bytes | 19.180% |

Source baseline 是
`ae5a7b55e7ac1eaa7ab31c66dba901be35ca7e26`。Candidate policy SHA-256
為 `7657daa3…cbb31e`；builder 產生並移除尾端換行的 `--agents` payload
SHA-256 為 `cf262ac3…c35e`。各角色完整 hash 記在
[`results.json`](./results.json)。

## 目前 Gate 狀態

| Gate | 結果 | Cost field |
|---|---|---:|
| 靜態 contract | 29/29 通過；`git diff --check` 通過 | — |
| Haiku context census | 單次 total input 減少 747 tokens | $0.0433408 |
| Candidate mechanical cell | 12/12 correctness；0 dispatch | $0.713846 |
| 未壓縮 v1.3.3 control | 相同的 0-dispatch session blocker | $0.5371145 |
| Candidate bug cell | 0 dispatch、只改一個 source file、2/2 通過 | $0.296559 |
| Explicit lifecycle | Baton + 兩個 scouts + 三次 fresh Plan review；停在 `REVISE`、零寫入 | $1.94195125 |
| 小型 explicit lifecycle | `READY` → 核准 → 唯一 `mech-executor` writer → 12/12 → fresh `CONFIRMED` | $1.07153025 |
| **Campaign 合計** | **在 $20 上限內完成** | **$4.6043418** |

Claude Code 2.1.220 對壓縮 candidate 與未改動的 v1.3.3 control 都表示：
除非 user prompt 明確要求，否則不能 spawn。因此兩者的 cue-free topology
claim 都不成立，不能把這個結果歸因於壓縮。Explicit lifecycle 則證明
named-role 可達、model routing、background scouts、readiness output 與兩次
`REVISE` 停止條件仍能運作，但大型 envelope 尚未到 `READY`。

接著把工作切成 materially smaller Plan epoch，使用同一組 candidate bytes
跑兩次 invocation：fresh Opus 5 `plan-verifier` 在零寫入狀態回 `READY`；
核准後由單一 Sonnet 5 `mech-executor` 獨占修改 12 個允許的 adapter，
main session 沒寫 source，`npm test` 12/12 通過，fresh Opus 5 `verifier`
回 `CONFIRMED`。這只證明該 input 的小型 lifecycle 相容；不證明大型 Plan
收斂、spontaneous activation、修正循環、安全路徑，也不主張 `Explore`、
`executor`、`security-reviewer`、`security-executor` 已有 runtime coverage。

## 重現方式

小型 lifecycle 重用 repo 既有 mechanical fixture 與精確
[`gate-snapshot`](./gate-snapshot/) inputs：

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

其他 exact prompts 都在 [`prompts/`](./prompts/)。
[`results.json`](./results.json) 記錄所有完成或停止觀察的 policy、payload、
prompt 與 raw-stream hashes。

> `--dangerously-skip-permissions` 僅限這個新建的 disposable fixture。
