# Scout Haiku probe

[English](./README.md)

這次探測要決定 `scout` 是否從 Sonnet 改回 Haiku。2026-09-26 把 `scout` 改成 Sonnet，依據是轉述的回報：「Haiku 太常幻覺」，但從頭到尾沒有留下任何一個失敗案例。2026-10-07 Haiku 5.5 發布，這次探測量測的正是當初被回報的失敗：偵察時答錯，或編造 `file:line` 引用。

## 方法

| 項目 | 內容 |
|---|---|
| 日期 | 2026-10-08 |
| Client | 探測用 Claude Code 2.1.287。模型以完整 ID 指定，因為該版本的 `haiku` alias 仍解析成 Haiku 4.5 |
| System prompt | `aa595da` 的 `templates/agents/scout.md` 本文，也就是 Sonnet 時期的 prompt；它和現在出貨的版本只差 model 那一行 |
| 工具 | `--tools Read,Glob,Grep`（與 scout 的 allowlist 相同） |
| 隔離 | `--setting-sources project --strict-mcp-config`，在 `git archive aa595da` 快照中執行；沒有使用者 hooks、plugins、MCP，也沒有未追蹤檔案 |
| 題目 | 兩輪各 10 題：[第一輪](./task-round1.txt)是查詢題；[第二輪](./task-round2.txt)包含 12 項的完整列舉、跨函式追蹤、精確計數，以及從繁中文件取數字。其中 6 題是陷阱題，問的東西並不存在，有幾題還安排了容易誤認的相近內容 |
| 設定 | Haiku 5.5 的 `low`、`medium`、`high`、`xhigh`、`max`；Sonnet 5.5 `low`（當時的 scout）；Haiku 4.5 `low`（9/26 被換掉的模型）。每組每輪跑 2 次，每組共 40 個答案 |
| 評分 | 主答案逐題對照 answer key（[第一輪](./answer-key-round1.md)、[第二輪](./answer-key-round2.md)）。所有答案附帶的 `file:line` 引用，全部打開快照逐條核對 |

## 結果

每次執行的評分、token 數與缺陷記在 [`results.json`](./results.json)，每份最終答案放在 [`answers/`](./answers/)。

| 設定 | 答錯或不完整（共 40） | 編造引用 | 其他瑕疵 | 平均耗時 | 平均輸入／輸出 token |
|---|---|---|---|---|---|
| Sonnet 5.5 `low` | 1 | 0 | 0 | 34 秒 | 79k / 4.9k |
| Haiku 5.5 `low` | 0 | 0 | 0 | 29 秒 | 113k / 6.9k |
| Haiku 5.5 `medium` | 0 | 0 | 1 | 37 秒 | 223k / 7.7k |
| Haiku 5.5 `high` | 0 | 0 | 0 | 59 秒 | 406k / 11.5k |
| Haiku 5.5 `xhigh` | 0 | 0 | 1 | 87 秒 | 447k / 19.1k |
| Haiku 5.5 `max` | 0 | 0 | 0 | 189 秒 | 459k / 45.2k |
| Haiku 4.5 `low` | 2 | 0 | 2 | 110 秒 | 938k / 9.5k |

輸入 token 包含 cache read。「其他瑕疵」指的是語句不通、hash 縮寫抄錯，或引用位置偏離重點；這幾種情況的主答案都是對的。

Haiku 5.5 的 effort 拉到 `low` 以上，主答案準確度沒有可量測的提升，反而多花時間和 token；出現其他瑕疵的兩組（`medium`、`xhigh`）也都在 `low` 以上，所以出貨的角色維持 `effort: low`。

## 限制

- **鑑別力弱。** Haiku 4.5 也幾乎全對，代表這次探測在任何模型上都沒有重現當初回報的失敗。它只能說明：在有範圍限制的偵察工作上，量不到準確度差距。它不能說明 Haiku 不會幻覺。
- Anthropic 的 [Haiku 5.5 system card](https://www.anthropic.com/document/claude-haiku-5-5-system-card)（2026-10-07）寫到，Haiku 5.5 的幻覺程度與 Haiku 4.5 相當，而 Sonnet 5.5 在 input hallucination（錯誤轉述檔案或工具輸出）上嚴格較佳。那是通用量測，不是 scout 的工作情境，但這正是 orchestrator 仍要核對「只靠單一事實的決策」的理由。
- 只測了一個 repo、20 題，每組重複 2 次。

## 出貨角色檢查

在 Claude Code 2.1.294 上，以 `--plugin-dir` 載入本分支的 `plugin/`，並加上 `--output-format stream-json --verbose`。主 session 發出 `Agent` `tool_use` `toolu_017ZLSiKQWjARhKAKtYfaKka`，其 `subagent_type` 為 `pilotfish:scout`；`parent_tool_use_id` 等於該 id 的 child assistant message，`message.model` 為 `claude-haiku-5-5`。整個 session 的 `modelUsage` 不能當證據，因為 Claude Code 自己的輔助呼叫也會用到 Haiku。

## 重現

```bash
bash benchmarks/scout-haiku-probe/run.sh benchmarks/scout-haiku-probe/task-round1.txt /tmp/scout-probe/round1
bash benchmarks/scout-haiku-probe/run.sh benchmarks/scout-haiku-probe/task-round2.txt /tmp/scout-probe/round2
```

每次呼叫都會計費，每輪 14 次。只要有任何一次呼叫失敗，腳本就會以非零值結束。`answers/` 裡的每個檔案，都是一份輸出 JSON 的 `result` 欄位。answer key 只適用 ref `aa595da`，也就是第三個參數的預設值。
