# Positive control 與被淘汰的委派 policy

原本的 state-clone benchmark 證明「委派可能造成浪費」，但無法證明同樣重要的另一半：加上 brake 後，仍會保留有價值的委派。這組 control 同時驗證兩端。

| Control | 預期決策 | 驗收閘門 |
|---|---|---|
| 小型唯讀研究 | 除非掃描量或 latency 足以攤平 worker 啟動與彙整成本，否則直接做 | `REPORT.md` 用 `file:line` 涵蓋兩個 surface；`npm test` 通過 |
| 穩定的 12 檔機械式修改 | 若節省成本高於小幅 latency 代價，就交給便宜的機械角色 | 12 個測試全數通過；只有 adapter source 改變 |
| 緊密耦合的未知 bug | 診斷與第一次修正留在同一條 main-session 推理鏈，並保留合比例的 fresh verification | 兩個 state-clone 測試通過 |

精確 fixture 與中立 prompt 位於 [`research/`](./research/) 和 [`mechanical/`](./mechanical/)。所有完整跑完與刻意中止的結果都記在 [`results.json`](./results.json)，正規化後的工具序列與 Agent input 位於 [`traces.json`](./traces.json) 和 [`agent-calls.json`](./agent-calls.json)。Raw stream 只公開 SHA-256，因為初始化事件包含本機路徑、session identifier、hook 與 plugin inventory。

## Balanced policy 前有哪些失敗

| Policy 迭代 | Negative control | 機械式 positive control | 小型研究 control | 判定 |
|---|---|---|---|---|
| 直接工作速度 hard veto | 良好：緊密耦合工作留在 main | 不良：pilotfish 直接做，便宜 worker 被壓掉 | 直接做 | 淘汰：直接做較快不能成為通用否決條件 |
| 寬鬆 net-benefit 預設 | remora 曾退化為 scout → executor | 有委派 | 不良：約十來個短檔案也叫了兩個 scout | 淘汰：目錄互相獨立不等於規模足夠 |
| Net benefit + single-bug guard | 兩套都良好 | 良好：pilotfish 交給 `mech-executor` | 規模描述仍太主觀 | 保留，再收窄唯讀 fan-out |
| 有規模門檻的唯讀 gate | 未改變 | 未改變 | pilotfish 無 Agent call、直接完成 | 納入；remora 與自動載入通用 skill 的互動列為已知限制 |

最終決策分成兩層：

| 層級 | 語意 |
|---|---|
| Hard blockers | 成功條件未穩定、worker 依賴 main session 持續變動的證據、寫入重疊或 closure 沒有 owner 時，不委派 |
| Net benefit | 其他工作比較 model 成本、稀缺 context、時間、隔離與 fresh independence，相對於重建、協調、整合與驗證成本 |

結論刻意不是「少委派」。穩定的機械式重複工作仍是明確 positive path。Repo 唯讀 fan-out 改為 opt-in，必須有每個 surface 都相當大的掃描量、可重疊的外部／工具 latency，或驗收明確要求獨立觀點。約十來個短檔案預設由 main session 一次讀完。

## 關鍵數據

| Run | Agent pattern | Wall time | Reported cost field | 結果 |
|---|---|---:|---:|---|
| pilotfish 機械式、hard veto | Inline | 128.24 s | $0.790263 | 12/12 pass |
| pilotfish 機械式、balanced | `mech-executor` 前景 | 138.40 s | $0.505682 | 12/12 pass |
| pilotfish 小型研究、寬鬆 fan-out | 2 個背景 scout | 261.52 s | $1.036893 | Pass |
| pilotfish 小型研究、直接比較 | Inline | 234.10 s | $0.896864 | Pass |
| pilotfish 小型研究、有規模 gate | Inline | 228.96 s | $0.918431 | Pass |
| pilotfish 緊密耦合 bug、balanced | Inline | 77.45 s | $0.365309 | 2/2 pass |
| remora 緊密耦合 bug、balanced | Inline 診斷／修正 → 前景 verifier | 200.86 s | $0.817504 | 2/2 pass |

機械式 control 中，委派讓 reported cost field 降低 36.01%，wall time 增加 7.92%。小型研究 control 中，過度寬鬆的兩個 scout 相較直接比較，wall time 增加 11.71%，reported cost field 增加 15.61%。這些都是單次觀察，不是母體估計值。

## 重現

把任一 fixture 複製到可丟棄目錄、初始化成 Git repo、確認 baseline，再使用相鄰 `task.md` 的 prompt。

```bash
cp -R benchmarks/dispatch-brake/positive-controls/mechanical/fixture /tmp/pilotfish-mechanical
cd /tmp/pilotfish-mechanical
git init
git add .
git commit -m baseline
npm test

TASK="$(sed -n '/^```text$/,/^```$/p' \
  /path/to/pilotfish/benchmarks/dispatch-brake/positive-controls/mechanical/task.md \
  | sed '1d;$d')"

/usr/bin/time -p claude -p "$TASK" \
  --output-format stream-json \
  --verbose \
  --no-session-persistence \
  --dangerously-skip-permissions \
  --max-budget-usd 3 \
  --append-system-prompt-file /path/to/pilotfish/templates/claude-md.orchestration.md
```

> ⚠️ **安全界線：** bypass mode 只用在這些公開 fixture 的可丟棄 copy。不要套用到不可信或有價值的 checkout。

## 已揭露限制

| 限制 | 影響 |
|---|---|
| 每個完整條件只有一次執行 | 時間與成本差異只代表觀察到的行為，不是穩定期望值 |
| Client-reported cost field | 不是 provider 帳單 |
| Claude 額度接近耗盡 | 沒有再啟動 pilotfish live repetition；已完成的 sized-gate run 完整保留 |
| 同時安裝 [baton-dispatch v0.1.1](https://github.com/cablate/baton) | GPT-5.6 Sol 自動載入通用 skill，remora 的小型研究仍 fan-out。兩個 follow-up probe 在觀察到決策違反後停止；沒通過驗證的 precedence 文字已移除，沒有假裝發布為修正 |
| Product／model 不對稱 | Claude Opus 遵守的 policy，不能自動外推到後續又注入 skill 指令的 GPT-5.6 Sol |

因此 remora／Baton 的互動是公開的 compatibility finding，不是已修正宣稱。Release policy 改善 standalone routing contract，且已有 positive／negative 行為證據，但不宣稱能壓過每一個使用者另外安裝的 orchestration skill。
