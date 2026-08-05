# Dispatch-rate harness

A reproducible, resumable experiment runner for measuring Claude Code dispatch
behaviour under a hard budget ceiling. It exists because the 2026-08-06 study
(`.agent-local/dispatch-rate-study/results.json`, 40 runs, $18.97) hit every
failure a runner like this should prevent: quota exhaustion recorded as
observations, batches killed mid-flight with no way to resume, arm collinear
with wall-clock time, and conclusions drawn before enough runs existed. Each
requirement below traces to one of those failures.

`run_study.py` is Python 3, standard library only. It does not implement its
own classifier — it calls
[`classify_stream.py`](../spontaneous-dispatch/classify_stream.py), and it
does not implement its own `--agents` payload builder — it calls
[`build-agents-json.py`](../baton-compatibility/build-agents-json.py).

## Commands

```
run_study.py plan   study.json                  # print the seeded schedule; spawns nothing
run_study.py run    study.json                  # execute; resumable; obeys both ceilings
run_study.py report study.json                  # validity-filtered tally + Fisher exact
run_study.py report --legacy <results.json>     # same analysis over a prior study's results.json
```

## Study file

See [`study.example.json`](./study.example.json):

```json
{
  "name": "cue-free-dispatch-rate",
  "prompt": "benchmarks/spontaneous-dispatch/prompts/mechanical.txt",
  "fixture": "benchmarks/dispatch-brake/positive-controls/mechanical/fixture",
  "agents_from": "templates/agents",
  "model": "opus",
  "target_n": 10,
  "per_run_cap_usd": 1.20,
  "total_cap_usd": 25.00,
  "max_retries_per_cell": 2,
  "max_backoff_seconds": 900,
  "seed": 20260806,
  "evidence_dir": ".agent-local/dispatch-rate/cue-free",
  "arms": {
    "control":   {"policy": "templates/claude-md.orchestration.md", "scope": "project"},
    "candidate": {"policy": "benchmarks/dispatch-rate/policies/candidate.md", "scope": "project"},
    "placebo":   {"policy": "benchmarks/dispatch-rate/policies/placebo.md", "scope": "project"}
  }
}
```

Every path is resolved relative to the repository root, regardless of the
working directory the tool is invoked from. `max_retries_per_cell`,
`max_backoff_seconds`, `total_cap_usd`, `per_run_cap_usd`, `target_n` and
`seed` are required; the runner refuses a study file missing any of them
rather than defaulting.

### Policy composition

`control`'s policy file is the base, used verbatim. Every other arm's policy
file is a *section*, appended onto that base as `base_bytes + b"\n" +
section_bytes`. [`policies/candidate.md`](./policies/candidate.md) and
[`policies/placebo.md`](./policies/placebo.md) are sections, not full
policies, for exactly this reason — they are not meant to be read standalone.

### Policy scope

`scope` is per arm, `"project"` (default) or `"user"`. It exists because the
source study measured everything at **project** scope — the policy was the
fixture's `CLAUDE.md` under `--setting-sources project,local` — while
pilotfish actually installs at **user** scope, `$CLAUDE_CONFIG_DIR/CLAUDE.md`.
Whether the measured effect survives that move is untested and is the single
most consequential open question about the tool's own product, so the harness
can vary it.

| scope | policy lands at | `--setting-sources` | fixture `CLAUDE.md` |
|---|---|---|---|
| `project` | `<fixture-copy>/CLAUDE.md` | `project,local` | the policy |
| `user` | `<run-root>/user-config/CLAUDE.md`, exported as `CLAUDE_CONFIG_DIR` | `user,project,local` | absent |

The per-cell `CLAUDE_CONFIG_DIR` lives inside the disposable run root the tool
creates — a user-scope study never touches the real `~/.claude`. The runner
refuses to start a user-scope cell if the resolved `CLAUDE_CONFIG_DIR` is, or
is inside, the real configuration root (`$CLAUDE_CONFIG_DIR` if set in the
environment, otherwise `~/.claude`); this check runs before any spawn.

A fixture whose copy already contains a `CLAUDE.md` is **refused** for a
user-scope arm, rather than having that file silently removed: leaving it in
place would make both the per-cell user policy and the fixture's own project
policy visible to the run at once, violating the table above (fixture
`CLAUDE.md` must be absent in user scope) and the single-variable-across-arms
contract. Remove the file from the fixture, or run that arm at project scope
instead.

