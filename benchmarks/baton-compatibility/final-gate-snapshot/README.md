# Runtime-tested Baton Gate snapshot

> Exact pilotfish v1.3.1 policy and eight-role `--agents` payload used by the successful Opus compatibility Gate. This directory is immutable historical runtime-tested evidence; the current policy and role templates have since changed and are tracked separately by the sibling Baton activation Gate and current release hashes. Prompt provenance records both file bytes and shell-normalized runtime-input bytes. Install pilotfish from [`templates/`](../../../templates/), not from this directory.

| File | Runtime use | Hash convention |
|---|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | Project memory copied above the disposable fixture | SHA-256 of file bytes as stored |
| [`agents.json`](./agents.json) | Value passed through `--agents` | SHA-256 after shell command substitution strips the repository trailing newline |

The successful final Gate used Claude Code 2.1.217, native first-party authentication, Fast mode off, explicit `--model opus`, and base HEAD `4d65cc94b59acec2debec37983ad0a021440d643`. Policy/snapshot SHA-256 is `7ff86564cd4cd8469cf3d24646fd395c57be09dc1fc7e1efa9d0d77c61ecfb21`; shell-stripped `agents.json` SHA-256 is `e901e16abdca03ea5f55e3d86f8726fcfa984488305e304c7a382426cd6b7c61`. Prompt hashes, transcript hash, invocation metrics, the prior v1.3.0 final Gate, and failed/superseded attempts are recorded additively in [`../results.json`](../results.json).

The successful lifecycle returned `READY` for Plan readiness and `CONFIRMED` for outcome verification. The Gate establishes compatibility and exact-byte provenance for this snapshot only. Current policy SHA `17d272b6…b39bf` is covered at the activation, four-scout dispatch, ownership, collection, and output-shape boundary by [`../../baton-dispatch-effect/`](../../baton-dispatch-effect/). Neither Gate is an efficiency, latency, cost, or population-frequency benchmark.

Historical records remain additive in [`../results.json`](../results.json): v1.3.0 under `previous_final_gate`, the earlier `40f3815` candidate, and summary-only v1.2.1 / v1.2.0 release Gates.

> **Post-Gate frontmatter update ([#18](https://github.com/Nanako0129/pilotfish/issues/18)):** the `executor` role's model changed from Opus to Sonnet after this Gate ran. This historical `agents.json` therefore remains at the exact `e901e16a…` bytes injected during the Gate; the current release payload is generated separately from `templates/agents` and hashes to `0b42c137…`. The recorded run never dispatched `executor`, so its observations remain accurate for the roles exercised. Later live replays accepted the changed payload but dispatched the distinct `mech-executor` or `scout` roles; the changed `executor` itself was not live-exercised.

## 中文

> 這是成功的 Opus 相容性 Gate 所使用 pilotfish v1.3.1 policy 與八角色 `--agents` payload 精確副本。本目錄是不可改寫的 historical runtime-tested evidence；目前 policy 與角色 templates 後來已有變更，另由相鄰 Baton activation Gate 與 current release hashes 記錄。Prompt provenance 分別記錄 file bytes 與 shell 正規化後的 runtime-input bytes。安裝時請使用 [`templates/`](../../../templates/)，不要從本目錄安裝。

| 檔案 | Runtime 用途 | Hash 規則 |
|---|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | 複製到可丟棄 fixture 上層的 project memory | 直接計算 repo 內 file bytes 的 SHA-256 |
| [`agents.json`](./agents.json) | 透過 `--agents` 傳入 | Shell command substitution 去掉 repo 尾端 newline 後再計算 SHA-256 |

成功的 final Gate 使用 Claude Code 2.1.217、原生 first-party authentication、Fast mode 關閉、明確 `--model opus`，以及 base HEAD `4d65cc94b59acec2debec37983ad0a021440d643`。Policy／snapshot SHA-256 是 `7ff86564cd4cd8469cf3d24646fd395c57be09dc1fc7e1efa9d0d77c61ecfb21`；shell-stripped `agents.json` SHA-256 是 `e901e16abdca03ea5f55e3d86f8726fcfa984488305e304c7a382426cd6b7c61`。Prompt hashes、transcript hash、invocation metrics、上一筆 v1.3.0 final Gate 與失敗／被取代嘗試都 additive 記錄於 [`../results.json`](../results.json)。

成功 lifecycle 的 Plan readiness 回覆 `READY`，outcome verification 回覆 `CONFIRMED`。這項 Gate 只為此 snapshot 建立相容性與 exact-byte provenance。目前 policy SHA `17d272b6…b39bf` 則由 [`../../baton-dispatch-effect/`](../../baton-dispatch-effect/) 在 activation、四 scout dispatch、ownership、collection 與 output-shape boundary 覆蓋。兩項 Gate 都不是效率、延遲、成本或 population-frequency benchmark。

歷史記錄持續 additive 保留於 [`../results.json`](../results.json)：v1.3.0 的 `previous_final_gate`、較早的 `40f3815` candidate，以及 summary-only v1.2.1／v1.2.0 release Gates。

> **Gate 之後的 frontmatter 更新（[#18](https://github.com/Nanako0129/pilotfish/issues/18)）：** 這次 Gate 跑完之後，`executor` 角色的 model 從 Opus 改成 Sonnet。因此這份歷史 `agents.json` 保留 Gate 當時實際注入的 `e901e16a…` bytes；目前 release payload 另由 `templates/agents` 產生，hash 是 `0b42c137…`。這個 run 從未派送過 `executor`，所以它對實際執行角色的觀察仍然準確。後續 live replays 接受 changed payload，但派出的是不同的 `mech-executor` 或 `scout` roles；被修改的 `executor` 本身沒有 live-exercise。
