# Dispatch Planning

Use this reference to decide whether to delegate, which primitive to use, and how to divide ownership.

## Decision sequence

Evaluate blockers before benefits:

1. Confirm that the task and acceptance conditions are stable enough to brief once.
2. Estimate the direct-work alternative, including main-context cost.
3. Group raw request items by shared context, artifacts, dependencies, and verification surface; never assume one request bullet equals one workstream.
4. Identify workstreams by source, artifact, or responsibility rather than by vague role names.
5. Estimate shared-context overlap. If several workers need the same conclusions, create one context pack first.
6. Map expected reads, writes, and possible secondary writes.
7. Decide where verification and synthesis occur.

A large task is not automatically a parallel task. Delegate only when boundaries are clear and outputs can be integrated cheaply.

## Primitive selection

### Main agent

Use for small work, tightly coupled reasoning, final decisions, and synthesis. Avoid delegation when briefing and reviewing would cost as much as execution.

### One worker

Use for bounded scouting, an isolated research source, a side quest, or an independent validation pass. Default to read-only unless writing is essential.

### Parallel workers

Use for a small number of low-overlap workstreams. Partition by mutually exclusive source or ownership boundary. If two workers need the same large source set, build a context pack or merge the tasks.

### Batch or workflow

Use for repeated homogeneous items with deterministic mapping, batching, retry, and stop logic. Start with a small sample before scaling. Prefer bounded batches over unbounded fan-out.

### Collaborative team

Use only when workers must exchange arguments, challenge hypotheses, or coordinate across owned surfaces. If independent reports plus main-agent synthesis are enough, use ordinary workers.

### Isolated workspace or branch

Use for competing solutions, independent deliverables, or overlapping changes that need isolation. Verify that the isolated base contains all required state before starting.

### Shared-workspace builders

Use when workers need the same uncommitted state and can write disjoint paths. Require exclusive ownership, forbid dependency installation and shared lockfile changes, and run final gates centrally.

## Ownership map

For every write task, record:

| Workstream | Must read | May write | Must not write | Possible secondary writes | Integration owner |
|---|---|---|---|---|---|

Treat shared schemas, registries, indexes, generated outputs, configuration, and lockfiles as high-risk. Converge them before parallel work or assign them to one integration owner.

Do not infer independence from task titles. Judge actual artifacts and dependencies.

## Scale conservatively

Choose worker count from independence, rate limits, verification cost, and integration capacity—not item count alone.

- Unclear direction: one scout.
- A few independent perspectives: a few parallel workers.
- Many homogeneous items: sampled trial, then bounded batches.
- Large multi-phase work: separate discovery, implementation, and verification phases with review points between them.

Reduce parallelism when outputs require judgment-heavy merging, shared state changes rapidly, or failures begin to cascade.

## Dispatch plan format

For non-trivial delegation, state:

```markdown
## Outcome and success conditions
## Why delegation is better than direct work
## Primitive and scale
## Shared context strategy
## Ownership and sequencing
## Verification and synthesis owner
## Budgets and stop conditions
## Direct-work fallback
```
