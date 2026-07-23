# Execution and Verification

Use this reference while delegated work is running and when integrating results.

## Monitor without over-dispatching

While workers run:

1. Prepare the integration checklist and final verification commands.
2. Incorporate returned conclusions into the shared context pack.
3. Check partial results for scope violations, contradictions, and changing assumptions.
4. Perform genuinely independent work that does not overlap worker ownership.
5. Monitor failure rate, elapsed time, resource use, and integration backlog.

Do not add workers merely because concurrency is available. Do not edit files owned by active workers. Do not treat the execution mechanism as a black box.

## Respond to failure signals

| Signal | Response |
|---|---|
| Repeated same-cause failure | Stop, change the brief, boundary, schema, or primitive |
| Scope or ownership violation | Pause affected work and reconcile changed artifacts |
| Conflicting conclusions | Recheck primary evidence and let the main agent adjudicate |
| Integration backlog growing | Stop fan-out and synthesize current results |
| Worker stuck in expensive verification | Recover partial work and centralize verification |
| Delegation capability unavailable | Fall back to direct execution |
| Rate-limit or retry cascade | Reduce concurrency and use bounded sequential batches |

## Verification economics

Match verification to the cheapest trustworthy evidence:

- Run fast, focused checks close to the change when they do not contend for shared resources.
- Run repository-wide builds, type checks, integration tests, and shared-environment checks once after integration.
- Centralize live or visual verification unless a worker needs it to establish root cause.
- Give exact human test steps when automation cannot provide reliable evidence.

Never claim that a delegated result is verified solely because a worker said it succeeded. Review changed artifacts and sample important evidence.

## Synthesize instead of concatenating

The main agent must:

1. confirm coverage and list failed, partial, or skipped work;
2. compare changed artifacts with ownership;
3. deduplicate repeated findings;
4. identify contradictions and adjudicate them with evidence;
5. preserve high-quality minority findings rather than using majority vote;
6. run final integration gates;
7. classify conclusions as verified, consistent-but-not-rechecked, reasoned, or human-test-needed.

Use this compact synthesis format:

```markdown
## Inputs and coverage
## Integrated changes or findings
## Conflicts and adjudication
## Remaining minority concerns
## Verification evidence
## Gaps and human checks
```

## Common failure modes

- Over-parallelizing before requirements stabilize.
- Rebuilding the same context independently in every worker.
- Dividing work by role names while artifacts still overlap.
- Letting multiple builders modify shared contracts or lockfiles.
- Running expensive repository gates in every worker.
- Scaling an untested prompt or output schema to many items.
- Retrying unchanged failures until resources are exhausted.
- Treating an isolated workspace as current without checking its base.
- Reporting only successful outputs and silently dropping failures.
- Returning several reports without synthesis or final verification.
