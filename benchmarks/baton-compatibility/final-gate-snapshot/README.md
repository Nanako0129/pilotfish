# Runtime-tested Baton Gate snapshot

> Exact pilotfish v1.3.0 policy and eight-role `--agents` payload used by the successful native compatibility Gate. The release templates and snapshot match the runtime-tested bytes exactly; prompt provenance records both file bytes and shell-normalized runtime-input bytes. Install pilotfish from [`templates/`](../../../templates/), not from this directory.

| File | Runtime use | Hash convention |
|---|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | Project memory copied above the disposable fixture | SHA-256 of file bytes as stored |
| [`agents.json`](./agents.json) | Value passed through `--agents` | SHA-256 after shell command substitution strips the repository trailing newline |

The successful final Gate used Claude Code 2.1.215, native first-party authentication, Fast mode off, and base HEAD `a38dd2dde000441b24881fa49495e545ff21b9e6`. Policy/snapshot SHA-256 is `d41a9d41db21e97176e82614dcfd4d80cba670ec28136666cc96906dd5efda35`; shell-stripped `agents.json` SHA-256 is `27b6f6df289715f302a1022b428c62ddf7a7dadb2e0cae4f9eb4197c5bd916de`. Prompt file hashes, shell-normalized runtime-input hashes, transcript hash, invocation metrics, and the failed candidate attempt are recorded in [`../results.json`](../results.json). The previous release evidence is v1.2.1 under `previous_release_gate` (summary-only); v1.2.0 is restored under `historical_release_gate` (summary-only). The 2026-07-20 v1.3.0 candidate from commit `40f3815` remains under `superseded_candidate_gate`, while the budget-exhausted prompt attempt remains under `failed_candidate_gate`.

The successful lifecycle returned `READY` for Plan readiness and `CONFIRMED` for outcome verification. The Gate establishes compatibility and exact-byte provenance only. It is not an efficiency, latency, cost, or A/B benchmark; the motivating field observations came from remora sessions routed to GPT-5.6.

> **Post-Gate frontmatter update ([#18](https://github.com/Nanako0129/pilotfish/issues/18)):** the `executor` role's model changed from Opus to Sonnet after this Gate ran, so `agents.json` has been regenerated to byte-match current templates and the hash above reflects that change (previously `e901e16abdca03ea5f55e3d86f8726fcfa984488305e304c7a382426cd6b7c61`, see `results.json`'s `post_gate_role_frontmatter_change`). The recorded transcript, turns, and verdicts below are unaffected: this fixture's `agent_calls` never dispatched `executor` (only `scout`, `plan-verifier`, `mech-executor`, and `verifier` ran), so no observed behavior in this record used the changed role. A fresh live Gate that specifically exercises the new Sonnet `executor` has not been separately run.

## 中文

> 這是成功的原生相容性 Gate 所使用 pilotfish v1.3.0 policy 與八角色 `--agents` payload 精確副本。發布 templates 與 snapshot 和 runtime 實測 bytes 完全一致；prompt provenance 分別記錄 file bytes 與 shell 正規化後的 runtime-input bytes。安裝時請使用 [`templates/`](../../../templates/)，不要從本目錄安裝。

| 檔案 | Runtime 用途 | Hash 規則 |
|---|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | 複製到可丟棄 fixture 上層的 project memory | 直接計算 repo 內 file bytes 的 SHA-256 |
| [`agents.json`](./agents.json) | 透過 `--agents` 傳入 | Shell command substitution 去掉 repo 尾端 newline 後再計算 SHA-256 |

成功的 final Gate 使用 Claude Code 2.1.215、原生 first-party authentication、Fast mode 關閉，以及 base HEAD `a38dd2dde000441b24881fa49495e545ff21b9e6`。Policy／snapshot SHA-256 是 `d41a9d41db21e97176e82614dcfd4d80cba670ec28136666cc96906dd5efda35`；shell-stripped `agents.json` SHA-256 是 `27b6f6df289715f302a1022b428c62ddf7a7dadb2e0cae4f9eb4197c5bd916de`。Prompt file hashes、shell 正規化 runtime-input hashes、transcript hash、invocation metrics 與失敗 candidate 嘗試都記錄於 [`../results.json`](../results.json)。上一個 release evidence 是 `previous_release_gate` 的 v1.2.1（summary-only）；v1.2.0 已還原至 `historical_release_gate`（summary-only）。2026-07-20、commit `40f3815` 的 v1.3.0 candidate 保留在 `superseded_candidate_gate`；budget exhausted 的 prompt 嘗試保留在 `failed_candidate_gate`。

成功 lifecycle 的 Plan readiness 回覆 `READY`，outcome verification 回覆 `CONFIRMED`。這項 Gate 只建立相容性與 exact-byte provenance，不是效率、延遲、成本或 A/B benchmark；政策的現場依據來自 remora／GPT-5.6 routing 的 field observations。

> **Gate 之後的 frontmatter 更新（[#18](https://github.com/Nanako0129/pilotfish/issues/18)）：** 這次 Gate 跑完之後，`executor` 角色的 model 從 Opus 改成 Sonnet，因此 `agents.json` 已重新產生以與目前 templates 保持 byte 一致，上面的 hash 也反映這項變動（原本是 `e901e16abdca03ea5f55e3d86f8726fcfa984488305e304c7a382426cd6b7c61`，詳見 `results.json` 的 `post_gate_role_frontmatter_change`）。下方記錄的 transcript、turns、verdicts 不受影響：這個 fixture 的 `agent_calls` 從未派送過 `executor`（只跑了 `scout`、`plan-verifier`、`mech-executor`、`verifier`），所以這筆記錄中沒有任何觀察到的行為使用到被改動的角色。目前還沒有另外針對新的 Sonnet `executor` 重新跑一次 live Gate。
