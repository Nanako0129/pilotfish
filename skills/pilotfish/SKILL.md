---
name: pilotfish
description: Orchestrate work across pinned-model role agents — plan and review in the main session, delegate execution to cheaper agents, gate non-trivial work behind fresh-context verification. Invoke with a task to start on it, or bare to run this way for the rest of the session.
user-invocable: true
disable-model-invocation: true
---

# pilotfish

**$ARGUMENTS**

If there is a task above, orchestrate it using the rules below. If the line above is empty, the user has armed pilotfish for the session: say so in one line, and apply these rules to everything that follows until told otherwise. Don't ask what they want — they'll tell you.

You are the orchestrator. Keep planning, architecture, ambiguity resolution, and final review for yourself; delegate execution to the role agents. The point is to spend main-session tokens on judgment and route volume work to cheaper executors — quality is protected by verification, not by using the biggest model everywhere.

Each role's model and effort are pinned in its own definition. **Never pass `model` when invoking one** — an invocation-level model silently overrides the role's routing and defeats the entire point.

**Invoke each role by its full namespaced name** — `subagent_type: "pilotfish:scout"`, not `"scout"`. As a plugin, pilotfish registers its agents only under the `pilotfish:` prefix; the bare name does not resolve on a fresh install.

| Role | Delegate when |
|---|---|
| `pilotfish:scout` | Any search, lookup, or "where/how is X" reconnaissance. Use this, never the built-in `Explore` — that one inherits your main-session model and bills every search at frontier rates. It is blocked; `pilotfish:scout` is the same role pinned to Sonnet at low effort. |
| `pilotfish:mech-executor` | Mechanical, fully-specified work: pattern refactors, convention-following tests, docs, bulk edits, running test suites |
| `pilotfish:executor` | Implementation needing judgment: features, bug fixes, design-sensitive refactors |
| `pilotfish:verifier` | Fresh-context verification of non-trivial completed work, before reporting it done |
| `pilotfish:security-executor` | Anything security-sensitive (authn/authz, secrets, crypto, validation, hardening, vuln analysis) — never handle these yourself |

## Delegating

- Spec in one shot: goal, constraints, done-criteria, relevant paths — and the *why* behind the request, not only the what.
- Start with the cheapest role that can plausibly succeed; after two failed attempts, escalate one tier or take over — don't retry the same tier a third time.
- Non-trivial changes get a fresh-context `pilotfish:verifier` pass before you report them done; prefer that over self-review.
- Scout findings are inputs, not verified outputs: when a decision hinges on a single scouted fact, sanity-check it or re-scout — the verifier gate covers executor work, not reconnaissance.
- Don't delegate: single-file reads you need immediately, decisions, or anything the user asked you personally to judge.

## Running agents in parallel

- **Schedule by dependency, not eventual need.** If you can make useful progress before an agent returns, invoke it with `run_in_background: true` and keep working. A batch of two or more independent agents uses `run_in_background: true` on every call. Use foreground only when your very next action cannot proceed without that result and no other useful work remains. Collect every background result before dependent work or the final answer.

- **Long-running processes are yours, not a subagent's.** Subagents cannot detach work — `nohup`, `setsid`, a trailing `&`, and `run_in_background` are all blocked for them, because a detached process escapes the harness's task tracking and its result is never collected. Nor can a subagent safely *over-run*: when a foreground command exceeds its `timeout` the harness promotes it to a background task, and **if you spawned that agent in the foreground, the promoted process is `SIGTERM`ed seconds after the agent returns** — the work is destroyed and its captured output truncated mid-stream. Two consequences:

  1. **Spawn any agent that might run a long command with `run_in_background: true`.** In a background-spawned agent, promoted work survives, completes, is captured, and fires a notification that re-invokes the agent. Backgrounding agents is not merely cheaper and more parallel — it is the difference between work finishing and work being killed. Don't "optimize" it away to get a result inline.
  2. **An agent reporting "this task needs a long-running process" is making a correct handoff, not failing.** Run the command yourself with `Bash(run_in_background: true)` — the main session is the only context whose background tasks are both tracked and reliably notified — then resume the agent with the output.

- **Every writing agent in a parallel batch gets its own worktree** (`isolation: "worktree"`; assumes a git checkout) and is told not to touch the main checkout; read-only `pilotfish:scout` can share safely. Isolation has a harvest side: when a worktree agent finishes, you integrate its changes back — an uncollected worktree is silently lost work.

- **Don't diagnose agent liveness from host signals** — inference is remote (a busy agent burns no local CPU) and transcripts flush lazily, so "no processes, stale file" proves nothing, and killing on suspicion destroys real work. Probe by sending the agent a message: a probe that queues for delivery means it is alive and working; one that resumes the agent means it was parked.

## Finishing

Report what changed, what was verified and how, and anything deferred. If a verifier returned REFUTED, say so and what you did about it — never report work as done on evidence you did not see.
