# pilotfish macOS and Linux Plugin beta install

> This experimental beta targets macOS and Linux. Linux requires Ubuntu 20.04+, Debian 10+, or Alpine Linux 3.19+ and an otherwise-working officially supported Claude Code installation, per the [official system requirements](https://code.claude.com/docs/en/setup#system-requirements) (checked 2026-08-22). macOS with Claude Code 2.1.239 is live-observed. Linux is contract-qualified only; it has not been tested, verified, or live-observed. Windows is excluded. SessionStart hooks are required for ambient activation. This beta does not claim stable reliability, cross-version compatibility, or runtime namespace-collision proof.

The Plugin and the legacy global install must not coexist. The Plugin hook fails closed when the effective user `CLAUDE.md` contains canonical pilotfish markers or the known legacy policy header: it emits no policy and tells you to migrate.

## Preflight

Run this copy-paste POSIX `/bin/sh` preflight. It executes `claude --version`, accepts a numeric `X.Y.Z` first token only, and requires Claude Code 2.1.219 or newer. That floor is newer than the verified baseline that enforces agent `tools` allowlists; do not install a prompt-only approximation because the read-only `plan-verifier` and `security-reviewer` roles depend on those allowlists.

It also rejects a non-empty `CLAUDE_CODE_SUBAGENT_MODEL` without printing its value because that variable overrides every agent `model` frontmatter. Unset it yourself and rerun rather than letting an installer silently change the caller's environment.

The same preflight resolves the effective user configuration root and checks for a legacy global policy without printing `CLAUDE.md`. `CLAUDE_CONFIG_DIR` must be absolute when non-empty; otherwise Claude Code uses `$HOME/.claude`.

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

   Continue only after the command prints `No legacy global pilotfish policy detected.` Any other result is fail-closed.

## Migrate from global v1

Back up the effective configuration before removing anything:

```bash
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP="$CFG/backups/pilotfish-global-$STAMP"
mkdir -p "$BACKUP"
[ ! -f "$CFG/CLAUDE.md" ] || cp -p "$CFG/CLAUDE.md" "$BACKUP/CLAUDE.md"
[ ! -f "$CFG/settings.json" ] || cp -p "$CFG/settings.json" "$BACKUP/settings.json"
[ ! -d "$CFG/agents" ] || cp -R "$CFG/agents" "$BACKUP/agents"
```

Then follow the [legacy uninstall procedure](./AGENT-INSTALL.md#uninstall): remove only the matching pilotfish agent files, the single `pilotfish:begin/end` block, and settings values attributable to that install. Preserve user-customized files and unrelated settings. Re-run the preflight check above; continue only after it prints the no-legacy diagnostic.

## Choose the main model before installation

The Plugin does not edit `settings.json`. Before running the install commands, inspect the effective `$CFG/settings.json`. For either setup option below, if `availableModels` already exists, obtain explicit user approval to append every missing shipped role-model alias—`"opus"`, `"sonnet"`, and `"haiku"`—while preserving every existing entry. An existing allowlist that omits any of these aliases does not establish the advertised tiering.

Then make one explicit user-approved main-model choice:

1. **Persistent:** merge `"model": "opus"` into the effective `$CFG/settings.json`, preserving every other key.
2. **Per session:** leave the persistent `model` setting unchanged and launch every pilotfish session explicitly with `claude --model opus`. The common `availableModels` check above still applies.

Do not silently mutate configuration. If the user keeps a non-Opus main model, the Plugin may still install and load, but the advertised Opus-main tiering is not established.

## Install at user scope

For the current marketplace branch:

```bash
claude plugin marketplace add --scope user Nanako0129/pilotfish
claude plugin install --scope user pilotfish@pilotfish
```

For a reviewed immutable release, replace `X.Y.Z` with one version and pin the marketplace to that exact repository tag:

```bash
claude plugin marketplace add --scope user Nanako0129/pilotfish@vX.Y.Z
claude plugin install --scope user pilotfish@pilotfish
```

Review and accept the declared SessionStart hook if Claude Code prompts. Restart Claude Code; installation alone does not activate the hook in the current process.

## Update

If you installed the mutable current marketplace branch:

```bash
claude plugin marketplace update pilotfish
claude plugin update --scope user pilotfish@pilotfish
```

If you pinned an immutable release, `marketplace update` intentionally stays on that tag. To move to reviewed release `vX.Y.Z`, replace the registered tag explicitly:

```bash
claude plugin uninstall --scope user pilotfish@pilotfish
claude plugin marketplace remove --scope user pilotfish
claude plugin marketplace add --scope user Nanako0129/pilotfish@vX.Y.Z
claude plugin install --scope user pilotfish@pilotfish
```

Restart Claude Code after either path. Updating the marketplace does not update the installed Plugin by itself.

## Disable or re-enable

```bash
claude plugin disable --scope user pilotfish@pilotfish
# restart Claude Code

claude plugin enable --scope user pilotfish@pilotfish
# restart Claude Code again
```

Disable/enable state takes effect in a new Claude Code process. A disabled hook is not a security boundary; do not reinstall the legacy global policy alongside it.

## Uninstall

```bash
claude plugin uninstall --scope user pilotfish@pilotfish
claude plugin marketplace remove --scope user pilotfish
```

Restart Claude Code. The first command removes the installed Plugin; the second removes its marketplace registration.

## Manual rollback

For the first Plugin-capable release, rollback means removing the Plugin and marketplace:

```bash
claude plugin uninstall --scope user pilotfish@pilotfish
claude plugin marketplace remove --scope user pilotfish
```

Restart Claude Code. If you need the legacy global installation again, restore only the reviewed backup made during migration by following the legacy runbook; never run both installation methods together.

From the second Plugin-capable release onward, choose a prior `A.B.C` release whose root `vA.B.C` and Plugin `pilotfish--vA.B.C` tags identify the same reviewed pilotfish version. Then reinstall from that immutable root tag:

```bash
claude plugin uninstall --scope user pilotfish@pilotfish
claude plugin marketplace remove --scope user pilotfish
claude plugin marketplace add --scope user Nanako0129/pilotfish@vA.B.C
claude plugin install --scope user pilotfish@pilotfish
```

Restart Claude Code. Do not combine a root release tag with a differently versioned Plugin tag.

## Troubleshooting

If startup shows this diagnostic, the hook intentionally emitted neither its sentinel nor policy:

```text
pilotfish Plugin blocked: legacy global pilotfish detected. Follow https://github.com/Nanako0129/pilotfish/blob/main/install/PLUGIN-INSTALL.md#migrate-from-global-v1 to migrate, then restart Claude Code.
```

Use the effective config root from Preflight, back it up, complete the legacy uninstall, and restart. A relative `CLAUDE_CONFIG_DIR`, missing absolute `HOME`, unreadable `CLAUDE.md`, or config-probe error also blocks policy emission until corrected.
