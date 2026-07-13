# Fable 5 多模型協作研究報告

> English version: [research.md](./research.md)

## 文件目的

這份文件整理 2026 年 7 月初針對「如何最大化 Claude Fable 5 價值」所做的一輪有出處研究：Fable 5 相對 Opus 4.8 的真實強項與不值得用的場景、Claude 訂閱制的配額經濟學、Claude Code 官方提供的多模型協作機制，以及社群的實測數字與模式。pilotfish 的三層架構（見 [design.md](./design.md)）就是這份研究的落地結論。研究方法為四個並行研究代理（官方文件、社群模式、訂閱經濟、Claude Code 機制）加一輪對照 code.claude.com 官方文件的驗證；資料時點為 2026-07-08。

## 目錄

- [Fable 5 的定位與強項](#fable-5-的定位與強項)
- [何時不該用 Fable 5](#何時不該用-fable-5)
- [訂閱制配額經濟學](#訂閱制配額經濟學)
- [Claude Code 官方機制](#claude-code-官方機制)
- [社群實測與模式](#社群實測與模式)
- [Effort 分層](#effort-分層)
- [Prompting 上的世代差異](#prompting-上的世代差異)
- [來源](#來源)

## Fable 5 的定位與強項

| 項目 | 值 |
|---|---|
| Model ID | `claude-fable-5` |
| API 定價 | $10 / $50 per MTok（Opus 4.8 的 2 倍） |
| Context / 輸出 | 1M（預設即最大）/ 128K |
| Tokenizer | 與 Opus 4.8 相同（token 數約略不變） |
| 發布 | 2026-06-09 GA；出口管制短暫下架後 07-01 恢復 |
| 資料保留 | 強制 30 天——ZDR 組織所有請求回 400 |

官方 prompting 指南列出七大優勢領域，核心原則是「**任務越長越複雜，Fable 5 領先幅度越大**」：

| 優勢領域 | 說明 |
|---|---|
| 長時程自主性 | 可持續多日的 goal-directed run |
| First-shot correctness | 規格明確的複雜問題一次到位 |
| 視覺 | 密集技術圖表；會主動用 bash/crop 工具處理模糊、翻轉影像 |
| 企業工作流 | 財務分析、試算表、簡報、文件端到端交付 |
| Code review 與除錯 | Bug-finding recall 顯著高於 Opus 4.8，含 repo 歷史搜尋 |
| 模糊需求 | Navigating ambiguity 明顯較佳 |
| 委派協作 | Dispatch 並維持平行 subagents 更可靠——天生的 orchestrator |

代表性基準：SWE-Bench Pro 80.3%（Opus 4.8 為 69.2%）、Cognition FrontierCode 29.3%（Opus 4.8 為 13.4%）——均為 Anthropic 官方自報數字（自家 scaffolding／system card），尚未經第三方獨立驗證。

## 何時不該用 Fable 5

| 場景 | 理由 | 改用 |
|---|---|---|
| 例行 feature 開發、聚焦除錯、測試生成、PR 例行審查 | 與 Opus 差距小、價格 2 倍 | Opus 4.8 |
| 高流量、延遲敏感管線 | 高 effort 單一請求可跑數分鐘 | Sonnet / Haiku |
| 資安相關（防禦性工作也算） | 安全分類器會誤拒良性工作（<5% sessions，但足以中斷任務） | 釘在 Opus 4.8 |
| ZDR 組織 | 30 天保留為硬性要求 | 不可用 |
| 機械性 token 量大的工作 | 重新命名、跑測試、格式化不需要前沿智慧 | Haiku / Sonnet |

> **提示：** 社群共識的升級守則是「從能可靠完成任務的最便宜模型開始，只有當 Opus 4.8 明顯失敗、中途丟失計畫、或重試燒掉更多總 token 時才升級到 Fable 5」。

## 訂閱制配額經濟學

| 機制 | 內容 |
|---|---|
| 雙層限額 | 5 小時滾動視窗＋每週上限；配額池跨 Claude Code / Claude.ai / Cowork 共用 |
| 雙桶每週制 | 共用的「所有模型」桶＋「**Sonnet 專用**」額外桶（2025-11 起）——Sonnet 除了計入「所有模型」桶外，還有專用桶提供額外額度（現行版本回報兩桶同時扣），並非完全獨立的池子，但實質擴大了 Sonnet 工作的可用量 |
| Fable 5 倍率 | 官方 UI 原文「Uses your limits ~2x faster than Opus」；agentic 重度使用實際更陡（有 Max $200 用戶 13 分鐘燒完 5 小時視窗的極端案例） |
| 相對單價（API 比價） | Fable 5 = Opus 的 2 倍；Sonnet 5 標準價 ≈ 0.6 倍（$3/$15；導入期 $2/$10 至 2026-08-31，約 0.4 倍）；Haiku 4.5 ≈ 0.2 倍 |
| 官方口徑 | 各方案絕對 token 數從未公布；只有倍率（Max 5x / 20x）與 Fable ~2x 為官方說法 |

Fable 5 在訂閱方案內的時間線（截至 2026-07-08）：

| 日期 | 事件 |
|---|---|
| 2026-06-09 | GA，免費含在 Pro/Max/Team（以 ~2x Opus 權重計） |
| 2026-06-12 | 出口管制暫停 |
| 2026-07-01 | 恢復供應，加「最多佔每週限額 50%」上限 |
| 2026-07-07 | 官方宣布延長訂閱內含 5 天 |
| 2026-07-12 之後 | 脫離訂閱限額：需啟用預付 usage credits 以 API 費率（$10/$50）計費；Anthropic 表示目標是算力允許後恢復為訂閱標配 |

> ⚠️ **警告：** 這正是 fallback 設計不可省略的原因。依文件規則，帳號失去 Fable 5 權限後 `best` 解析為最新 Opus；2026 年 6 月停用期的實測行為與此一致——通知橫幅＋新 session 自動改跑 Opus，而**釘死完整 model ID 的人收到硬性 404**。但 7/12 計費邊界的確切 UI（自動降級、錯誤、或啟用 credits 提示）官方尚未發布，且 `fallbackModel` 明確不接計費類錯誤、救不了這種情況——最壞情況是手動切換一次。

## Claude Code 官方機制

以下機制全部經 code.claude.com 官方文件（sub-agents、model-config、settings 頁面）逐條驗證：

| 機制 | 內容 |
|---|---|
| Subagent `model` frontmatter | 接受 alias（`sonnet`/`opus`/`haiku`/`fable`）、完整 model ID、`inherit`（省略即預設 inherit） |
| Subagent `effort` frontmatter | `low`/`medium`/`high`/`xhigh`/`max`，可對單一 agent 覆寫 session effort |
| 全域 agents 目錄 | `~/.claude/agents/`（使用者層）；專案層為 `.claude/agents/`；同名時依優先序解析 |
| 模型解析優先序 | `CLAUDE_CODE_SUBAGENT_MODEL` env → Agent tool 呼叫的 `model` 參數 → frontmatter → 主對話模型 |
| `best` alias | 有 Fable 5 權限就用 Fable 5，否則最新 Opus——內建的前沿降級機制 |
| `fallbackModel`（settings）/ `--fallback-model` | 陣列切換鏈；主模型過載或不可用（非 auth/計費/rate-limit 錯誤）時依序自動切換並通知 |
| `opusplan` alias | Plan mode 用 Opus 思考、離開後切 Sonnet 執行——內建的「強模型想、便宜模型做」 |
| `availableModels`（settings） | 白名單，同時約束主 session、subagent frontmatter、Task 的 model 參數；超出名單的值被靜默跳過改為繼承 |
| `[1m]` 後綴 | 啟用 1M context；文件明列支援 `sonnet`/`opus`/`opusplan` alias 與完整 model ID——`best` 不在列（實測 `best[1m]` 不報錯，但建議用純 `best`；Fable 5 本身預設即 1M） |
| CLAUDE.md 與模型 | **不能**改主模型（settings / `/model` / `--model` 才行）——CLAUDE.md 管的是委派行為政策 |
| 內建 Explore agent | v2.1.198 起繼承主對話模型（Claude API 上以 Opus 封頂）——此發現仍成立。自建同名的*使用者層* agent 可覆寫回 Haiku，但**外掛（plugin）**的 agent 不行（plugin agent 帶命名空間，例如 `pilotfish:Explore`），因此 pilotfish 改以 `PreToolUse` guard hook **封鎖**內建 Explore，並把偵查工作導向 `scout`（釘在 Haiku） |
| 版本釘選 | `ANTHROPIC_DEFAULT_OPUS_MODEL` 等 env 可把 alias 釘到特定版本（third-party provider 部署適用） |

## 社群實測與模式

| 模式 / 實測 | 數字或做法 | 出處 |
|---|---|---|
| **官方第一方 benchmark**（2026-07-08） | Fable 5 orchestrator + Sonnet 5 workers：**全 Fable 效能的 96%、成本 46%**（BrowseComp：準確率 86.8% vs 90.8%、每題 $18.53 vs $40.56）；反向 advisor 模式（Sonnet 執行、諮詢 Fable）約 92% 效能、63% 成本（SWE-bench Pro）——orchestrator 分工兩軸皆勝 | Anthropic（[@ClaudeDevs 官方推文](https://x.com/ClaudeDevs/status/2074606058128224365)；[multi-agent 文件](https://platform.claude.com/docs/en/managed-agents/multi-agent)） |
| 12-worker 稽核成本對照 | 全 Fable $14.50；Fable+Sonnet $6.10（−58%）；Fable+Haiku $3.70（−74%）；orchestrator 溢價僅 $1.75 | Developers Digest |
| Token 成本削減宣稱 | Orchestrator + 便宜 subagents 普遍宣稱 5–10 倍；個案宣稱 −90% | 多篇社群貼文 |
| Explore 遙測 | 選 Sonnet 的 session 中約 36% API 呼叫實際跑 Haiku（內建 Explore 舊行為），證明廉價探索量體巨大 | mirin.pro |
| Marketplace 分層慣例 | Tier 0 Fable（最長時程）→ Tier 1 Opus（架構/資安/關鍵決策）→ Tier 3 Sonnet（文件/測試）→ Tier 4 Haiku（快速營運） | wshobson/agents（199 agents） |
| 交棒模式 | 五角色管線（ORCHESTRATOR/SCOUT/GUARD/BUILD/CHECK），agent 間以 `.handoff/` JSON 檔交棒、可稽核可續跑 | clouatre.ca |
| 機械式紀律 | PreToolUse「Spawn Guard」擋規格不足的委派、Stop hook 擋未完成收尾——hooks 強制而非僅靠 prompt | Rylaa/fable5-orchestrator |
| 資安 worker 釘 Opus | HN 主要抱怨為 Fable 5 資安工作被分類器攔截後降級回答；解法是資安類型從一開始就路由 Opus | Hacker News |

## Effort 分層

Effort 是配額的第二大槓桿，且 Fable 5 的建議與 Opus 4.7/4.8 世代**不同**：

| 對象 | 建議 effort | 理由 |
|---|---|---|
| Fable 5 主 session | `high`（預設） | 官方：大多數任務用 high；Fable 5 低 effort 已常超越前代 xhigh |
| Fable 5 最長時程任務 | `xhigh` | >30 分鐘、百萬 token 級的 run；需搭配大 `max_tokens`（64K 起） |
| `max` | 極少用 | 報酬遞減、易 overthinking |
| 偵察 / 機械執行 subagents | `low` | 高量低判斷工作，低 effort = 更少工具呼叫與前言 |
| 判斷型 executor / verifier | `medium` | 品質與成本的平衡點 |
| 資安 executor | `high` | 正確性優先於成本 |

## Prompting 上的世代差異

| 發現 | 落地含意 |
|---|---|
| 為前代模型寫的過度規範式 prompt/skill 會**降低** Fable 5 品質 | 政策文件做減法：陳述目標與限制，刪逐步 scaffolding |
| 第一輪就給完整任務規格（well-specified single turn）表現最佳 | 委派規則要求 one-shot spec：goal、constraints、done-criteria、paths |
| 「給理由不只給要求」顯著提升表現 | 委派 spec 必含 why |
| Fresh-context 驗證者優於自我批判（官方口徑） | `verifier` 角色是品質閘門的核心 |
| 進度聲稱須對照 tool result 稽核（幾乎消除捏造回報） | 寫進 executor/verifier 的 system prompt |
| 要求模型複述內部推理會觸發 `reasoning_extraction` 拒絕 | 政策與 agent prompt 避免此類指示 |

## 來源

| 類別 | 連結 |
|---|---|
| 官方 | [Introducing Claude Fable 5](https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5.md) · [發布公告](https://www.anthropic.com/news/claude-fable-5-mythos-5) · [Prompting Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5.md) · [Effort](https://platform.claude.com/docs/en/build-with-claude/effort.md) · [Redeploying Fable 5](https://www.anthropic.com/news/redeploying-fable-5) · [限額調整](https://www.anthropic.com/news/higher-limits-spacex) |
| Claude Code 文件 | [Subagents](https://code.claude.com/docs/en/sub-agents) · [Model config](https://code.claude.com/docs/en/model-config) · [Settings](https://code.claude.com/docs/en/settings) |
| 訂閱與限額 | [Models, usage and limits in Claude Code](https://support.claude.com/en/articles/14552983) · [What is the Max plan](https://support.claude.com/en/articles/11049741) · [BleepingComputer：非永久移除](https://www.bleepingcomputer.com/news/artificial-intelligence/claude-fable-5-isnt-permanently-leaving-subscriptions-anthropic-says/) · [Forbes：延長 5 天](https://www.forbes.com/sites/sandycarter/2026/07/07/claude-fable-5-extends-by-five-more-days-10-moves-to-make-now/) |
| 社群實測 | [Developers Digest：orchestrator playbook](https://www.developersdigest.tech/blog/fable-5-orchestrator-model-playbook) · [mirin.pro：Haiku 遙測](https://mirin.pro/blog/claude-code-subagents-haiku-telemetry/) · [Upstash：成本控制](https://upstash.com/blog/keep-claude-fable-5-costs-under-control) · [TrueFoundry：限額實測](https://www.truefoundry.com/blog/claude-code-limits-explained) |
| 社群模式 | [Rylaa/fable5-orchestrator](https://github.com/Rylaa/fable5-orchestrator) · [wshobson/agents](https://github.com/wshobson/agents) · [clouatre.ca：subagent 架構](https://clouatre.ca/posts/orchestrating-ai-agents-subagent-architecture/) · [MindStudio：orchestrator 政策](https://www.mindstudio.ai/blog/smart-orchestrator-cheaper-sub-agent-models-claude-code) · [HN 討論](https://news.ycombinator.com/item?id=48752030) |
