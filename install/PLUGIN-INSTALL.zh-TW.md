# pilotfish macOS 與 Linux Plugin beta 安裝指南

[English](./PLUGIN-INSTALL.md)

> 這個 experimental beta 適用於 macOS 與 Linux。依據[官方系統需求](https://code.claude.com/docs/en/setup#system-requirements)（查核日期 2026-08-22），Linux 需要 Ubuntu 20.04+、Debian 10+ 或 Alpine Linux 3.19+，並且 Claude Code 本身已能在官方支援範圍內正常運作。macOS 搭配 Claude Code 2.1.239 已有 live observation；Linux 僅完成 contract qualification，未經測試、驗證或 live observation。Windows 不在範圍內。Ambient activation 需要 SessionStart hooks。本 beta 不主張 stable reliability、跨版本相容性或 runtime namespace-collision proof。

Plugin 不可與 legacy global install 共存。若有效的 user `CLAUDE.md` 包含 pilotfish 的標準 markers 或已知 legacy policy header，Plugin hook 會 fail closed：不輸出 policy，並要求先完成遷移。

## 目錄

- [安裝前檢查](#安裝前檢查)
- [從 global v1 遷移](#從-global-v1-遷移)
- [安裝前選擇主模型](#安裝前選擇主模型)
- [安裝到 user scope](#安裝到-user-scope)
- [更新](#更新)
- [停用或重新啟用](#停用或重新啟用)
- [移除](#移除)
- [手動 rollback](#手動-rollback)
- [疑難排解](#疑難排解)

## 安裝前檢查

執行以下可直接貼上的 POSIX `/bin/sh` preflight。它會執行 `claude --version`，只接受第一個 token 為數字格式 `X.Y.Z`，並要求 Claude Code 2.1.219 或更新版本。這個最低版本比已驗證能強制 agent `tools` allowlists 的 baseline 更新；不要安裝只有 prompt 的近似版本，因為 read-only 的 `plan-verifier` 與 `security-reviewer` roles 依賴這些 allowlists。

若 `CLAUDE_CODE_SUBAGENT_MODEL` 非空，preflight 也會拒絕繼續，且不會輸出其值，因為這個變數會覆蓋所有 agent 的 `model` frontmatter。請自行 unset 後重跑，不要讓 installer 默默修改呼叫端環境。

同一個 preflight 會解析有效的 user configuration root，並在不輸出 `CLAUDE.md` 內容的情況下檢查 legacy global policy。若 `CLAUDE_CONFIG_DIR` 非空，必須是 absolute path；否則 Claude Code 使用 `$HOME/.claude`。

```bash
pilotfish_plugin_preflight() {
  if CLAUDE_VERSION_OUTPUT=$(claude --version 2>/dev/null); then
    :
  else
    echo "Stop: claude --version failed. Install or repair Claude Code, then rerun this preflight." >&2
    return 1
  fi

  read -r CLAUDE_VERSION _ <<EOF
$CLAUDE_VERSION_OUTPUT
EOF
  case "$CLAUDE_VERSION" in
    *.*.*) ;;
    *)
      echo "Stop: Claude Code version must be a first-token numeric X.Y.Z. Update Claude Code, then rerun this preflight." >&2
      return 1
      ;;
  esac
  case "$CLAUDE_VERSION" in
    ''|*[!0-9.]*|*.*.*.*|.*|*.|*..*)
      echo "Stop: Claude Code version must be a first-token numeric X.Y.Z. Update Claude Code, then rerun this preflight." >&2
      return 1
      ;;
  esac

  CLAUDE_MAJOR=${CLAUDE_VERSION%%.*}
  CLAUDE_REST=${CLAUDE_VERSION#*.}
  CLAUDE_MINOR=${CLAUDE_REST%%.*}
  CLAUDE_PATCH=${CLAUDE_REST#*.}
  while [ "${CLAUDE_MAJOR#0}" != "$CLAUDE_MAJOR" ]; do CLAUDE_MAJOR=${CLAUDE_MAJOR#0}; done
  while [ "${CLAUDE_MINOR#0}" != "$CLAUDE_MINOR" ]; do CLAUDE_MINOR=${CLAUDE_MINOR#0}; done
  while [ "${CLAUDE_PATCH#0}" != "$CLAUDE_PATCH" ]; do CLAUDE_PATCH=${CLAUDE_PATCH#0}; done
  CLAUDE_MAJOR=${CLAUDE_MAJOR:-0}
  CLAUDE_MINOR=${CLAUDE_MINOR:-0}
  CLAUDE_PATCH=${CLAUDE_PATCH:-0}

  CLAUDE_VERSION_OK=0
  if [ "${#CLAUDE_MAJOR}" -gt 1 ] || [ "$CLAUDE_MAJOR" -gt 2 ]; then
    CLAUDE_VERSION_OK=1
  elif [ "$CLAUDE_MAJOR" -eq 2 ]; then
    if [ "${#CLAUDE_MINOR}" -gt 1 ] || [ "$CLAUDE_MINOR" -gt 1 ]; then
      CLAUDE_VERSION_OK=1
    elif [ "$CLAUDE_MINOR" -eq 1 ] && \
        { [ "${#CLAUDE_PATCH}" -gt 3 ] || \
          { [ "${#CLAUDE_PATCH}" -eq 3 ] && [ "$CLAUDE_PATCH" -ge 219 ]; }; }; then
      CLAUDE_VERSION_OK=1
    fi
  fi
  if [ "$CLAUDE_VERSION_OK" -ne 1 ]; then
    echo "Stop: pilotfish requires Claude Code 2.1.219 or newer. Update Claude Code, then rerun this preflight." >&2
    return 1
  fi

  if [ -n "${CLAUDE_CODE_SUBAGENT_MODEL:-}" ]; then
    echo "Stop: CLAUDE_CODE_SUBAGENT_MODEL is non-empty and overrides every agent model frontmatter. Unset it yourself, then rerun this preflight." >&2
    return 1
  fi

  CFG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
  case "$CFG" in
    /*) ;;
    *) echo "Stop: CLAUDE_CONFIG_DIR must be absolute." >&2; return 1 ;;
  esac

  if [ ! -d "$CFG" ] || [ ! -r "$CFG" ] || [ ! -x "$CFG" ]; then
    echo "Stop: the effective config root must be an existing, readable, searchable directory." >&2
    return 1
  elif [ -L "$CFG/CLAUDE.md" ]; then
    echo "Stop: CLAUDE.md must not be a symlink; replace it with a regular readable file or remove it." >&2
    return 1
  elif [ ! -e "$CFG/CLAUDE.md" ]; then
    echo "No legacy global pilotfish policy detected."
  elif [ ! -f "$CFG/CLAUDE.md" ] || [ ! -r "$CFG/CLAUDE.md" ]; then
    echo "Stop: CLAUDE.md cannot be checked safely." >&2
    return 1
  elif PATH=/usr/bin:/bin grep -F -q \
      -e '<!-- pilotfish:begin -->' \
      -e '<!-- pilotfish:end -->' \
      -e '<!-- pilotfish v' \
      -e 'Main-session policy. Named roles (' \
      "$CFG/CLAUDE.md"; then
    echo "Stop: legacy global pilotfish detected; migrate before installing." >&2
    return 1
  else
    case $? in
      1) echo "No legacy global pilotfish policy detected." ;;
      *) echo "Stop: CLAUDE.md cannot be checked safely." >&2; return 1 ;;
    esac
  fi
}

pilotfish_plugin_preflight
```

只有在指令輸出 `No legacy global pilotfish policy detected.` 後才能繼續；任何其他結果都代表 fail closed。

## 從 global v1 遷移

最簡單的方式，是讓 Claude Code 從已審閱的本地 pilotfish checkout 執行遷移。請在該 checkout 中啟動 Claude Code，貼上以下 prompt：

```text
請讀取這個 checkout 中的 install/PLUGIN-INSTALL.zh-TW.md 與
install/AGENT-INSTALL.md，嚴格依照這兩份 runbook，把我既有的 global
pilotfish v1 安裝遷移成 user-scope pilotfish Plugin。

請先解析有效的 Claude configuration root，並執行 read-only preflight。顯示
解析後的 root、預定的 timestamped backup path，以及將要修改的確切檔案與
settings，然後只向我要求一次批准。批准後，先建立該 backup，
並進行 read-back verification。若任何必要的 backup copy 或 verification 失敗，
請在移除或安裝任何內容之前停止。只有 verified backup 成功後，才能移除 legacy
pilotfish policy block、未經修改的 pilotfish agent files，以及可歸因於該安裝
的 settings；保留所有無關的設定與檔案。如果 agent file 曾被自訂，或 ownership
不明，請停止並顯示差異，不要刪除。重新執行 preflight，將
pilotfish@pilotfish 安裝到 user scope，驗證已安裝的 Plugin，最後告訴我重啟
Claude Code。不要輸出 credentials，也不要在仍有 legacy policy 時安裝 Plugin。
```

除非 AI 發現自訂內容或無法確認的 legacy state，否則只需要這一次寫入批准。以下是對應的手動操作。

移除任何內容前，先備份有效設定：

```bash
set -eu

CFG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
case "$CFG" in
  /*) ;;
  *) echo "Stop: CLAUDE_CONFIG_DIR must be absolute." >&2; exit 1 ;;
esac
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$CFG/backups/pilotfish-global-$STAMP"
BACKUP_TEMP="$CFG/backups/.pilotfish-global-$STAMP.tmp"
mkdir -p "$CFG/backups"
if [ -e "$BACKUP" ] || [ -L "$BACKUP" ]; then
  echo "Stop: backup destination already exists: $BACKUP" >&2
  exit 1
elif [ -e "$BACKUP_TEMP" ] || [ -L "$BACKUP_TEMP" ]; then
  echo "Stop: backup temporary path already exists: $BACKUP_TEMP" >&2
  exit 1
fi
mkdir "$BACKUP_TEMP"

pilotfish_backup_fail() {
  PILOTFISH_BACKUP_ERROR=$1
  rm -rf "$BACKUP_TEMP"
  echo "Stop: $PILOTFISH_BACKUP_ERROR" >&2
  exit 1
}

pilotfish_published_backup_fail() {
  PILOTFISH_BACKUP_ERROR=$1
  rm -rf "$BACKUP"
  echo "Stop: $PILOTFISH_BACKUP_ERROR" >&2
  exit 1
}

BACKED_UP_CLAUDE=0
BACKED_UP_SETTINGS=0
BACKED_UP_AGENTS=0

if [ -e "$CFG/CLAUDE.md" ] || [ -L "$CFG/CLAUDE.md" ]; then
  if [ -L "$CFG/CLAUDE.md" ] || [ ! -f "$CFG/CLAUDE.md" ]; then
    pilotfish_backup_fail "CLAUDE.md must be a regular file."
  elif ! cp -p "$CFG/CLAUDE.md" "$BACKUP_TEMP/CLAUDE.md"; then
    pilotfish_backup_fail "CLAUDE.md backup copy failed."
  fi
  if [ -L "$BACKUP_TEMP/CLAUDE.md" ] || [ ! -f "$BACKUP_TEMP/CLAUDE.md" ] || \
      ! cmp -s "$CFG/CLAUDE.md" "$BACKUP_TEMP/CLAUDE.md"; then
    pilotfish_backup_fail "CLAUDE.md backup verification failed."
  fi
  BACKED_UP_CLAUDE=1
fi

if [ -e "$CFG/settings.json" ] || [ -L "$CFG/settings.json" ]; then
  if [ -L "$CFG/settings.json" ] || [ ! -f "$CFG/settings.json" ]; then
    pilotfish_backup_fail "settings.json must be a regular file."
  elif ! cp -p "$CFG/settings.json" "$BACKUP_TEMP/settings.json"; then
    pilotfish_backup_fail "settings.json backup copy failed."
  fi
  if [ -L "$BACKUP_TEMP/settings.json" ] || \
      [ ! -f "$BACKUP_TEMP/settings.json" ] || \
      ! cmp -s "$CFG/settings.json" "$BACKUP_TEMP/settings.json"; then
    pilotfish_backup_fail "settings.json backup verification failed."
  fi
  BACKED_UP_SETTINGS=1
fi

if [ -e "$CFG/agents" ] || [ -L "$CFG/agents" ]; then
  if [ -L "$CFG/agents" ] || [ ! -d "$CFG/agents" ]; then
    pilotfish_backup_fail "agents must be a directory."
  elif ! cp -Rp "$CFG/agents" "$BACKUP_TEMP/agents"; then
    pilotfish_backup_fail "agents backup copy failed."
  fi
  if [ -L "$BACKUP_TEMP/agents" ] || [ ! -d "$BACKUP_TEMP/agents" ] || \
      ! diff -r "$CFG/agents" "$BACKUP_TEMP/agents" >/dev/null 2>&1; then
    pilotfish_backup_fail "agents backup verification failed."
  fi
  BACKED_UP_AGENTS=1
fi

if ! mv "$BACKUP_TEMP" "$BACKUP"; then
  pilotfish_backup_fail "backup publication failed."
fi
if [ -L "$BACKUP" ] || [ ! -d "$BACKUP" ]; then
  pilotfish_published_backup_fail "published backup must be a directory."
elif [ "$BACKED_UP_CLAUDE" -eq 1 ] && \
    { [ -L "$BACKUP/CLAUDE.md" ] || [ ! -f "$BACKUP/CLAUDE.md" ] || \
      ! cmp -s "$CFG/CLAUDE.md" "$BACKUP/CLAUDE.md"; }; then
  pilotfish_published_backup_fail "published CLAUDE.md backup verification failed."
elif [ "$BACKED_UP_SETTINGS" -eq 1 ] && \
    { [ -L "$BACKUP/settings.json" ] || [ ! -f "$BACKUP/settings.json" ] || \
      ! cmp -s "$CFG/settings.json" "$BACKUP/settings.json"; }; then
  pilotfish_published_backup_fail "published settings.json backup verification failed."
elif [ "$BACKED_UP_AGENTS" -eq 1 ] && \
    { [ -L "$BACKUP/agents" ] || [ ! -d "$BACKUP/agents" ] || \
      ! diff -r "$CFG/agents" "$BACKUP/agents" >/dev/null 2>&1; }; then
  pilotfish_published_backup_fail "published agents backup verification failed."
fi
```

只有 backup block 以 `0` 結束時才能繼續。若任何 copy 或 read-back verification 失敗，請在 legacy removal 或 Plugin installation 之前停止，並保持原始 configuration 不變。接著依照 [legacy uninstall procedure](./AGENT-INSTALL.md#uninstall)：只移除相符的 pilotfish agent files、唯一的 `pilotfish:begin/end` block，以及可歸因於該次安裝的 settings values。保留使用者自訂檔案與無關設定。重新執行上方 preflight；只有在輸出 no-legacy diagnostic 後才能繼續。

## 安裝前選擇主模型

Plugin 不會修改 `settings.json`。執行安裝指令前，請在每個要使用 Plugin 的 project 中重複以下檢查：使用 `/status` 找出有效的 managed、local（`.claude/settings.local.json`）、project（`.claude/settings.json`）與 user settings，再確認有效的 model picker 包含所有隨附 role-model aliases：`"opus"`、`"sonnet"` 與 `"haiku"`。

User、project 與 local 的 `availableModels` arrays 會合併並去除重複項目。先計算它們有效的 non-managed union。只有該 union 缺少隨附 alias 時，才由使用者明確批准，把每個缺少的 alias 加到一個適當、可編輯的 scope，並保留所有既有 entries；若另一個 scope 已提供 alias，請勿重複加入。Managed policy 優先級最高，可強制執行 lower scopes 無法放寬的嚴格 `availableModels` allowlist；若它排除任何隨附 alias，且 administrator 無法修改，請停止。請參考[官方 settings precedence](https://code.claude.com/docs/en/configuration#settings-precedence)。任何缺少隨附 alias 的有效 model set，都不足以證明所宣稱的 tiering。

接著，由使用者明確批准以下其中一種主模型選擇，並在每個預定 project 中使用 `/status` 確認有效主模型是 Opus：

| 選擇 | 操作與限制 |
|---|---|
| Persistent | 將 `"model": "opus"` merge 到目前設定 `model` 的最高優先級 editable scope：local、project 或 user，並保留其他所有 key。若 editable scopes 都沒有設定 `model`，且 managed selection 未阻止 persistent setup，請明確批准在 user `$CFG/settings.json` 建立或 merge `"model": "opus"`。低優先級 user setting 無法覆蓋 project 或 local model selection。Managed non-Opus `model` 仍是 startup default，因此僅設定此選項不足以證明 persistent Opus selection。 |
| Per session | 不修改 persistent settings，每次啟動 pilotfish session 時明確使用 `claude --model opus`。Model selection 是 generic settings precedence 的已記錄 key-specific exception：`--model` 會在該 session 覆蓋任何 settings file 的 `model` value。它仍受 managed `availableModels` 與 organization model restrictions 限制，因此仍須通過上述 effective-scope checks。請參考[官方 model configuration](https://code.claude.com/docs/en/model-config)與[命令列 override 行為](https://code.claude.com/docs/en/configuration#the-command-line-overrides-your-files-for-one-session)。 |

只有在 managed `availableModels` 或其他 organization restriction 阻止選擇 Opus，或完成所選設定後 `/status` 仍未確認有效 Opus main 時才停止。不要默默修改 configuration。若使用者保留 non-Opus main model，Plugin 仍可能安裝並載入，但不能宣稱已建立 advertised Opus-main tiering。

## 安裝到 user scope

若要使用目前的 marketplace branch：

```bash
claude plugin marketplace add --scope user Nanako0129/pilotfish
claude plugin install --scope user pilotfish@pilotfish
```

若要使用已審閱的 immutable release，將 `X.Y.Z` 換成同一個版本，並把 marketplace pin 到該 repository tag：

```bash
claude plugin marketplace add --scope user Nanako0129/pilotfish@vX.Y.Z
claude plugin install --scope user pilotfish@pilotfish
```

若 Claude Code 詢問，請檢查並接受宣告的 SessionStart hook。接著重啟 Claude Code；只完成安裝不會在目前 process 啟用 hook。

## 更新

若安裝的是可變動的 current marketplace branch：

```bash
claude plugin marketplace update pilotfish
claude plugin update --scope user pilotfish@pilotfish
```

若 pin 到 immutable release，`marketplace update` 會刻意留在該 tag。要移動到已審閱的 release `vX.Y.Z`，請明確替換已註冊的 tag：

```bash
claude plugin uninstall --scope user pilotfish@pilotfish
claude plugin marketplace remove --scope user pilotfish
claude plugin marketplace add --scope user Nanako0129/pilotfish@vX.Y.Z
claude plugin install --scope user pilotfish@pilotfish
```

兩種路徑都要在完成後重啟 Claude Code。只更新 marketplace 不會同時更新已安裝的 Plugin。

## 停用或重新啟用

```bash
claude plugin disable --scope user pilotfish@pilotfish
# restart Claude Code

claude plugin enable --scope user pilotfish@pilotfish
# restart Claude Code again
```

Disable/enable state 會在新的 Claude Code process 生效。停用 hook 不是 security boundary；不要同時重新安裝 legacy global policy。

## 移除

```bash
claude plugin uninstall --scope user pilotfish@pilotfish
claude plugin marketplace remove --scope user pilotfish
```

重啟 Claude Code。第一個指令移除已安裝的 Plugin；第二個指令移除其 marketplace registration。

## 手動 rollback

對第一個支援 Plugin 的 release，rollback 代表移除 Plugin 與 marketplace：

```bash
claude plugin uninstall --scope user pilotfish@pilotfish
claude plugin marketplace remove --scope user pilotfish
```

重啟 Claude Code。若要恢復 legacy global installation，只能依照 legacy runbook 還原遷移時建立且已審閱的 backup；絕對不要同時使用兩種安裝方式。

從第二個支援 Plugin 的 release 開始，請選擇先前版本 `A.B.C`，其 root `vA.B.C` 與 Plugin `pilotfish--vA.B.C` tags 必須指向同一個已審閱的 pilotfish version。接著從該 immutable root tag 重新安裝：

```bash
claude plugin uninstall --scope user pilotfish@pilotfish
claude plugin marketplace remove --scope user pilotfish
claude plugin marketplace add --scope user Nanako0129/pilotfish@vA.B.C
claude plugin install --scope user pilotfish@pilotfish
```

重啟 Claude Code。不可混用 root release tag 與不同版本的 Plugin tag。

## 疑難排解

若 startup 顯示以下 diagnostic，代表 hook 刻意沒有輸出 sentinel 或 policy：

```text
pilotfish Plugin blocked: legacy global pilotfish detected. Follow https://github.com/Nanako0129/pilotfish/blob/main/install/PLUGIN-INSTALL.md#migrate-from-global-v1 to migrate, then restart Claude Code.
```

使用 Preflight 解析出的有效 config root，完成備份與 legacy uninstall，再重新啟動。Relative `CLAUDE_CONFIG_DIR`、缺少 absolute `HOME`、無法讀取 `CLAUDE.md`，或 config-probe error，也會阻止 policy emission，直到問題修正為止。

每次 SessionStart 也會重新檢查 `CLAUDE_CODE_SUBAGENT_MODEL`。若其值非空，hook 不會輸出該值、sentinel 或 policy；請從啟動環境 unset，然後重新啟動或 relaunch Claude Code。
