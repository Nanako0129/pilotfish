# Effort selection

[繁體中文](./README.zh-TW.md)

From Claude Code 2.1.292 the Agent tool takes a per-invocation `effort`, which overrides an agent's frontmatter `effort`; `CLAUDE_CODE_EFFORT_LEVEL` overrides both. This study checked whether the main session should choose effort per delegation instead of every role always running at its frontmatter level. Each role's frontmatter effort stays as the recommended default.

All runs used Claude Code 2.1.294, with the main session on `claude-opus-5-5` and the pilotfish Plugin loaded. Per-run records are in [`results.json`](./results.json); the harness is in [`scripts/`](./scripts/).

## 1. Does the main session choose by task?

With an explicit instruction appended to the system prompt ([`scripts/ab-rule-B.md`](./scripts/ab-rule-B.md)), the main session passed `effort` on 14 of 14 delegations. It changed the level within a role according to the task, and chose the same level both times a task was repeated:

| Role | Easy task | Hard task |
|---|---|---|
| `scout` | file of one function: `low` | repo-wide map of model/role bindings: `high` |
| `executor` | one spelling fix: `low` | diagnose a signal-handling bug: `medium` |
| `security-reviewer` | does one `printf` print an env var: `low` | adversarial review of the SessionStart hook: `high` |

## 2. Does it change quality or cost?

This A/B used the same Plugin and exactly one delegation per task. Arm A was told not to pass `effort`, so the role default applied. Arm B carried the instruction above.

| Suite | Role (default) | A | B | B's choices |
|---|---|---|---|---|
| Aider Polyglot, 40 tasks (20 Python, 20 Rust) | `mech-executor` (`low`) | 37/40 | 39/40 | `low` 21, `medium` 18, `high` 1 |
| SWE-bench Verified, "15 min – 1 hour", 20 tasks, official harness | `executor` (`medium`) | 18/20 | 16/20 | `medium` 16, `low` 4 |
| **Total** | | **55/60** | **55/60** | |

