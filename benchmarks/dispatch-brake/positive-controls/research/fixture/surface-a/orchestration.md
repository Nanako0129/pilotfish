# remora session orchestration

Main-session policy. If you are running as a subagent role (`Explore`, `scout`, `mech-executor`, `executor`, `verifier`, or `security-executor`), ignore this section and complete the task yourself without further delegation.

Use the supplied role agents for execution while keeping planning, architecture, ambiguity resolution, integration, and final review in the main session. Choose `Explore` or `scout` for read-only reconnaissance, `mech-executor` for fully specified mechanical work, `executor` for implementation requiring local judgment, `verifier` for fresh-context verification, and `security-executor` for security-sensitive work.

Before invoking an agent, apply a dispatch brake. Delegate only when the outcome and observable success conditions are stable, direct main-session work would not be faster or more reliable, the worker can progress without repeatedly reconstructing the main session's evidence or waiting on it, write ownership is exclusive, and the main session retains a cheap integration and verification path. If any condition is unclear, continue directly until the contract stabilizes. Matching a role makes work eligible for delegation; it does not make delegation mandatory.

Keep root-cause discovery, trace-driven debugging, tightly coupled state propagation, unresolved architecture, and small fixes in the main session when diagnosis and implementation repeatedly depend on the same evidence. Delegate an executor only after the root cause, scope, owned files, constraints, and done criteria can be given once without asking the worker to rediscover the investigation. Use a scout only for a bounded side question whose answer does not transfer ownership of the main reasoning chain.

Model routing is owned by agent definitions. When invoking any existing named role, including every supplied role above, omit the `model` argument entirely; an invocation-level model overrides the role definition and defeats the configured routing map. Specify `model` only for a truly ad-hoc agent that has no named role definition.

Schedule eligible delegation by data dependency, not by whether the result will eventually be needed:

- If the main session can make useful progress before an agent returns, invoke that agent with `run_in_background: true` and continue working.
- When dispatching two or more independent agents, launch them as one parallel batch with `run_in_background: true` on every call. Give each writing agent an isolated worktree and integrate its changes after completion; read-only agents may share the checkout.
- Use foreground execution only when the very next main-session action cannot proceed without that agent's result, there is no other useful independent work to do, and delegation still beats direct execution. Do not launch an agent merely to wait for it when the main session already has enough context to finish the work.
- A background launch is not a completed result. Track it, collect its output before any dependent action or final answer, and resume the agent when follow-up is required. Do not poll while other useful work remains.
