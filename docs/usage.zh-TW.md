# 使用 pilotfish

這份文件集中說明日常的模型選擇、委派行為、相容性與停用方式。安裝與檔案變更規則仍以
[安裝 runbook](../install/AGENT-INSTALL.md) 為準；精確的編排行為仍以
[政策範本](../templates/claude-md.orchestration.md) 為準。

[English](./usage.md)

## 目錄

- [模型分流](#模型分流)
- [委派行為](#委派行為)
- [設定與相容性](#設定與相容性)
- [調校](#調校)
- [長時間執行與驗證](#長時間執行與驗證)
- [停用、更新或移除](#停用更新或移除)

## 模型分流

| 需求 | 設定或操作 | 效果 |
|---|---|---|
| 預設主 session | `model: "opus"` | 使用 provider 解析的 Opus family alias；除非你批准，installer 會保留既有選擇 |
| 明確使用 Fable | `/model fable` | 只切換目前 session，不改各角色 agent 的綁定 |
| 降低主 session 額度消耗 | `/model opusplan` | 規劃 turn 使用 Opus，主 session 的執行 turn 使用 Sonnet |
| 明確要求 1M context | `model: "opus[1m]"` | 在 provider 支援時要求官方文件列出的 1M Opus alias |
| 主模型不可用 | `fallbackModel: ["sonnet"]` | 過載或不可用時 fallback；不處理驗證、計費或 rate-limit 錯誤 |

每個角色的模型與 effort 都在該 agent 的 frontmatter。除非你確實要覆寫所有角色，否則不要設定
`CLAUDE_CODE_SUBAGENT_MODEL`；它也會覆蓋 Opus review 與 security roles。

## 委派行為

Claude Code 較高優先級的指示可能壓制 Agent dispatch。需要 pilotfish lifecycle 時，請明確寫入：

```text
Use pilotfish. Follow its dispatch brake: keep direct work in the main session
and call the named agents only when the policy selects delegation.
```

| 工作形狀 | 預期 owner |
|---|---|
| 小型、局部、穩定工作，或單一緊密耦合的未知 bug | 主 session |
| 有完整 one-shot brief 的穩定多檔機械性重複工作 | `mech-executor` |
| 已批准且需要局部判斷的實作 | `executor` |
| 批准後的資安敏感實作 | `security-executor` |
| 由風險觸發的 Plan 或 outcome challenge | `plan-verifier`、`security-reviewer` 或 `verifier` |

[Cue-free 證據](../benchmarks/spontaneous-dispatch/README.zh-TW.md) 記錄自動委派在哪些格發生或未發生。
這些是有邊界的觀察，不是 dispatch rate，也不是 active system-prompt bytes 的證明。

## 設定與相容性

| 情境 | 要檢查什麼 |
|---|---|
| 自訂設定根目錄 | 所有 `~/.claude/` 路徑會移到 `CLAUDE_CONFIG_DIR`；installer 會在寫入前解析 |
| 專案層 `CLAUDE.md` | Claude Code 會疊加專案與使用者記憶；pilotfish 不會寫入專案 |
| 自訂 `Explore` 角色 | 將偵察固定到 Haiku，但與內建角色不同，它會載入使用者記憶；policy 在 subagent 角色內自我停用，以限制這項開銷 |
| `availableModels` 白名單 | 納入 `opus`、`fable`、`sonnet`、`haiku` 與選定的主模型，否則角色 alias 可能靜默繼承主模型 |
| Managed／企業設定 | Managed model、allowlist 與同名 agent 優先於 user-level install；pilotfish 不會繞過它們 |
| `claude-router` | 不要啟用 `forceRoute`，它會覆寫 agent frontmatter；`restoreDelegation` 會移除另一個被追蹤的 delegation injection |
| Delegation-planning skill | [Baton](https://github.com/cablate/baton) 等工具可以塑造工作拓撲；具名角色、模型分流、approval 與 verifier contract 仍由 pilotfish 負責 |

## 調校

| 目標 | 調整方式 |
|---|---|
| 減少額度消耗 | 使用 `/model opusplan`；偵察與機械性角色維持預設 low effort |
| 增加主 session 判斷力 | 從 `high` effort 開始，只有在額度或延遲更重要時再降低 |
| 改單一角色 tier | 只改該 agent 檔的 `model:` frontmatter；政策只寫角色，不寫模型 |
| 讓更多工作留在主 session | 要求 inline 執行；這只停用 optional execution delegation，不停用 mandatory risk review |
| 判斷 spawn overhead | 每個 agent 都會建立新 context，需支付重建與整合成本；只有整體效益為正才委派 |

模型經濟、官方機制與實測限制請見 [研究報告](./research.zh-TW.md)、
[設計理由](./design.md) 與 [行為 benchmark](../benchmarks/dispatch-brake/README.zh-TW.md)。

## 長時間執行與驗證

| 狀態 | 意義 |
|---|---|
| `AUTO` | 在已批准 scope 內繼續可逆工作；不新增 commit、publish、install、破壞性、外部操作或付費權限 |
| `ASK` | 透過原生輸入或 `PAUSED_NEEDS_USER` 暫停等待決策 |
| P0 | 凍結受影響的 slice 與 dependent work |
| P1 或 introduced P2 | 在批准 scope 內修正，否則暫停；P3/P4 只作建議 |
| `verifier` verdict | 供主 session 判斷的證據，不自動授予 scope 或實作權限 |

正常 verification 是一輪完整檢查，加上可重現 blocker 修正後的一次定向複驗。長時間 command
由主 session 擁有；leaf agent 交回精確 command 與 working context，不自行 detach process。

## 停用、更新或移除

| 操作 | 方法 |
|---|---|
| 更新 | 重跑釘選版本的安裝 prompt，並依 runbook 的 **Updating an existing install** 執行 |
| 停用 optional execution delegation | 要求主 session inline 執行 |
| 只對一個 repo 停用 | 用不含 pilotfish policy block 的另一個 `CLAUDE_CONFIG_DIR` 啟動該 repo |
| 全域停用 policy | 移除或註解 `pilotfish:begin/end` block，再開新 session |
| 移除 | 依 runbook 的 **Uninstall** section 執行，安全處理 agent 檔與 settings backup |
