# 實戰歸因報告：兩個長時 orchestration session 的時間與 token 分佈（2026-07）

> 核心發現：機器時間的大頭不在跑測試、不在等 agent，而在主模型自己「想＋寫」——佔活躍時間的 58%～79%，吃掉全部 output tokens 的 92%。政策的每一個單獨決策都對，聚合起來卻讓 orchestrator 悄悄變成了 implementer。

## 目錄

- [文件目的](#文件目的)
- [場景與資料](#場景與資料)
- [時間歸因](#時間歸因)
- [Token 分佈](#token-分佈)
- [主 session 自留工解剖](#主-session-自留工解剖)
- [驗證的成效與成本](#驗證的成效與成本)
- [外部 review 迴圈](#外部-review-迴圈)
- [發現與對應修正](#發現與對應修正)
- [侷限](#侷限)

## 文件目的

這份報告對兩個真實的長時 orchestration session（合計約 101 小時 wall-clock、61.8 小時活躍）做完整的時間與 token 歸因：規劃、執行、驗證、外部 review 各花了多少，主模型與各角色 agent 各燒了多少 output tokens，以及委派政策在長 session 裡實際的行為模式。session transcript 不公開，但兩個 session 的全部產出都是公開的 GitHub artifacts（見下表），數字可與公開的 PR、commit、review thread 交叉對照。報告結論已轉成對 pilotfish 政策、[Baton](https://github.com/cablate/baton) dispatch brake 與 [remora](https://github.com/Nanako0129/remora-cc) 政策鏡像的具體修正。

## 場景與資料

兩個 session 都跑在 remora 上：Claude Code 作為介面與 agent runtime，模型經 gateway 路由到 OpenAI GPT-5.6（主模型與判斷型角色用 Sol，執行型角色用 Luna），角色 roster 與委派語意是 pilotfish v1.2 世代的八角色政策鏡像。也就是說：**政策語意是 pilotfish 的，模型檔位對應「frontier 判斷檔＋便宜執行檔」的同構配置**。

| | Session A | Session B |
|---|---|---|
| 專案 | TokenBar-Windows | TokenBar（tokscale 對齊，canonical worktree） |
| 公開 artifacts | [PR #3](https://github.com/Nanako0129/TokenBar-Windows/pull/3) | [PR #64](https://github.com/Nanako0129/TokenBar/pull/64)–[#72](https://github.com/Nanako0129/TokenBar/pull/72)（9 個 milestone PR）、[issue #45](https://github.com/Nanako0129/TokenBar/issues/45) |
| 期間 | 07-16 17:36 → 07-19 20:39（75.1h） | 07-18 18:20 → 07-19 20:39（26.3h） |
| 活躍時間（扣除 >10 分鐘閒置段） | ~36.8h（46 段閒置共 38.2h） | ~25.0h（5 段閒置共 1.4h） |
| 人類訊息數 | 439 | 186 |
| 主模型 output tokens | 8.59M | 6.76M |

歸因方法：解析 session JSONL transcript，將每個 `tool_use` 與其 `tool_result` 配對取得前景工具時長；`>10` 分鐘無事件的空窗視為使用者閒置並排除；subagent 各自的 transcript 統計其時長、模型與 output tokens；Bash 指令以 pattern 分類（測試、build、git、GitHub 操作、輪詢等待……）。已知誤差：背景任務的啟動呼叫立即返回，其真實耗時以阻塞式收割（TaskOutput）與 agent transcript 時間戳補回；agent-hours 之間互相平行，不可與 wall-clock 相加。

## 時間歸因

活躍時間內，主 session 前景視角的分佈：

| 項目 | Session A | Session B |
|---|---|---|
| **主模型產生／決策**（無工具在跑） | **~21.3h（58%）** | **~19.7h（79%）** |
| 等使用者（提問回答＋計畫核准） | ~8.5h | ~15m |
| 阻塞等背景任務 | 3h23m | 2h51m |
| 主 session 跑 unit test | 1h43m／187 次 | 37m／220 次 |
| build／lint | 6m | 28m |
| git 操作 | 21m／600 次 | 16m／563 次 |
| GitHub 操作（gh） | 4m | 11m／370 次 |

阻塞等待的對象，Session A 依序是 verifier（64m）、security-executor（46m）、外部 review 輪詢（19m）、SSH Windows VM（16m）；Session B 最大宗是**外部 review 輪詢（1h42m）**，其次 verifier（22m）與 Plan agent（16m）。

Subagent 工時（背景平行，agent-hours）：

| 階段 | Session A | Session B | 合計佔比 |
|---|---|---|---|
| 執行（executor／security-executor／mech-executor） | 15.4h／61 次 | 2.2h／12 次 | 48% |
| 驗證（verifier） | 8.5h／140 次（平均 3m38s） | 5.6h／61 次（平均 5m32s） | 39% |
| 規劃（Plan＋plan-verifier） | 1.4h／18 次 | 1.5h／26 次 | 8% |
| 探勘（Explore／scout／security-reviewer） | 1.3h／33 次 | 33m／10 次 | 5% |

## Token 分佈

| 消費者 | 模型檔 | output tokens | 佔比 |
|---|---|---|---|
| 主 session（兩場合計） | Sol | 15.35M | 72.3% |
| verifier ×201 | Sol | 2.35M | 11.1% |
| security-reviewer／security-executor | Sol | 1.12M | 5.3% |
| plan-verifier ×36 | Sol | 0.53M | 2.5% |
| Plan ×8 | Sol | 0.28M | 1.3% |
| executor ×42 | Luna | 1.12M | 5.3% |
| Explore／scout／mech-executor | Luna | 0.41M | 1.9% |

**判斷檔（Sol）合計約 19.6M tokens、佔 92.4%；執行檔（Luna）只分走 7.2%。**「把量產工作路由到便宜執行檔」的設計意圖，在這兩場 session 的實際分流比例是 8%——而且主因不是路由壞掉（milestone 實作有正常派 Luna worktree agents），是量產工作根本沒被辨識成可委派的形狀，詳見下節。

## 主 session 自留工解剖

以 Session B 為例。session 開場即載入委派規劃 skill，Plan 階段也明確寫了「不重疊檔案以多個 isolated worktree agents 平行處理」——而且做到了：12 個 executor 全帶 isolated worktree，其中 3 個同時平行（三個獨立 parser milestone）。**dispatch brake 沒有擋住該委派的工作。**

問題在另一側。主 session 自己執行了 1,356 次 Edit/Write，拆開來：

| 類別 | 次數 | 內容 |
|---|---|---|
| Rust 原始碼 | 700 | 核心檔 302 次、各 parser 檔 24～126 次——幾乎全是 review 修正迴圈（外部 review findings、verifier REFUTED 的後續修正、fixtures）加上 worktree patch 整合回 canonical |
| 模板化寫作 | ~610 | 計畫文件 177、上游對帳 README 165、PR body 106、issue 帳務貼文 ~87、知識庫文件 70 |
| 雜項 | ~46 | 草稿與腳本 |

時間軸上的形狀：開場兩小時做規劃（含 plan-verifier 迴圈），之後**連續 24 小時維持每小時 40～110 次自我編輯**，executor 派工集中在少數幾個時點，verifier 穩定每小時 2～4 次。transcript 裡主模型的自述足以說明它在做什麼：「外部 review 第五輪 3 項 finding 均已依根因修正並加入 fixtures」「第六輪實際有三項 findings，已全部修正並補上 hermetic fixtures」「完整 round 13 Rust gates 已通過」。

機制很清楚，這不是哪條規則被違反，而是**逐決策正確、聚合錯誤**：

> 每一條 review finding 的修正，context 都已經熱在主 session 手上（finding 本身、diff、gate 狀態），「直接修比派工快」的判斷單看每一次都成立。但這類小修是逐條到達的，任何一次決策當下都不長得像 batch——於是沒有任何一條規則會觸發「同型小任務已經連續直接做了 N 次，該改派了」。26 小時下來，1,267 次直接編輯對 12 次派工，orchestrator 變成了 implementer。

模板化寫作同理：PR body、發版帳務、計畫文件是照既有格式產文的機械工，按政策字面就該給 mech-executor，但它們夾在 gate 之間「順手就寫了」，從未被重新審視。

## 驗證的成效與成本

| 指標 | Session A | Session B |
|---|---|---|
| verifier 判定 | CONFIRMED 78／REFUTED 59（42%） | CONFIRMED 34／REFUTED 25（41%） |
| plan-verifier 判定 | READY 4／REVISE 7 | READY 6／REVISE 17（71% 打回） |
| plan-verifier 呼叫次數 vs Plan 數 | 12 次對 6 個 Plan | 24 次對 2 個 Plan |

兩個結論並存：**驗證是有效的**——42% 的 REFUTED 率表示 fresh-context verifier 真的在抓問題，不是橡皮圖章，這個 gate 不能砍；**但粒度太細**——201 次 verifier、平均每次不到六分鐘，大多在重驗一個測試已經覆蓋的小修正。主 session 自己已經跑了 407 次 unit test，每輪小修再開一個 frontier 檔 verifier 的邊際資訊量很低。plan-verifier 的 71% REVISE 率與「24 次呼叫對 2 個 Plan」則是規劃迴圈的 churn：readiness 審查有價值，但無上限的 REVISE 迴圈讓 Plan 收斂成本失控。

## 外部 review 迴圈

兩場 session 的 PR 都掛了 GitHub 端的自動 review bot（Codex）。實測數字：

| 指標 | Session A | Session B |
|---|---|---|
| 輪詢背景任務啟動次數 | 16 | 47 |
| 主 session 阻塞等待 | ~19m | **1h42m** |
| 抽出的 inline findings | 2 條 | 11 條（去重後 8 條） |
| findings 嚴重度 | 全部 P2 | 全部 P2，P1 為零 |
| 單一 PR 最多 review 輪數 | — | 6 輪 |

findings 內容全是 parser 邊角條件（非 session 檔的略過、缺 action 的 log、巢狀 cache 欄位的解析……）。對一個以 parser 為產品本體的專案，這些 P2 有真實使用者影響，**意見品質不是問題；互動模式才是**：逐修逐推的節奏讓每輪都付一次「push→輪詢→triage→修→驗→再 push→再 review」的全額成本，單 PR 跑到第 6 輪，而 R2 之後的邊際收益趨近於零。修正方向：review findings 合批成一個 commit 一次回覆、每 PR 輪次預算 2（僅 critical/high 可加開）、輪詢一律背景化、無重現路徑的理論性低嚴重度意見允許以證據回覆結案。

## 發現與對應修正

| # | 發現 | 修正 | 落點 |
|---|---|---|---|
| 1 | 逐條到達的同型小修永遠通過「直接做比較快」測試，聚合後 orchestrator 變 implementer | dispatch 規則加「recurrence」條款：同型小工直接做約三次後仍持續到達，即改合批派工，主 session 只留逐項 triage | pilotfish `templates/claude-md.orchestration.md`（提案 [#15](https://github.com/Nanako0129/pilotfish/issues/15)，須隨 Baton gate 證據重跑一併釋出）；Baton `SKILL.md`（[cablate/baton#1](https://github.com/cablate/baton/pull/1)）；remora `agents/orchestration.md`（[remora-cc#8](https://github.com/Nanako0129/remora-cc/pull/8)，已合入政策鏡像） |
| 2 | 已診斷、修法已知的 review finding 被「單一 bug 留主 session」規則掩護 | 明確排除：已診斷的 review finding 不是 unknown bug，首修落地後其餘同型 finding 屬可合批執行 | 同上 |
| 3 | verifier 每小修必驗：201 次、14.1 agent-hours、2.35M frontier tokens | 驗證粒度收斂到 feature／PR 收尾；修正迴圈中段以主 session 測試 gate 為準 | pilotfish（提案 [#15](https://github.com/Nanako0129/pilotfish/issues/15)）；remora（[remora-cc#8](https://github.com/Nanako0129/remora-cc/pull/8)） |
| 4 | plan-verifier 無上限 REVISE 迴圈（71% 打回、24 次對 2 Plans） | 每 Plan 最多 2 輪 REVISE，之後主 session 自行裁決殘餘分歧並記錄 | 同上 |
| 5 | 外部 review 逐修逐推、單 PR 6 輪、阻塞 1h42m | 輪次預算 2、findings 合批、輪詢背景化、理論性 P2 可 won't-fix 結案 | 使用者私有 review skill（已修） |

> **注意：** pilotfish 的 policy 位元組由 `test_baton_gate_snapshot_matches_recorded_hashes` 鎖定為「與 live Baton gate 實測快照完全一致」，且 v1.2.1 起明確拒絕 version-only normalization——所以 #1–#4 的政策文字修改不能只靠 PR 落地，必須跟著一次新的 gate 實測與證據刷新（VERSION、stamp、`results.json`）一併釋出，細節見 [#15](https://github.com/Nanako0129/pilotfish/issues/15)。

## 侷限

樣本是同一位使用者的兩場 session、同一個產品家族（TokenBar），且跑在 GPT-5.6 gateway 上而非原生 Claude 路由——模型檔位語意同構（frontier 判斷檔＋便宜執行檔），但絕對數字（尤其生成速度與 effort 表現）不可直接外推到原生配置。時間歸因對背景任務有近似（見方法段）；「主模型產生／決策」是活躍時間減前景工具聯集的殘差，包含少量 harness 排隊時間。發現 #1–#4 的方向不依賴這些近似：token 分佈（92% 對 8%）與呼叫次數（1,267 對 12、201 次 verifier、24 次 plan-verifier 對 2 Plans）都是精確計數。
