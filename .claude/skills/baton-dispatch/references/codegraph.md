# CodeGraph Evidence Adapter

Use CodeGraph when it is available and the task needs repository context, dependency impact, caller relationships, or focused test selection. Treat it as evidence for planning and verification—not as the owner of dispatch decisions.

## Check readiness

1. Confirm that `codegraph` or its MCP capability exists.
2. Inspect current help or tool schemas instead of relying on remembered flags.
3. Check index status for the target repository.
4. If the index is missing or stale, decide whether initializing or syncing it is authorized and worthwhile.
5. If CodeGraph is unavailable, fall back to targeted repository search and mark impact conclusions as less complete.

Do not initialize, sync, or modify repository metadata merely because CodeGraph exists; keep that action within user scope and repository policy.

## Use it at three decision points

### 1. Build task context

Use task-context or symbol-query capabilities to identify relevant files and relationships before writing worker briefs. Keep the returned context bounded and verify critical paths against source files.

### 2. Improve impact and ownership maps

Use caller, callee, or impact analysis for high-risk shared symbols, contracts, registries, and entrypoints. Add discovered secondary files to the ownership plan before fan-out.

CodeGraph improves the candidate impact set; it does not prove that parallel writes are safe. The main agent must still assign exclusive artifact ownership.

### 3. Focus integration verification

After changes are integrated, use affected-test analysis from the actual changed-file set to select focused tests. Add mandatory repository gates required by project policy; do not treat affected-test output as permission to skip them.

## Typical CLI capability mapping

When supported by the installed version, the relevant commands are commonly:

```text
codegraph status <repo>
codegraph context <task> --path <repo>
codegraph callers <symbol>
codegraph impact <symbol> --path <repo>
codegraph affected <changed-files...> --path <repo>
```

Confirm exact syntax with the current command help. Prefer structured output when another tool will consume the result; prefer concise human-readable output for direct review.

## Evidence discipline

- Record the repository and index state used for each conclusion.
- Separate graph-derived candidates from source-verified facts.
- Recheck critical symbols in source before changing ownership or architecture.
- Feed actual changed files—not only planned files—into affected-test selection.
- Report empty or incomplete graph results as coverage gaps rather than proof of no impact.
