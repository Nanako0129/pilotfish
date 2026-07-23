# Context Packs and Worker Briefs

Use this reference when multiple workers share background or when issuing delegated tasks.

## Shared context pack

Create a pack only when at least two workers need the same conclusions or when the main agent has already completed expensive exploration that should not be repeated.

Keep it factual and compact:

```markdown
# Shared Context Pack — <task>

## Outcome and non-goals
## Success conditions
## Current state and constraints
## Relevant architecture and file map
## Verified conclusions from sources already read
## Rejected directions and reasons
## Shared contracts and invariants
## Ownership boundaries
## Minimum reading set per workstream
## Risks, unknowns, and confidence
## Verification and synthesis plan
```

Mark conclusions as verified or inferred. Update the pack after each phase so later workers do not receive stale state. Do not turn it into a tutorial or duplicate entire source files.

## Worker brief

Assume a worker has no access to the main conversation unless the platform explicitly guarantees otherwise. Give all task-critical context in one brief.

Finalize a brief only after shared decisions, upstream dependencies, ownership, verification, and stop conditions are stable. Treat earlier drafts as non-dispatchable. If any of those assumptions change, revise every affected brief that has not yet been dispatched.

```markdown
# Brief — <workstream>

## Objective and why it matters
## Shared context path or embedded background
## Exact in-scope and out-of-scope work
## Minimum files or sources to read
## Files or artifacts allowed to change
## Forbidden writes and high-risk shared artifacts
## Allowed commands and verification
## Required output format
## Time, token, retry, and scope stop conditions
## What to do when assumptions fail
```

Include known paths, patterns, identifiers, and prior conclusions. Do not ask workers to rediscover information already available.

For independent verification, provide the artifact and acceptance criteria without the implementer's reasoning, suspected bug, or preferred conclusion.

## Default execution boundaries

Unless the task requires otherwise:

- allow only local, scoped checks;
- reserve repository-wide gates and live verification for integration;
- forbid dependency installation and lockfile changes;
- require workers to stop before touching unowned artifacts;
- require changed-file and deviation reporting.

## Worker result format

```markdown
## Summary
## Changed artifacts
## Verified evidence
## Unverified but reasoned conclusions
## Risks and assumptions
## Deviations from brief
## Needs main-agent decision
## Large artifact paths
```

Prefer artifact paths and concise summaries over dumping large outputs into the main context.
