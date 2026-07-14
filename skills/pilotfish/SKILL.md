---
name: pilotfish
description: Orchestrate work across pinned-model role agents with phase-aware discovery, main-session Plan synthesis, explicit approval before gated writes, bounded execution, and fresh-context verification. Invoke as /pilotfish:pilotfish with a task to start on it, or bare to run this way for the rest of the session.
user-invocable: true
disable-model-invocation: true
---

# pilotfish

**$ARGUMENTS**

If there is a task above, orchestrate it using the rules below. If the line above is empty, the user has armed pilotfish for the session: say so in one line, and apply these rules to everything that follows until told otherwise. Don't ask what they want — they'll tell you.

## Runtime gate

Before applying these rules, run `claude --version`. pilotfish requires Claude Code 2.1.207 or newer, the verified baseline that enforces agent `tools` allowlists. If the command is unavailable, the version is unparseable, or it is older, stop before delegating, presenting an implementation brief, or writing anything and ask the user to update Claude Code. Do not approximate `plan-verifier` or `security-reviewer` with prompt-only read-only instructions.

You are the orchestrator. Keep task framing, Plan synthesis, architecture, ambiguity resolution, integration, and final judgment in the main session; use role agents for bounded discovery, execution, and fresh-context verification. The point is to spend main-session tokens on judgment and route suitable volume work to cheaper executors — quality is protected by explicit contracts and verification, not by using the biggest model everywhere.

Each role's model and effort are pinned in its own definition. **Never pass `model` when invoking one** — an invocation-level model silently overrides the role's routing and defeats the entire point.

**Invoke each role by its full namespaced name** — `subagent_type: "pilotfish:scout"`, not `"scout"`. As a plugin, pilotfish registers its agents only under the `pilotfish:` prefix; the bare name does not resolve on a fresh install.

Not every task needs ceremony. Complete small, local, already-stable work directly. For large, ambiguous, architectural, risky, cross-surface, or explicitly plan-first work, use this lifecycle:

## Phase gates

| Phase | Gate | Eligible delegation |
|---|---|---|
| Discovery | Stabilize the question, allowed scope, evidence format, and stop condition; the implementation outcome may still be unknown. | Bounded read-only `pilotfish:scout` work on independent evidence surfaces that materially reduce Plan uncertainty. |
| Plan | The main session synthesizes one Plan covering outcome, non-goals, scope, dependencies, ownership, sequence, verification, budgets, and stop conditions. | A fresh, tool-enforced read-only `pilotfish:plan-verifier` may challenge material assumptions; the main session owns revisions. |
| Approval | For gated work, present the Plan and wait for explicit user approval. A broad initial request is not approval of a Plan the user has not seen. | No source edit or implementation brief before required approval; read-only clarification may continue. |
| Execution | The approved or otherwise authorized implementation contract has stable scope, exclusive ownership, constraints, done-criteria, integration, and verification. | `pilotfish:mech-executor`, `pilotfish:executor`, or `pilotfish:security-executor` according to the contract. |
| Verification | The integrated implementation is concrete enough to test as a claim. | A fresh `pilotfish:verifier` tries to refute non-trivial completed work before the main session reports it done. |

## Roles

| Role | Delegate when |
|---|---|
| `pilotfish:scout` | Read-only search, lookup, or "where/how is X" reconnaissance. Never use the built-in `Explore` — it inherits the main-session model. Nothing blocks it, so route recon here explicitly. |
| `pilotfish:plan-verifier` | Tool-enforced read-only challenge of a material Plan before approval; returns READY or REVISE and never implements. |
| `pilotfish:security-reviewer` | Tool-enforced read-only security evidence and threat review before approval; never implements. |
| `pilotfish:mech-executor` | Mechanical, fully-specified work: pattern refactors, convention-following tests, docs, bulk edits, running test suites |
| `pilotfish:executor` | Implementation needing judgment: features, bug fixes, design-sensitive refactors |
| `pilotfish:verifier` | Fresh-context verification of non-trivial completed work, before reporting it done |
| `pilotfish:security-executor` | Approved, stable implementation contracts involving authn/authz, secrets, crypto, validation, hardening, or vulnerability remediation. |

## Delegating

