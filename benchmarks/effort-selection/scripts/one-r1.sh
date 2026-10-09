#!/bin/bash
# A2 gate, one session: one-r1.sh <plugin|template> <task-id> <rep>
# Needs A2_DIR containing fixture-<arm>/ (a `git archive` copy; the template arm
# also has CLAUDE.md + .claude/agents/ from templates/), and PILOTFISH_PLUGIN for
# the plugin arm. Tasks come from ../a2-tasks-<arm>.tsv; output goes to $A2_DIR/out.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; arm=$1; id=$2; rep=$3
A2="${A2_DIR:?set A2_DIR}"
task=$(awk -F'\t' -v id="$id" '$1==id{print $2}' "$HERE/../a2-tasks-$arm.tsv")
[ -n "$task" ] || { echo "no task $id" >&2; exit 1; }
W="$A2/w-$arm-$id-$rep"; rm -rf "$W"; cp -R "$A2/fixture-$arm" "$W" || exit 1; cd "$W" || exit 1
mkdir -p "$A2/out"
extra=(); [ "$arm" = plugin ] && extra=(--plugin-dir "${PILOTFISH_PLUGIN:?set PILOTFISH_PLUGIN to the plugin/ directory}")
env -u CLAUDE_EFFORT -u CLAUDE_CODE_EFFORT_LEVEL claude -p "$task" ${extra[@]+"${extra[@]}"} \
  --setting-sources project --strict-mcp-config --no-session-persistence \
  --permission-mode acceptEdits --allowedTools Bash \
  --output-format stream-json --verbose < /dev/null >| "$A2/out/$arm-$id-$rep.jsonl" 2>| "$A2/out/$arm-$id-$rep.err"
rc=$?
echo "done $arm $id $rep rc=$rc"
exit "$rc"
