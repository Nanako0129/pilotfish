# Effort selection

[English](./README.md)

從 Claude Code 2.1.292 起，Agent tool 可以在每次呼叫時傳入 `effort`，覆蓋 agent frontmatter 裡設定的 `effort`；若設定了 `CLAUDE_CODE_EFFORT_LEVEL`，則會蓋過兩者。這項研究要回答：每次委派時是否該由主 session 決定 effort，而不是讓每個角色固定用 frontmatter 的檔位。各角色 frontmatter 的 effort 仍保留為建議預設值。

所有執行都使用 Claude Code 2.1.294，主 session 為 `claude-opus-5-5`，並載入 pilotfish Plugin。每次執行的紀錄在 [`results.json`](./results.json)，harness 在 [`scripts/`](./scripts/)。

## 1. 主 session 會不會依任務選擇？

在 system prompt 附加一段明確指示（[`scripts/ab-rule-B.md`](./scripts/ab-rule-B.md)）後，主 session 在 14 次委派中都傳入了 `effort`。同一個角色會依任務改變檔位，同一個任務重複兩次也選了相同的檔位：

| 角色 | 簡單任務 | 困難任務 |
|---|---|---|
| `scout` | 找一個函式在哪個檔案：`low` | 整個 repo 的 model／角色綁定對照：`high` |
| `executor` | 修一個拼字：`low` | 診斷訊號處理 bug：`medium` |
| `security-reviewer` | 一行 `printf` 會不會印出環境變數：`low` | 對 SessionStart hook 做對抗性審查：`high` |

## 2. 會不會改變品質或費用？

這組 A/B 使用同一個 Plugin，每題只委派一次。A 組被告知不要傳 `effort`，因此套用角色預設；B 組附上前述指示。

| 題組 | 角色（預設） | A | B | B 的選擇 |
|---|---|---|---|---|
| Aider Polyglot，40 題（Python 20、Rust 20） | `mech-executor`（`low`） | 37/40 | 39/40 | `low` 21、`medium` 18、`high` 1 |
| SWE-bench Verified「15 分鐘到 1 小時」20 題，官方 harness | `executor`（`medium`） | 18/20 | 16/20 | `medium` 16、`low` 4 |
| **合計** | | **55/60** | **55/60** | |

A 組 60 次委派都沒有傳 `effort`，B 組 60 次都有傳。兩個題組的 McNemar p 都是 0.5。SWE 中只有 A 組解出的 2 題，兩組都是以 `medium` 執行；設定完全相同卻結果不同，代表這是每次執行之間的雜訊。以定價計算的費用（Claude Code 的 `costUSD`）A 組 $11.45、B 組 $11.57（+1.1%），中位耗時相近。

**解讀：** 在這兩個 Sonnet 角色上，沒有量到品質或費用的提升，也沒有量到下降。Opus 角色（verifier、plan-verifier、security-reviewer）與 Haiku scout 沒有做 A/B。B 組用的是附加指示，不是出貨的 policy 寫法，而且沒有審查角色下限。在第 3 節的 Gate 任務上，出貨寫法選出的檔位與附加指示相同，只有下限適用的地方例外：E4 從 `low` 變成 `high`。出貨寫法本身的品質與費用沒有做 A/B。

A/B 執行時，shell 環境中有 `CLAUDE_EFFORT=xhigh`；提交的 `ab.py` 現在會先清掉它。另外做了一次檢查（`results.json` 的 `env_default_probe`）：在不傳 `effort` 的情況下委派一次 scout 查詢。設 `CLAUDE_EFFORT=max` 時用了 1.2k 個 Haiku 輸出 token、14 秒；不設這個變數時用了 2.3k；明確傳 `effort` 為 `max` 時則是 115k。這表示這個變數應該不會蓋過 frontmatter 預設值，A 組很可能是以角色預設執行。這只是推論：每種情況只跑一次，測的是 Haiku scout 而不是 A/B 裡的 Sonnet 角色，用的也是 `max` 而不是實際設定的 `xhigh`。記錄的 120 次 A/B 執行，每次都只委派一次，主 session 也沒有自己呼叫工具（`ab.validity_check`）。

## 3. 出貨文字的 Gate（A2）

指示必須寫在 policy 那一行裡，不能靠附加 prompt。Agent tool 的說明要求只有在指示明確要求某個檔位時才設定 `effort`，所以結果取決於 policy 寫得多明確。出貨的那一行也寫明了審查角色的下限：`verifier` 與 `plan-verifier` 至少 `medium`，`security-reviewer` 至少 `high`，也就是它們的預設值。之所以直接寫出檔位，是因為主 session 看不到角色的 frontmatter。

隔離條件記在 [`a2-isolation.txt`](./a2-isolation.txt)：
- fixture 是 `git archive` 的副本，並移除了巢狀的快照 `CLAUDE.md`；
- 未設定 `CLAUDE_EFFORT` 與 `CLAUDE_CODE_EFFORT_LEVEL`；
- 沒有使用 `--append-system-prompt`；
- 使用者的 `CLAUDE.md` 不含 "effort"；
- 題目（[plugin](./a2-tasks-plugin.tsv)、[template](./a2-tasks-template.tsv)）不含任何 effort 檔位字詞。

