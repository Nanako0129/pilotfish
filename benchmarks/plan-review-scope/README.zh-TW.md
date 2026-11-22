# Plan 審查範圍與 verifier 阻擋門檻

[English](./README.md)

v1.5.0 之後有兩項改動，各做了一次小型付費檢查：

1. **阻擋門檻。** 對 `verifier` 來說，沒有行為影響的文字或數量不符是 P3，而 P3 不會產生 REFUTED。最初的措辭還把所有未達成的驗收條件限制成「只在目前 head 的執行失敗、或使用者會碰到該行為時」才是 P2；這個子句在 v1.6.0 之前換掉了（見[未達成條件的下限](#未達成條件的下限)）。
2. **Plan 審查範圍。** 核准前的 `plan-verifier` 只在四種情況下強制：明確要求審查、破壞性／不可逆／對外的變更、資料／schema／序列化／遷移、發版。其他風險觸發（安全與信任、重大跨元件驗收）仍然要有 Plan、核准停點和實作後的 `verifier`，而且每份 Plan 開頭都要重述意圖。

範圍的改動在手動安裝的範本和 Plugin 上各跑了一次。之後審查在改過的文字裡找到兩處不一致，文字修正後把受影響的各格重跑了一次（見[在最終文字上重跑](#在最終文字上重跑)）。全部都是每格一次觀察，不是每格兩次的 Gate。

## 方法

| 項目 | 值 |
|---|---|
| 日期 | 2026-11-20 至 2026-11-23 |
| 用戶端 | Claude Code 2.1.325；`--model opus --effort high`，實際解析為 `claude-opus-5-5` |
| 隔離 | `--setting-sources project,local --strict-mcp-config`；每格在 `benchmarks/verifier-boundary/fixture` 的拋棄式 Git 複本裡執行，政策範本當作 `CLAUDE.md`，角色用 `--agents` 傳入 |
| 計數 | 只算最上層的串流事件。在 `scope` 與 `plugin`，必要角色的呼叫要沒有錯誤地回傳才算數；`blocking-bar` 沒有檢查這一點，而它的串流裡沒有失敗的最上層工具結果 |
| 角色模型 | 串流裡子代理的訊息顯示 `verifier` 與 `plan-verifier` 是 `claude-opus-5-5`、`mech-executor` 與 `executor` 是 `claude-sonnet-5-5`，所以沒有子代理模型覆寫在作用（和上一列的失敗結果數一樣，是從沒有提交的原始串流讀出來的） |
| 花費 | 每次呼叫 result 行的 `total_cost_usd`。續接的回合回報的是整個 session 的累計值，所以每個 session 只算一次。前三份 `run.log` 的 `DONE spent=` 把每一回合都加進去，數字偏高 |

輸入檔的雜湊在 [`blocking-bar/`](./blocking-bar/)、[`scope/`](./scope/)、[`plugin/`](./plugin/)、[`rerun/`](./rerun/)、[`precedence/`](./precedence/)、[`precedence-2/`](./precedence-2/)、[`floor/`](./floor/) 各自的 `inputs.sha256`。各格數值在 [`results.json`](./results.json)。

## 阻擋門檻

Prompt：[`blocking-bar/prompts/verify.txt`](./blocking-bar/prompts/verify.txt)。受測狀態：[`blocking-bar/states/`](./blocking-bar/states/)。紀錄：[`blocking-bar/run.log`](./blocking-bar/run.log)。花費 2.16 美元，上限 6.00 美元。

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

Prompt：[`scope/prompts/cross-turn-1.txt`](./scope/prompts/cross-turn-1.txt)，以及 `benchmarks/verifier-boundary/prompts/` 裡既有的 schema 與例行修改 prompt。額外的 fixture 檔案：[`scope/xfix/`](./scope/xfix/)。紀錄：[`scope/run.log`](./scope/run.log)。花費 1.28 美元，上限 5.00 美元。

| 格 | 核准前 | 核准後 | 變更的檔案 | `npm test` |
|---|---|---|---|---|
| `cross`（跨元件、可逆） | 沒有 Agent 呼叫、沒有寫檔，提出 Plan 後停下 | `mech-executor`，再由 `verifier` 判 CONFIRMED | 範圍內的六個檔案 | 通過 |
| `schema`（payload 遷移） | `plan-verifier` 判 READY、沒有寫檔，停下 | `mech-executor`，再由 `verifier` 判 CONFIRMED | `store.mjs`、`store.test.mjs` | 通過 |
| `routine`（README 錯字） | 不適用 | 主 session 直接修改，沒有 Agent 呼叫 | `README.md` | 通過 |

沒有任何呼叫在叫用時指定 `model` 或要求在背景執行，也沒有任何一格移動 `HEAD`。`cross` 的 Plan 開頭寫了使用者會得到什麼、什麼不會變：[`scope/outputs/cross-t1.final.txt`](./scope/outputs/cross-t1.final.txt)。

## Plugin 上的 Plan 審查範圍

同樣的 `cross` 與 `schema` prompt，但沒有 `CLAUDE.md`、也沒有 `--agents`：用 `--plugin-dir` 載入 `0ffce36` 的 `plugin/` 凍結複本，所以政策只來自 SessionStart hook 輸出的壓縮版文字（`sessionstart.txt` 的 SHA-256 是 `52daf9bf...eaf1`）。紀錄：[`plugin/run.log`](./plugin/run.log)。花費 0.88 美元，上限 3.00 美元。

preflight 與每格第一回合的串流都必須含有 hook 輸出的 `*=mandatory pre-approval pilotfish:plan-verifier.`，每個 init 事件都必須列出 `pilotfish:` 角色。Opus 的各格執行之前，先用一次 Haiku 的 preflight 呼叫確認這兩點。

| 格 | 核准前 | 核准後 | 變更的檔案 | `npm test` |
|---|---|---|---|---|
| `cross` | 沒有 Agent 呼叫、沒有寫檔，提出 Plan 後停下 | `pilotfish:mech-executor`，再由 `pilotfish:verifier` 判 CONFIRMED | 範圍內的六個檔案 | 通過 |
| `schema` | `pilotfish:plan-verifier` 判 READY、沒有寫檔，停下 | 主 session 自己寫了兩個檔案，再由 `pilotfish:verifier` 判 CONFIRMED | `store.mjs`、`store.test.mjs` | 通過 |

`schema` 這格的主 session 自己動手修改，並在回答裡說明了；在手動範本那次它用的是 `mech-executor`。檢查只要求 `verifier` 的呼叫，兩種做法都接受。

## 在最終文字上重跑

`scope` 和 `plugin` 跑的是 `0ffce36` 的政策與角色檔。`blocking-bar` 在那之前執行，用的是 `main`（`40d170e`）的政策，搭配一組候選角色檔，其中的 `verifier` 和 `0ffce36` 的相同。`0ffce36` 的文字有兩處和這次改動對不上：

- `verifier` 把 CONFIRMED 定義成每個必要條件都有證據，但只在 P3 未達成的條件同樣會得到 CONFIRMED。定義現在寫成「evaluates every required acceptance condition; each is met or fails only at P3/P4 (report)」。
- 政策第 36、37、40 行對所有單元都提到 readiness，可是只有 `plan-verifier` 會回 READY。第 36 行現在寫「any readiness review」，第 37 行寫「After any required readiness」。第 40 行把審查順序和「both must be READY」限定在「Plan-review units:」，其餘三條規則放在「All units:」之下。Plugin 壓縮版用 `*-marked:` 和 `All:` 做同樣的區分。

各格用同一支腳本重跑，政策 SHA-256 是 `93fb822a...fc45`，`sessionstart.txt` 的 SHA-256 是 `c72fa1f2...a055`。紀錄：[`rerun/run.log`](./rerun/run.log)。花費 2.76 美元，上限 4.00 美元。

| 格 | 路徑 | 結果 |
|---|---|---|
| `v1` | 範本 | `verifier` 判 REFUTED |
| `v2` | 範本 | `verifier` 判 CONFIRMED，數量不符列為 P3 |
| `cross` | 範本 | 沒有 Agent 呼叫、沒有寫檔，提出 Plan 後停下；之後 `mech-executor`，`verifier` 判 CONFIRMED；範圍內六個檔案中的四個（`cli.test.mjs` 與 `report.test.mjs` 沒有動）；測試通過 |
| `schema` | 範本 | `plan-verifier` 判 READY、沒有寫檔，停下；之後 `mech-executor`，`verifier` 判 CONFIRMED；`store.mjs`、`store.test.mjs`；測試通過 |
| `routine` | 範本 | 主 session 直接修改，沒有 Agent 呼叫；`README.md`；測試通過 |
| `p-preflight` | Plugin | hook 文字與 `pilotfish:` 角色都在 |
| `p-cross` | Plugin | 沒有 Agent 呼叫、沒有寫檔，提出 Plan 後停下；之後 `pilotfish:executor`，`pilotfish:verifier` 判 CONFIRMED；範圍內的六個檔案；測試通過 |
| `p-schema` | Plugin | `pilotfish:plan-verifier` 判 READY、沒有寫檔，停下；之後 `pilotfish:executor`，`pilotfish:verifier` 判 CONFIRMED；`store.mjs`、`store.test.mjs`；測試通過 |

這次 Plugin 的兩格都把修改交給 `pilotfish:executor`。第一次 Plugin 執行時，`cross` 用的是 `pilotfish:mech-executor`，`schema` 是主 session 自己寫的。

`p-schema` 第一回合裡，用戶端把 `pilotfish:plan-verifier` 的呼叫放到背景執行，呼叫本身並沒有這樣要求。[`rerun/outputs/p-schema-t1.agent0.txt`](./rerun/outputs/p-schema-t1.agent0.txt) 裡的工具結果是啟動通知。READY 是在完成通知裡送達的，session 等到它之後才提出 Plan。腳本把啟動通知算成一次已回傳的呼叫。所有各輪裡沒有其他呼叫在背景執行。

各格通過與否和判定都與先前相同，所以重跑顯示沒有退步；執行角色和 `cross` 動到的檔案有差異，如上所述。它沒有顯示新措辭有效：在先前的文字上 `cross` 就已經不叫 `plan-verifier` 並停下、`v2` 也已經是 CONFIRMED，沒有任何一格能分辨這些措辭。

這是第二次重跑。第一次跑的是 `a9179ea` 提交的措辭（2.74 美元，判定相同），紀錄在 [`rerun-a9179ea/`](./rerun-a9179ea/) 以及 `results.json` 的 `superseded_run` 底下。之後審查發現那版第 40 行的前綴涵蓋過多，所以文字再改，各格又跑了一次。

`v2base`、`plancap`、`plancapbase` 沒有重跑。`v2base` 與 `plancapbase` 用的是 `main` 的角色檔。`plancap` 用的是候選角色檔搭配 `main` 的政策，失敗的方式和 `plancapbase` 相同；它沒有在最終文字上跑過。

## 判定的優先順序

這一節是上面的變更合併之後加的。`verifier` 把 CONFIRMED 定義成每個必要條件都達成，把 REFUTED 定義成有可重現、會擋住主張的 P0-P2 發現；列出的條件全數達成、但受審的提交另外造成條件以外的 P0-P2 回歸時，沒有任何一句話說明該用哪一個。`main` 在 `40d170e` 就有同樣的缺口。第 19 行現在寫成「REFUTED takes precedence when a reproducible P0-P2 blocker coexists with met conditions or missing evidence; report both.」

兩次執行都拿修改後的角色（agents SHA-256 `899b9e01...cf93`）對照 `5ba7ee0` 的角色（`2e0ee951...b75`），政策文字沒有變。提示詞沿用阻擋門檻那一份：[`precedence/prompts/verify.txt`](./precedence/prompts/verify.txt)。

| 執行 | 格 | 角色 | 受審狀態 | 判定 |
|---|---|---|---|---|
| [`precedence/`](./precedence/) | `v1` | 修改後 | 版本 1 的 payload 解碼後沒有 `id`；測試通過 | REFUTED |
| | `v2` | 修改後 | 程式正確；README 寫 3 個測試，實際有 4 個 | CONFIRMED，數量不符列為 P3 |
| | `v3` | 修改後 | `encodeUser` 把呼叫端物件的 `id` 刪掉；該提交改寫了 round-trip 測試 | REFUTED，P1 |
| | `v3base` | `5ba7ee0` | 同 `v3` | REFUTED，P1 |
| [`precedence-2/`](./precedence-2/) | `v3` | 修改後 | 測試與 `v2` 相同；`encodeUser` 把每個使用者與 payload 留在模組層陣列裡，沒有任何地方讀取或清除 | REFUTED，P1；五個條件都回報達成 |
| | `v3base` | `5ba7ee0` | 同 `v3` | REFUTED，P1；五個條件都回報達成 |

花費 1.29 美元（腳本上限 2.50；沒有授權上限）與 0.68 美元（上限 1.50）。紀錄：[`precedence/run.log`](./precedence/run.log)、[`precedence-2/run.log`](./precedence-2/run.log)。

第一個 `v3` 狀態沒有把情境隔離出來：兩個 verifier 都說各項檢查照字面通過，但修改後的 verifier 把發現連到驗收條件 3，對照組則把條件 3 標成「Met on decode」並附但書。第二個狀態沒有動測試，兩個 verifier 都把五個條件標成達成、沒有附帶但書，再判 REFUTED。對照組仍把它的發現標成影響條件 2，所以這次的區隔比第一個狀態乾淨，但不算完全。

`5ba7ee0` 的 verifier 在兩個狀態上本來就判 REFUTED。這兩次執行顯示 `v1`、`v2` 沒有回歸，也沒有任何判定因為新的那句話而改變；那句話是把模型在這兩次觀察裡已經做的事寫進角色文字。

第一次執行沒有經過授權。負責審查的子代理被要求用假的用戶端試跑腳本，但假的用戶端沒有建立成功，腳本找到了真的用戶端。腳本與輸入就是原本準備要跑的那一份，所以結果保留。同一個子代理的第二次啟動在 `v1` 途中被中止，擷取檔沒有 result 行，也沒有提交或列入雜湊，那筆花費不明，沒有算進總額。`precedence-2/run-copy/run.sh` 執行時就帶有檢查，沒有設定 `PAID_RUN=1` 會拒絕真的用戶端；同樣的檢查事後也補進 `precedence/run-copy/run.sh`。

## 未達成條件的下限

這一節是 v1.6.0 之前加的。發版前的獨立閱讀發現 `verifier` 第 23 行有兩條 P2 規則：「P2 = material bounded/recoverable issue」，以及針對未達成驗收條件的「P2 only when current-head run fails/users hit behavior」。照第二條，只靠檢視就看得出沒達成的必要條件（例如規定要補的測試沒補）會低於 P2，可能以 CONFIRMED 收場。這一行現在寫成「Failed acceptance condition: P0/P1 when criteria met, else P2, incl. missing required test/file. Exception: wording/count mismatch lacking behavioral effect = P3 unless users rely on mismatched text (P2).」

執行一次，拿修改後的角色（agents SHA-256 `393a2c93...5eed`）對照 `1a5bad8` 的角色（`899b9e01...cf93`），政策文字沒有變。`v4` 用 [`floor/prompts/verify-test.txt`](./floor/prompts/verify-test.txt)，多了驗收條件 6：`store.test.mjs` 要有一個測試確認版本 1 的舊 payload 仍可解碼。紀錄：[`floor/run.log`](./floor/run.log)。花費 1.25 美元，上限 2.50。

| 格 | 角色 | 受審狀態 | 判定 |
|---|---|---|---|
| `v1` | 修改後 | 版本 1 的 payload 解碼後沒有 `id`；測試通過 | REFUTED |
| `v2` | 修改後 | 程式正確；README 寫 3 個測試，實際有 4 個 | CONFIRMED，數量不符列為 P3 |
| `v4` | 修改後 | 程式正確、3 個測試通過、README 的數量正確；條件 6 要求的測試不存在 | REFUTED，P2 |
| `v4base` | `1a5bad8` | 同 `v4` | REFUTED，P2 |

`1a5bad8` 的 verifier 在 `v4` 上同樣判 REFUTED，理由是「a required acceptance condition fails at the current head」，把缺少的測試評為 P2。所以在這次觀察裡，先前的措辭並沒有產生閱讀者預測的 CONFIRMED，也沒有任何判定改變。新措辭是把文字裡兩條規則的衝突拿掉；`v1`、`v2` 沒有回歸。

## 限制

- 每格只跑一次。
- 在 `scope` 與 `plugin`，腳本檢查的是叫了哪些角色、有沒有寫檔、變更了哪些檔案、測試有沒有過。腳本不檢查判定結果和呼叫順序：上面的 CONFIRMED 與 READY 是從 `outputs/` 讀出來的。
- 阻擋門檻的對照只涵蓋一種 P3 條件，也就是 README 裡的數量不符。驗收條件本身要求的數量（例如「新增 4 個測試」但只有 3 個）可以讀成數量不符（P3），也可以讀成缺少規定的測試（P2）；沒有任何一格包含這種情況。
- 續接呼叫的 `--max-budget-usd` 會不會把 session 先前的花費算進去，沒有查過。每個續接回合都在上限內結束。
- `cross` 的 prompt 直接寫明風險類別。這一格驗的是觸發條件到角色的路由，不是模型自己分類風險的能力。
- 每個 prompt 都明確選用 pilotfish。
- Plugin 那次沒有 `routine` 格，也沒有阻擋門檻的各格。
- 安全與信任、發版、破壞性或對外變更這幾類觸發沒有跑過。
- 原始串流檔沒有提交。各資料夾的 `streams.sha256` 列出它們的雜湊；`outputs/` 保存每個 Agent 的回傳與最終回答，本機工作路徑已換成 `<workdir>`。

## 重現

每次呼叫都要付費。把其中一輪的資料夾（`blocking-bar`、`scope`、`plugin`、`rerun`、`precedence`、`precedence-2` 或 `floor`）複製到暫存目錄再執行，這樣 repo 只會被讀取：

```bash
cp -R benchmarks/plan-review-scope/scope /tmp/plan-review-scope
PAID_RUN=1 SRC="$PWD" bash /tmp/plan-review-scope/run-copy/run.sh
```

提交的腳本是當時執行內容的紀錄，不當作共用工具維護，所以彼此重複。改了三處：`SRC` 原本是絕對路徑；`blocking-bar/run-copy/run.sh` 原本從 `main` 取對照用的角色檔，現在固定為 `40d170e`；各檢查程式的花費加總原本把續接 session 的每一回合都加進去，現在每個 session 只算一次。`plugin/run-copy/run.sh` 會從 repo 的 `scope/` 讀取 `cross` 的 fixture 與 prompt。改完之後沒有重跑過；現在每支腳本會先把 `claude` 解析成一個絕對路徑、之後每次呼叫都用同一個路徑，並在第一次呼叫之前停下，除非設定了 `PAID_RUN=1` 或該用戶端回報 `stub`；`blocking-bar`、`scope`、`plugin`、`rerun`、`rerun-a9179ea` 的腳本是在執行之後才補上這項檢查，而 `rerun` 與 `rerun-a9179ea` 的腳本只改了這一處。`precedence` 與 `precedence-2` 的腳本經審查後在執行之後改了兩處，改完沒有重跑：`precedence/run-copy/run.sh` 補上 `precedence-2` 執行時就有的 `PAID_RUN=1` 檢查；兩份 `parse.py` 遇到沒有 `total_cost_usd` 的 result 行會停下，不再當成零。已在不付費的情況下確認：用真的用戶端、不帶 `PAID_RUN` 時，每支腳本都以結束碼 4 停下。`blocking-bar/run-copy/run2.sh` 加跑兩個 `main` 對照格，並沿用 `run.sh` 凍結的輸入。
