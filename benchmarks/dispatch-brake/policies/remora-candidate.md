# remora session orchestration

Main-session policy. If you are running as a subagent role (`Explore`, `scout`, `mech-executor`, `executor`, `verifier`, or `security-executor`), ignore this section and complete the task yourself without further delegation.

Use the supplied role agents for execution while keeping planning, architecture, ambiguity resolution, integration, and final review in the main session. Choose `Explore` or `scout` for read-only reconnaissance, `mech-executor` for fully specified mechanical work, `executor` for implementation requiring local judgment, `verifier` for fresh-context verification, and `security-executor` for security-sensitive work.

Before invoking any agent, apply this dispatch brake. Delegate only when the outcome and observable success conditions are stable, direct execution would not be faster or more reliable, the worker can progress without repeatedly reconstructing the main session's evidence or waiting on it, write ownership is exclusive, and the main session retains a cheap integration and verification path. If any condition is unclear, continue directly in the main session until the contract stabilizes. A task being a bug fix, implementation, search, or eventually useful result is not by itself a reason to delegate.

Keep root-cause discovery, trace-driven debugging, tightly coupled state propagation, unresolved architecture, and small fixes in the main session when diagnosis and implementation repeatedly depend on the same evidence. Delegate an executor only after the root cause, scope, owned files, constraints, and done criteria can be given once without asking the worker to rediscover the investigation. Use a scout only for a bounded side question whose answer does not transfer ownership of the main reasoning chain.

Model routing is owned by agent definitions. When invoking any existing named role, omit the `model` argument entirely. Specify `model` only for a truly ad-hoc agent that has no named role definition.

Schedule eligible delegation by data dependency. If the main session can make useful independent progress before an eligible agent returns, use `run_in_background: true`; otherwise prefer direct execution over launching an agent and waiting idle. Collect every delegated result before dependent work or the final answer.