Arm A passed no `effort` on any of its 60 delegations, and arm B passed one on all 60. McNemar p = 0.5 for each suite. Both SWE tasks that only arm A resolved ran at `medium` in both arms, so the discordance at identical settings is run-to-run noise. List-price cost (Claude Code's `costUSD`) was $11.45 for A and $11.57 for B (+1.1%), and median durations were similar.

**Reading:** on these two Sonnet roles the change was not measured to help or hurt quality or cost. Opus roles (verifier, plan-verifier, security-reviewer) and the Haiku scout were not A/B-tested. Arm B used the appended instruction, not the shipped policy line, and had no reviewer floor. On the gate tasks (section 3) the shipped line chose the same levels as that instruction except where the floor applies: E4 moved from `low` to `high`. The shipped line's own quality and cost were not A/B-tested.

The A/B ran with `CLAUDE_EFFORT=xhigh` in the shell environment; the committed `ab.py` now unsets it. A separate check (`env_default_probe` in `results.json`) delegated a scout lookup without `effort`. With `CLAUDE_EFFORT=max` it used 1.2k Haiku output tokens in 14 s, against 2.3k with the variable unset and 115k for an explicit `effort` of `max`. That suggests the variable does not override the frontmatter default, so arm A most likely ran at the role defaults. This is an inference: the check is one run each, on the Haiku scout rather than the Sonnet roles in the A/B, and with `max` rather than the `xhigh` that was set. All 120 recorded A/B runs had exactly one delegation and no tool call by the main session (`ab.validity_check`).

## 3. Gate on the shipped wording (A2)

The policy line has to carry the instruction itself; nothing is appended. The Agent tool's own description tells the model to set `effort` only when instructions explicitly ask for a level, and the result depends on how explicitly the policy says so. The shipped line also states a floor for the reviewers (`verifier` and `plan-verifier` at least `medium`, `security-reviewer` at least `high`, their defaults), because the main session cannot see role frontmatter.

Isolation is recorded in [`a2-isolation.txt`](./a2-isolation.txt):
- fixtures are `git archive` copies with nested snapshot `CLAUDE.md` files removed;
- `CLAUDE_EFFORT` and `CLAUDE_CODE_EFFORT_LEVEL` were unset;
- there was no `--append-system-prompt`;
- the user `CLAUDE.md` contained no "effort";
- the task prompts ([plugin](./a2-tasks-plugin.tsv), [template](./a2-tasks-template.tsv)) contain no effort-level word.

The run had two arms. The Plugin arm loaded the plugin with `--plugin-dir`. The template arm used a project `CLAUDE.md` and `.claude/agents/` as a proxy for the global install; the real `~/.claude/CLAUDE.md` placement was not run.

**Pass rule** (`a2_gate.pass_rule`): each arm runs 8 tasks twice. For each arm:
- `effort` is present on at least 13/14 of delegations;
- every delegation goes to the requested role;
- the scout pair (T1/H1) and the executor pair (E3/T3) put the hard task strictly higher in both repetitions;
- no reviewer delegation is below its floor.

E4 (a one-line `security-reviewer` check) and E5 (a trivial `verifier` check) are the cases where a free choice would go below the floor.

| Wording | Plugin arm | Template arm |
|---|---|---|
| Round 0, compressed, no floor (earlier rule) | FAIL: effort 1/14 | FAIL: effort 11/15, scout pair failed |
| Round 1, explicit, no floor (earlier rule) | PASS: effort 14/14 | PASS: effort 14/14 |
| **Round 2, shipped (explicit, with floor)** | **PASS**: effort 16/16, both pairs, no floor break | **PASS**: effort 17/17, both pairs, no floor break |

Under the shipped wording both arms chose the same levels in both repetitions:
- `scout`: `low` for the lookup, `high` for the investigation;
- `executor`: `low` for the typo, `medium` for the bug;
- `mech-executor`: `low`;
- `security-reviewer`: `high` for both tasks (E4 was `low` in round 1);
- `verifier`: `medium` for E5.

In one template session (T3, repetition 2) the main session delegated twice, the second time to `executor` at `low`. Round 2 cost $5.53 (Plugin) and $6.71 (template) at list price. Per-run records are in `a2_gate.round2_floor_wording`.

## Limits

- The effort a subagent actually ran at is not logged. Only the requested value in the Agent `tool_use` input is visible; that the request takes effect is inferred from scaling, where the same scout lookup at `low`, `high` and `max` used 1.0k, 6.0k and 115k Haiku output tokens in total (`effort_scaling_probe` in `results.json`).
- When a subagent answers without any tool call, its message does not appear as a child message in stream-json; `task_notification` usage is the reliable signal there.
- Clients older than 2.1.292 have no Agent `effort` parameter. In one run on 2.1.287 (`old_client_probe`, with the round-1 wording, before the floor), the main session passed none and the delegation completed normally, presumably at the role default.
- `plan-verifier` is not an A2 task. In two separate runs (`plan_verifier_floor_probe`), a one-line plan sent to it got `medium`, its floor.
- None of 107 recorded delegations passed `model` (`model_param_check`), so the compressed model sentence in the Plugin line did not change routing in these runs.
- `scripts/agent_run.py`'s `./envrun` helper joins its arguments with `$*`, so arguments with inner quoting are re-split inside the container. Both A/B arms ran with the same helper.
- The precedence of `CLAUDE_CODE_EFFORT_LEVEL` is taken from the Claude Code sub-agents documentation and was not measured here.
- One run per task per arm in the A/B; the effect sizes are within run-to-run noise.

## Reproduce

The scripts are the harness as run, adapted to a repository layout; they are not a turnkey package, and every call is paid.

- **A2:** build `$A2_DIR/fixture-plugin/` and `$A2_DIR/fixture-template/` as described in section 3. Set `A2_DIR` and `PILOTFISH_PLUGIN` (the current `plugin/`), then run `scripts/one-r1.sh <arm> <task-id> <rep>` for each task in `a2-tasks-<arm>.tsv` and repetitions 1–2. Score with `python3 scripts/score.py "$A2_DIR/out" <arm>`.
- **A/B:** set `PILOTFISH_PLUGIN` to a `plugin/` exported from `a12b57a`, the state the recorded arms ran against, before the effort clause. `scripts/ab.py` imports `polyglot.py` and `agent_run.py` from the same directory. It also needs the Polyglot task list `tasks.json` (included), a clone of [Aider-AI/polyglot-benchmark](https://github.com/Aider-AI/polyglot-benchmark) at `scripts/data/polyglot-benchmark`, `med20.json` (included), the `swebench` package and the instance images pulled with `--platform linux/amd64`. Grading SWE-bench predictions uses `python -m swebench.harness.run_evaluation -d SWE-bench/SWE-bench_Verified`. The standalone modes of `polyglot.py` and `agent_run.py` (direct role-prompt probes, not used by `ab.py`) also need `role-*.md` and `pick20.json`, which are not included.
