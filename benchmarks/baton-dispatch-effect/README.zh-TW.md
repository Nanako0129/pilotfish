# Prompt-neutral Baton 啟用與委派矩陣

這組 behavioral matrix 分開問兩件事：小型任務只讓 Baton 可見時是否會呼叫它，以及目前 pilotfish policy 遇到沒有點名 Baton／Agent 的大型跨 surface user prompt 時，是否能同時觀察到 Baton invocation 與完整、可驗證的委派流程。

> **結果：**小型 availability observation 仍由 main inline 完成；大型 v1.3.1 Gate 則通過。之後以 post-PR-19 exact release payload 重跑，也通過相同的 activation、四-scout dispatch、ownership、collection 與 final-byte correctness 邊界；agents SHA 是 `0b42c137…9723c`。

## 測試內容

| Cell | Prompt 與 fixture | Policy | 結果 |
|---|---|---|---|
| Small control | 雙 surface research task；沒有 Baton | 較早的 v1.3.1 candidate | 0 `Skill`、0 `Agent`、correctness 通過 |
| Small treatment | 同一任務；可見 project-scoped Baton 0.1.1 | 同一份較早 candidate | 0 `Skill`、0 `Agent`、correctness 通過 |
| Large Gate | 四個 substantial domains；可見 project-scoped Baton 0.1.1 | v1.3.1 release policy，SHA `17d272b6…b39bf` | 1 次 Baton `Skill`、4 個完成的 background `scout`；ownership／collection／correctness 通過 |
| Release-payload replay | 相同 substantial prompt 與 pinned fixture | Policy SHA `17d272b6…b39bf`；post-PR-19 agents SHA `0b42c137…9723c` | 相同的 1 Skill／4 completed scouts topology；in-session 與獨立 final-byte tests 都通過 |

兩份 prompt 都通過大小寫不敏感掃描，不含 Baton、agent、subagent、worker、role、skill、delegation、orchestration、parallelism 或 fan-out 字樣。但這只描述 prompt；兩個 fixtures 都含 orchestration 內容。因此 small ordered pair 只保留為 availability observation，大型 Gate 只建立 prompt-neutral policy reachability，不宣稱是完整 cue-free causal experiment。另一項 [`spontaneous-dispatch`](../spontaneous-dispatch/README.zh-TW.md) matrix 才會同時掃描 user prompts 與 task fixtures，支撐 cue-free topology claim。

## 大型 Gate 契約

| Input | 固定值 |
|---|---|
| Client | 最終 `large-v131-4` 使用 Claude Code 2.1.218；attempts 1–3 使用 2.1.217 |
| Requested / observed main model | `opus` / `claude-opus-4-8` |
| Settings | `project,local`；strict MCP；不保留 session |
| Baton | 0.1.1、commit `77f12e6`、`SKILL.md` SHA `48b1e573…3d67` |
| 歷史 attempts role payload | 八個 pilotfish roles，SHA `e901e16a…c61` |
| Release replay role payload | 八個 pilotfish roles，SHA `0b42c137…9723c`；#18 後 `executor` 由 Opus 改為 Sonnet |
| Policy | v1.3.1 release policy，SHA `17d272b6…b39bf` |
| Prompt | [`prompts/large-audit.txt`](./prompts/large-audit.txt)，SHA `c0cebdce…ffba` |
| Fixture baseline | Commit `34ebabe2…245f`、tree `3773149b…2574`；45 個 domain files／3,032 行 |
| Budget | 每次上限 $5 |

Disposable fixture 把四組 repository surfaces 映射成 `domain-a` 至 `domain-d`，將目前 policy 複製成 `CLAUDE.md`，以 project skill 安裝 pinned Baton，並加入只驗證輸出形狀的 [`verify-audit.mjs`](./large-fixture/verify-audit.mjs)。

## 嘗試矩陣

| Attempt | Baton / agents | Ownership 與 collection | 結果 |
|---|---:|---|---|
| `large-v131-1` | 1 / 2 完成 | 失敗：main 重複讀取 active domain-c/domain-d | `AUDIT.md` 與 test 通過，但 Gate 失敗 |
| `large-v131-2` | 1 / 2 完成 | 失敗：mixed-scope Bash 讀到 active `domain-c/VERSION` | `AUDIT.md` 與 test 通過，但 Gate 失敗 |
| `large-v131-3` | 1 / 4 派出、2 完成 | 未觀察到 overlap | 兩個 scouts 撞到 session limit，沒有 report；Gate 失敗 |
| `large-v131-4` | 1 / 4 完成 | 通過：四份結果都先收回，才開始跨域工作 | 只新增 `AUDIT.md`；`npm test` 通過；Gate 通過 |

