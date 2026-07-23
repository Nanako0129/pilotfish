---
name: baton-dispatch
description: Design efficient multi-agent execution plans by choosing between direct work, one worker, bounded parallel workers, repeatable workflows, collaborative teams, isolated workspaces, or shared-workspace builders. Use when the user requests delegation, parallel work, Claude Code Ultracode workflows, or CodeGraph-assisted planning, or when a large audit, migration, research task, or multi-surface change has genuinely separable workstreams. Do not use for small edits, ordinary questions, or work that one agent can complete more cheaply than coordinating others.
---

# Baton

> Dispatch less. Deliver more.

Choose the smallest execution structure that improves delivery quality or elapsed time after accounting for context reconstruction, coordination, conflicts, verification, and synthesis.

Treat delegation as an implementation detail. Obey the active platform's permissions, concurrency limits, and user instructions. Never assume a particular agent product, workflow engine, model, or version is available.

## Start with the dispatch brake

Before delegating, answer these questions:

1. **Outcome**: Can you state the deliverable and observable success conditions?
2. **Direct-work alternative**: Would one agent finish faster or more reliably?
3. **Independence**: Can each workstream progress without repeatedly reading the same sources or waiting on another worker?
4. **Ownership**: For write tasks, can every file or artifact have one clear owner?
5. **Closure**: Who will integrate results, resolve contradictions, and run final verification?

If any answer is unclear, do not fan out. Clarify the task, perform a small scout, converge the shared contract, or design ownership first.

## Choose an execution primitive

| Task shape | Prefer |
|---|---|
| Small task, final judgment, or synthesis | Main agent |
| Unknown location, bounded research, or fresh-context review | One read-only worker |
| Two to four independent perspectives or disjoint surfaces | Bounded parallel workers |
| Repeated homogeneous items with deterministic control flow | Batch or workflow |
| Workers must challenge or coordinate with each other | Collaborative team, if available |
| Competing implementations or overlapping writes requiring isolation | Separate workspace or branch |
| Uncommitted shared state with disjoint file ownership | Shared-workspace parallel builders |

Use capability-neutral language in plans. Map these primitives to the tools currently available only after choosing the task shape.

Read [references/dispatch-planning.md](references/dispatch-planning.md) when choosing the primitive, worker count, sequencing, or ownership model.

## Run the standard workflow

1. Define the outcome, non-goals, constraints, and evidence required.
2. Group raw request items by shared context, artifacts, dependencies, and verification surface. Do not equate one request bullet with one worker.
3. Select the minimum useful execution primitive.
4. Converge shared contracts, schemas, registries, and architecture decisions before fan-out.
5. Create a compact shared context pack only when multiple workers need the same conclusions.
6. Assign exclusive ownership, then finalize self-contained worker briefs only after shared decisions, dependencies, verification, and stop conditions are stable. Revise any undispatched brief when those assumptions change.
7. Monitor progress, scope, failures, and integration capacity without adding workers merely because capacity is idle.
8. Synthesize results, resolve conflicts, run centralized gates, and report evidence honestly.

Read only the reference needed for the current decision:

- Shared context and worker briefs: [references/context-and-briefs.md](references/context-and-briefs.md)
- Execution, monitoring, verification, and synthesis: [references/execution-and-verification.md](references/execution-and-verification.md)
- Compact positive and negative patterns: [references/examples.md](references/examples.md)

Load optional capability adapters only when relevant:

- Claude Code with Ultracode or a Workflow tool: [references/claude-code-ultracode.md](references/claude-code-ultracode.md)
- Repositories with CodeGraph available: [references/codegraph.md](references/codegraph.md)

## Preserve these invariants

- Keep final judgment and synthesis with the main agent.
- Do not parallelize unresolved shared contracts or overlapping writes.
- Give every worker the minimum sufficient context, exact scope, output shape, and stop condition.
- Centralize repository-wide or expensive verification unless isolated verification is required for diagnosis.
- Separate verified facts, reasoned conclusions, and human-only checks.
- Treat failed, partial, and skipped work as coverage gaps; never silently drop them.
- Stop increasing parallelism when integration cannot keep up with production.
- Fall back to direct execution when delegation infrastructure is unavailable or repeatedly fails.

## Apply global stop conditions

Every loop, batch, or delegated phase must stop when any of these occurs:

- the objective is satisfied;
- the declared time, token, retry, or worker budget is reached;
- repeated rounds produce no material progress;
- failures repeat with the same cause;
- ownership boundaries become invalid;
- integration or verification cost exceeds the remaining benefit.

After repeated same-cause failure, change the prompt, task boundary, primitive, or verification strategy. Do not repeat an unchanged attempt indefinitely.

## Keep the skill current

Record reusable lessons as capability-neutral decision rules. Keep optional adapters focused on stable responsibilities and capability discovery. Put temporary limits, version-specific syntax, and environment-specific behavior in project-local documentation rather than this skill. Retain examples only when they teach a distinct decision pattern.
