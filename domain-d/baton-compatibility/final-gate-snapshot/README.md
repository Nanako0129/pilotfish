# Runtime-tested Baton Gate snapshot

> Exact pilotfish v1.3.1 policy and eight-role `--agents` payload used by the successful Opus compatibility Gate. The release templates and snapshot match the runtime-tested bytes exactly; prompt provenance records both file bytes and shell-normalized runtime-input bytes. Install pilotfish from [`templates/`](../../../templates/), not from this directory.

| File | Runtime use | Hash convention |
|---|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | Project memory copied above the disposable fixture | SHA-256 of file bytes as stored |
| [`agents.json`](./agents.json) | Value passed through `--agents` | SHA-256 after shell command substitution strips the repository trailing newline |

The successful final Gate used Claude Code 2.1.217, native first-party authentication, Fast mode off, explicit `--model opus`, and base HEAD `4d65cc94b59acec2debec37983ad0a021440d643`. Policy/snapshot SHA-256 is `7ff86564cd4cd8469cf3d24646fd395c57be09dc1fc7e1efa9d0d77c61ecfb21`; shell-stripped `agents.json` SHA-256 is `e901e16abdca03ea5f55e3d86f8726fcfa984488305e304c7a382426cd6b7c61`. Prompt hashes, transcript hash, invocation metrics, the prior v1.3.0 final Gate, and failed/superseded attempts are recorded additively in [`../results.json`](../results.json).

The successful lifecycle returned `READY` for Plan readiness and `CONFIRMED` for outcome verification. The Gate establishes compatibility and exact-byte provenance only. It is not an efficiency, latency, cost, or A/B benchmark; the motivating field observations came from remora sessions routed to GPT-5.6.

Historical records remain additive in [`../results.json`](../results.json): v1.3.0 under `previous_final_gate`, the earlier `40f3815` candidate, and summary-only v1.2.1 / v1.2.0 release Gates.

## 中文

> 這是成功的 Opus 相容性 Gate 所使用 pilotfish v1.3.1 policy 與八角色 `--agents` payload 精確副本。發布 templates 與 snapshot 和 runtime 實測 bytes 完全一致；prompt provenance 分別記錄 file bytes 與 shell 正規化後的 runtime-input bytes。安裝時請使用 [`templates/`](../../../templates/)，不要從本目錄安裝。

| 檔案 | Runtime 用途 | Hash 規則 |
|---|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | 複製到可丟棄 fixture 上層的 project memory | 直接計算 repo 內 file bytes 的 SHA-256 |
| [`agents.json`](./agents.json) | 透過 `--agents` 傳入 | Shell command substitution 去掉 repo 尾端 newline 後再計算 SHA-256 |

成功的 final Gate 使用 Claude Code 2.1.217、原生 first-party authentication、Fast mode 關閉、明確 `--model opus`，以及 base HEAD `4d65cc94b59acec2debec37983ad0a021440d643`。Policy／snapshot SHA-256 是 `7ff86564cd4cd8469cf3d24646fd395c57be09dc1fc7e1efa9d0d77c61ecfb21`；shell-stripped `agents.json` SHA-256 是 `e901e16abdca03ea5f55e3d86f8726fcfa984488305e304c7a382426cd6b7c61`。Prompt hashes、transcript hash、invocation metrics、上一筆 v1.3.0 final Gate 與失敗／被取代嘗試都 additive 記錄於 [`../results.json`](../results.json)。

成功 lifecycle 的 Plan readiness 回覆 `READY`，outcome verification 回覆 `CONFIRMED`。這項 Gate 只建立相容性與 exact-byte provenance，不是效率、延遲、成本或 A/B benchmark；政策的現場依據來自 remora／GPT-5.6 routing 的 field observations。

歷史記錄持續 additive 保留於 [`../results.json`](../results.json)：v1.3.0 的 `previous_final_gate`、較早的 `40f3815` candidate，以及 summary-only v1.2.1／v1.2.0 release Gates。
