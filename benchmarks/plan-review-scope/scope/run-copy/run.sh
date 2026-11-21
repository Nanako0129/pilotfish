#!/usr/bin/env bash
# Paid Gate for the Plan-review scope change (plan-verifier only for the Plan-review subset).
# Runs on the Mac. Authorized hard cap: USD 5 total for this campaign; stop at the first failed cell.
# Every claude call runs inside a disposable Git copy of a fixture. The pilotfish repository is only read.
set -euo pipefail

G="$(cd "$(dirname "$0")/.." && pwd)"          # gate-1121/ (script runs from gate-1121/run-copy/)
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${SRC:-$(git rev-parse --show-toplevel)}"
CAP_TOTAL=5.00
LOG="$G/run.log"
FROZEN="$G/src"
STREAMS="$G/streams"
CELLS="$G/cells"
export GIT_OPTIONAL_LOCKS=0
GITC=(-c user.name=gate -c user.email=gate@example.invalid -c commit.gpgsign=false)

say() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }
trap 'rc=$?; say "RUNNER-EXIT code=$rc"' EXIT

# ---- freeze inputs (refuse to start over leftovers) ----
for d in "$FROZEN" "$STREAMS" "$CELLS"; do
  if [ -e "$d" ]; then say "STOP exists $d"; exit 4; fi
  mkdir -p "$d"
done
cp "$SRC/templates/claude-md.orchestration.md" "$FROZEN/CLAUDE.md"
python3 "$SRC/benchmarks/baton-compatibility/build-agents-json.py" "$SRC/templates/agents" > "$FROZEN/agents.json"
mkdir "$FROZEN/fixture" "$FROZEN/xfix" "$FROZEN/prompts"
cp "$SRC"/benchmarks/verifier-boundary/fixture/{package.json,README.md,store.mjs,store.test.mjs} "$FROZEN/fixture/"
cp "$G"/xfix/{format.mjs,report.mjs,cli.mjs,format.test.mjs,report.test.mjs,cli.test.mjs} "$FROZEN/xfix/"
cp "$SRC"/benchmarks/verifier-boundary/prompts/{schema-turn-1-explicit.txt,schema-turn-2-explicit.txt,routine-docs-explicit.txt} "$FROZEN/prompts/"
cp "$G/prompts/cross-turn-1.txt" "$FROZEN/prompts/"
( cd "$FROZEN" && find . -type f ! -name SHA256.txt | sort | xargs shasum -a 256 > SHA256.txt )
say "FROZEN client=$(claude --version) policy=$(shasum -a 256 "$FROZEN/CLAUDE.md" | cut -c1-16) agents=$(shasum -a 256 "$FROZEN/agents.json" | cut -c1-16)"
say "REPO-STATUS-BEFORE $(git -C "$SRC" status --porcelain | shasum -a 256 | cut -c1-16)"

