#!/bin/sh
set -eu
PATH=/usr/bin:/bin
export PATH

MIGRATION_URL="https://github.com/Nanako0129/pilotfish/blob/main/install/PLUGIN-INSTALL.md#migrate-from-global-v1"

if [ -n "${CLAUDE_CODE_SUBAGENT_MODEL:-}" ]; then
    printf '%s\n' "pilotfish Plugin blocked: CLAUDE_CODE_SUBAGENT_MODEL is non-empty and overrides every agent model frontmatter. Unset it, then restart or relaunch Claude Code."
    exit 0
fi

if [ -n "${CLAUDE_CONFIG_DIR:-}" ]; then
    case "$CLAUDE_CONFIG_DIR" in
        /*) config_root=$CLAUDE_CONFIG_DIR ;;
        *) printf '%s\n' "pilotfish Plugin blocked: CLAUDE_CONFIG_DIR must be absolute. Fix it, then follow $MIGRATION_URL and restart Claude Code."; exit 0 ;;
    esac
else
    case "${HOME:-}" in
        /*) config_root=$HOME/.claude ;;
        *) printf '%s\n' "pilotfish Plugin blocked: HOME must be absolute when CLAUDE_CONFIG_DIR is empty. Fix it, then follow $MIGRATION_URL and restart Claude Code."; exit 0 ;;
    esac
fi

if [ ! -d "$config_root" ] || [ ! -r "$config_root" ] || [ ! -x "$config_root" ]; then
    printf '%s\n' "pilotfish Plugin blocked: the effective CLAUDE.md cannot be checked safely. Follow $MIGRATION_URL and restart Claude Code."
    exit 0
fi

config_file=$config_root/CLAUDE.md
if [ -e "$config_file" ] || [ -L "$config_file" ]; then
    if [ ! -f "$config_file" ] || [ ! -r "$config_file" ]; then
        printf '%s\n' "pilotfish Plugin blocked: the effective CLAUDE.md cannot be checked safely. Follow $MIGRATION_URL and restart Claude Code."
        exit 0
    fi
    set +e
    grep -F -q \
        -e '<!-- pilotfish:begin -->' \
        -e '<!-- pilotfish:end -->' \
        -e '<!-- pilotfish v' \
        -e 'Main-session policy. Named roles (' \
        "$config_file"
    grep_status=$?
    set -e
    case $grep_status in
        0)
            printf '%s\n' "pilotfish Plugin blocked: legacy global pilotfish detected. Follow $MIGRATION_URL to migrate, then restart Claude Code."
            exit 0
            ;;
        1) ;;
        *)
            printf '%s\n' "pilotfish Plugin blocked: the effective CLAUDE.md cannot be checked safely. Follow $MIGRATION_URL and restart Claude Code."
            exit 0
            ;;
    esac
fi

cat "${CLAUDE_PLUGIN_ROOT}/policy/sessionstart.txt"
