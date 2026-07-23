# Dispatch Examples

Use these examples only when the task shape remains ambiguous after reading the core skill.

## Small known fix

A formatting helper has one known bug and a focused test. The main agent reads the implementation, changes it, and runs the focused test. Delegating discovery, implementation, and verification would cost more than the work.

## Independent research perspectives

An architecture decision needs official documentation, repository usage analysis, and external operational experience. Assign three read-only workers because the source sets are distinct. Require source-backed reports, then let the main agent reconcile conclusions.

## Shared-state multi-surface change

A project has uncommitted structural changes and needs updates to two disjoint application surfaces plus documentation. Converge shared types first, assign exclusive paths to each builder, forbid shared configuration and repository-wide gates, then integrate and verify centrally.

## Bad batch fan-out

Dozens of homogeneous items are sent simultaneously using an untested strict output format. Validation retries and rate limits cascade while integration falls behind. Correct by testing a small sample, loosening the output contract when necessary, processing bounded batches, and stopping when repeated failures exceed the declared threshold.

## Competing implementation strategies

Two approaches modify overlapping files and should be compared independently. Use isolated workspaces based on the same verified state, apply the same acceptance criteria, and let the main agent compare evidence. Do not merge both implementations mechanically.
