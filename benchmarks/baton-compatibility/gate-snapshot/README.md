# Baton Gate snapshot

> Evidence only — do not install these files as the current pilotfish policy. They preserve the exact working-tree inputs used by the published compatibility Gate. Later fixes supersede the snapshot's long-process instructions.

| File | Runtime use | Hash convention |
|---|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | Project memory copied above the disposable fixture | SHA-256 of the file bytes as stored |
| [`agents.json`](./agents.json) | Value passed to Claude Code through `--agents` | SHA-256 after shell command substitution strips the repository trailing newline |

The recorded hashes and current-template hashes are separate in [`../results.json`](../results.json). Reproduction commands and limitations are in the [compatibility report](../README.md).

## 中文

> 這些檔案只用於證據稽核，請勿當成目前 pilotfish policy 安裝。它們保留公開相容性 Gate 實測時的精確 working-tree inputs；後續修正已取代 snapshot 內的 long-process 指引。

| 檔案 | Runtime 用途 | Hash 規則 |
|---|---|---|
| [`CLAUDE.md`](./CLAUDE.md) | 複製到可丟棄 fixture 上層的 project memory | 直接計算 repo 內 file bytes 的 SHA-256 |
| [`agents.json`](./agents.json) | 透過 `--agents` 傳給 Claude Code | Shell command substitution 去掉 repo 尾端 newline 後再計算 SHA-256 |

實測 snapshot 與目前 templates 的 hashes 分開記錄於 [`../results.json`](../results.json)；重現命令與限制請見[相容性報告](../README.zh-TW.md)。
