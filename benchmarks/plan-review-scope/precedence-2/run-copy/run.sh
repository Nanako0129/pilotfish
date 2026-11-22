#!/usr/bin/env bash
# Second paid check of the verifier verdict-precedence wording. The first v3 state (../precedence)
# could be read as failing listed condition 3; this one keeps every listed condition met and
# leaves the round-trip test untouched: encodeUser retains every user and payload in a
# module-level array that nothing reads or clears.
# Runs on the Mac. Hard cap: USD 1.50 total. Refuses to call a real client unless PAID_RUN=1.
# Cells: v3 on the working-tree roles, v3base on the roles at BASE_REF. Both verdicts are
#        recorded; neither stops the run.
# Every claude call runs inside a disposable Git copy of a fixture. The pilotfish repository is only read.
set -euo pipefail

G="$(cd "$(dirname "$0")/.." && pwd)"          # run folder (script runs from <folder>/run-copy/)
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${SRC:-$(git rev-parse --show-toplevel)}"
PRS="$SRC/benchmarks/plan-review-scope"
BASE_REF=5ba7ee0f2cbaa3ebe84b6b33a7e81158a0550226
CAP_TOTAL=1.50
LOG="$G/run.log"
FROZEN="$G/src"
STREAMS="$G/streams"
CELLS="$G/cells"
export GIT_OPTIONAL_LOCKS=0
GITC=(-c user.name=gate -c user.email=gate@example.invalid -c commit.gpgsign=false)

say() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }
trap 'rc=$?; say "RUNNER-EXIT code=$rc"' EXIT

