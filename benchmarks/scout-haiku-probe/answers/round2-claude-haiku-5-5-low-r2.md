**H1.** 12 methods, all in `tests/test_policy.py`; none in `tests/` outside that file.
- `:452` test_baton_dispatch_effect_attempts_are_source_bound
- `:929` test_cue_free_tui_attempts_are_source_bound
- `:1727` test_issue_29_recovery_attempts_are_source_bound
- `:2177` test_compact_policy_full_matrix_attempts_are_source_bound
- `:2552` test_spontaneous_dispatch_attempts_are_source_bound
- `:3288` test_verifier_boundary_attempts_are_source_bound
- `:3751` test_verifier_paid_campaign_summary_is_source_bound
- `:4094` test_current_derived_benchmark_prose_is_source_bound
- `:4631` test_prompt_compression_attempts_are_source_bound
- `:4941` test_dispatch_brake_attempts_are_source_bound
- `:5149` test_dispatch_brake_positive_control_attempts_are_source_bound
- `:6789` test_baton_compatibility_attempts_are_source_bound

**H2.** `v1.2.0 — 2026-07-14`. Its entry mentions `security-executor` at `CHANGELOG.md:224` and `:226`, and no earlier-dated entry does (`:218` heading, newest entries first).

**H3.** `VERSION` → `"version"` field, in call order:
1. `main()` `tools/render_plugin_spike.py:369` calls `write()` (`:375-376`) and/or `check()` (`:377`).
2. `write()` `:360` and `check()` `:335` each call `generated()` (`:361`, `:345`).
3. `generated()` `:301` calls `version()` (`:304`).
4. `version()` `:157` reads `VERSION_FILE` (`:13`, `:158`), validates `X.Y.Z` (`:159-161`), returns the value.
5. `generated()` passes it to `build_manifest(release_version)` (`:168`, called at `:306`).
6. `build_manifest` sets `"version": release_version` (`:174`), serialized by `json_bytes` (`:164-165`).
7. The output is written to `MANIFEST` = `plugin/.claude-plugin/plugin.json` (`:14`, `:306`) by `write()` at `:363`; `check()` compares it at `:349-356`.

**H4.** The seven `plugin/agents/` files all use line 6:
- `scout.md:6` `tools: Read, Glob, Grep`
- `plan-verifier.md:6` `tools: Read, Glob, Grep`
- `security-reviewer.md:6` `tools: Read, Glob, Grep, WebSearch, WebFetch`
- `mech-executor.md:6` `disallowedTools: Agent, Workflow`
- `executor.md:6` `disallowedTools: Agent, Workflow`
- `security-executor.md:6` `disallowedTools: Agent, Workflow`
- `verifier.md:6` `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`

**H5.** `tests/test_plugin_hook.py:198` `test_nonempty_model_override_fails_closed_without_value_or_policy`, with `CLAUDE_CODE_SUBAGENT_MODEL` set to `"secret-model-value"`. Its assertions:
1. `:207` `returncode == 0`
2. `:208` `stdout == MODEL_OVERRIDE_DIAGNOSTIC`
3. `:209` the secret bytes are not in `stdout + stderr`
4. `:210` `SENTINEL` is not in `stdout`
5. `:211` `POLICY` is not in `stdout`
6. `:212` `stderr == b""`

**H6.** Not found. `CHANGELOG.md:9` says `scout` moved Haiku→Sonnet in v1.4.2 (`:5`). `:12` says "No other role changes" and `Explore` stays on Haiku. No other Explore/Haiku/Sonnet line describes an `Explore` move.

**H7.** Explore/scout/mech-executor used 0.41M output tokens (1.9%) on the **Luna** model profile (`docs/field-report-tokscale-2026-07.zh-TW.md:71`). The table header is at `:63`.

**H8.** Verifier REFUTED rates (`docs/field-report-tokscale-2026-07.zh-TW.md:97-99`):
- Session A: REFUTED 59 (42%)
- Session B: REFUTED 25 (41%)

**H9.** 14 `self.assertIn(` calls in `tests/test_plugin.py` (grep count).

**H10.** Not found. Searched `tests/test_plugin_hook.py` for "space" and for `CLAUDE_CONFIG_DIR` assignments. The `CLAUDE_CONFIG_DIR` setups are at `:86`, `:112`, `:151`, `:535`, `:610`, `:725`, and none shows a path with spaces.
