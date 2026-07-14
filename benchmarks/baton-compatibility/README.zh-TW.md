# pilotfish + Baton 相容性 Gate

## 目錄

- [目的](#目的)
- [合成契約](#合成契約)
- [隔離與重現](#隔離與重現)
- [精確 prompts](#精確-prompts)
- [最終 Gate 結果](#最終-gate-結果)
- [已取代與被拒絕的 harness runs](#已取代與被拒絕的-harness-runs)
- [限制與揭露](#限制與揭露)

## 目的

這項實驗驗證 [Baton](https://github.com/cablate/baton) 與 phase-aware pilotfish v1.2.0 release candidate，能否在原生 Claude 路由下完成真正的 plan-first lifecycle。Baton 負責選擇最小且有淨效益的 delegation topology；pilotfish 繼續掌管具名角色、角色模型、leaf-agent 邊界、approval、tool capabilities 與 verifier 詞彙。精確實測 snapshot 帶有先前的 v1.1.6 candidate stamp；發布前因這是 feature-level 變更而重分類為 v1.2.0，policy bytes 唯一差異是這行不影響執行的版本註解。

> **Gate：** Discovery 可以發生在實作結果仍未知時，但 source write 必須等待 main-session Plan 與明確批准。Plan review 回覆 `READY` / `REVISE`；outcome review 回覆 `CONFIRMED` / `REFUTED`。

Fixture 是最早發佈於 pilotfish commit `5f027b8c` 的[雙 surface 研究 control](../dispatch-brake/positive-controls/research/fixture)。執行環境為 Claude Code 2.1.207、原生 first-party Claude authentication、PR #10 candidate policy，以及 `SKILL.md` SHA-256 記錄於 [`results.json`](./results.json) 的 Baton skill。

## 合成契約

```mermaid
flowchart TD
    REQUEST["使用者需求"] --> DISCOVERY["Baton 選擇 Discovery topology"]
    DISCOVERY --> PLAN["Main session 彙整 Plan"]
    PLAN --> READINESS["唯讀 plan-verifier：READY 或 REVISE"]
    READINESS --> APPROVAL["使用者明確批准"]
    APPROVAL --> EXECUTION["已批准的 execution contract"]
    EXECUTION --> OUTCOME["Fresh verifier：CONFIRMED 或 REFUTED"]
    OUTCOME --> FINAL["Main session 最終判斷"]
    PILOTFISH["pilotfish 角色、模型、leaf 與安全 gate"] --> DISCOVERY
    PILOTFISH --> READINESS
    PILOTFISH --> EXECUTION
    PILOTFISH --> OUTCOME
```

| Layer | 掌管 | 不得覆寫 |
|---|---|---|
| Baton | 問題、topology、worker 數、ownership、順序、budget、stop condition | 具名角色模型、approval、verifier capability、leaf 邊界 |
| pilotfish | 具名角色、角色模型、tool allowlist、phase gate、approval contract、verifier 詞彙 | Baton 在 gate 內的 topology 判斷 |
| Main session | 證據整合、Plan 彙整、integration、最終判斷 | 必要 approval 或獨立 verification |

## 隔離與重現

測試只在可丟棄的 Git repo 執行。最終實測的精確 policy 與八角色 session JSON 已提交於 [`final-gate-snapshot/`](./final-gate-snapshot/)；[`build-agents-json.py`](./build-agents-json.py) 會把 candidate role files 轉成注入的 `--agents` payload。這既避免覆寫已安裝的全域 pilotfish files，也讓實測 working-tree snapshot 可稽核。User memory 仍疊在較具體的 project candidate 下方，並列為限制；session-scoped roles 則會在這次 run 取代 user role definitions。

> ⚠️ **安全界線：** `--dangerously-skip-permissions` 只用在可丟棄 fixture。不要在不可信或有價值的 checkout 使用。

```bash
SOURCE=/path/to/pilotfish-pr10
ROOT="$(mktemp -d /tmp/pilotfish-baton-gate.XXXXXX)"
WORK="$ROOT/fixture"
SNAPSHOT="$SOURCE/benchmarks/baton-compatibility/final-gate-snapshot"

mkdir -p "$WORK"
cp -R "$SOURCE/benchmarks/dispatch-brake/positive-controls/research/fixture/." "$WORK/"
cp "$SNAPSHOT/CLAUDE.md" "$ROOT/CLAUDE.md"
git init -q "$WORK"
git -C "$WORK" add .
git -C "$WORK" -c user.name=pilotfish-gate \
  -c user.email=pilotfish-gate@example.invalid commit -qm baseline

AGENTS_JSON="$(cat "$SNAPSHOT/agents.json")"
SESSION_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
cd "$WORK"
```

保留 user setting source 是刻意的：Baton 安裝在使用者 skill 目錄。排除 `user` 時，Skill tool 會回覆 `Unknown skill`。Project 層 candidate policy 比 user memory 更具體；session-scoped `--agents` definitions 也高於 user agent files。

```bash
claude --dangerously-skip-permissions \
  -p --output-format json --max-budget-usd 3 \
  --session-id "$SESSION_ID" --model best --effort high \
  --setting-sources user,project,local --strict-mcp-config \
  --agents "$AGENTS_JSON" \
  "$(cat "$SOURCE/benchmarks/baton-compatibility/prompts/turn-1.txt")"

claude --dangerously-skip-permissions \
  -p --output-format json --max-budget-usd 3 \
  --resume "$SESSION_ID" --model best --effort high \
  --setting-sources user,project,local --strict-mcp-config \
  --agents "$AGENTS_JSON" \
  "$(cat "$SOURCE/benchmarks/baton-compatibility/prompts/turn-2.txt")"
```

這項 Gate 驗證 runtime policy composition 與最終精確角色定義。[`final-gate-snapshot/CLAUDE.md`](./final-gate-snapshot/CLAUDE.md) 直接以 repo 內 bytes 計算 hash；`agents.json` 透過 shell command substitution 讀取，注入與計算 hash 前會去掉檔案尾端 newline。角色定義與目前 templates 完全一致；發布 policy 在正規化不影響執行的 v1.1.6 → v1.2.0 版本註解後，也與實測 policy 完全一致。[`results.json`](./results.json) 記錄兩份 raw policy hash，tests 則鎖定只有這一項差異。Gate 不另外驗證 global file discovery 或 installer；後兩者仍由 installer review path 與 policy contract tests 覆蓋。

## 精確 prompts

| Turn | Prompt | 必要停止點 |
|---|---|---|
| Discovery + Plan | [`prompts/turn-1.txt`](./prompts/turn-1.txt) | Baton 已載入、零寫入、唯讀 `plan-verifier` 只用 `READY` / `REVISE`，接著等待批准 |
| 批准 + execution | [`prompts/turn-2.txt`](./prompts/turn-2.txt) | 只有 `REPORT.md`、測試通過、fresh outcome verifier 回 `CONFIRMED` |

## 最終 Gate 結果

| Turn | Wall time | Client-reported cost | API turns | Models | 結果 |
|---|---:|---:|---:|---|---|
| Discovery + Plan | 221.661 s | $1.763515 | 18 | Fable 5 + Opus 4.8 | Baton 已載入；直接 discovery；Git clean；唯讀 `plan-verifier` 回 `READY` |
| 已批准 execution + verification | 226.487 s | $2.025533 | 4 | Fable 5 + Sonnet 5 + Opus 4.8 | `mech-executor` 只寫 `REPORT.md`；`npm test` 通過；outcome `verifier` 回 `CONFIRMED` |
| 合計 | 448.148 s | $3.789048 | 22 | Fable 5 + Sonnet 5 + Opus 4.8 | 完整 lifecycle 通過，沒有重送 |

Baton 選擇由 main session 直接 discovery，再把穩定的單檔 execution contract 委派給 `mech-executor`。這正是預期的 phase 差異：探索中的工作留在 main；批准後的機械式撰寫走便宜 worker。Main session 保留 Plan synthesis、integration、tests 與最終判斷。

| Agent call | 排程 | Invocation `model` | 實際 model | Verdict |
|---|---|---|---|---|
| `plan-verifier`：Plan readiness | Foreground | 省略 | `claude-opus-4-8` | `READY`；實際只用 `Glob`／`Read` |
| `mech-executor`：已批准撰寫 | Foreground | 省略 | `claude-sonnet-5` | 只有 `REPORT.md` |
| `verifier`：outcome verification | Foreground | 省略 | `claude-opus-4-8` | `CONFIRMED` |

| 驗收檢查 | 結果 |
|---|---|
| Baton 可用性 | Skill tool 回覆 `Launching skill: baton-dispatch` |
| 批准前寫入 | 無；Turn 1 結束時 Git tree 乾淨 |
| Plan ownership | Main session |
| Write scope | 只有 `REPORT.md`；36 行、7,071 bytes |
| 引用驗證 | Outcome verifier 核對 34 個 surface citations |
| Repo 測試 | `REPORT.md covers both independent surfaces with file:line evidence` |
| Verifier 詞彙 | Plan `READY`；outcome `CONFIRMED`；沒有跨 mode labels |
| 具名角色路由 | 三個 Agent call 都省略 invocation-level `model`；Plan／outcome 驗證走 Opus 4.8，execution 走 Sonnet 5 |
| Startup resend | 不需要；兩個 turn 的 transcript 都正常建立並持續增長 |

Machine-readable 資料位於 [`results.json`](./results.json)。最終 raw transcript SHA-256 是 `022871ac102442caeb6f902449442d8ccea5248617efafb4bb59dbce237c2569`。

Writer 的 `Write` tool 被環境中「避免 subagent 寫報告」的保護擋了兩次；在明確批准的單檔 scope 內，它改用 Bash heredoc。最終檔案仍通過 main-session tests 與 fresh verification。這項插曲沒有擴大 scope，但確實影響 trace，因此完整揭露。

Gate 沒有觸發 long-running process，也沒有呼叫 `security-reviewer`。Long-process 保留 [@dromsak 的 4 次直接 harness 實測](https://github.com/Nanako0129/pilotfish/pull/10#issuecomment-4958570683)與四角色 contract tests；security-reviewer 邊界由正向 tool allowlist 與 policy tests 驗證。沒有額外把 edge-case Claude run 包裝成證據。

## 已取代與被拒絕的 harness runs

較早的完整 Gate 讓同一個雙 mode `verifier` 同時負責 Plan 與 outcome review。它當時通過（494.933 秒、$3.906375、12 turns），但 Codex review 指出 Plan 與批准前 security 邊界只靠 prompt。它已被上方 capability-separated run 取代；精確 inputs 仍保留於 [`gate-snapshot/`](./gate-snapshot/)，transcript hash 也仍在 [`results.json`](./results.json)。

第一次隔離嘗試不列入相容性證據。它使用 `--setting-sources project,local`，因此看不到安裝在 user 層的 Baton skill。剩餘 pilotfish gate 雖然仍得到乾淨的 `READY`，但該 run 沒有測到指定 composition，也沒有啟動批准回合。

| 證據 | 值 |
|---|---:|
| Wall time | 213.558 s |
| Client-reported cost | $1.627875 |
| API turns | 17 |
| Git state | Clean |
| 處置 | Turn 2 前拒絕 |
| Raw transcript SHA-256 | `64376ea52a4e67192df29d8595c180ddc5017638029759a8ac13aff87d5cca81` |

公開這次拒絕，是因為 dependency 根本沒載入時，其他行為即使通過也不能算相容性證據。

## 限制與揭露

> **不要把單次通過外推成通用效能主張。** 這項 Gate 只建立一條有效 lifecycle 與 routing trace，不代表預期 topology、latency 或 cost。

| 限制 | 影響 |
|---|---|
| 單次 final run | 時間與 cost 是觀察值，不是母體估計 |
| Client-reported cost field | 不是 provider invoice |
| 小型 fixture | Baton 選擇直接 discovery 與一個 mechanical writer；大型任務可能選擇有界 fan-out 或直接撰寫 |
| 動態角色注入 | 已驗證精確 final snapshot definitions，但 global agent-file discovery 不在這次 runtime Gate 範圍 |
| 未觸發的 security／long-process 路徑 | Tool allowlists、policy tests 與 contributor 專門實測涵蓋其 contract；本 fixture 不宣稱 runtime coverage |
| Candidate project memory 疊加 user memory | 較具體的 candidate policy 管理 fixture；managed policy 或矛盾的 project instruction 仍可能改變行為 |
| 本機為 patched Claude binary | Provider route 是原生 first-party Claude，但其他 Claude Code 版本仍需自己的 smoke test |
| Raw transcript 未提交 | 內含本機絕對路徑與 session metadata；改為公開 prompts、正規化 calls、content hashes、metrics 與 verdicts |