CLAUDE_BIN="$(command -v claude)" || { say "STOP claude not found"; exit 4; }
case "$CLAUDE_BIN" in /*) ;; *) say "STOP claude does not resolve to an absolute path: $CLAUDE_BIN"; exit 4 ;; esac
CLIENT="$("$CLAUDE_BIN" --version)"
if [ "$CLIENT" != stub ] && [ "${PAID_RUN:-}" != 1 ]; then say "STOP real client '$CLIENT' without PAID_RUN=1"; exit 4; fi

# ---- freeze inputs (refuse to start over leftovers) ----
for d in "$FROZEN" "$STREAMS" "$CELLS"; do
  if [ -e "$d" ]; then say "STOP exists $d"; exit 4; fi
  mkdir -p "$d"
done
cp "$SRC/templates/claude-md.orchestration.md" "$FROZEN/CLAUDE.md"
python3 "$SRC/benchmarks/baton-compatibility/build-agents-json.py" "$SRC/templates/agents" > "$FROZEN/agents.json"
cmp -s "$SRC/templates/agents/verifier.md" "$SRC/plugin/agents/verifier.md" || { say "STOP template and Plugin verifier differ"; exit 4; }
mkdir "$FROZEN/base"
git -C "$SRC" archive "$BASE_REF" templates/agents | tar -x -C "$FROZEN/base"
python3 "$SRC/benchmarks/baton-compatibility/build-agents-json.py" "$FROZEN/base/templates/agents" > "$FROZEN/agents-base.json"
if cmp -s "$FROZEN/agents.json" "$FROZEN/agents-base.json"; then say "STOP working-tree roles equal the base roles"; exit 4; fi
git -C "$SRC" diff --quiet "$BASE_REF" -- templates/claude-md.orchestration.md || { say "STOP policy differs from base; v3base would not isolate the roles"; exit 4; }
mkdir "$FROZEN/fixture" "$FROZEN/prompts" "$FROZEN/states"
cp "$SRC"/benchmarks/verifier-boundary/fixture/{package.json,README.md,store.mjs,store.test.mjs} "$FROZEN/fixture/"
cp -R "$PRS/precedence-2/states/v3" "$FROZEN/states/"
cp "$PRS/precedence/prompts/verify.txt" "$FROZEN/prompts/"
( cd "$FROZEN" && find . -type f ! -name SHA256.txt | sort | xargs shasum -a 256 > SHA256.txt )
say "FROZEN client=$CLIENT policy=$(shasum -a 256 "$FROZEN/CLAUDE.md" | cut -c1-16) agents=$(shasum -a 256 "$FROZEN/agents.json" | cut -c1-16) agents_base=$(shasum -a 256 "$FROZEN/agents-base.json" | cut -c1-16) repo_head=$(git -C "$SRC" rev-parse --short HEAD) base=$(printf %s "$BASE_REF" | cut -c1-7)"
say "REPO-STATUS-BEFORE $(git -C "$SRC" status --porcelain | shasum -a 256 | cut -c1-16)"

mkrepo() {   # mkrepo CELL STATE
  local dir="$CELLS/$1" state=$2
  mkdir "$dir"
  cp "$FROZEN"/fixture/{package.json,README.md,store.mjs,store.test.mjs} "$dir/"
  cp "$FROZEN/CLAUDE.md" "$dir/CLAUDE.md"
  git -C "$dir" init -q
  git -C "$dir" add -A
  git -C "$dir" "${GITC[@]}" commit -q -m baseline
  cp "$FROZEN/states/$state"/{README.md,store.mjs,store.test.mjs} "$dir/"
  git -C "$dir" add -A
  git -C "$dir" "${GITC[@]}" commit -q -m "migrate payload to version 2"
  git -C "$dir" tag baseline
  ( cd "$dir" && npm test > "$STREAMS/$1-npm-test-before.txt" 2>&1 ) || { say "STOP $1 state does not pass its own tests"; exit 4; }
}

call() {     # call CELL AGENTS_JSON EXPECT_REGEX   (one fresh session, cap 0.60)
  local cell=$1 agents=$2 expect=$3 cap=0.60
  local out="$STREAMS/$cell-t1.jsonl" err="$STREAMS/$cell-t1.stderr" rc=0 prc=0 spent line
  spent="$(python3 "$HERE/parse.py" --spent "$STREAMS")" || { say "STOP unknown-cost"; exit 3; }
  if ! python3 -c 'import sys; sys.exit(0 if float(sys.argv[1])+1.5*float(sys.argv[2]) <= float(sys.argv[3]) else 1)' "$spent" "$cap" "$CAP_TOTAL"; then
    say "STOP budget spent=$spent next_cap=$cap total_cap=$CAP_TOTAL"; exit 3
  fi
  if [ -e "$out" ]; then say "STOP stream-exists $out"; exit 4; fi
  say "START $cell-t1 cap=$cap spent_so_far=$spent"
  ( cd "$CELLS/$cell" && env -u CLAUDE_CODE_SUBAGENT_MODEL perl -e 'alarm shift; exec @ARGV' 1500 \
      "$CLAUDE_BIN" --dangerously-skip-permissions -p --output-format stream-json --verbose \
        --max-budget-usd "$cap" --session-id "$(python3 -c 'import uuid; print(uuid.uuid4())')" --model opus --effort high \
        --setting-sources project,local --strict-mcp-config \
        --agents "$(<"$agents")" "$(<"$FROZEN/prompts/verify.txt")" < /dev/null > "$out" 2> "$err" ) || rc=$?
  say "END $cell-t1 claude_rc=$rc stderr_bytes=$(wc -c < "$err" | tr -d ' ') tree=[$(git -C "$CELLS/$cell" status --porcelain | tr '\n' ';')]"
  line="$(python3 "$HERE/parse.py" "$out" verifier "$expect")" || prc=$?
  say "$line"
  if [ "$rc" -ne 0 ]; then say "FAIL $cell-t1 claude exited $rc"; return 1; fi
  return "$prc"
}

clean_tree() {   # clean_tree CELL  -> fail if HEAD moved or anything changed
  local h b s
  h="$(git -C "$CELLS/$1" rev-parse --verify -q HEAD)" || return 1
  b="$(git -C "$CELLS/$1" rev-parse --verify -q 'baseline^{commit}')" || return 1
  [ "$h" = "$b" ] || return 1
  s="$(git -C "$CELLS/$1" status --porcelain)" || return 1
  [ -z "$s" ]
}

# ---- V3: every listed condition met, plus a regression outside them ----
mkrepo v3 v3
call v3 "$FROZEN/agents.json" 'REFUTED' || say "NOTE v3 not REFUTED or incomplete; recorded as is"
clean_tree v3 || say "NOTE v3 changed the tree"

# ---- V3BASE: same state on the roles at BASE_REF ----
mkrepo v3base v3
call v3base "$FROZEN/agents-base.json" 'CONFIRMED|REFUTED|INCONCLUSIVE' || say "NOTE v3base cell incomplete; recorded as is"
clean_tree v3base || say "NOTE v3base changed the tree"

say "REPO-STATUS-AFTER $(git -C "$SRC" status --porcelain | shasum -a 256 | cut -c1-16)"
FINAL="$(python3 "$HERE/parse.py" --spent "$STREAMS")" || { say "STOP final spend unknown"; exit 2; }
say "DONE spent=$FINAL"
