# What enforces each rule

pilotfish is mostly prose. This table lists every rule unit in `templates/claude-md.orchestration.md` and says what holds it in place today: a mechanism the model cannot talk its way around, or text alone. It exists so that a new rule is added with its enforcement decided, and so that the rules worth moving into a mechanism are visible.

Three kinds of enforcement exist in the shipped files:

- **Tool list.** A role's frontmatter `tools` or `disallowedTools`. `scout`, `Explore`, `plan-verifier` and `security-reviewer` have a read-only `tools` allowlist. `verifier` disallows `Write`, `Edit`, `NotebookEdit`, `Agent` and `Workflow`. The three executors disallow `Agent` and `Workflow`.
- **Frontmatter routing.** A role's `model` and `effort`.
- **Text.** The rule is stated in the policy or a role prompt and nothing else checks it.

The Plugin's only hook, `SessionStart`, delivers the policy text. It enforces nothing.

A tool list binds only the role that carries it. A rule about what the main session does is text even when it mentions a restricted role.

## Table

"Line" is the line of the rule in `templates/claude-md.orchestration.md`. `tests/test_policy.py` fails when the set of lines here differs from the rule lines in the template, so a rule cannot be added, removed or moved without editing this table.

The last column is a candidate, not a plan: none of these mechanisms is built or tested.

| Line | Rule | Enforced today by | Candidate mechanism |
|---|---|---|---|
| 11 | Choose interaction shape first; the first `explore_then_plan` turn is read-only | Text | `PreToolUse` on `Write`/`Edit`/`NotebookEdit` in a turn the session marked read-only |
| 13 | Invoke `baton-dispatch` before the dispatch choice on large or risky work | Text | None obvious |
| 14 | Risk triggers; the four Plan-review triggers | Text | None: classification is judgment |
| 15 | Small, local, stable work without a risk trigger stays direct | Text | None |
| 16 | Discovery gate: bounded read-only discovery roles | Tool list for the roles' read-only limit; text for the gate | None |
| 17 | Plan gate: one Plan, intent restated, fresh `plan-verifier` for Plan-review units | Tool list keeps `plan-verifier` read-only; text for the rest | None |
| 18 | Approval gate: no source edit or implementation brief before approval | Text | `PreToolUse` on write tools and on `Agent` with an executor role until an approval marker exists |
| 19 | Execution gate: approved contract, routing among the three executors | Frontmatter routing for each role's model; text for the choice | None |
| 20 | Verification gate: fresh `verifier` on risk-triggered units | Tool list keeps `verifier` from editing; text for calling it | `Stop` check that a risk-marked unit has a `verifier` result |
| 24 | State phase and apply the dispatch brake before every Agent call | Text | None |
| 25 | Bounded local search stays in the main session | Text | None |
| 26 | Declare read scopes; an agent's scope is exclusive while it runs | Text | None |
| 27 | Collect all discovery before comparing | Text | None |
| 28 | Same-shape mechanical repetition defaults to one `mech-executor` | Text | None |
| 29 | Collect the mechanical result before main edits | Text | None |
| 30 | Main does qualifying mechanical work only after naming a blocker | Text | None |
| 31 | Delegate only when the benefit outweighs coordination cost | Text | None |
| 32 | Judge each call; recurrence needs a stable one-shot brief | Text | None |
| 33 | A single unknown bug stays in the main session | Text | None |
| 34 | Large investigation may use read-only discovery; executor waits for a stable contract | Text | None |
| 35 | One-shot spec; after two failures escalate or take over | Text | None |
| 36 | Security work never uses general executors; `security-reviewer` first | Tool list keeps `security-reviewer` read-only; text for the routing | None |
| 37 | Risk units require `verifier`; Plan-review units also `plan-verifier` | Text | Same `Stop` check as line 20 |
| 38 | No `model` on a named-role call; pass `effort` per task with reviewer floors | Frontmatter routing supplies the defaults; text for the call arguments | `PreToolUse` on `Agent`: reject `model` with a named role, reject `effort` under a reviewer's floor |
| 39 | `plan-verifier` and `verifier` contracts; never swap them | Tool lists make the swap fail in one direction (`plan-verifier` cannot run commands); text otherwise | None |
| 40 | Envelope before slice for Plan-review units; shared blockers gate dependents | Text | None |
| 41 | After two automatic `REVISE` verdicts, disposition every blocker; one closing review | Text | None |
| 42 | One fresh outcome pass at the smallest coherent boundary | Text | None |
| 43 | Verdicts are evidence; priority rules for dispositions | Text | None |
| 44 | No "fixed" claim without contrary evidence or a recheck | Text | None |
| 45 | Scout findings are inputs; what never gets delegated | Tool list: leaf roles cannot delegate further; text for the rest | None |
| 49 | Recovery budget and verification pass limits | Text | None |
| 50 | Offer `AUTO` or `ASK` before long autonomous work | Text | None |
| 51 | `AUTO` permits only reversible approved-scope work | Text | `PreToolUse` on `Bash` matching commit, push, publish and delete commands while `AUTO` is active |
| 52 | `ASK` uses `AskUserQuestion`; headless runs exit paused | Text | None |
| 56 | Launch independent agents together in the background; integrate all | Text | None |
| 57 | Long processes belong to main; Bash-capable leaves never detach | Text in the policy and in each Bash-capable role prompt | `PreToolUse` on `Bash` inside a role: reject `nohup`, `setsid`, a trailing `&` and `run_in_background` |

## Reading the table

Twenty-eight of the thirty-seven rules are text only. The other nine (lines 16, 17, 19, 20, 36, 38, 39, 45 and 57) have a mechanism or a second statement behind part of them, and that part is always about what a role can do, never about what the main session does.

Line 38 is the cheapest candidate: the check is a comparison of call arguments, with no state to track. Lines 18, 20, 37 and 51 need the session to record a state (approved, risk-marked, `AUTO`) that a hook can read, which is new machinery. `docs/design.md` lists enforcement hooks under "Deliberately left out"; this table does not change that decision.
