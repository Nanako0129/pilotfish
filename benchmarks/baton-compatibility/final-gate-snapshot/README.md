# Final Baton Gate snapshot

> Evidence copy of the exact pilotfish v1.2.1 policy and eight-role `--agents` payload used by the final Gate. The release templates match these runtime-tested bytes exactly. Install pilotfish from [`templates/`](../../../templates/), not from this directory.

| File | Runtime use | Hash convention |
|---|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | Project memory copied above the disposable fixture | SHA-256 of file bytes as stored |
| [`agents.json`](./agents.json) | Value passed through `--agents` | SHA-256 after shell command substitution strips the repository trailing newline |

The hashes, role/model observations, timing, and disclosed limits are in [`../results.json`](../results.json). The earlier six-role Gate remains under [`../gate-snapshot/`](../gate-snapshot/) as superseded evidence rather than being rewritten. The previous v1.2.0 final snapshot remains available in Git history at commit `1251465`.

## 中文

> 這是最終 Gate 所使用 pilotfish v1.2.1 policy 與八角色 `--agents` payload 的精確證據副本。發布 templates 與 runtime 實測 bytes 完全相同。安裝時請使用 [`templates/`](../../../templates/)，不要從本目錄安裝。

| 檔案 | Runtime 用途 | Hash 規則 |
|---|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | 複製到可丟棄 fixture 上層的 project memory | 直接計算 repo 內 file bytes 的 SHA-256 |
| [`agents.json`](./agents.json) | 透過 `--agents` 傳入 | Shell command substitution 去掉 repo 尾端 newline 後再計算 SHA-256 |

Hashes、角色／模型觀察、時間與已揭露限制都在 [`../results.json`](../results.json)。較早的六角色 Gate 保留於 [`../gate-snapshot/`](../gate-snapshot/) 作為 superseded evidence，不改寫歷史。上一版 v1.2.0 的最終 snapshot 仍可由 Git commit `1251465` 取得。