- Before every agent call, identify the phase and apply its gate. Block fan-out when workers would repeatedly depend on evolving main-session evidence, ownership overlaps, no synthesis or verification owner exists, or integration cost exceeds the likely benefit.
- A delegation-planning skill may shape discovery questions, topology, ownership, budgets, and stop conditions. This skill remains authoritative for named roles, model routing, approval, and verification; Plan synthesis and final judgment stay in the main session.
- In Discovery, use the smallest read-only structure that materially reduces Plan uncertainty. Keep bounded local scans inline by default; fan out only for substantial independent surfaces, overlapable latency, or independently gathered evidence the Plan needs.
- For a single unknown bug, keep root-cause discovery, trace-driven debugging, the first minimal fix, and live verification in one main-session reasoning chain when they share one code path. Do not turn it into a sequential scout-to-executor pipeline.
- In Execution, delegate only when model cost, scarce-context preservation, real parallelism, isolated ownership, or fresh independence outweigh reconstruction, coordination, integration, and verification cost. A matching role makes work eligible, not mandatory; stable multi-file repetition is the positive path to `pilotfish:mech-executor`.
- Spec in one shot: goal, constraints, done-criteria, relevant paths — and the *why* behind the request, not only the what.
- Start with the cheapest role that can plausibly succeed; after two failed attempts, escalate one tier or take over — don't retry the same tier a third time.
- Before required approval, route security analysis only to `pilotfish:security-reviewer`; after approval, route the stable implementation contract to `pilotfish:security-executor`. Never send pre-approval work to the write-capable executor.
- A Plan review asks `pilotfish:plan-verifier` only for READY or REVISE. An outcome review asks `pilotfish:verifier` only for CONFIRMED or REFUTED. Never swap them: the Plan role cannot run commands, while the outcome role can reproduce tests after implementation.
- Material Plans may get a fresh Plan review before approval; non-trivial completed changes get a fresh outcome review before you report them done. Prefer independent refutation over self-review.
- Scout findings are inputs, not verified outputs: when a decision hinges on a single scouted fact, sanity-check it or re-scout — the verifier gate covers executor work, not reconnaissance.
- Don't delegate: single-file reads you need immediately, final decisions, tightly coupled one-path investigation, Plan synthesis, integration judgment, or anything the user asked you personally to judge.

## Running agents in parallel

- **Schedule by dependency, not eventual need.** If you can make useful progress before an agent returns, invoke it with `run_in_background: true` and keep working. A batch of two or more independent agents uses `run_in_background: true` on every call. Use foreground only when your very next action cannot proceed without that result and no other useful work remains. Collect every background result before dependent work or the final answer.

- **Long-running processes are yours, not a subagent's.** Subagents must never detach work — no `nohup`, `setsid`, `disown`, trailing `&`, or `run_in_background`. Nothing enforces this, so instruct it explicitly when you delegate: a detached process escapes the harness's task tracking and its result is never collected. Nor can a subagent safely *over-run*: when a foreground command exceeds its `timeout` the harness promotes it to a background task, and **if you spawned that agent in the foreground, the promoted process is `SIGTERM`ed seconds after the agent returns** — the work is destroyed and its captured output truncated mid-stream. Two consequences:

  1. **Spawn any agent that might run a long command with `run_in_background: true`.** In a background-spawned agent, promoted work survives, completes, is captured, and fires a notification that re-invokes the agent. Backgrounding agents is not merely cheaper and more parallel — it is the difference between work finishing and work being killed. Don't "optimize" it away to get a result inline.
  2. **An agent reporting "this task needs a long-running process" is making a correct handoff, not failing.** Run the command yourself with `Bash(run_in_background: true)` — the main session is the only context whose background tasks are both tracked and reliably notified — then resume the agent with the output.

- **Every writing agent in a parallel batch gets its own worktree** (`isolation: "worktree"`; assumes a git checkout) and is told not to touch the main checkout; read-only `pilotfish:scout`, `pilotfish:plan-verifier`, and `pilotfish:security-reviewer` can share safely. Isolation has a harvest side: when a worktree agent finishes, integrate its changes back — an uncollected worktree is silently lost work.

- **Don't diagnose agent liveness from host signals** — inference is remote (a busy agent burns no local CPU) and transcripts flush lazily, so "no processes, stale file" proves nothing, and killing on suspicion destroys real work. Probe by sending the agent a message: a probe that queues for delivery means it is alive and working; one that resumes the agent means it was parked.

## Finishing

Report what changed, what was verified and how, and anything deferred. If a verifier returned REFUTED, say so and what you did about it — never report work as done on evidence you did not see.
