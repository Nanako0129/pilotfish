#!/usr/bin/env bash
# Paid rerun after the wording fix (verifier CONFIRMED definition; policy lines 36, 37, 40; ambient line 29).
# Runs on the Mac. Hard cap: USD 4.00 total across all cells; stop at the first failed cell.
# Cells: v1, v2 (verifier blocking bar), cross, schema, routine (manual template),
#        p-preflight, p-cross, p-schema (Plugin path: no CLAUDE.md, no --agents).
# Every claude call runs inside a disposable Git copy of a fixture. The pilotfish repository is only read.
set -euo pipefail

G="$(cd "$(dirname "$0")/.." && pwd)"          # gate-1123/ (script runs from gate-1123/run-copy/)
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${SRC:-$(git rev-parse --show-toplevel)}"
PRS="$SRC/benchmarks/plan-review-scope"
CAP_TOTAL=4.00
LOG="$G/run.log"
FROZEN="$G/src"
STREAMS="$G/streams"
CELLS="$G/cells"
MARKER='*=mandatory pre-approval pilotfish:plan-verifier.'
INIT_AGENTS='pilotfish:plan-verifier,pilotfish:verifier,pilotfish:mech-executor'
export GIT_OPTIONAL_LOCKS=0
GITC=(-c user.name=gate -c user.email=gate@example.invalid -c commit.gpgsign=false)

say() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }
trap 'rc=$?; say "RUNNER-EXIT code=$rc"' EXIT
# Added after the recorded run: refuse to call a real client unless PAID_RUN=1.
CLAUDE_BIN="$(command -v claude)" || { say "STOP claude not found"; exit 4; }
case "$CLAUDE_BIN" in /*) ;; *) say "STOP claude does not resolve to an absolute path: $CLAUDE_BIN"; exit 4 ;; esac
if [ "$("$CLAUDE_BIN" --version)" != stub ] && [ "${PAID_RUN:-}" != 1 ]; then say "STOP real client without PAID_RUN=1"; exit 4; fi

# ---- freeze inputs (refuse to start over leftovers) ----
for d in "$FROZEN" "$STREAMS" "$CELLS"; do
  if [ -e "$d" ]; then say "STOP exists $d"; exit 4; fi
  mkdir -p "$d"
done
cp "$SRC/templates/claude-md.orchestration.md" "$FROZEN/CLAUDE.md"
python3 "$SRC/benchmarks/baton-compatibility/build-agents-json.py" "$SRC/templates/agents" > "$FROZEN/agents.json"
cp -R "$SRC/plugin" "$FROZEN/plugin"
grep -F -q -- "$MARKER" "$FROZEN/plugin/policy/sessionstart.txt" || { say "STOP marker not in frozen sessionstart.txt"; exit 4; }
cmp -s "$SRC/templates/agents/verifier.md" "$FROZEN/plugin/agents/verifier.md" || { say "STOP template and Plugin verifier differ"; exit 4; }
mkdir "$FROZEN/fixture" "$FROZEN/xfix" "$FROZEN/prompts" "$FROZEN/states"
cp "$SRC"/benchmarks/verifier-boundary/fixture/{package.json,README.md,store.mjs,store.test.mjs} "$FROZEN/fixture/"
cp "$PRS"/scope/xfix/{format.mjs,report.mjs,cli.mjs,format.test.mjs,report.test.mjs,cli.test.mjs} "$FROZEN/xfix/"
cp -R "$PRS/blocking-bar/states/v1" "$PRS/blocking-bar/states/v2" "$FROZEN/states/"
cp "$SRC"/benchmarks/verifier-boundary/prompts/{schema-turn-1-explicit.txt,schema-turn-2-explicit.txt,routine-docs-explicit.txt} "$FROZEN/prompts/"
cp "$PRS/scope/prompts/cross-turn-1.txt" "$G/prompts/verify.txt" "$G/prompts/preflight.txt" "$FROZEN/prompts/"
( cd "$FROZEN" && find . -type f ! -name SHA256.txt | sort | xargs shasum -a 256 > SHA256.txt )
say "FROZEN client=$("$CLAUDE_BIN" --version) policy=$(shasum -a 256 "$FROZEN/CLAUDE.md" | cut -c1-16) agents=$(shasum -a 256 "$FROZEN/agents.json" | cut -c1-16) sessionstart=$(shasum -a 256 "$FROZEN/plugin/policy/sessionstart.txt" | cut -c1-16) repo_head=$(git -C "$SRC" rev-parse --short HEAD)"
say "REPO-STATUS-BEFORE $(git -C "$SRC" status --porcelain | shasum -a 256 | cut -c1-16)"

mkrepo() {   # mkrepo CELL tmpl|plug [with-xfix|v1|v2]   (plug: no CLAUDE.md, the Plugin supplies the policy)
  local cell=$1 kind=$2 extra=${3:-} dir="$CELLS/$1"
  mkdir "$dir"
  cp "$FROZEN"/fixture/{package.json,README.md,store.mjs,store.test.mjs} "$dir/"
  if [ "$extra" = with-xfix ]; then cp "$FROZEN"/xfix/*.mjs "$dir/"; fi
  if [ "$kind" = tmpl ]; then cp "$FROZEN/CLAUDE.md" "$dir/CLAUDE.md"; fi
  git -C "$dir" init -q
  git -C "$dir" add -A
  git -C "$dir" "${GITC[@]}" commit -q -m baseline
  if [ "$extra" = v1 ] || [ "$extra" = v2 ]; then
    cp "$FROZEN/states/$extra"/{README.md,store.mjs,store.test.mjs} "$dir/"
    git -C "$dir" add -A
    git -C "$dir" "${GITC[@]}" commit -q -m "migrate payload to version 2"
  fi
  git -C "$dir" tag baseline
}

head_is_baseline() {   # fail if HEAD moved off the baseline commit or git cannot answer
  local h b
  h="$(git -C "$CELLS/$1" rev-parse --verify -q HEAD)" || return 1
  b="$(git -C "$CELLS/$1" rev-parse --verify -q 'baseline^{commit}')" || return 1
  [ -n "$h" ] && [ "$h" = "$b" ]
}

call() {     # call CELL TAG CAP MODEL PROMPT MODE SID tmpl|plug parse|check -- CHECKER-ARGS...
  local cell=$1 tag=$2 cap=$3 model=$4 prompt=$5 mode=$6 sid=$7 kind=$8 checker=$9; shift 10
  local out="$STREAMS/$cell-$tag.jsonl" err="$STREAMS/$cell-$tag.stderr" rc=0 prc=0 spent line
  local -a src
  if [ "$kind" = tmpl ]; then src=(--agents "$(<"$FROZEN/agents.json")"); else src=(--plugin-dir "$FROZEN/plugin"); fi
  spent="$(python3 "$HERE/check.py" --spent "$STREAMS")" || { say "STOP unknown-cost"; exit 3; }
  if ! python3 -c 'import sys; sys.exit(0 if float(sys.argv[1])+1.5*float(sys.argv[2]) <= float(sys.argv[3]) else 1)' "$spent" "$cap" "$CAP_TOTAL"; then
    say "STOP budget spent=$spent next_cap=$cap total_cap=$CAP_TOTAL"; exit 3
  fi
  if [ -e "$out" ]; then say "STOP stream-exists $out"; exit 4; fi
  say "START $cell-$tag cap=$cap spent_so_far=$spent"
  ( cd "$CELLS/$cell" && env -u CLAUDE_CODE_SUBAGENT_MODEL perl -e 'alarm shift; exec @ARGV' 1500 \
      "$CLAUDE_BIN" --dangerously-skip-permissions -p --output-format stream-json --verbose \
        --max-budget-usd "$cap" "$mode" "$sid" --model "$model" --effort high \
        --setting-sources project,local --strict-mcp-config \
        "${src[@]}" "$(<"$prompt")" < /dev/null > "$out" 2> "$err" ) || rc=$?
  say "END $cell-$tag claude_rc=$rc stderr_bytes=$(wc -c < "$err" | tr -d ' ') tree=[$(git -C "$CELLS/$cell" status --porcelain | tr '\n' ';')]"
  if [ "$checker" = parse ]; then
    line="$(python3 "$HERE/parse.py" "$out" "$@")" || prc=$?
  elif [ "$kind" = plug ]; then
    line="$(python3 "$HERE/check.py" "$out" --init-agents "$INIT_AGENTS" "$@")" || prc=$?
  else
    line="$(python3 "$HERE/check.py" "$out" "$@")" || prc=$?
  fi
  say "$line"
  if [ "$rc" -ne 0 ]; then say "FAIL $cell-$tag claude exited $rc"; return 1; fi
  return "$prc"
}

clean_tree() {   # clean_tree CELL  -> fail if anything changed
  local s
  head_is_baseline "$1" || return 1
  s="$(git -C "$CELLS/$1" status --porcelain)" || return 1
  [ -z "$s" ]
}

only_changed() { # only_changed CELL FILE... -> fail if a path outside the list changed or nothing changed
  local cell=$1; shift
  head_is_baseline "$cell" || { echo "HEAD moved off baseline or git failed"; return 1; }
  python3 - "$CELLS/$cell" "$@" <<'PY'
import subprocess, sys
out = subprocess.run(["git", "-C", sys.argv[1], "status", "--porcelain"], capture_output=True, text=True, check=True).stdout
changed = {line[3:].strip() for line in out.splitlines() if line.strip()}
allowed = set(sys.argv[2:])
print("changed:", sorted(changed))
sys.exit(0 if changed and changed <= allowed else 1)
PY
}

tests_pass() {   # tests_pass CELL
  ( cd "$CELLS/$1" && npm test > "$STREAMS/$1-npm-test.txt" 2>&1 )
}

newsid() { python3 -c 'import uuid; print(uuid.uuid4())'; }

# ---- V1: behavioral defect must still be REFUTED ----
mkrepo v1 tmpl v1
call v1 t1 0.60 opus "$FROZEN/prompts/verify.txt" --session-id "$(newsid)" tmpl parse -- verifier 'REFUTED' \
  || { say "STOP v1 failed: a real defect was not refuted"; exit 1; }
clean_tree v1 || { say "STOP v1 changed the tree"; exit 1; }

# ---- V2: wording-only mismatch must not block ----
mkrepo v2 tmpl v2
call v2 t1 0.60 opus "$FROZEN/prompts/verify.txt" --session-id "$(newsid)" tmpl parse -- verifier 'CONFIRMED|INCONCLUSIVE' \
  || { say "STOP v2 failed: wording-only mismatch still blocked or cell incomplete"; exit 1; }
clean_tree v2 || { say "STOP v2 changed the tree"; exit 1; }
say "PASS blocking-bar"

# ---- X: cross-component, reversible. No plan-verifier; approval stop; verifier after implementation ----
mkrepo cross tmpl with-xfix
SID="$(newsid)"
call cross t1 0.40 opus "$FROZEN/prompts/cross-turn-1.txt" --session-id "$SID" tmpl check -- --allow scout --no-main-writes \
  || { say "STOP cross t1 failed routing"; exit 1; }
clean_tree cross || { say "STOP cross t1 wrote before approval"; exit 1; }
call cross t2 0.80 opus "$FROZEN/prompts/schema-turn-2-explicit.txt" --resume "$SID" tmpl check -- --require verifier --allow scout,executor,mech-executor \
  || { say "STOP cross t2 failed routing"; exit 1; }
OC="$(only_changed cross format.mjs report.mjs cli.mjs format.test.mjs report.test.mjs cli.test.mjs)" || { say "STOP cross t2 changed files outside scope or nothing"; exit 1; }
say "cross $OC"
tests_pass cross || { say "STOP cross tests fail"; exit 1; }
say "PASS cross"

# ---- S: schema migration. plan-verifier before approval; approval stop; verifier after implementation ----
mkrepo schema tmpl
SID="$(newsid)"
call schema t1 0.50 opus "$FROZEN/prompts/schema-turn-1-explicit.txt" --session-id "$SID" tmpl check -- --require plan-verifier --allow scout --no-main-writes \
  || { say "STOP schema t1 failed routing"; exit 1; }
clean_tree schema || { say "STOP schema t1 wrote before approval"; exit 1; }
call schema t2 0.80 opus "$FROZEN/prompts/schema-turn-2-explicit.txt" --resume "$SID" tmpl check -- --require verifier --allow scout,executor,mech-executor,plan-verifier \
  || { say "STOP schema t2 failed routing"; exit 1; }
OC="$(only_changed schema store.mjs store.test.mjs)" || { say "STOP schema t2 changed files outside scope or nothing"; exit 1; }
say "schema $OC"
tests_pass schema || { say "STOP schema tests fail"; exit 1; }
say "PASS schema"

# ---- R: routine docs. No Agent call at all ----
mkrepo routine tmpl
call routine t1 0.30 opus "$FROZEN/prompts/routine-docs-explicit.txt" --session-id "$(newsid)" tmpl check -- \
  || { say "STOP routine failed routing"; exit 1; }
OC="$(only_changed routine README.md)" || { say "STOP routine changed files outside README.md or nothing"; exit 1; }
say "routine $OC"
tests_pass routine || { say "STOP routine tests fail"; exit 1; }
say "PASS routine"

# ---- Plugin preflight (cheap model): the Plugin loads, its roles are listed, the hook's policy text is in the capture ----
mkrepo p-preflight plug
call p-preflight t1 0.10 haiku "$FROZEN/prompts/preflight.txt" --session-id "$(newsid)" plug check -- --marker "$MARKER" --no-main-writes \
  || { say "STOP preflight: Plugin policy or roles not observed in the capture"; exit 1; }
clean_tree p-preflight || { say "STOP preflight wrote files"; exit 1; }
say "PASS p-preflight"

# ---- Plugin X ----
mkrepo p-cross plug with-xfix
SID="$(newsid)"
call p-cross t1 0.40 opus "$FROZEN/prompts/cross-turn-1.txt" --session-id "$SID" plug check -- --marker "$MARKER" --allow pilotfish:scout --no-main-writes \
  || { say "STOP p-cross t1 failed routing"; exit 1; }
clean_tree p-cross || { say "STOP p-cross t1 wrote before approval"; exit 1; }
call p-cross t2 0.70 opus "$FROZEN/prompts/schema-turn-2-explicit.txt" --resume "$SID" plug check -- --require pilotfish:verifier --allow pilotfish:scout,pilotfish:executor,pilotfish:mech-executor \
  || { say "STOP p-cross t2 failed routing"; exit 1; }
OC="$(only_changed p-cross format.mjs report.mjs cli.mjs format.test.mjs report.test.mjs cli.test.mjs)" || { say "STOP p-cross t2 changed files outside scope or nothing"; exit 1; }
say "p-cross $OC"
tests_pass p-cross || { say "STOP p-cross tests fail"; exit 1; }
say "PASS p-cross"

# ---- Plugin S ----
mkrepo p-schema plug
SID="$(newsid)"
call p-schema t1 0.50 opus "$FROZEN/prompts/schema-turn-1-explicit.txt" --session-id "$SID" plug check -- --marker "$MARKER" --require pilotfish:plan-verifier --allow pilotfish:scout --no-main-writes \
  || { say "STOP p-schema t1 failed routing"; exit 1; }
clean_tree p-schema || { say "STOP p-schema t1 wrote before approval"; exit 1; }
call p-schema t2 0.70 opus "$FROZEN/prompts/schema-turn-2-explicit.txt" --resume "$SID" plug check -- --require pilotfish:verifier --allow pilotfish:scout,pilotfish:executor,pilotfish:mech-executor,pilotfish:plan-verifier \
  || { say "STOP p-schema t2 failed routing"; exit 1; }
OC="$(only_changed p-schema store.mjs store.test.mjs)" || { say "STOP p-schema t2 changed files outside scope or nothing"; exit 1; }
say "p-schema $OC"
tests_pass p-schema || { say "STOP p-schema tests fail"; exit 1; }
say "PASS p-schema"

FINAL="$(python3 "$HERE/check.py" --spent "$STREAMS")" || { say "STOP final spend unknown"; exit 2; }
say "REPO-STATUS-AFTER $(git -C "$SRC" status --porcelain | shasum -a 256 | cut -c1-16)"
say "DONE spent=$FINAL"
