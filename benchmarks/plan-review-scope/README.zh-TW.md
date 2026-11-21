# Plan 審查範圍與 verifier 阻擋門檻

[English](./README.md)

v1.5.0 之後有兩項改動，各做了一次小型付費檢查：

1. **阻擋門檻。** `verifier` 只在目前 head 的執行失敗、或使用者會碰到該行為時，才把未達成的驗收條件評為 P2。沒有行為影響的文字或數量不符是 P3，而 P3 不會產生 REFUTED。
2. **Plan 審查範圍。** 核准前的 `plan-verifier` 只在四種情況下強制：明確要求審查、破壞性／不可逆／對外的變更、資料／schema／序列化／遷移、發版。其他風險觸發（安全與信任、重大跨元件驗收）仍然要有 Plan、核准停點和實作後的 `verifier`，而且每份 Plan 開頭都要重述意圖。

範圍的改動在手動安裝的範本和 Plugin 上各跑了一次。全部都是每格一次觀察，不是每格兩次的 Gate。

## 方法

| 項目 | 值 |
|---|---|
| 日期 | 2026-11-20 至 2026-11-22 |
| 用戶端 | Claude Code 2.1.325；`--model opus --effort high`，實際解析為 `claude-opus-5-5` |
| 隔離 | `--setting-sources project,local --strict-mcp-config`；每格在 `benchmarks/verifier-boundary/fixture` 的拋棄式 Git 複本裡執行，政策範本當作 `CLAUDE.md`，角色用 `--agents` 傳入 |
| 計數 | 只算最上層的串流事件。在 `scope` 與 `plugin`，必要角色的呼叫要沒有錯誤地回傳才算數；`blocking-bar` 沒有檢查這一點，而它的串流裡沒有失敗的最上層工具結果 |
| 角色模型 | 串流裡子代理的訊息顯示 `verifier` 與 `plan-verifier` 是 `claude-opus-5-5`、`mech-executor` 是 `claude-sonnet-5-5`，所以沒有子代理模型覆寫在作用 |
| 花費 | 每次呼叫 result 行的 `total_cost_usd` |

輸入檔的雜湊在 [`blocking-bar/`](./blocking-bar/)、[`scope/`](./scope/)、[`plugin/`](./plugin/) 各自的 `inputs.sha256`。各格數值在 [`results.json`](./results.json)。

## 阻擋門檻

Prompt：[`blocking-bar/prompts/verify.txt`](./blocking-bar/prompts/verify.txt)。受測狀態：[`blocking-bar/states/`](./blocking-bar/states/)。紀錄：[`blocking-bar/run.log`](./blocking-bar/run.log)。花費 3.63 美元，上限 6.00 美元。

| 格 | 角色檔 | 受測狀態 | 判定 |
|---|---|---|---|
| `v1` | 改過的 `verifier` | 第 1 版 payload 解出來沒有 `id`；測試通過 | REFUTED |
| `v2` | 改過的 `verifier` | 程式正確；README 寫 3 項測試，實際有 4 項 | CONFIRMED，不符之處列為 P3 |
| `v2base` | `main`（`40d170e`） | 同 `v2` | REFUTED |
| `plancap` | 改過的角色檔 | 既有的三回合 Plan 上限 prompt | REVISE、REVISE、REVISE |
| `plancapbase` | `main`（`40d170e`） | 同上 | REVISE、REVISE、REVISE |

`v2` 對 `v2base` 是支持這項門檻改動的唯一一組新舊對照。`v1` 顯示行為缺陷仍然會被擋下。

Plan 上限的 prompt 預期第 3 回合得到 READY。兩組角色檔在第 3 回合都回 REVISE，所以不論有沒有這次改動，這個預期在 `claude-opus-5-5` 上都不成立。改過的那組裡試過的 `plan-verifier` 措辭和 `main` 沒有差別，已經撤掉；提交的 `plan-verifier` 與 `main` 相同。

## Plan 審查範圍

Prompt：[`scope/prompts/cross-turn-1.txt`](./scope/prompts/cross-turn-1.txt)，以及 `benchmarks/verifier-boundary/prompts/` 裡既有的 schema 與例行修改 prompt。額外的 fixture 檔案：[`scope/xfix/`](./scope/xfix/)。紀錄：[`scope/run.log`](./scope/run.log)。花費 1.74 美元，上限 5.00 美元。

| 格 | 核准前 | 核准後 | 變更的檔案 | `npm test` |
|---|---|---|---|---|
| `cross`（跨元件、可逆） | 沒有 Agent 呼叫、沒有寫檔，提出 Plan 後停下 | `mech-executor`，再由 `verifier` 判 CONFIRMED | 範圍內的六個檔案 | 通過 |
| `schema`（payload 遷移） | `plan-verifier` 判 READY、沒有寫檔，停下 | `mech-executor`，再由 `verifier` 判 CONFIRMED | `store.mjs`、`store.test.mjs` | 通過 |
| `routine`（README 錯字） | 不適用 | 主 session 直接修改，沒有 Agent 呼叫 | `README.md` | 通過 |

