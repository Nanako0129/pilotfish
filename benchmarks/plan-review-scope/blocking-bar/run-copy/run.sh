#!/usr/bin/env bash
# Paid Gate for the verifier blocking-bar and plan-verifier direction-check wording.
# Runs on the Mac. Authorized hard cap: USD 6 total; stop at the first failed cell.
# Every claude call runs inside a disposable Git copy of the benchmark fixture.
# Nothing in the pilotfish repository is written; it is only read.
set -euo pipefail

G="$(cd "$(dirname "$0")/.." && pwd)"          # gate-1120/ (script runs from gate-1120/run-copy/)
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${SRC:-$(git rev-parse --show-toplevel)}"
CAP_TOTAL=6.00
LOG="$G/run.log"
FROZEN="$G/src"
STREAMS="$G/streams"
CELLS="$G/cells"

say() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }
trap 'rc=$?; say "RUNNER-EXIT code=$rc"' EXIT

# ---- freeze inputs (fail if a previous run left anything behind) ----
for d in "$FROZEN" "$STREAMS" "$CELLS"; do
  if [ -n "$(ls -A "$d" 2>/dev/null)" ]; then say "STOP not-empty $d"; exit 4; fi
  mkdir -p "$d"
done
cp "$SRC/templates/claude-md.orchestration.md" "$FROZEN/CLAUDE.md"
python3 "$SRC/benchmarks/baton-compatibility/build-agents-json.py" "$SRC/templates/agents" > "$FROZEN/agents-candidate.json"
mkdir -p "$FROZEN/base"
git -C "$SRC" archive main templates/agents | tar -x -C "$FROZEN/base"
python3 "$SRC/benchmarks/baton-compatibility/build-agents-json.py" "$FROZEN/base/templates/agents" > "$FROZEN/agents-base.json"
cp "$SRC"/benchmarks/verifier-boundary/prompts/plan-cap-turn-{1,2,3}.txt "$G/prompts/"
if cmp -s "$FROZEN/agents-candidate.json" "$FROZEN/agents-base.json"; then say "STOP candidate equals base"; exit 4; fi
( cd "$G" && shasum -a 256 src/CLAUDE.md src/agents-candidate.json src/agents-base.json prompts/*.txt > "$FROZEN/SHA256.txt" )
say "FROZEN client=$(claude --version) $(tr '\n' ' ' < "$FROZEN/SHA256.txt" | cut -c1-400)"

say "REPO-STATUS-BEFORE $(git -C "$SRC" status --porcelain | shasum -a 256 | cut -c1-16)"

mkrepo() {   # mkrepo CELL [STATE]
  local cell=$1 state=${2:-} dir="$CELLS/$1"
  mkdir "$dir"
  cp "$SRC"/benchmarks/verifier-boundary/fixture/{package.json,README.md,store.mjs,store.test.mjs} "$dir/"
  cp "$FROZEN/CLAUDE.md" "$dir/CLAUDE.md"
  git -C "$dir" init -q
  git -C "$dir" add -A
  git -C "$dir" -c user.name=gate -c user.email=gate@example.invalid -c commit.gpgsign=false commit -q -m baseline
  if [ -n "$state" ]; then
    cp "$G/states/$state"/{README.md,store.mjs,store.test.mjs} "$dir/"
    git -C "$dir" add -A
    git -C "$dir" -c user.name=gate -c user.email=gate@example.invalid -c commit.gpgsign=false commit -q -m "migrate payload to version 2"
  fi
}

call() {     # call CELL TAG CAP AGENTS PROMPT ROLE EXPECT MODE SID
  local cell=$1 tag=$2 cap=$3 agents=$4 prompt=$5 role=$6 expect=$7 mode=$8 sid=$9
  local out="$STREAMS/$cell-$tag.jsonl" err="$STREAMS/$cell-$tag.stderr" rc=0 spent
  spent="$(python3 "$HERE/parse.py" --spent "$STREAMS")" || { say "STOP unknown-cost"; exit 3; }
  if ! python3 -c 'import sys; sys.exit(0 if float(sys.argv[1])+1.5*float(sys.argv[2]) <= float(sys.argv[3]) else 1)' "$spent" "$cap" "$CAP_TOTAL"; then
    say "STOP budget spent=$spent next_cap=$cap total_cap=$CAP_TOTAL"; exit 3
  fi
  if [ -e "$out" ]; then say "STOP stream-exists $out"; exit 4; fi
  say "START $cell-$tag cap=$cap spent_so_far=$spent"
  ( cd "$CELLS/$cell" && perl -e 'alarm shift; exec @ARGV' 1500 \
      claude --dangerously-skip-permissions -p --output-format stream-json --verbose \
        --max-budget-usd "$cap" "$mode" "$sid" --model opus --effort high \
        --setting-sources project,local --strict-mcp-config \
        --agents "$(<"$agents")" "$(<"$prompt")" > "$out" 2> "$err" ) || rc=$?
  say "END $cell-$tag claude_rc=$rc stderr_bytes=$(wc -c < "$err" | tr -d ' ') tree=[$(git -C "$CELLS/$cell" status --porcelain | tr '\n' ';')]"
  local line prc=0
  line="$(python3 "$HERE/parse.py" "$out" "$role" "$expect")" || prc=$?
  say "$line"
  return "$prc"
}

newsid() { python3 -c 'import uuid; print(uuid.uuid4())'; }

# ---- V1: behavioral defect must still be REFUTED ----
mkrepo v1 v1
call v1 t1 1.00 "$FROZEN/agents-candidate.json" "$G/prompts/verify.txt" verifier 'REFUTED' --session-id "$(newsid)" \
  || { say "STOP v1 failed: a real defect was not refuted"; exit 1; }

# ---- V2: wording-only mismatch must not block ----
mkrepo v2 v2
call v2 t1 1.00 "$FROZEN/agents-candidate.json" "$G/prompts/verify.txt" verifier 'CONFIRMED|INCONCLUSIVE' --session-id "$(newsid)" \
  || { say "STOP v2 failed: wording-only mismatch still blocked or cell incomplete"; exit 1; }

# ---- P: plan-cap control, REVISE -> REVISE -> READY, zero writes ----
mkrepo plancap
SID="$(newsid)"
call plancap t1 0.80 "$FROZEN/agents-candidate.json" "$G/prompts/plan-cap-turn-1.txt" plan-verifier 'REVISE' --session-id "$SID" \
  || { say "STOP plancap t1 failed"; exit 1; }
call plancap t2 0.80 "$FROZEN/agents-candidate.json" "$G/prompts/plan-cap-turn-2.txt" plan-verifier 'REVISE' --resume "$SID" \
  || { say "STOP plancap t2 failed"; exit 1; }
call plancap t3 0.80 "$FROZEN/agents-candidate.json" "$G/prompts/plan-cap-turn-3.txt" plan-verifier 'READY' --resume "$SID" \
  || { say "STOP plancap t3 failed"; exit 1; }
if [ -n "$(git -C "$CELLS/plancap" status --porcelain)" ]; then say "STOP plancap wrote files"; exit 1; fi

# ---- V2-base: same wording-only cell on the unchanged main-branch agents (informational) ----
mkrepo v2base v2
call v2base t1 1.00 "$FROZEN/agents-base.json" "$G/prompts/verify.txt" verifier 'REFUTED' --session-id "$(newsid)" \
  || say "NOTE v2base not PASS: read its RESULT line (verdict other than REFUTED = cell does not discriminate; subtype/is_error = broken run)"

FINAL="$(python3 "$HERE/parse.py" --spent "$STREAMS")" || { say "STOP final spend unknown"; exit 2; }
say "REPO-STATUS-AFTER $(git -C "$SRC" status --porcelain | shasum -a 256 | cut -c1-16)"
say "DONE spent=$FINAL"
