# Claude Code Ultracode Workflow Adapter

Use this adapter only when the user has enabled or requested Ultracode, a Claude Code Workflow tool, or an equivalent saved workflow capability. The core dispatch brake and ownership rules still apply; opt-in permits the primitive, not indiscriminate fan-out.

## Discover current capabilities first

Before designing executable workflow syntax:

1. Inspect the currently available Workflow tool schema, help, or installed documentation.
2. Confirm supported control-flow primitives, isolation modes, budgets, resume behavior, output formats, and concurrency controls.
3. Treat any remembered limits or APIs as unverified until confirmed in the active environment.
4. If the Workflow capability is missing or unhealthy, use bounded workers or direct execution instead.

Do not encode version-specific limits in the shared dispatch plan.

## Use Workflow for the right task shape

Prefer Workflow when the task needs repeatable deterministic orchestration, such as:

- mapping the same operation across many independent items;
- bounded batches with controlled concurrency;
- staged pipelines such as discover, validate, synthesize;
- repeated migrations or audits with stable prompts and output contracts;
- resumable work where completed prefixes or artifacts can be reused.

Prefer ordinary workers when there are only a few heterogeneous tasks or the main agent must make a judgment between every step. Avoid a single long workflow when human approval is required mid-run; split it into phases with an approval boundary.

## Design before execution

Write down:

- input items and their source of truth;
- phase boundaries and dependencies;
- small-slice trial size;
- maximum active work and batching policy;
- output contract and tolerance for malformed results;
- time, token, retry, and no-progress stops;
- treatment of failed, partial, and skipped items;
- synthesis owner and centralized verification plan.

Test a small representative slice before scaling. If structured output repeatedly fails, simplify the schema or return text for later parsing instead of letting validation retries multiply.

## Avoid workflow-specific failure patterns

- Do not equate item count with concurrent agent count.
- Do not use full parallel barriers when streaming or bounded batches suffice.
- Do not let workers repeat expensive repository or live verification.
- Do not silently filter null, partial, or failed results.
- Do not resume after changing assumptions without checking which cached results remain valid.
- Do not store a one-off workflow as reusable until its inputs, outputs, and stop behavior are stable.

## Monitor and recover

Monitor the signals exposed by the active tool, especially completed items, failures, retries, resource use, elapsed time, and integration backlog. Stop and redesign when failures share a cause or synthesis cannot keep up.

On recovery, preserve trustworthy completed artifacts, revise the smallest invalid phase, and resume only when the active tool documents that behavior. Otherwise restart a bounded phase or fall back to direct execution.