Agents are delivered identically in both scopes: built from `agents_from` and
passed via `--agents`, never written into the disposable config directory.
That keeps policy scope the single variable across arms. A full-install
variant, where the roles also move to user scope, is a separate future study
and is deliberately not mixed into this one.

## Safety contract

1. **Reservation accounting.** Before spawning `claude`, the runner appends an
   entry charging `per_run_cap_usd` to the state file. On clean completion the
   reservation is reconciled to the client-reported cost. If the run is
   interrupted, invalid, or retried, the reservation stays charged. Cumulative
   charge is checked before every spawn; when the next reservation would
   exceed `total_cap_usd` the runner stops and names the reservation blocking
   it. There is no flag to disable this. `run` takes an exclusive lock
   (`evidence_dir/.lock`) for its whole invocation; a second `run` against the
   same `evidence_dir` refuses to start and names the holding pid, because
   `state.json` is a whole-file rewrite and two concurrent writers could
   otherwise silently erase each other's reservations. Both ceilings are
   themselves recorded in the run header and checked on every resume:
   **raising** `total_cap_usd` or `per_run_cap_usd` after the study began is
   refused outright, naming the stored and current values — otherwise editing
   the study file up would silently restart a study that had already stopped
   at its hard ceiling. **Lowering** either is allowed without an override,
   since a lower ceiling only tightens what a resumed run can still spend.
2. **Rejected runs are not observations.** A run whose stream has empty
   `model_costs_usd`, or whose terminal event subtype is not `success`, is
   recorded `valid: false` with a reason and never enters a numerator or
   denominator. Retries are bounded by `max_retries_per_cell`; their spend is
   still charged.
3. **Bounded backoff.** On a rejection matching quota or rate limiting, the
   runner waits with exponential backoff capped at `max_backoff_seconds`
   total, then stops the whole study and writes resumable state. It never
   spins through the remaining schedule hoping the limit clears.
4. **Disposable fixtures only.** Fixtures are copied into a run root the tool
   creates under the system temp directory, recorded in state.
   `--dangerously-skip-permissions` is passed only inside those copies — the
   boundary [`spontaneous-dispatch/README.md`](../spontaneous-dispatch/README.md)
   already documents.
5. **Contamination invariants.** The `--agents` payload is built from
   `agents_from` and passed on the command line, never copied into the
   fixture or the user-scope config directory. No run artifact — stream,
   state, or evidence — is written inside the fixture copy.
6. **Raw streams are never committed.** `run` refuses to start unless the
   resolved `evidence_dir` is Git-ignored (`git check-ignore`), naming the
   path and a suggested `.gitignore` line otherwise. The shipped example sits
   under `.agent-local/`, which this slice's `.gitignore` entry already
   covers. If `evidence_dir` is outside any Git work tree at all, the check is
   skipped and that is recorded in the run header — not a failure, since
   there's no repository to leave streams visible in.
7. **Pre-registration.** `report` prints per-arm counts at any time but
   refuses pooled comparisons or p-values until every arm reaches `target_n`,
   naming the shortfall. `target_n` itself is recorded in the run's header the
   moment `run` first starts a study, and `report` uses that recorded value —
   not whatever the study file currently says. Editing `target_n` down after
   the fact does not relax the guard; `report` refuses outright, naming both
   values, instead of silently comparing against the edited number.
8. **Observed conditions, not just declared inputs.** The header freezes
   *inputs* the study declares up front (policy/prompt/fixture bytes, model,
   both caps, ...). It cannot freeze conditions a run only *observes* —
   `client_version` and `observed_main_model` per attempt — because a Claude
   Code upgrade or a model alias resolving to a different concrete model
   mid-study are outside this tool's control. Before emitting any pooled
   comparison, `report` aggregates the distinct values of every such field
   across all valid attempts in the reported arms; if more than one distinct
   value shows up for any field, pooled comparisons are refused (naming the
   field and the values seen) rather than averaging over heterogeneous
   implementations. Per-arm counts and `observed_conditions` are still
   printed either way.

## Known limitations

- **No per-run timeout or kill.** `per_run_cap_usd` is enforced entirely by
  the real `claude` binary honouring `--max-budget-usd`; the runner never
  independently times out or kills a spawned process. A client that ignores
  that flag can spend past the per-run ceiling with nothing here to stop it.
  This assumption is exercised by the paid smoke gate (acceptance item 8),
  not by anything free.
