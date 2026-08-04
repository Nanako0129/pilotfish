# 自發委派行為閘門

這個閘門用一般任務請求驗證 Pilotfish 是否會自行選出預期的執行拓撲。下面兩格，以及 [v1.3.7 配對 opt-in matrix](#v137-配對-opt-in-matrix) 的 cue-free 臂，其 prompt 都不會要求委派、不委派，也不會提示模型去遵循 orchestration policy。唯一例外是該 matrix 的明確指定臂——它的 prompt 刻意寫出委派指示，那正是被比較的介入手段，其觀察不能當成自發委派的證據。

| 測試格 | 預期拓撲 | 行為驗收條件 |
|---|---|---|
| 穩定的 12 檔機械式修改 | 恰好一個前景 `mech-executor` | Stream 包含一筆相符且已完成的 Agent result；diff 恰好 12 個 adapter；12/12 測試通過 |
| 單一未知且緊耦合的 bug | 主 session 負責診斷與第一個最小修正 | 主 session 完成修正並觀察 focused 2/2 通過之前，不得呼叫 discovery 或 implementation agent；結尾可呼叫 `verifier` |

精確 Prompt 位於 [`prompts/`](./prompts/)。執行結果、正規化工具序列與可觀測 Agent 呼叫分別位於 [`results.json`](./results.json)、[`traces.json`](./traces.json) 與 [`agent-calls.json`](./agent-calls.json)。Issue #29 的修正回溯記錄在 [`issue-29-topology.json`](./issue-29-topology.json)，由 [`classify_stream.py`](./classify_stream.py) 產生。Raw stream 的初始化事件會包含本機路徑、session ID 與 plugin inventory，因此不提交原文，只保留 SHA-256。

## 輸入契約

| 控制項 | 規則 |
|---|---|
| Prompt 詞彙 | 大小寫不敏感掃描並拒絕 `agent`、`subagent`、`worker`、`role`、`policy`、`baton`、`parallel`、`independent`、`delegat`、`orchestrat`、`fan-out` |
| Fixture 詞彙 | 對 mechanical 與 tightly coupled bug fixtures 使用同一掃描 |
| 模型歸因 | 以 stream initialization event 為準；請求 alias 不能證明實際模型 |
| 角色歸因 | 必須觀察到 `subagent_type: mech-executor` 的 `Agent` 呼叫；不得在 invocation 指定 model |
| 證據邊界 | 以 `parent_tool_use_id` 分開 main 與 child tools，並要求相符的 completed Agent result。Modified paths 與 tests 是另外的 final-state observations；不推論 filesystem mutation 的因果歸屬 |
| 隔離 | 只在全新 disposable copy 與乾淨的 committed baseline 執行 |

Classifier 記錄 dispatch reachability，不判讀 shell side effects。Final diff 正確且 worker result 已收回，也不能證明每一筆修改由哪個 process 造成。

## Baseline 結果

| 執行 | 實際模型 | 正確性 | 拓撲 | 判定 |
|---|---|---|---|---|
| Fable 5、v1.3.0 mechanical | `claude-fable-5` | 未執行 | 未觀察 | `usage_credits_required`；不做行為或成本結論 |
| Opus 4.8、v1.3.0 mechanical | `claude-opus-4-8` | 12/12 | 沒有 Agent 呼叫；主 session 改寫全部檔案 | 正確性通過，拓撲失敗 |

Opus 只在一個 disposable fixture 執行一次，不能推論委派頻率或效能期望。它只能證明受測 v1.3.0 policy 在該次執行未通過這個拓撲閘門。

## Candidate 結果

| 執行 | Main 拓撲 | 已觀察到的 source-tool scope | 正確性 | Gate |
|---|---|---|---|---|
| Opus 4.8、v1.3.1 candidate 1 mechanical | Main triage → 一個前景 `mech-executor` → main acceptance | Source-targeted tools 出現在 worker trace | 12/12 | 通過 |
| Opus 4.8、v1.3.1 candidate 1 bug | Main 診斷 → main 最小修正 → main 測試與 identity probe | Main session | 2/2 | 通過 |

Mechanical Agent invocation 沒有傳入 `model`，模型 routing 由 named role definition 負責。Source-targeted tool calls 出現在 worker nested trace，main trace 中沒有；這是 stream evidence，不是 filesystem ownership 的因果證明。Bug trace 在主 session 自行修正並看到 2/2 通過的前後都沒有 Agent 呼叫。

## Exact release-payload replay

PR #19 與 PR #20 合併進 release branch 後，兩格都以 Claude Code 2.1.218、policy SHA `17d272b6…b39bf`、generated agents SHA `0b42c137…9723c` 重跑。

| Run | 可觀察 topology | Correctness | Gate |
|---|---|---|---|
| Mechanical | Opus main → 一個前景 `mech-executor`；invocation 省略 `model`；nested model 實際解析為 `claude-sonnet-5`；source-targeted tools 出現在 worker trace | In-session 12/12；獨立 post-run 12/12 | 通過 |
| Bug | Opus main 擁有診斷、first minimal fix 與 post-fix test；零 Agent call | In-session 2/2；獨立 post-run 2/2 | 通過 |

這兩筆 additive replay 在 JSON evidence 中分別命名為 `opus-v1.3.1-release-payload-mechanical` 與 `opus-v1.3.1-release-payload-bug`。它們證明這兩個精確 input 仍守住 routing 邊界，也證明 Claude Code 接受 post-[#18](https://github.com/Nanako0129/pilotfish/issues/18) generated payload。Mechanical role 是 `mech-executor`，不是 #18 修改的另一個 `executor` definition；這次 replay 沒有 live-exercise 該 role，也不代表 dispatch 發生率。

## 重現

將 `HARNESS` 設成這個 checkout。以下命令會建立 disposable repository，明確注入 repository policy 與 role definitions，不會修改來源 checkout。

```bash
HARNESS=/path/to/pilotfish
RUN_ROOT="$(mktemp -d /tmp/pilotfish-spontaneous.XXXXXX)"
FIXTURE="$RUN_ROOT/fixture"

cp -R "$HARNESS/benchmarks/dispatch-brake/positive-controls/mechanical/fixture" "$FIXTURE"
cp "$HARNESS/templates/claude-md.orchestration.md" "$FIXTURE/CLAUDE.md"
git -C "$FIXTURE" init -q
git -C "$FIXTURE" add .
git -C "$FIXTURE" -c user.name=pilotfish-benchmark \
  -c user.email=pilotfish-benchmark@example.invalid commit -qm baseline

TASK="$(<"$HARNESS/benchmarks/spontaneous-dispatch/prompts/mechanical.txt")"
AGENTS_JSON="$(python3 \
  "$HARNESS/benchmarks/baton-compatibility/build-agents-json.py" \
  "$HARNESS/templates/agents")"

cd "$FIXTURE"
claude -p "$TASK" \
  --model opus \
  --setting-sources project,local \
  --strict-mcp-config \
  --output-format stream-json \
  --verbose \
  --no-session-persistence \
  --dangerously-skip-permissions \
  --max-budget-usd 3 \
  --agents "$AGENTS_JSON" >"$RUN_ROOT/stream.jsonl"
```

Negative cell 改複製 `benchmarks/dispatch-brake/fixture`、讀取 [`prompts/bug.txt`](./prompts/bug.txt)，其餘 invocation 相同。

> ⚠️ **安全邊界：**permission bypass 只用於新建立、由 repository 自有 fixture 複製出的 disposable copy。不可在重要或不受信任的 checkout 執行。

## v1.3.7 配對 opt-in matrix

記錄在 [`results.json`](./results.json) 的 `v1_3_7_paired_opt_in_matrix`。它回答 [#29](https://github.com/Nanako0129/pilotfish/issues/29) 未結的 Gate 項目：把 cue-free 與明確指定的 lifecycle 分成獨立 cell，各自帶帳號方案、client build、model route 與 Agent call 數。

它包含兩組比較，不是一組。

| 比較 | 測試格 | 結果 |
|---|---|---|
| 有 cue 對無 cue，皆在 Pro | cue-free schema ×2、明確 schema ×2、各一個 routine control | cue-free 兩次都沒有委派；明確臂兩次都派出 `plan-verifier`、`mech-executor` 與 `verifier`。routine 兩臂都沒有委派，符合其合約 |
| Pro 對 Max，皆為 prompt-cue-free | 每個方案各 schema ×2 與 routine ×1 | Max 兩次中有一次派出 `plan-verifier` 再派 `verifier`，prompt 裡沒有任何委派指示，四個 fixture 檔案也通過 cue 掃描。Pro 兩次都沒有 |

那次有委派的 Max attempt 在沒有被提示的情況下走完了政策 lifecycle：把帶 stable slice ID、acceptance 與 rollback 的 program envelope 交給 `plan-verifier`，取得 bare `READY`；接著由主 session 自己實作，沒有派出任何 executor；最後把五項 exact claim 交給 outcome `verifier`，取得 `CONFIRMED`。

二取一不是發生率。兩次 attempt 既無法把方案效應和 run-to-run 變異分開，也無法把它和隨方案一起變動的樹分開：Pro 那組追蹤了一份 `agents.json`，Max 那組沒有，這是兩個 baseline 唯一的 blob 差異。帳號方案與 repository 樹同時改變，所以這個 matrix 記錄的是可達性，不對成因排序。要釐清必須在 Max 的樹上重跑 Pro，而帳號已升級，該實驗不再可得。記在 `cue_free.tree_difference_between_plans`，含先前版本提出後又撤回的單調性論證。

這個限制只涉及方案比較。有 cue 對無 cue 那組是配對的：兩個 Pro 臂都從完全相同的 baseline tree `fd81141c…` 出發，含 `agents.json`，所以該檔案在那裡是共用常數，委派句仍是唯一的介入。明確臂兩次 attempt 都綁定到該樹，不只第一次。另外請注意 [`../verifier-boundary/README.md`](../verifier-boundary/README.zh-TW.md) 記載的做法是把 `agents.json` 從外部傳入；實際記錄的 run 是把它追蹤進樹，該 README 現已載明此事。細節見 `cue_free.pro_arms_share_one_tree`。

六次 schema attempt 中有五次收斂到同一份 `store.mjs`（`6aa2e259…`）——明確臂兩次、Max cue-free 兩次，以及 Pro cue-free attempt a。只有 Pro cue-free attempt b 不同。每次的測試檔案彼此都不同。也就是說，同一份實作分別由「主 session 獨力完成」、「主 session 加派兩個 review 角色」與「三角色明確 lifecycle」三種路徑抵達。

有一個用詞需要小心。`cue_free` 標示的是 prompt 不含委派指示的那一臂——亦即 prompt-cue-free。`input_contract.why` 定義的全脈絡嚴格版本，本 matrix 沒有任何 cell 完全滿足：Pro 那組追蹤了無法通過 cue 掃描的 `agents.json`，而每個 cell 的目錄裡都有未追蹤的 stream capture。Pro 那組記錄的是「repository 內已有該詞彙，仍然零委派」；這裡不與假想的乾淨脈絡 run 做強弱排序，因為那需要上面已撤回的同一個單調性假設。Max 那組的 fixture 通過掃描，餘下的脈絡明列為 `CLAUDE.md` 與那份未追蹤的 capture。各臂實際滿足什麼，記在 `cue_free.classification`。

本 matrix 每個 run 也都把自己的 stream capture 以未追蹤檔案寫進 run 目錄，因此已提交的 baseline tree 並不完全等於 session 看得到的全部脈絡。在那唯一一次有委派的 run 裡，沒有任何被記錄的 tool call 讀過那些位元組——`ls -la`、`git status` 與 `git ls-files --others` 只會列出檔名，沒有任何指令讀取內容——但 `plan-verifier` subagent 自己的 tool call 不會出現在 parent stream，所以對它無法做出同樣陳述。這些檔案在兩臂與兩個方案都同樣存在。記在 `input_contract.tree_binding.untracked_stream_captures`，連同往後的修正做法：把 capture 寫到拋棄式 repo 之外。

它的 prompt 在 [`../verifier-boundary/prompts/`](../verifier-boundary/prompts/)，不在本 benchmark 的 `prompts/`；fixture 是 [`../verifier-boundary/fixture`](../verifier-boundary/fixture)，由 matrix 記錄的 digest 綁定。schema cell 是兩輪、需要 resume session，因此不像上面較舊的 cell 使用 `--no-session-persistence`。

### 重現

請沿用上面 [重現](#重現) 區塊的 `$HARNESS`，不要從工作目錄推導 checkout：該區塊會把 shell 留在 `$FIXTURE`，而它本身也是一個 Git repository，`git rev-parse --show-toplevel` 會解析到那份拋棄式複本，底下每個路徑都會不存在。

```bash
HARNESS=/path/to/pilotfish
SNAPSHOT="$HARNESS/benchmarks/verifier-boundary/gate-snapshot-v2"
PROMPTS="$HARNESS/benchmarks/verifier-boundary/prompts"
WORK="$(mktemp -d /tmp/pilotfish-cue-free.XXXXXX)"

cp -R "$HARNESS/benchmarks/verifier-boundary/fixture/." "$WORK/"
cp "$SNAPSHOT/CLAUDE.md" "$WORK/CLAUDE.md"
git -C "$WORK" init -q && git -C "$WORK" add -A
git -C "$WORK" -c user.name=pilotfish-gate   -c user.email=pilotfish-gate@example.invalid commit -qm baseline

SESSION_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
cd "$WORK"

# turn 1 — cue-free
claude --dangerously-skip-permissions   -p --output-format stream-json --verbose --max-budget-usd 6   --session-id "$SESSION_ID" --model opus --effort high   --setting-sources project,local --strict-mcp-config   --agents "$(<"$SNAPSHOT/agents.json")"   "$(<"$PROMPTS/schema-turn-1.txt")"

# turn 2 — cue-free, resumed
claude --dangerously-skip-permissions   -p --output-format stream-json --verbose --max-budget-usd 6   --resume "$SESSION_ID" --model opus --effort high   --setting-sources project,local --strict-mcp-config   --agents "$(<"$SNAPSHOT/agents.json")"   "$(<"$PROMPTS/schema-turn-2.txt")"
```

角色定義是從 snapshot 直接傳給 `--agents`，絕不複製進 `$WORK`，與 [verifier-boundary](../verifier-boundary/README.zh-TW.md) 的做法一致。把 `agents.json` commit 進 fixture 會多出一個列出全部五個角色的受追蹤檔案，改變 run 觀察到的任務脈絡。

**這個區塊是給新 run 用的修正形狀，不是任何已記錄 cell 的精確重現。** 它與每一次已記錄的 run 有兩處刻意的差異：

| 差異 | 已記錄的 run | 這個區塊 |
|---|---|---|
| `agents.json` | Pro 那組有追蹤，baseline tree `fd81141c…`；Max 那組沒有，`d31e2096…` | 完全不複製進去；建出 `d31e2096…` |
| Stream capture | 寫進 run 目錄，`t1.jsonl` 與 `t2.jsonl` 在工作樹裡看得到 | 不做導向；`$WORK` 內不會產生任何帶線索的檔案 |

若要重建已記錄的任務脈絡而非開一份乾淨的，請補上對應的差異。Pro 那組在 commit 之前加 `cp "$SNAPSHOT/agents.json" "$WORK/agents.json"`。已記錄的 schema cell，把兩次呼叫導向 run 目錄成 `>"$WORK/t1.jsonl"` 與 `>"$WORK/t2.jsonl"`；已記錄的 routine control 則是單次呼叫導向 `>"$WORK/stream.jsonl"`。檔名本身也是已記錄脈絡的一部分，因為目錄列表顯示的就是它。這兩者只在重新檢視已記錄內容時使用，都不該出現在新的 run。各差異准許與不准許推導出什麼，記在 `cue_free.tree_difference_between_plans` 與 `input_contract.tree_binding.untracked_stream_captures`。

routine control 在另一份全新的拋棄式複本執行，使用新的 session ID、`--max-budget-usd 4` 與 [`routine-docs.txt`](../verifier-boundary/prompts/routine-docs.txt)。明確臂使用同樣三個 prompt 的 `-explicit` 版本；該臂的逐格證據記在 [`../verifier-boundary/results.json`](../verifier-boundary/results.json) 的 `passing_gate`。

重算 fixture digest：

請在原始 checkout 執行，不要在 `$WORK` ——上一個區塊會把 shell 留在拋棄式複本裡，該處相對路徑找不到任何檔案，會印出空 manifest 的 digest：

```bash
cd "$HARNESS"
python3 - <<'EOF'
import hashlib, pathlib
fx = pathlib.Path("benchmarks/verifier-boundary/fixture")
files = sorted(p for p in fx.rglob("*") if p.is_file())
manifest = "".join(
    f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(fx).as_posix()}\n"
    for p in files
)
print(hashlib.sha256(manifest.encode()).hexdigest())
EOF
```

`--dangerously-skip-permissions` 僅限這些拋棄式 fixture 使用。

## v1.3.7 Max prompt baseline

記錄在 [`results.json`](./results.json) 的 `v1_3_7_max_prompt_baseline`。它是 [#29](https://github.com/Nanako0129/pilotfish/issues/29) 上 prompt 工作的比較基準：出貨的 v1.3.7 政策在 Max 帳號上、正向與負向格一起量出來的行為，讓候選政策有東西可比，而不是憑印象。

| 測試格 | 預期 | a | b |
|---|---|---|---|
| Mechanical，12 檔案 | 一個 foreground `mech-executor`，主 session 不動原始碼 | **FAIL** — 0 Agent call，主 session 改完 12 檔 | **FAIL** — 0 Agent call，用 shell 重導向改完 12 檔 |
| 緊耦合 bug | 負向：主 session 自己診斷與首次修正 | PASS — 0 Agent call，一個 `Edit` | PASS — 0 Agent call，一個 `Edit` |
| Schema lifecycle | `plan-verifier`、實作、`verifier` | PASS — 2 個 Agent call | **FAIL** — 0 Agent call，跳過 approval gate |
| Routine docs | 負向：零 Agent call | PASS | PASS |

**正向嘗試：四取一。負向嘗試：四取四。正確性：每一格的測試都通過。** 所有失敗都是 routing 失敗，沒有一次是結果錯誤。負向那側有餘裕、正向那側沒有——候選要改善的正是這個形狀，而且不能把負向那側弄壞。

Mechanical 是目前最銳利的比較：同一份 prompt、同一個 fixture，在 Opus 4.8 與 client 2.1.217／2.1.218 上曾經二取二通過，即上面的 `opus-v1.3.1-candidate-1-mechanical` 與 `opus-v1.3.1-release-payload-mechanical`。現在二取二失敗。可觀察能力確實退化，但那些記錄與這一組之間，model、client 與政策版本三者都不同，所以這份 baseline 是起點，不是歸因。

這是第一組同時修掉 review 找出的兩個污染源的 run：`agents.json` 只經 `--agents` 傳入、絕不複製進去，每一份 capture 都寫在拋棄式 repo 之外。五個新建目錄的 `git ls-files --others --exclude-standard` 都是空的。從配對 matrix 沿用的那三次 attempt——schema a 與 b、routine a——早於 capture 修正，各自都已載明。

## Issue #29 reachability 修正

已關閉的 PR #45 曾把二十次 mechanical attempt 報成零次 dispatch pass。它的 extractor 把 child-agent event 也放進 `top_level_tools`；修正後的 classifier 只分開 scope 並比對 completed Agent result，不再解析 shell side effects。

| 修正後設定 | Dispatch reachability |
|---|---|
| Candidate 3、Opus 5、client 2.1.220 | 二取二通過 |
| v1.3.1 與 v1.3.7 policy、Opus 4.8、client 2.1.218、current roles | 四取四通過 |
| 使用 release roles 的完整 v1.3.1 reproduction | 二取一通過 |
| 其餘設定 | 十二取零通過 |

修正後總數是 **7/20**，二十次的正確性仍全為 12/12，final modified paths 也都是相同十二檔。通過代表恰好一個 foreground、已收回的 `mech-executor`，而且 invocation 沒有指定 model。Tool stream、final diff 與 test result 是分開的觀察：不能證明 filesystem mutation 的因果歸屬，也不是 dispatch rate。Client 2.1.218 使用 default effort，2.1.220 使用 high effort，因此這組比較也不能單獨歸因於 client。

歷史 Candidate 3 只證明 wording 方向，不是 release candidate：它的 mechanical dispatch reachability 二取二通過，但超出 prompt density 預算，兩次 schema attempt 也都跳過 approval gate。壓縮後候選必須重新通過 mechanical、bug、routine 與 schema gate，才能更新 snapshot hash。

## Issue #29 opt-in recovery

記錄中的 Gate candidate 使用以下明確 opt-in 後通過修正 matrix。v1.3.8 release candidate 之後又恢復 independent-review qualifier，並補上 mechanical worker 可能需要長指令時的 background 例外；這些 post-Gate policy bytes 發版前必須重新 replay：

```text
Use pilotfish. Follow its dispatch brake: keep direct work in the main session and call the named agents only when the policy selects delegation.
```

| 測試格 | Blocking contract | 結果 |
|---|---|---|
| Routine docs | 主 session 直接修改；零 Agent call | 二取二通過 |
| 單一未知 bug | 主 session 負責診斷與首次最小修正；零 Agent call | 二取二通過 |
| 穩定 12 檔重複工作 | 一個 foreground、已收回的 `mech-executor`；final modified paths 恰好十二檔 | 二取二通過，每次 12/12 tests |
| Schema lifecycle | `plan-verifier` → approval stop → 實作 → primary tests → `verifier`；實作 owner 由 brake 決定 | 二取二通過；兩次直接實作最後皆為 `CONFIRMED` |

Schema review 與 implementation routing 是兩個不同決策。Serialization 會強制 Plan 與 outcome review，但不會強制兩檔實作一定委派。Mechanical delegation 已有獨立正向格。若把 execution-agent hop 當成 schema blocker，就會違反 policy 的 net-benefit brake；先前實測也曾讓一行 docs 工作過度委派。

[`issue-29-recovery.json`](./issue-29-recovery.json) 綁定 repository policy、注入方法、generated agents payload、prompts、成本與 raw-stream hashes。歷史 transcript 觀察到 fixture `CLAUDE.md` 為預期的 17,996 bytes，但沒有提供實際併入 runtime system prompt 的位元組 digest，因此這不是 exact-loaded-policy claim。Stream 與 final-state evidence 不用來宣稱 causal mutation ownership。合格完成 cells reported `$3.91628855`；另有一次 routing 正確的 mechanical invocation 在收回 child result 前用完 `$0.60` cap，已揭露但不算通過。連同該次，campaign reported `$4.53105325`。

## 結論邊界

| 限制 | 影響 |
|---|---|
| Baseline、candidate 與 release-payload sections 各格一筆觀察；Issue #29 recovery matrix 各格兩次 attempt | 結果是行為案例，不是發生率 |
| v1.3.7 matrix 只有三個已觀察的 cell，不是完整 matrix——Pro 兩臂皆有，Max 只有 cue-free 臂，每個 cell 為 schema ×2、routine ×1 | 同樣不是發生率。Max 二取一那次委派是可達性案例；兩次 attempt 無法把方案效應、run-to-run 變異，以及隨方案一起變動的樹差異分開 |
| Client 回報的 cost 欄位 | 不是 provider invoice |
| Fable usage-credit gate | 沒有可用的 Fable 行為、正確性或效率比較 |
| Candidate 只以 Opus 評估 | Opus 通過不能證明其他模型有相同 routing |
| Policy iteration 數量 | Candidate 1 已通過兩格；之後 executor frontmatter 變更後，又以 exact release payload 重測相同兩格 |
| 正規化證據 | Raw-stream hash 可比對身分；公開 trace 刻意排除敏感本機資訊 |
| Stream 加 final state | 收回 worker call、modified paths 與 passing tests 不能證明 filesystem mutation 的因果歸屬 |

這個閘門是 additive evidence，不會覆寫先前的 [`dispatch-brake`](../dispatch-brake/README.zh-TW.md) 或 [`baton-compatibility`](../baton-compatibility/README.zh-TW.md) 證據。
