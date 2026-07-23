# Contributing to pilotfish

Thanks for improving pilotfish. This repository packages policy, role templates,
installation instructions, and behavioral evidence; a wording-only change can
alter runtime orchestration, while a one-line frontmatter change can invalidate
an exact-byte fixture. Contributions should keep those surfaces synchronized
without rewriting historical evidence.

## Set up a checkout

pilotfish has no project dependency installation step. Use a recent `python3`
and a clean branch based on the pull request's intended base.

```bash
git clone https://github.com/Nanako0129/pilotfish.git
cd pilotfish
git switch -c your-change
python3 -m unittest discover -s tests -v
```

The test suite uses the Python standard library. Fixture-local `npm test`
commands described under `benchmarks/` apply to those disposable benchmark
repositories, not to the pilotfish repository itself.

## Keep each source authoritative

| Surface | Authority and contribution rule |
|---|---|
| `templates/claude-md.orchestration.md` | Model-independent orchestration policy. Role names belong here; model bindings do not. |
| `templates/agents/*.md` | Current role prompts, tool boundaries, models, and effort settings. Change the role frontmatter here. |
| `install/AGENT-INSTALL.md` | Installer behavior and merge contract. Preserve idempotency and the user's existing configuration. |
| `README.md`, `README.zh-TW.md`, `docs/` | User-facing behavior and design rationale. Keep English and Traditional Chinese claims aligned when both surfaces cover the change. |
| `benchmarks/*/results.json` | Machine-readable evidence. Add new observations; do not relabel failed, superseded, or historical runs. |
| `benchmarks/*/*-snapshot/` | Exact historical runtime inputs. Never regenerate an old snapshot to match newer templates. |

Keep claims within the evidence collected. Static tests can establish template
shape and invariants; they cannot establish that Claude dispatched a role.
A live Gate can establish the behavior it actually exercised; it does not prove
lower cost, lower latency, or general efficiency without an appropriate
controlled comparison. Record unexercised controls and failed attempts instead
of silently extending a passing result.

## Preserve generated payload provenance

[`build-agents-json.py`](./benchmarks/baton-compatibility/build-agents-json.py)
is the only supported builder for the current eight-role `--agents` payload:

```bash
python3 benchmarks/baton-compatibility/build-agents-json.py templates/agents
```

When a role template changes, update current candidate evidence from the
builder output. Do not paste a hand-reordered JSON object and do not replace the
payload stored beside an already-recorded runtime Gate.

| Evidence | Required treatment |
|---|---|
| Historical Gate payload | Preserve the exact bytes and its `final_gate_*` hash. |
| Current generated candidate | Record its builder-derived `release_candidate_*` hash separately. |
| New live Gate | Add or version a new snapshot and runtime record; do not overwrite the previous run. |
| Post-Gate template change | State the exact delta, whether the changed role was exercised, and what has not been rerun. |

Hash conventions are part of the evidence contract:

| Input | SHA-256 bytes |
|---|---|
| Policy or ordinary file | File bytes exactly as committed. |
| `agents.json` passed through shell command substitution | File bytes with repository trailing newline stripped. |
| Prompt provenance | Record both file bytes and the shell-normalized runtime-input bytes. |

Use LF line endings. A CRLF conversion or an extra newline changes exact-byte
hashes even when rendered content looks identical. The policy contract tests
rebuild the current candidate and verify the recorded evidence contract.

## Verify the change

Run the narrowest relevant test while editing, then the complete suite before
opening or updating a pull request:

```bash
python3 -m unittest \
  tests.test_policy.PolicyContractTests.test_baton_gate_snapshot_matches_recorded_hashes \
  -v

python3 -m unittest discover -s tests -v
```

### Behavioral orchestration changes

Changes to dispatch eligibility, planning-skill activation, ownership,
background scheduling, result collection, or verifier boundaries need a
behavioral Gate when the pull request makes a runtime claim. A spontaneous or
cue-free claim requires a neutral user prompt: scan the prompt and fixture for
agent, role, skill, policy, delegation, orchestration, parallelism, fan-out, and
the named planning skill. An explicitly plan-first or user-directed delegation
Gate may name those mechanisms, but must not be presented as spontaneous.

Record each observable layer separately:

| Layer | Minimum evidence |
|---|---|
| Availability | Whether the skill or named role appeared in runtime initialization. |
| Activation | The observable skill invocation, distinct from mere availability. |
| Dispatch | Named role, background or foreground mode, and absence of an invocation-level model override. |
| Completion | Every dispatched result collected before dependent synthesis, with ownership overlap checked. |
| Acceptance | Repository-owned checks run against the final artifact bytes, after the last write. |

Pin the policy bytes, generated agents payload, client version, model route, and
skill source used by each run. Retain failed attempts and version differences.
A single passing Gate can establish reachability for that exact input; it does
not establish activation frequency, causality, latency, cost, or efficiency.

If the change claims runtime behavior, also run the documented isolated
reproduction for that behavior and publish the actual disposition. Never run
`--dangerously-skip-permissions` in a valuable checkout; benchmark instructions
that use it are limited to disposable fixtures.

## Prepare the pull request

| Check | Expected evidence in the pull request |
|---|---|
| Scope | Explain the user-visible or policy outcome and what is intentionally unchanged. |
| Synchronization | List every affected policy, role, installer, English, Traditional Chinese, and benchmark surface. |
| Provenance | Distinguish historical runtime input from the current generated candidate. |
| Verification | Include exact commands and results; state explicitly when a live Gate was not run. |
| Claims | Avoid causal, quality, cost, latency, or efficiency claims beyond the published controls. |
| Automation | If AI or another automated tool materially authored the change, disclose it and state what was independently verified. |

Use a concise Conventional Commit subject for non-trivial work, followed by a
body that records the concrete behavior, control flow or evidence boundary,
important trade-offs, and verification actually included in the commit.