- **Rate-limit rejections don't get their own reason code.** A run rejected
  for hitting a quota or rate limit is still recorded with
  `reason: "empty_model_costs_usd"` rather than something rate-limit-specific
  — the empty-cost check runs first because it's the source study's exact
  contamination shape and always takes forensic priority. No information is
  lost: `terminal_subtype` and `rate_limited: true` are still stored on the
  same attempt, so the rate-limit condition is fully recoverable from those
  two fields, just not from `reason` alone.
- **`report` skips the Git-ignore check and will `mkdir` its output path.**
  Unlike `run`, `report` does not verify `evidence_dir` is Git-ignored before
  writing `results.json` into it, and it creates the directory tree if
  missing. This is only reachable by pointing `report` at a study whose `run`
  was never invoked (or was invoked with a since-edited `evidence_dir`), so
  the safety contract's real enforcement point — before any `claude` spawn —
  is unaffected.
- **`flock` on NFS is unverified.** The concurrency guarantee in safety
  contract 1 (`acquire_run_lock`) relies on `fcntl.flock`, which is only
  reliably advisory-locking on a local filesystem. The claim of "only one
  `run` at a time" is made for local filesystems only; behaviour with
  `evidence_dir` on an NFS mount has not been tested.
- **A non-`SystemExit` exception between reserving and spawning leaves a
  charged reservation with zero spend.** The reservation is appended and
  `status: "in_progress"` is saved *before* `make_run_root` runs (so a hard
  kill mid-spawn is recovered correctly), but only `SystemExit` from
  `make_run_root` (the config-root guard) refunds it. Anything else raised in
  that window — an arm deleted from the study file on resume, `git init`
  failing, disk full — propagates uncaught and leaves the reservation
  charged for zero observed spend. The direction is conservative: it can
  only stop the study early against `total_cap_usd`, never let it overspend.
  But repeated occurrences consume the ceiling without buying any
  observations. Not fixed deliberately — broadening the exception handling
  here risks masking a real failure as a routine, retryable one.

## Dispatch predicate

A run counts as dispatched when the classifier reports exactly one top-level
`Agent` call with `subagent_type: mech-executor`, `run_in_background: false`,
no invocation-level model override, and the child result collected. Anything
else is `direct`. The classifier itself (`classify_stream.py`) is unchanged;
this predicate is applied on top of its output.

## Evidence

Each attempt records: the stream JSONL's SHA-256, the classifier verdict,
changed files, client-reported cost, observed main model, client version,
arm, attempt index, schedule position, UTC timestamp, resolved scope and
`--setting-sources`, and the SHA-256 of the resolved policy, prompt and
fixture manifest. The study header additionally records the seed and the
digests (and scope) of every arm's policy. `report` aggregates all of this
into `<evidence_dir>/results.json`, in the same shape as the repaired source
study.

## Reproduce

```bash
python3 benchmarks/dispatch-rate/run_study.py plan benchmarks/dispatch-rate/study.example.json
python3 benchmarks/dispatch-rate/run_study.py run  benchmarks/dispatch-rate/study.example.json
python3 benchmarks/dispatch-rate/run_study.py report benchmarks/dispatch-rate/study.example.json
python3 benchmarks/dispatch-rate/run_study.py report --legacy .agent-local/dispatch-rate-study/results.json
```

`run` invokes `claude` by name on `$PATH`. Nothing about this tool talks to a
live account on its own — it spends only what the resolved `claude` binary
on `$PATH` spends. Point `$PATH` at a real Claude Code install to run for
real, or at [`tests/`](./tests/) to run the free, spend-nothing acceptance
suite:

```bash
python3 benchmarks/dispatch-rate/tests/test_run_study.py
```

That suite drives every branch — reservation accounting across a hard kill,
bounded retry and backoff on a simulated rate limit, resume-without-rerun,
pre-registration refusal, the legacy-report reproduction, the git-cleanliness
invariants, and both policy scopes — entirely against the shipped
[`tests/claude`](./tests/claude) stub. It never invokes a real model. The
legacy-report check round-trips against a small synthetic fixture tracked at
[`tests/fixtures/legacy-results.sample.json`](./tests/fixtures/legacy-results.sample.json),
so this passes on any clean clone; the real 2026-08-06 study's reproduction
(control 3/10, placebo 1/10, candidate 8/8) is a separate check that only
runs, and only asserts, when the Git-ignored
`.agent-local/dispatch-rate-study/results.json` is present locally — it
prints and skips otherwise.