mkrepo() {   # mkrepo CELL [with-xfix]
  local cell=$1 extra=${2:-} dir="$CELLS/$1"
  mkdir "$dir"
  cp "$FROZEN"/fixture/{package.json,README.md,store.mjs,store.test.mjs} "$dir/"
  if [ "$extra" = with-xfix ]; then cp "$FROZEN"/xfix/*.mjs "$dir/"; fi
  cp "$FROZEN/CLAUDE.md" "$dir/CLAUDE.md"
  git -C "$dir" init -q
  git -C "$dir" add -A
  git -C "$dir" "${GITC[@]}" commit -q -m baseline
  git -C "$dir" tag baseline
}

head_is_baseline() {   # fail if HEAD moved off the baseline commit or git cannot answer
  local h b
  h="$(git -C "$CELLS/$1" rev-parse --verify -q HEAD)" || return 1
  b="$(git -C "$CELLS/$1" rev-parse --verify -q 'baseline^{commit}')" || return 1
  [ -n "$h" ] && [ "$h" = "$b" ]
}

call() {     # call CELL TAG CAP PROMPT MODE SID -- CHECK-ARGS...
  local cell=$1 tag=$2 cap=$3 prompt=$4 mode=$5 sid=$6; shift 7
  local out="$STREAMS/$cell-$tag.jsonl" err="$STREAMS/$cell-$tag.stderr" rc=0 prc=0 spent line
  spent="$(python3 "$HERE/check.py" --spent "$STREAMS")" || { say "STOP unknown-cost"; exit 3; }
  if ! python3 -c 'import sys; sys.exit(0 if float(sys.argv[1])+1.5*float(sys.argv[2]) <= float(sys.argv[3]) else 1)' "$spent" "$cap" "$CAP_TOTAL"; then
    say "STOP budget spent=$spent next_cap=$cap total_cap=$CAP_TOTAL"; exit 3
  fi
  if [ -e "$out" ]; then say "STOP stream-exists $out"; exit 4; fi
  say "START $cell-$tag cap=$cap spent_so_far=$spent"
  ( cd "$CELLS/$cell" && perl -e 'alarm shift; exec @ARGV' 1500 \
      claude --dangerously-skip-permissions -p --output-format stream-json --verbose \
        --max-budget-usd "$cap" "$mode" "$sid" --model opus --effort high \
        --setting-sources project,local --strict-mcp-config \
        --agents "$(<"$FROZEN/agents.json")" "$(<"$prompt")" < /dev/null > "$out" 2> "$err" ) || rc=$?
  say "END $cell-$tag claude_rc=$rc stderr_bytes=$(wc -c < "$err" | tr -d ' ') tree=[$(git -C "$CELLS/$cell" status --porcelain | tr '\n' ';')]"
  line="$(python3 "$HERE/check.py" "$out" "$@")" || prc=$?
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

# ---- X: cross-component, reversible. No plan-verifier; approval stop; verifier after implementation ----
mkrepo cross with-xfix
SID="$(newsid)"
call cross t1 0.80 "$FROZEN/prompts/cross-turn-1.txt" --session-id "$SID" -- --allow scout --no-main-writes \
  || { say "STOP cross t1 failed routing"; exit 1; }
clean_tree cross || { say "STOP cross t1 wrote before approval"; exit 1; }
call cross t2 1.20 "$FROZEN/prompts/schema-turn-2-explicit.txt" --resume "$SID" -- --require verifier --allow scout,executor,mech-executor \
  || { say "STOP cross t2 failed routing"; exit 1; }
OC="$(only_changed cross format.mjs report.mjs cli.mjs format.test.mjs report.test.mjs cli.test.mjs)" || { say "STOP cross t2 changed files outside scope or nothing"; exit 1; }
say "cross $OC"
tests_pass cross || { say "STOP cross tests fail"; exit 1; }
say "PASS cross"

# ---- S: schema migration. plan-verifier before approval; approval stop; verifier after implementation ----
mkrepo schema
SID="$(newsid)"
call schema t1 1.20 "$FROZEN/prompts/schema-turn-1-explicit.txt" --session-id "$SID" -- --require plan-verifier --allow scout --no-main-writes \
  || { say "STOP schema t1 failed routing"; exit 1; }
clean_tree schema || { say "STOP schema t1 wrote before approval"; exit 1; }
call schema t2 1.20 "$FROZEN/prompts/schema-turn-2-explicit.txt" --resume "$SID" -- --require verifier --allow scout,executor,mech-executor,plan-verifier \
  || { say "STOP schema t2 failed routing"; exit 1; }
OC="$(only_changed schema store.mjs store.test.mjs)" || { say "STOP schema t2 changed files outside scope or nothing"; exit 1; }
say "schema $OC"
tests_pass schema || { say "STOP schema tests fail"; exit 1; }
say "PASS schema"

# ---- R: routine docs. No Agent call at all ----
mkrepo routine
call routine t1 0.50 "$FROZEN/prompts/routine-docs-explicit.txt" --session-id "$(newsid)" -- \
  || { say "STOP routine failed routing"; exit 1; }
OC="$(only_changed routine README.md)" || { say "STOP routine changed files outside README.md or nothing"; exit 1; }
say "routine $OC"
tests_pass routine || { say "STOP routine tests fail"; exit 1; }
say "PASS routine"

FINAL="$(python3 "$HERE/check.py" --spent "$STREAMS")" || { say "STOP final spend unknown"; exit 2; }
say "REPO-STATUS-AFTER $(git -C "$SRC" status --porcelain | shasum -a 256 | cut -c1-16)"
say "DONE spent=$FINAL"
