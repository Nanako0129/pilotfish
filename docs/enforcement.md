# What enforces each rule

pilotfish is mostly prose. This table lists every rule unit in `templates/claude-md.orchestration.md`, plus the preamble that tells roles not to delegate and the indented boundary under the first rule, and says what holds each in place today: a mechanism in the shipped files, or text alone. It exists so that a rule is added or changed with its enforcement decided, and so that the rules worth moving into a mechanism are visible.

The "Enforced today by" column was filled by reading role frontmatter and the policy. One tool list was observed in a running client: `pilotfish:scout` from the installed Plugin v1.5.0 on Claude Code 2.1.325 reported `Read`, `Glob` and `Grep` as its only file tools and could not create a file it was asked to create (2026-11-23, one run). No other role's tool list was observed.

A row credits a tool list only when the rule itself states a limit on a role. A rule that merely relies on a restricted role is marked text.

Three kinds of enforcement exist in the shipped files:

- **Tool list.** A role's frontmatter `tools` or `disallowedTools`. `scout`, `Explore`, `plan-verifier` and `security-reviewer` have a read-only `tools` allowlist. The Plugin does not ship `Explore`; there the name resolves to the client's built-in agent, which pilotfish's frontmatter does not control. `verifier` disallows `Write`, `Edit`, `NotebookEdit`, `Agent` and `Workflow`, but keeps `Bash`, so its tool list removes the dedicated editing tools and does not stop a shell command from writing a file; "never edit" is text for that path. The three executors disallow `Agent` and `Workflow`.
- **Frontmatter routing.** A role's `model` and `effort`.
- **Text.** The rule is stated in the policy or a role prompt and nothing else checks it.

The Plugin's only hook, `SessionStart`, delivers the policy text. It enforces nothing.

A tool list binds only the role that carries it. A rule about what the main session does is text even when it mentions a restricted role.

## Table

"Key" is the first eight hex digits of the SHA-256 of the rule's line in `templates/claude-md.orchestration.md`. `tests/test_policy.py` fails when the keys here differ from the keys of the template's rule lines, so adding, removing or rewording a rule fails until its key is updated. [`agy-parity.md`](./agy-parity.md) uses the same keys and has to be reread with the same change. The test detects that a rule changed; it cannot check that the rest of the row was reread, which is the editor's job. "Line" is a reading aid and is not checked, and neither are the line numbers and counts in the prose below. The indented `explore_then_plan` boundary on line 12 has its own row.

The last column is a candidate, not a plan: none of these mechanisms is built or tested.

