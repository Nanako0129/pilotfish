#!/bin/bash
# Scout accuracy probe: scout's own prompt and read-only tools against a clean
# snapshot of this repository, one headless `claude -p` call per configuration.
# Usage: bash run.sh <task-file> <out-dir> [git-ref]   (paid: 14 calls per task file)
# The recorded runs used ref aa595da; the answer keys are only valid there.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(git -C "$HERE" rev-parse --show-toplevel)"
TASK="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
REF="${3:-aa595da}"
mkdir -p "$2"; OUT="$(cd "$2" && pwd)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/repo"
git -C "$ROOT" archive "$REF" | tar -x -C "$WORK/repo"
# Agent body = everything after the second `---` of the frontmatter.
git -C "$ROOT" show "$REF:templates/agents/scout.md" \
  | awk 'n<2 { if (/^---$/) n++; next } 1' >| "$WORK/scout-system.md"
[ -s "$WORK/scout-system.md" ] && [ -f "$WORK/repo/VERSION" ] || { echo "snapshot of $REF failed" >&2; exit 1; }
cd "$WORK/repo" || exit 1
run() { # model effort rep
  local tag="$1-$2-r$3" rc=0
  claude -p "$(cat "$TASK")" --model "$1" --effort "$2" \
    --system-prompt-file "$WORK/scout-system.md" \
    --tools Read,Glob,Grep --allowedTools Read,Glob,Grep \
    --setting-sources project --strict-mcp-config --no-session-persistence \
    --output-format json >| "$OUT/$tag.json" 2>| "$OUT/$tag.err" || rc=$?
  echo "done $tag rc=$rc"
  return "$rc"
}
for rep in 1 2; do
  for e in low medium high xhigh max; do run claude-haiku-5-5 "$e" "$rep" & done
  run claude-sonnet-5-5 low "$rep" &
  run claude-haiku-4-5-20251001 low "$rep" &
done
fail=0
for pid in $(jobs -p); do wait "$pid" || fail=1; done
exit "$fail"