分兩組執行。Plugin 組用 `--plugin-dir` 載入 plugin。template 組以專案層的 `CLAUDE.md` 加 `.claude/agents/` 代替全域安裝；實際放在 `~/.claude/CLAUDE.md` 的情境沒有執行。

**判定規則**（`a2_gate.pass_rule`）：每組 8 題各跑兩次。每組要符合：
- 至少 13/14 比例的委派有傳 `effort`；
- 每次委派都交給指定角色；
- scout（T1／H1）與 executor（E3／T3）兩組對比，兩次重複中困難任務的檔位都嚴格較高；
- 沒有任何審查角色的委派低於下限。

E4（`security-reviewer` 的單行檢查）與 E5（`verifier` 的簡單確認），就是自由選擇時可能低於下限的情況。

| 寫法 | Plugin 組 | template 組 |
|---|---|---|
| 第 0 輪，精簡、無下限（舊規則） | FAIL：effort 1/14 | FAIL：effort 11/15，scout 對比失敗 |
| 第 1 輪，明確、無下限（舊規則） | PASS：effort 14/14 | PASS：effort 14/14 |
| **第 2 輪，出貨（明確、有下限）** | **PASS**：effort 16/16，兩組對比皆過，未低於下限 | **PASS**：effort 17/17，兩組對比皆過，未低於下限 |

在出貨寫法下，兩組在兩次重複中選擇的檔位都相同：
- `scout`：查詢 `low`，調查 `high`；
- `executor`：拼字 `low`，bug `medium`；
- `mech-executor`：`low`；
- `security-reviewer`：兩題都是 `high`（第 1 輪時 E4 是 `low`）；
- `verifier`：E5 為 `medium`。

template 組有一個 session（T3 第 2 次）委派了兩次，第二次以 `low` 交給 `executor`。第 2 輪以定價計算花費 $5.53（Plugin）與 $6.71（template）。每次執行的紀錄在 `a2_gate.round2_floor_wording`。

## 限制

- subagent 實際執行的 effort 沒有被記錄。看得到的只有 Agent `tool_use` 輸入裡要求的值；要求確實生效，是從規模變化推得的：同一個 scout 查詢，`low`、`high`、`max` Haiku 輸出 token 總數分別為 1.0k、6.0k、115k（`results.json` 的 `effort_scaling_probe`）。
- subagent 如果完全不呼叫工具就直接回答，它的訊息不會以 child message 出現在 stream-json 中；這種情況要看 `task_notification` 的 usage。
- 早於 2.1.292 的 client 沒有 Agent `effort` 參數。在 2.1.287 上實測一次（`old_client_probe`，用的是第 1 輪、加入下限之前的寫法），主 session 沒有傳入 effort，委派正常完成，推測是以角色預設值執行。
- A2 沒有 `plan-verifier` 的任務。另外跑了兩次（`plan_verifier_floor_probe`）：把一行計畫交給它審查，兩次都選 `medium`，正好是它的下限。
- 記錄中的 107 次委派都沒有傳 `model`（`model_param_check`），所以這幾次執行裡，Plugin 那一行縮短後的 model 句子沒有改變路由。
- `scripts/agent_run.py` 的 `./envrun` 用 `$*` 串接參數，帶內層引號的參數在 container 裡會被重新切開。A/B 兩組用的是同一個 helper。
- `CLAUDE_CODE_EFFORT_LEVEL` 的優先順序取自 Claude Code 的 sub-agents 文件，本研究沒有量測。
- A/B 中每題每組只跑一次，效果大小落在每次執行的雜訊範圍內。

## 重現

scripts 是實際執行時使用的 harness，已調整成配合 repo 的目錄結構。它們不是可直接上手的套件，而且每次呼叫都會計費。

- **A2：** 依第 3 節建立 `$A2_DIR/fixture-plugin/` 與 `$A2_DIR/fixture-template/`。設定 `A2_DIR` 與 `PILOTFISH_PLUGIN`（目前的 `plugin/`），對 `a2-tasks-<arm>.tsv` 裡的每一題、重複 1 到 2 次，執行 `scripts/one-r1.sh <arm> <task-id> <rep>`。用 `python3 scripts/score.py "$A2_DIR/out" <arm>` 計分。
- **A/B：** 將 `PILOTFISH_PLUGIN` 設為從 `a12b57a` 匯出的 `plugin/`，也就是記錄中 A/B 執行時、還沒有 effort 子句的版本。`scripts/ab.py` 會從同一個目錄 import `polyglot.py` 與 `agent_run.py`。它還需要 Polyglot 題目清單 `tasks.json`（已附）、clone 到 `scripts/data/polyglot-benchmark` 的 [Aider-AI/polyglot-benchmark](https://github.com/Aider-AI/polyglot-benchmark)、`med20.json`（已附）、`swebench` 套件，以及用 `--platform linux/amd64` 拉下的 instance image。SWE-bench 的預測用 `python -m swebench.harness.run_evaluation -d SWE-bench/SWE-bench_Verified` 判分。`polyglot.py` 與 `agent_run.py` 的獨立模式（直接用角色 prompt 的探測，`ab.py` 不會用到）另外需要 `role-*.md` 與 `pick20.json`，這兩個沒有附上。
