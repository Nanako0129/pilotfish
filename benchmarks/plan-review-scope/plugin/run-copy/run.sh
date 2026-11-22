#!/usr/bin/env bash
# Paid Gate for the Plan-review scope change on the Plugin path (compressed SessionStart policy).
# Runs on the Mac. Authorized hard cap: USD 3 total for this campaign; stop at the first failed cell.
# Every claude call runs inside a disposable Git copy of a fixture, with a frozen copy of plugin/
# loaded by --plugin-dir. No CLAUDE.md and no --agents: the policy comes only from the SessionStart hook.
# The pilotfish repository is only read.
set -euo pipefail

G="$(cd "$(dirname "$0")/.." && pwd)"          # gate-1122/ (script runs from gate-1122/run-copy/)
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${SRC:-$(git rev-parse --show-toplevel)}"
XFIX="${XFIX:-$SRC/benchmarks/plan-review-scope/scope/xfix}"
CAP_TOTAL=3.00
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
cp -R "$SRC/plugin" "$FROZEN/plugin"
grep -F -q -- "$MARKER" "$FROZEN/plugin/policy/sessionstart.txt" || { say "STOP marker not in frozen sessionstart.txt"; exit 4; }
mkdir "$FROZEN/fixture" "$FROZEN/xfix" "$FROZEN/prompts"
cp "$SRC"/benchmarks/verifier-boundary/fixture/{package.json,README.md,store.mjs,store.test.mjs} "$FROZEN/fixture/"
cp "$XFIX"/{format.mjs,report.mjs,cli.mjs,format.test.mjs,report.test.mjs,cli.test.mjs} "$FROZEN/xfix/"
cp "$SRC"/benchmarks/verifier-boundary/prompts/{schema-turn-1-explicit.txt,schema-turn-2-explicit.txt} "$FROZEN/prompts/"
cp "$SRC/benchmarks/plan-review-scope/scope/prompts/cross-turn-1.txt" "$FROZEN/prompts/"
cp "$G/prompts/preflight.txt" "$FROZEN/prompts/"
( cd "$FROZEN" && find . -type f ! -name SHA256.txt | sort | xargs shasum -a 256 > SHA256.txt )
say "FROZEN client=$("$CLAUDE_BIN" --version) sessionstart=$(shasum -a 256 "$FROZEN/plugin/policy/sessionstart.txt" | cut -c1-16) repo_head=$(git -C "$SRC" rev-parse --short HEAD)"
say "REPO-STATUS-BEFORE $(git -C "$SRC" status --porcelain | shasum -a 256 | cut -c1-16)"

mkrepo() {   # mkrepo CELL [with-xfix]   (no CLAUDE.md: the Plugin supplies the policy)
  local cell=$1 extra=${2:-} dir="$CELLS/$1"
  mkdir "$dir"
  cp "$FROZEN"/fixture/{package.json,README.md,store.mjs,store.test.mjs} "$dir/"
  if [ "$extra" = with-xfix ]; then cp "$FROZEN"/xfix/*.mjs "$dir/"; fi
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

call() {     # call CELL TAG CAP MODEL PROMPT MODE SID -- CHECK-ARGS...
  local cell=$1 tag=$2 cap=$3 model=$4 prompt=$5 mode=$6 sid=$7; shift 8
  local out="$STREAMS/$cell-$tag.jsonl" err="$STREAMS/$cell-$tag.stderr" rc=0 prc=0 spent line
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
        --plugin-dir "$FROZEN/plugin" "$(<"$prompt")" < /dev/null > "$out" 2> "$err" ) || rc=$?
  say "END $cell-$tag claude_rc=$rc stderr_bytes=$(wc -c < "$err" | tr -d ' ') tree=[$(git -C "$CELLS/$cell" status --porcelain | tr '\n' ';')]"
  line="$(python3 "$HERE/check.py" "$out" --init-agents "$INIT_AGENTS" "$@")" || prc=$?
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

# ---- preflight (cheap model): the Plugin loads, its roles are listed, the hook's policy text is in the capture ----
mkrepo preflight
call preflight t1 0.10 haiku "$FROZEN/prompts/preflight.txt" --session-id "$(newsid)" -- --marker "$MARKER" --no-main-writes \
  || { say "STOP preflight: Plugin policy or roles not observed in the capture"; exit 1; }
clean_tree preflight || { say "STOP preflight wrote files"; exit 1; }
say "PASS preflight"

# ---- X: cross-component, reversible. No plan-verifier; approval stop; verifier after implementation ----
mkrepo cross with-xfix
SID="$(newsid)"
call cross t1 0.40 opus "$FROZEN/prompts/cross-turn-1.txt" --session-id "$SID" -- --marker "$MARKER" --allow pilotfish:scout --no-main-writes \
  || { say "STOP cross t1 failed routing"; exit 1; }
clean_tree cross || { say "STOP cross t1 wrote before approval"; exit 1; }
call cross t2 0.80 opus "$FROZEN/prompts/schema-turn-2-explicit.txt" --resume "$SID" -- --require pilotfish:verifier --allow pilotfish:scout,pilotfish:executor,pilotfish:mech-executor \
  || { say "STOP cross t2 failed routing"; exit 1; }
OC="$(only_changed cross format.mjs report.mjs cli.mjs format.test.mjs report.test.mjs cli.test.mjs)" || { say "STOP cross t2 changed files outside scope or nothing"; exit 1; }
say "cross $OC"
tests_pass cross || { say "STOP cross tests fail"; exit 1; }
say "PASS cross"

# ---- S: schema migration. plan-verifier before approval; approval stop; verifier after implementation ----
mkrepo schema
SID="$(newsid)"
call schema t1 0.50 opus "$FROZEN/prompts/schema-turn-1-explicit.txt" --session-id "$SID" -- --marker "$MARKER" --require pilotfish:plan-verifier --allow pilotfish:scout --no-main-writes \
  || { say "STOP schema t1 failed routing"; exit 1; }
clean_tree schema || { say "STOP schema t1 wrote before approval"; exit 1; }
call schema t2 0.80 opus "$FROZEN/prompts/schema-turn-2-explicit.txt" --resume "$SID" -- --require pilotfish:verifier --allow pilotfish:scout,pilotfish:executor,pilotfish:mech-executor,pilotfish:plan-verifier \
  || { say "STOP schema t2 failed routing"; exit 1; }
OC="$(only_changed schema store.mjs store.test.mjs)" || { say "STOP schema t2 changed files outside scope or nothing"; exit 1; }
say "schema $OC"
tests_pass schema || { say "STOP schema tests fail"; exit 1; }
say "PASS schema"

FINAL="$(python3 "$HERE/check.py" --spent "$STREAMS")" || { say "STOP final spend unknown"; exit 2; }
say "REPO-STATUS-AFTER $(git -C "$SRC" status --porcelain | shasum -a 256 | cut -c1-16)"
say "DONE spent=$FINAL"
