<!-- pilotfish:begin -->
## Orchestration

This section supersedes more generic delegation guidance when deciding whether work is eligible for delegation.

Main-session policy. Subagent roles complete their assigned task without further delegation.

Keep planning, architecture, ambiguity resolution, integration, and final review in the main session. Before invoking any agent, apply the dispatch brake: the outcome and observable success conditions must be stable; direct main-session work must not be faster or more reliable; the worker must progress without repeatedly reconstructing the main session's evidence or waiting on it; every write must have exclusive ownership; and integration plus verification must remain cheap. If any condition is unclear, continue directly until the contract stabilizes.

Do not delegate root-cause discovery, trace-driven debugging, tightly coupled state propagation, unresolved shared contracts, or a small fix whose diagnosis and implementation use the same evidence. A task being a search, bug fix, or implementation is not by itself a reason to delegate. Delegate an executor only after root cause, scope, owned files, constraints, and done criteria can be stated once without rediscovery. Use a scout only for a bounded side question independent of the main reasoning chain.

For eligible work, use `scout` or `Explore` for bounded read-only reconnaissance, `mech-executor` for fully specified mechanical changes, `executor` for stable implementation work, `verifier` for fresh-context verification of completed non-trivial changes, and `security-executor` for security-sensitive work. Named role definitions are the only model source; omit `model` when invoking them.

Schedule eligible agents by dependency. Use `run_in_background: true` only when useful independent main-session work remains. If the main session would launch an agent and wait idle, perform the work directly. Collect all results before dependent actions or the final answer.
<!-- pilotfish:end -->
