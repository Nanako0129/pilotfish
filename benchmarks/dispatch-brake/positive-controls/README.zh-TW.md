# Positive control 與被淘汰的委派 policy

## 目錄

- [重現](#重現)
- [Balanced policy 前有哪些失敗](#balanced-policy-前有哪些失敗)
- [關鍵數據](#關鍵數據)
- [已揭露限制](#已揭露限制)

原本的 state-clone benchmark 證明「委派可能造成浪費」，但無法證明同樣重要的另一半：加上 brake 後，仍會保留有價值的委派。這組 control 同時驗證兩端。

| Control | 預期決策 | 驗收閘門 |
|---|---|---|
| 小型 task-local 唯讀研究 | 比較這個 fixture 的直接閱讀與有界 fan-out；不外推完整 plan-first lifecycle | `REPORT.md` 用 `file:line` 涵蓋兩個 surface；`npm test` 通過 |
| 穩定的 12 檔機械式修改 | 若節省成本高於小幅 latency 代價，就交給便宜的機械角色 | 12 個測試全數通過；只有 adapter source 改變 |
| 緊密耦合的未知 bug | 診斷與第一次修正留在同一條 main-session 推理鏈，並保留合比例的 fresh verification | 兩個 state-clone 測試通過 |

精確 fixture 與中立 prompt 位於 [`research/`](./research/) 和 [`mechanical/`](./mechanical/)。所有完整跑完與刻意中止的結果都記在 [`results.json`](./results.json)，正規化後的工具序列與 Agent input 位於 [`traces.json`](./traces.json) 和 [`agent-calls.json`](./agent-calls.json)。Raw stream 只公開 SHA-256，因為初始化事件包含本機路徑、session identifier、hook 與 plugin inventory。

## Balanced policy 前有哪些失敗

| Policy 迭代 | Negative control | 機械式 positive control | 小型研究 control | 判定 |
|---|---|---|---|---|
| 直接工作速度 hard veto | 良好：緊密耦合工作留在 main | 不良：pilotfish 直接做，便宜 worker 被壓掉 | 直接做 | 淘汰：直接做較快不能成為通用否決條件 |
| 寬鬆 net-benefit 預設 | remora 曾退化為 scout → executor | 有委派 | 兩個 scout 在此 fixture 的 overhead 高於直接做 | 不作為 task-local 預設；未測試放入大型 Plan 的情況 |
| Net benefit + single-bug guard | 兩套都良好 | 良好：pilotfish 交給 `mech-executor` | 規模描述仍太主觀 | 保留，再收窄唯讀 fan-out |
| 有規模門檻的唯讀 gate | 未改變 | 未改變 | pilotfish 無 Agent call、直接完成 | 保留為 task-local 預設；歷史 Baton probe 未完成，後續由獨立 lifecycle Gate 補足 |

Release 決策改成 phase-aware：

| 階段 | 語意 |
|---|---|
| Discovery | 問題、scope、證據格式與 stop condition 穩定後，可在實作結果仍未知時委派唯讀調查 |
| Plan 與 approval | Main session 彙整一份 Plan；重要工作在 source write 或 implementation brief 前等待明確批准 |
| Execution | Writing agent 開始前，scope、獨佔 ownership、done criteria、整合與驗證都要穩定 |
| Net benefit | 在各階段安全邊界內，比較 model 成本、稀缺 context、時間、隔離與 fresh independence，相對於重建、協調、整合與驗證成本 |

結論刻意不是「少委派」。穩定的機械式重複工作仍是明確 positive path。Task-local 有界掃描預設由 main session 一次讀完；若有相當大的獨立 surface、可重疊的外部／工具 latency，或獨立收集的證據能實質降低 Plan 不確定性，唯讀 discovery 仍可 fan-out。

## 關鍵數據

| Run | Agent pattern | Wall time | Reported cost field | 結果 |
|---|---|---:|---:|---|
| pilotfish 機械式、hard veto | Inline；無 outcome verifier | 128.24 s | $0.790263 | 12/12 pass |
| pilotfish 機械式、balanced | `mech-executor` 前景；無 outcome verifier | 138.40 s | $0.505682 | 12/12 pass |
| pilotfish 小型研究、寬鬆 fan-out | 2 個背景 scout | 261.52 s | $1.036893 | Pass |
| pilotfish 小型研究、直接比較 | Inline | 234.10 s | $0.896864 | Pass |
| pilotfish 小型研究、有規模 gate | Inline | 228.96 s | $0.918431 | Pass |
| pilotfish 緊密耦合 bug、balanced | Inline | 77.45 s | $0.365309 | 2/2 pass |
| remora 緊密耦合 bug、balanced | Inline 診斷／修正 → 前景 verifier | 200.86 s | $0.817504 | 2/2 pass |

機械式 control 的 execution-only 區段中，委派讓 reported cost field 降低 36.01%，wall time 增加 7.92%。兩次 mechanical run 都沒有執行 release policy 必要的 outcome-verifier pass，因此只能證明便宜 execution route 仍可到達，**不能**建立完整 lifecycle savings。小型研究 control 中，兩個 scout 相較直接比較，wall time 增加 11.71%，reported cost field 增加 15.61%。這些都是單次 task-local 觀察，不是母體估計值，而且研究比較沒有包含後續 Plan 彙整或 execution。

## 重現

這是安全的 static baseline-contract check。目前 fixture 在 mechanical task 前刻意是 red：fixture-owned `npm test` 必須以 exit status 1 回報精確的 `pass 0` 與 `fail 12`。這不會重現 implementation 後的 acceptance、live model behavior、dispatch／topology、cost 或 latency。歷史 commit `863b117b9da42179c5bb77a05158920fbc092ee2` 沒有已證明可遠端取得的 named ref；任何歷史 live replay 都具備前提且非 turnkey，需要已登入且相容的 account／client／provider、另行批准的 spend authorization 與 disposable fixture。

```bash
set -eu
HARNESS="$(git rev-parse --show-toplevel)"
ROOT="$(mktemp -d "${TMPDIR:-/tmp}/pilotfish-dispatch-static.XXXXXX")"
case "$ROOT" in "${TMPDIR:-/tmp}"/pilotfish-dispatch-static.*) ;; *) exit 1 ;; esac
test -d "$ROOT"
SENTINEL="$ROOT/.sentinel"
(umask 077 && (set -C; : > "$SENTINEL"))
test -f "$SENTINEL"
test -d "$HARNESS/benchmarks/dispatch-brake/positive-controls/mechanical/fixture"
test ! -e "$ROOT/fixture"
cp -R "$HARNESS/benchmarks/dispatch-brake/positive-controls/mechanical/fixture" "$ROOT/fixture"
test -f "$ROOT/fixture/package.json"
set +e
NPM_OUTPUT="$(npm --prefix "$ROOT/fixture" test 2>&1)"
NPM_STATUS=$?
set -e
test "$NPM_STATUS" -eq 1
NORMALIZED_OUTPUT="$(printf '%s\n' "$NPM_OUTPUT" | sed 's/ℹ pass/# pass/; s/ℹ fail/# fail/')"
printf '%s\n' "$NORMALIZED_OUTPUT"
printf '%s\n' "$NORMALIZED_OUTPUT" | grep -Fx '# pass 0' >/dev/null
printf '%s\n' "$NORMALIZED_OUTPUT" | grep -Fx '# fail 12' >/dev/null
find "$ROOT/fixture" -name '*.js' -type f -print0 | xargs -0 -n 1 node --check
echo "Static fixture retained at $ROOT; remove manually when authorized."
```

只能發布審核過的 normalized evidence 與 hashes。若另行授權 raw capture，必須在 checkout／fixture 外、private mode `0600`，且不得 commit 或分享。

## 已揭露限制

| 限制 | 影響 |
|---|---|
| 每個完整條件只有一次執行 | 時間與成本差異只代表觀察到的行為，不是穩定期望值 |
| Client-reported cost field | 不是 provider 帳單 |
| 歷史 Baton probes | GPT-5.6 Sol 自動載入 [baton-dispatch v0.1.1](https://github.com/cablate/baton) 並選擇兩個唯讀 discovery call；兩個 probe 都在 Plan 彙整、批准、execution 與 verification 前停止，因此那些 run 本身沒有評估完整組合 |
| Product／model 不對稱 | Claude Opus 觀察到的決策，不能自動外推到啟用 planning skill 的 GPT-5.6 Sol |
| 完整 lifecycle | 後續、現在已是 historical 的 [pilotfish + Baton 相容性 Gate](../../baton-compatibility/README.zh-TW.md) 已為其 exact recorded bytes 完成原生 Claude 雙 turn lifecycle；那是另一個單次 Gate，不是重新解讀這兩次 probe |

歷史 remora／Baton 觀察仍是 composition probe，不是獨立的 compatibility finding。Baton 選擇可成立的 discovery topology，remora 提供具名角色與 GPT 模型分流，但兩次 probe 都在 closure 前停止。完整 E2E 證據另行公開，讓早期觀察維持原本範圍。