| Line | Key | Rule | Enforced today by | Candidate mechanism |
|---|---|---|---|---|
| 5 | `b0a0070e` | Preamble: named roles ignore the policy and never spawn subagents | Tool list: every role file pilotfish ships lacks `Agent` and `Workflow` (the Plugin's `Explore` is the client's own agent); text for ignoring the policy | None |
| 11 | `e703296f` | Choose interaction shape first | Text | None |
| 12 | `4fbdba88` | `explore_then_plan` is read-only until approval | Text | `PreToolUse` on `Write`/`Edit`/`NotebookEdit` in a turn the session marked read-only |
| 13 | `e280ac38` | Invoke `baton-dispatch` before the dispatch choice on large or risky work | Text | None obvious |
| 14 | `28bcfe16` | Risk triggers; the four Plan-review triggers | Text | None: classification is judgment |
| 15 | `b551db5a` | Small, local, stable work without a risk trigger stays direct | Text | None |
| 16 | `e6826de3` | Discovery gate: bounded read-only discovery roles | Tool list for the roles' read-only limit; text for the gate | None |
| 17 | `869dc7bd` | Plan gate: one Plan, intent restated, fresh `plan-verifier` for Plan-review units | Tool list keeps `plan-verifier` read-only; text for the rest | None |
| 18 | `0c16cb69` | Approval gate: no source edit or implementation brief before approval; approval asked through `AskUserQuestion` when available | Text | `PreToolUse` on write tools and on `Agent` with an executor role until an approval marker exists |
| 19 | `2db7affa` | Execution gate: approved contract, routing among the three executors | Frontmatter routing for each role's model; text for the choice | None |
| 20 | `70d96906` | Verification gate: fresh `verifier` on risk-triggered units | Tool list removes `verifier`'s editing tools (it keeps `Bash`, so no-write through the shell is text); text for calling it | `Stop` check that a risk-marked unit has a `verifier` result |
| 24 | `d8f10e1d` | State phase and apply the dispatch brake before every Agent call | Text | None |
| 25 | `62aeb4ac` | Bounded local search stays in the main session | Text | None |
| 26 | `b4ceb2d3` | Declare read scopes; an agent's scope is exclusive while it runs | Text | None |
| 27 | `65c5a6e3` | Collect all discovery before comparing | Text | None |
| 28 | `97330a36` | Same-shape mechanical repetition defaults to one `mech-executor` | Text | None |
| 29 | `02676d3a` | Collect the mechanical result before main edits | Text | None |
| 30 | `92b8718b` | Main does qualifying mechanical work only after naming a blocker | Text | None |
| 31 | `e2935861` | Delegate only when the benefit outweighs coordination cost | Text | None |
| 32 | `779611ae` | Judge each call; recurrence needs a stable one-shot brief | Text | None |
| 33 | `7e076cba` | A single unknown bug stays in the main session | Text | None |
| 34 | `7a67bc1c` | Large investigation may use read-only discovery; executor waits for a stable contract | Text | None |
| 35 | `7e0f39fc` | One-shot spec; after two failures escalate or take over | Text | None |
| 36 | `720b9edb` | Security work never uses general executors; `security-reviewer` first | Tool list keeps `security-reviewer` read-only; text for the routing | None |
| 37 | `7945fd86` | Risk units require `verifier`; Plan-review units also `plan-verifier` | Text | Same `Stop` check as line 20 |
| 38 | `3dec77b3` | No `model` on a named-role call; pass `effort` per task with reviewer floors | Frontmatter routing supplies the defaults; text for the call arguments | `PreToolUse` on `Agent`: reject `model` with a named role, reject `effort` under a reviewer's floor |
| 39 | `75846ef0` | `plan-verifier` and `verifier` contracts; never swap them | Tool list: `plan-verifier` has no `Bash`, so it cannot run an outcome check; nothing rejects a swapped call; text otherwise | None |
| 40 | `454a1508` | Envelope before slice for Plan-review units; shared blockers gate dependents | Text | None |
| 41 | `2aadb121` | After two automatic `REVISE` verdicts, disposition every blocker; one closing review | Text | None |
| 42 | `4a9666b1` | One fresh outcome pass at the smallest coherent boundary | Text | None |
| 43 | `7db9444d` | Verdicts are evidence; priority rules for dispositions | Text | None |
| 44 | `9529494e` | No "fixed" claim without contrary evidence or a recheck | Text | None |
| 45 | `7e773462` | Scout findings are inputs; what never gets delegated | Text | None |
| 49 | `49ccbdcd` | Recovery budget and verification pass limits | Text | None |
| 50 | `6252299a` | Offer `AUTO` or `ASK` before long autonomous work | Text | None |
| 51 | `02c7d03b` | `AUTO` permits only reversible approved-scope work | Text | `PreToolUse` on `Bash` matching commit, push, publish and delete commands while `AUTO` is active |
| 52 | `ca8cdc61` | User-decision stops use `AskUserQuestion` when available; headless runs exit paused | Text | None |
| 56 | `3fb44ea6` | Launch independent agents together in the background; integrate all | Text | None |
| 57 | `b68716fd` | Long processes belong to main; Bash-capable leaves never detach | Text (also repeated in each Bash-capable role prompt) | `PreToolUse` on `Bash` inside a role: reject `nohup`, `setsid`, a trailing `&` and `run_in_background` |

## Reading the table

Thirty of the thirty-seven rule units are text only, and so is the line-12 boundary. The other seven (lines 16, 17, 19, 20, 36, 38 and 39) have a mechanism behind part of them, and that part is always about what a role can do, never about what the main session does. The preamble's no-delegation rule is backed by a tool list in every role file pilotfish ships.

Line 38 is the cheapest candidate: the check is a comparison of call arguments, with no state to track. Lines 18, 20, 37 and 51 need the session to record a state (approved, risk-marked, `AUTO`) that a hook can read, which is new machinery. `docs/design.md` lists enforcement hooks under "Deliberately left out"; this table does not change that decision.