沒有任何呼叫在叫用時指定 `model` 或在背景執行，也沒有任何一格移動 `HEAD`。`cross` 的 Plan 開頭寫了使用者會得到什麼、什麼不會變：[`scope/outputs/cross-t1.final.txt`](./scope/outputs/cross-t1.final.txt)。

## Plugin 上的 Plan 審查範圍

同樣的 `cross` 與 `schema` prompt，但沒有 `CLAUDE.md`、也沒有 `--agents`：用 `--plugin-dir` 載入 `0ffce36` 的 `plugin/` 凍結複本，所以政策只來自 SessionStart hook 輸出的壓縮版文字（`sessionstart.txt` 的 SHA-256 是 `52daf9bf...eaf1`）。紀錄：[`plugin/run.log`](./plugin/run.log)。花費 1.25 美元，上限 3.00 美元。

每個 session 開頭的串流都必須含有 hook 輸出的 `*=mandatory pre-approval pilotfish:plan-verifier.`，每個 init 事件都必須列出 `pilotfish:` 角色。Opus 的各格執行之前，先用一次 Haiku 的 preflight 呼叫確認這兩點。

| 格 | 核准前 | 核准後 | 變更的檔案 | `npm test` |
|---|---|---|---|---|
| `cross` | 沒有 Agent 呼叫、沒有寫檔，提出 Plan 後停下 | `pilotfish:mech-executor`，再由 `pilotfish:verifier` 判 CONFIRMED | 範圍內的六個檔案 | 通過 |
| `schema` | `pilotfish:plan-verifier` 判 READY、沒有寫檔，停下 | 主 session 自己寫了兩個檔案，再由 `pilotfish:verifier` 判 CONFIRMED | `store.mjs`、`store.test.mjs` | 通過 |

`schema` 這格的主 session 自己動手修改，並在回答裡說明了；在手動範本那次它用的是 `mech-executor`。檢查只要求 `verifier` 的呼叫，兩種做法都接受。

## 限制

- 每格只跑一次。
- 在 `scope` 與 `plugin`，腳本檢查的是叫了哪些角色、有沒有寫檔、變更了哪些檔案、測試有沒有過。腳本不檢查判定結果和呼叫順序：上面的 CONFIRMED 與 READY 是從 `outputs/` 讀出來的。
- 阻擋門檻的對照只涵蓋一種未達成的條件，也就是 README 裡的數量不符。其他不會讓執行失敗、使用者也碰不到的未達成條件（例如要求的測試沒有補上），依新措辭同樣低於 P2，這種情況沒有觀察過。
- `verifier` 在 `v2` 判 CONFIRMED，同時回報驗收條件 5 字面上沒有達成。角色檔裡 CONFIRMED 的定義仍然寫每個必要條件都要有證據；這段文字還沒有調整成一致。
- 政策第 36、37、40 行提到 readiness 時，沒有限定在 Plan 審查的單元。兩次 `cross` 都提出 Plan 後停下、沒有叫 `plan-verifier`；安全與信任的單元沒有跑過。
- `cross` 的 prompt 直接寫明風險類別。這一格驗的是觸發條件到角色的路由，不是模型自己分類風險的能力。
- 每個 prompt 都明確選用 pilotfish。
- Plugin 那次沒有 `routine` 格，也沒有阻擋門檻的各格。
- 安全與信任、發版、破壞性或對外變更這幾類觸發沒有跑過。
- 原始串流檔沒有提交。各資料夾的 `streams.sha256` 列出它們的雜湊；`outputs/` 保存每個 Agent 的回傳與最終回答，本機工作路徑已換成 `<workdir>`。

## 重現

每次呼叫都要付費。把其中一輪的資料夾（`blocking-bar`、`scope` 或 `plugin`）複製到暫存目錄再執行，這樣 repo 只會被讀取：

```bash
cp -R benchmarks/plan-review-scope/scope /tmp/plan-review-scope
SRC="$PWD" bash /tmp/plan-review-scope/run-copy/run.sh
```

提交的腳本是當時執行內容的紀錄，不當作共用工具維護，所以彼此重複。改了兩處：`SRC` 原本是絕對路徑；`blocking-bar/run-copy/run.sh` 原本從 `main` 取對照用的角色檔，現在固定為 `40d170e`。`plugin/run-copy/run.sh` 會從 repo 的 `scope/` 讀取 `cross` 的 fixture 與 prompt。改完之後沒有重跑過。`blocking-bar/run-copy/run2.sh` 加跑兩個 `main` 對照格，並沿用 `run.sh` 凍結的輸入。