前三次失敗都保留在 [`results.json`](./results.json)，沒有只挑成功樣本。這些失敗直接促成兩項 policy 修正：active agent-owned read scope 在回收結果前是暫時 exclusive，mixed Bash command 內每一條 path 都要檢查；選定多個 agents 後，必須先 back-to-back 完成所有 background launch，再繼續 main 的 disjoint work。

## 最終 trace

```text
Bash → Read → Bash → Skill(baton-dispatch)
  → Agent(domain-a, background)
  → Agent(domain-b, background)
  → Agent(domain-c, background)
  → Agent(domain-d, background)
  → 收回四份結果
  → post-collection spot-check → Write → npm test → Edit
```

| Gate 維度 | 證據 | 狀態 |
|---|---|---|
| Activation | Init 可見 Baton，而且 dispatch 前先呼叫 Baton | 通過 |
| Topology | 四個 `scout`；全是 background；invocation-level `model` 全省略 | 通過 |
| Ownership | Agents active 期間，main 沒有讀取或分析任何 agent-owned domain content | 通過 |
| Collection | Completion events 199、236、252、258 都早於 spot-check event 280 | 通過 |
| Correctness boundary | In-session test 在 event 313，最後 Edit 在 event 320；因此另以 final SHA `1a23459c…4969` 重跑 `npm test`，通過且仍只變更 `AUDIT.md` | 通過 |

最終 run 的 wall time 是 400.00 秒，client cost 欄位為 $1.8456953。平行 agent 的 API time 是 655.635 秒，因此可以大於 wall time。一位 fresh verifier 拒絕原本的 completed claim；後續檢查發現 in-session test 早於最後 Edit，所以再對 final bytes 獨立重跑，結果通過，並在 `2026-07-23T02:01:06Z` 記錄這份證據。Raw streams 的 initialization events 含本機 path 與 session metadata，所以不提交原文；[`results.json`](./results.json) 用 SHA-256 綁定每份 stream 與 report，[`traces.json`](./traces.json) 與 [`agent-calls.json`](./agent-calls.json) 公開正規化證據。

## Exact release-payload replay

Replay 使用 Claude Code 2.1.218、相同 committed fixture baseline 與 prompt-neutral user request、精確 current policy SHA `17d272b6…b39bf`，以及 generated agents SHA `0b42c137…9723c`。Init inventory 可見 Baton，dispatch 前也確實呼叫；之後四個 background `scout` back-to-back 啟動，所有 invocation 都未帶 model override。Completion events 278、320、348、360 全部早於第一個跨域 sanity check event 394。

唯一變更是新增 `AUDIT.md`。單一 Write 在 event 402，in-session `npm test` 在 event 405；另一次獨立重跑也對相同 final SHA `92a111dd…17a` 通過。Replay 的 client duration 是 168.156 秒，client cost 欄位為 $1.6609134，並 additive 記錄於 `release_payload_replay`，不會改寫歷史 attempts。

## 結論邊界

| 已建立 | 未建立 |
|---|---|
| Substantial prompt-neutral request 在 final Gate 啟用 Baton，exact release payload 重跑時也再次啟用 | 完整 cue-free 環境，或具代表性樣本中的啟用頻率與可靠度 |
| Baton invocation 之後觀察到四個完成的 named-role calls | 與大型 no-Baton control 的 causal comparison |
| 最終 run 遵守 exclusive discovery ownership 並收回每份結果 | 更低 latency、cost 或更高效率 |
| 產物通過 repository-owned shape test | Audit 內每一條語意 claim 都正確 |
| 最終 Gate 在 Claude Code 2.1.218 通過 | Policy 修正單獨解釋與 attempts 1–3 的差異；前三次使用 2.1.217 |

先前的 [`baton-compatibility`](../baton-compatibility/README.zh-TW.md) Gate 仍是其 exact historical policy bytes 的 approval-lifecycle 記錄；本矩陣則驗證更新後 policy 的 activation、dispatch、ownership、collection 與 output-shape boundary。

> ⚠️ Permission bypass 只用在全新建立的 disposable fixtures。
