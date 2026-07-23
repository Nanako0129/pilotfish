# 無提示 Baton dispatch-effect 配對測試

這個 paired behavioral test 問的是比 compatibility Gate 更窄的問題：任務沒有點名 Baton 時，光是讓 Baton 可見，是否會讓模型自主載入 skill 或改變 Agent topology？

> **結果：**沒有觀察到 dispatch effect。Treatment 的初始化 skill inventory 確實出現 `baton-dispatch`，但 Opus 沒有呼叫 `Skill`，也沒有呼叫 `Agent`；兩格都 inline 完成並通過 fixture test。

## 配對契約

| 變因 | Control | Treatment |
|---|---|---|
| Task prompt | 完全相同 bytes | 完全相同 bytes |
| Fixture | 完全相同 research fixture | 完全相同 research fixture |
| Pilotfish policy 與 roles | 完全相同 v1.3.1 bytes | 完全相同 v1.3.1 bytes |
| Main model | `claude-opus-4-8` | `claude-opus-4-8` |
| Setting sources | `project,local` | `project,local` |
| Baton | 不存在 | Project-scoped Baton 0.1.1、commit `77f12e6` |
| Client budget 上限 | $3 | $3 |

[`prompts/task.txt`](./prompts/task.txt) 經過大小寫不敏感掃描，不含 `baton`、`agent`、`subagent`、`worker`、獨立單字 `role`、`policy`、`skill`、`delegat`、`orchestrat`、`parallel`、`independent` 或 `fan-out`。Prompt 沒有要求任一格最佳化 topology，也沒有要求使用 planning layer。

## 觀察結果

| 觀察 | Control | Treatment | Effect Gate |
|---|---:|---:|---|
| Init 列出 Baton | 否 | 是 | Capability injection 通過 |
| `Skill` calls | 0 | 0 | 自主啟用失敗 |
| `Agent` calls | 0 | 0 | Topology delta 失敗 |
| 執行形狀 | Inline | Inline | 未觀察到 dispatch effect |
| Fixture test | 通過 | 通過 | Correctness control 通過 |
| Wall time | 129.27 s | 130.17 s | 只是單次觀察 |
| Client-reported cost | $0.718764 | $0.741686 | 不是 provider invoice |

[`results.json`](./results.json) 保留精確 hashes、metrics 與失敗的 effect Gate；[`traces.json`](./traces.json) 和 [`agent-calls.json`](./agent-calls.json) 公開正規化 tool evidence。Raw streams 的 initialization events 會包含本機路徑與 session metadata，因此不提交原文，只記錄 SHA-256。

## 重現

Treatment 會在建立 disposable baseline commit 前，把 pinned Baton dependency 複製到 project skill directory；control 不建立該目錄。兩格都排除 user settings，避免其他 user memory 或 skills 變成 A/B 變因。

```bash
SOURCE=/path/to/pilotfish
BATON=/path/to/baton-at-77f12e600406065a6e62a22a66347355e278a9d7
PAIR_ROOT="$(mktemp -d /tmp/pilotfish-baton-effect.XXXXXX)"

for CELL in control treatment; do
  WORK="$PAIR_ROOT/$CELL"
  mkdir -p "$WORK"
  cp -R "$SOURCE/benchmarks/dispatch-brake/positive-controls/research/fixture/." "$WORK/"
  cp "$SOURCE/templates/claude-md.orchestration.md" "$WORK/CLAUDE.md"

  if [ "$CELL" = treatment ]; then
    mkdir -p "$WORK/.claude/skills/baton-dispatch"
    cp "$BATON/SKILL.md" "$WORK/.claude/skills/baton-dispatch/SKILL.md"
    cp -R "$BATON/references" "$WORK/.claude/skills/baton-dispatch/references"
  fi

  git -C "$WORK" init -q
  git -C "$WORK" add .
  git -C "$WORK" -c user.name=pilotfish-benchmark \
    -c user.email=pilotfish-benchmark@example.invalid commit -qm baseline
done

TASK="$(<"$SOURCE/benchmarks/baton-dispatch-effect/prompts/task.txt")"
AGENTS_JSON="$(python3 \
  "$SOURCE/benchmarks/baton-compatibility/build-agents-json.py" \
  "$SOURCE/templates/agents")"

for CELL in control treatment; do
  cd "$PAIR_ROOT/$CELL"
  claude -p "$TASK" \
    --model opus \
    --setting-sources project,local \
    --strict-mcp-config \
    --output-format stream-json \
    --verbose \
    --no-session-persistence \
    --dangerously-skip-permissions \
    --max-budget-usd 3 \
    --agents "$AGENTS_JSON" >"$PAIR_ROOT/$CELL-stream.jsonl"
done
```

> ⚠️ **安全邊界：**permission bypass 只用於新建立、由 repository 自有 fixture 複製出的 disposable copy。

## 結論邊界

| 限制 | 影響 |
|---|---|
| 只有一個 ordered pair | 結果是一次未啟用的觀察，不是發生率 |
| 可見不等於啟用 | Init 看得到 Baton，不能證明模型讀取或遵循它 |
| 正確性相同、報告不同 | 報告文字與大小具有非決定性，不能當 effect 證據 |
| 兩格皆零 Agent call | 這項測試沒有 Baton dispatch 改變 topology 的證據 |
| 不是效能實驗 | 不得把時間或 cost 差異解讀成 Baton overhead |

先前的 [`baton-compatibility`](../baton-compatibility/README.zh-TW.md) Gate 對 lifecycle composition 仍然有效。這個配對測試補的是不同證據缺口，而且如實失敗：compatibility 不代表 Baton 會自主啟用。
