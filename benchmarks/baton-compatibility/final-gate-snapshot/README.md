# Final Baton Gate snapshot

> Evidence copy of the exact policy and eight-role `--agents` payload used by the final capability-separated Gate. Its policy retains the v1.1.6 candidate stamp used at runtime; the change was reclassified as v1.2.0 before release, whose policy differed only in that inert version comment. The v2 plugin later changed delivery and routing while preserving the phase gates. Follow the current [root README](../../../README.md) to install pilotfish; never install from this snapshot.

| File | Runtime use | Hash convention |
|---|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | Project memory copied above the disposable fixture | SHA-256 of file bytes as stored |
| [`agents.json`](./agents.json) | Value passed through `--agents` | SHA-256 after shell command substitution strips the repository trailing newline |

The hashes, role/model observations, timing, and disclosed limits are in [`../results.json`](../results.json). The earlier six-role Gate remains under [`../gate-snapshot/`](../gate-snapshot/) as superseded evidence rather than being rewritten.

## 中文

> 這是 capability split 後最終 Gate 所使用 policy 與八角色 `--agents` payload 的精確證據副本。Policy 保留 runtime 實測時的 v1.1.6 candidate stamp；發布前已重分類為 v1.2.0，當時的 policy 唯一差異是這行不影響執行的版本註解。後續 v2 plugin 改變了交付與 routing，同時保留 phase gates。安裝 pilotfish 請依照目前的 [root README](../../../README.zh-TW.md)，不要從本 snapshot 安裝。

| 檔案 | Runtime 用途 | Hash 規則 |
|---|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | 複製到可丟棄 fixture 上層的 project memory | 直接計算 repo 內 file bytes 的 SHA-256 |
| [`agents.json`](./agents.json) | 透過 `--agents` 傳入 | Shell command substitution 去掉 repo 尾端 newline 後再計算 SHA-256 |

Hashes、角色／模型觀察、時間與已揭露限制都在 [`../results.json`](../results.json)。較早的六角色 Gate 保留於 [`../gate-snapshot/`](../gate-snapshot/) 作為 superseded evidence，不改寫歷史。
