#!/usr/bin/env bash
# Paid check of the verifier verdict-precedence wording (REFUTED over CONFIRMED when a
# reproducible P0-P2 blocker coexists with met conditions).
# Runs on the Mac. Hard cap: USD 2.50 total across all cells. Refuses to call a real client unless
# PAID_RUN=1 (added after the run this folder records, which had no such check).
# Cells: v1 (behavioral defect), v2 (count mismatch), v3 (all listed conditions met, the
#        commit also mutates the caller's object) on the working-tree roles; v3base = v3 on
#        the roles at BASE_REF. v1, v2, v3 stop the run on an unexpected verdict; v3base is
#        a control and is only recorded.
# Every claude call runs inside a disposable Git copy of a fixture. The pilotfish repository is only read.
set -euo pipefail

G="$(cd "$(dirname "$0")/.." && pwd)"          # run folder (script runs from <folder>/run-copy/)
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${SRC:-$(git rev-parse --show-toplevel)}"
PRS="$SRC/benchmarks/plan-review-scope"
BASE_REF=5ba7ee0f2cbaa3ebe84b6b33a7e81158a0550226
CAP_TOTAL=2.50
LOG="$G/run.log"
FROZEN="$G/src"
STREAMS="$G/streams"
CELLS="$G/cells"
export GIT_OPTIONAL_LOCKS=0
GITC=(-c user.name=gate -c user.email=gate@example.invalid -c commit.gpgsign=false)

say() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }
trap 'rc=$?; say "RUNNER-EXIT code=$rc"' EXIT

CLIENT="$(claude --version)"
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
cp -R "$PRS/blocking-bar/states/v1" "$PRS/blocking-bar/states/v2" "$PRS/precedence/states/v3" "$FROZEN/states/"
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
      claude --dangerously-skip-permissions -p --output-format stream-json --verbose \
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

# ---- V1: behavioral defect must still be REFUTED ----
mkrepo v1 v1
call v1 "$FROZEN/agents.json" 'REFUTED' || { say "STOP v1 failed: a real defect was not refuted"; exit 1; }
clean_tree v1 || { say "STOP v1 changed the tree"; exit 1; }

# ---- V2: wording-only mismatch must not block ----
mkrepo v2 v2
call v2 "$FROZEN/agents.json" 'CONFIRMED|INCONCLUSIVE' || { say "STOP v2 failed: wording-only mismatch blocked or cell incomplete"; exit 1; }
clean_tree v2 || { say "STOP v2 changed the tree"; exit 1; }

# ---- V3: every listed condition met, plus a regression outside them ----
mkrepo v3 v3
call v3 "$FROZEN/agents.json" 'REFUTED' || { say "STOP v3 failed: regression outside the listed conditions was not refuted"; exit 1; }
clean_tree v3 || { say "STOP v3 changed the tree"; exit 1; }

# ---- V3BASE: same state on the roles at BASE_REF; control, any verdict is recorded ----
mkrepo v3base v3
call v3base "$FROZEN/agents-base.json" 'CONFIRMED|REFUTED|INCONCLUSIVE' || say "NOTE v3base cell incomplete; recorded as is"
clean_tree v3base || say "NOTE v3base changed the tree"

FINAL="$(python3 "$HERE/parse.py" --spent "$STREAMS")" || { say "STOP final spend unknown"; exit 2; }
say "REPO-STATUS-AFTER $(git -C "$SRC" status --porcelain | shasum -a 256 | cut -c1-16)"
say "DONE spent=$FINAL"
