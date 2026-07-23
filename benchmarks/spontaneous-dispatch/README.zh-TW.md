# 自發委派行為閘門

這個閘門用一般任務請求驗證 Pilotfish 是否會自行選出預期的執行拓撲。Prompt 不會要求委派、不委派，也不會提示模型去遵循 orchestration policy。

| 測試格 | 預期拓撲 | 行為驗收條件 |
|---|---|---|
| 穩定的 12 檔機械式修改 | 恰好一個前景 `mech-executor` | 主 session 全程不得修改 source；worker 是唯一修改路徑；diff 恰好 12 個 adapter；12/12 測試通過 |
| 單一未知且緊耦合的 bug | 主 session 負責診斷與第一個最小修正 | 主 session 完成修正並觀察 focused 2/2 通過之前，不得呼叫 discovery 或 implementation agent；結尾可呼叫 `verifier` |

精確 Prompt 位於 [`prompts/`](./prompts/)。執行結果、正規化工具序列與可觀測 Agent 呼叫分別位於 [`results.json`](./results.json)、[`traces.json`](./traces.json) 與 [`agent-calls.json`](./agent-calls.json)。Raw stream 的初始化事件會包含本機路徑、session ID、hook 與 plugin inventory，因此不提交原文，只保留 SHA-256。

## 輸入契約

| 控制項 | 規則 |
|---|---|
| Prompt 詞彙 | 大小寫不敏感掃描並拒絕 `agent`、`subagent`、`worker`、`role`、`policy`、`baton`、`parallel`、`independent`、`delegat`、`orchestrat`、`fan-out` |
| Fixture 詞彙 | 對 mechanical 與 tightly coupled bug fixtures 使用同一掃描 |
| 模型歸因 | 以 stream initialization event 為準；請求 alias 不能證明實際模型 |
| 角色歸因 | 必須觀察到 `subagent_type: mech-executor` 的 `Agent` 呼叫；不得在 invocation 指定 model |
| 修改歸因 | 拒絕 top-level `Edit` 或 `Write`；保守分類每個 top-level Bash，任何 redirection 或可修改 source 的命令都判定失敗 |
| 隔離 | 只在全新 disposable copy 與乾淨的 committed baseline 執行 |

嚴格 Bash classifier 遇到不確定就判定失敗。即使最終 diff 正確，只要主 session 曾執行未分類或可寫入的命令，就不能證明修改由 worker 獨佔。

## Baseline 結果

| 執行 | 實際模型 | 正確性 | 拓撲 | 判定 |
|---|---|---|---|---|
| Fable 5、v1.3.0 mechanical | `claude-fable-5` | 未執行 | 未觀察 | `usage_credits_required`；不做行為或成本結論 |
| Opus 4.8、v1.3.0 mechanical | `claude-opus-4-8` | 12/12 | 沒有 Agent 呼叫；主 session 改寫全部檔案 | 正確性通過，拓撲失敗 |

Opus 只在一個 disposable fixture 執行一次，不能推論委派頻率或效能期望。它只能證明受測 v1.3.0 policy 在該次執行未通過這個拓撲閘門。

## Candidate 結果

| 執行 | Main 拓撲 | Source owner | 正確性 | Gate |
|---|---|---|---|---|
| Opus 4.8、v1.3.1 candidate 1 mechanical | 唯讀 triage → 一個前景 `mech-executor` → main acceptance | 僅 `mech-executor` | 12/12 | 通過 |
| Opus 4.8、v1.3.1 candidate 1 bug | Main 診斷 → main 最小修正 → main 測試與 identity probe | Main session | 2/2 | 通過 |

Mechanical Agent invocation 沒有傳入 `model`，模型 routing 由 named role definition 負責。所有 source-writing tools 都在 worker nested trace；main trace 沒有 `Edit`、`Write`、redirection 或可寫入 source 的 Bash。Bug trace 在主 session 自行修正並看到 2/2 通過的前後都沒有 Agent 呼叫。

## Exact release-payload replay

PR #19 與 PR #20 合併進 release branch 後，兩格都以 Claude Code 2.1.218、policy SHA `17d272b6…b39bf`、generated agents SHA `0b42c137…9723c` 重跑。

| Run | 可觀察 topology | Correctness | Gate |
|---|---|---|---|
| Mechanical | Opus main → 一個前景 `mech-executor`；invocation 省略 `model`；nested model 實際解析為 `claude-sonnet-5`；worker 是唯一 source-mutation path | In-session 12/12；獨立 post-run 12/12 | 通過 |
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

## 結論邊界

| 限制 | 影響 |
|---|---|
| 每格只有一筆已記錄觀察 | 結果是行為案例，不是發生率 |
| Client 回報的 cost 欄位 | 不是 provider invoice |
| Fable usage-credit gate | 沒有可用的 Fable 行為、正確性或效率比較 |
| Candidate 只以 Opus 評估 | Opus 通過不能證明其他模型有相同 routing |
| Policy iteration 數量 | Candidate 1 已通過兩格；之後 executor frontmatter 變更後，又以 exact release payload 重測相同兩格 |
| 正規化證據 | Raw-stream hash 可比對身分；公開 trace 刻意排除敏感本機資訊 |

這個閘門是 additive evidence，不會覆寫先前的 [`dispatch-brake`](../dispatch-brake/README.zh-TW.md) 或 [`baton-compatibility`](../baton-compatibility/README.zh-TW.md) 證據。
