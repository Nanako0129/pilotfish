**H1.** 12 test methods end in `_source_bound`, all in `tests/test_policy.py`:
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

**H2.** The earliest entry is **v1.2.0, 2026-07-14** (`CHANGELOG.md:218`). It first mentions `security-executor` at `:224` and again at `:226`. The other mentions are in v1.3.1 (`:192`) and v1.4.2 (`:10`, `:16`).

**H3.** `VERSION` reaches `"version"` through this call chain in `tools/render_plugin_spike.py`:
1. `main()` at `:369` calls `write()` (`:360`) when `--write` is given, then `check()` (`:335`).
2. `write()` iterates `generated()` at `:361`.
3. `generated()` (`:301`) calls `version()` at `:304`.
4. `version()` (`:157`) reads `VERSION` at `:158`, checks it is `X.Y.Z` at `:159`, and returns it.
5. `generated()` passes the value to `build_manifest(release_version)` at `:306`.
6. `build_manifest()` (`:168`) sets `"version": release_version` at `:174`, then serialises via `json_bytes()` (`:164`).
7. `write()` writes the bytes to `MANIFEST` (`:14`) at `:363`.

`check()` repeats steps 3–6 at `:345` and compares bytes at `:355`. The result is `plugin/.claude-plugin/plugin.json:5` = `"version": "1.4.2"`, matching `VERSION:1`. `tests/test_plugin.py:80-85` also asserts the equality.

**H4.** Each file has the tool-restriction line at frontmatter line 6:
- `plugin/agents/scout.md:6` — `tools: Read, Glob, Grep`
- `plugin/agents/plan-verifier.md:6` — `tools: Read, Glob, Grep`
- `plugin/agents/mech-executor.md:6` — `disallowedTools: Agent, Workflow`
- `plugin/agents/verifier.md:6` — `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`
- `plugin/agents/executor.md:6` — `disallowedTools: Agent, Workflow`
- `plugin/agents/security-executor.md:6` — `disallowedTools: Agent, Workflow`
- `plugin/agents/security-reviewer.md:6` — `tools: Read, Glob, Grep, WebSearch, WebFetch`

**H5.** The test is `test_nonempty_model_override_fails_closed_without_value_or_policy` (`tests/test_plugin_hook.py:198-212`). It sets `CLAUDE_CODE_SUBAGENT_MODEL="secret-model-value"`. Its assertions are:
1. `assertEqual(result.returncode, 0)` — `:207`
2. `assertEqual(result.stdout, MODEL_OVERRIDE_DIAGNOSTIC)` — `:208`
3. `assertNotIn(secret.encode(), result.stdout + result.stderr)` — `:209`
4. `assertNotIn(SENTINEL, result.stdout)` — `:210`
5. `assertNotIn(POLICY, result.stdout)` — `:211`
6. `assertEqual(result.stderr, b"")` — `:212`

The `run_hook` helper it calls also asserts the config directory snapshot is unchanged (`:173`). Two other tests also use a non-empty override: `:282-326` and the `override-nonempty` case at `:511`.

**H6.** No CHANGELOG version moves `Explore` from Haiku to Sonnet. The premise is not supported.
- `CHANGELOG.md:9` says v1.4.2 moved `scout` from Haiku to Sonnet.
- `CHANGELOG.md:12` says v1.4.2 keeps `Explore` on Haiku in the legacy global install.
- `templates/agents/Explore.md:4` has `model: haiku`.
- `tests/test_policy.py:5811` expects `"Explore": "haiku"`.

**H7.** Per `docs/field-report-tokscale-2026-07.zh-TW.md:71`, the Explore/scout/mech-executor group used **0.41M output tokens (1.9%)** on the **Luna** model file. Output tokens, not total tokens, is what the table reports. `:23` says Luna is the execution-role model.

**H8.** Per `docs/field-report-tokscale-2026-07.zh-TW.md:99`:
- Session A: REFUTED 59, **42%**.
- Session B: REFUTED 25, **41%**.

**H9.** `tests/test_plugin.py` contains **14** `self.assertIn(` calls, at lines 89, 100, 101, 122, 127, 167, 245, 267, 271, 272, 310, 329, 358 and 377.

**H10.** No test in `tests/test_plugin_hook.py` checks a `CLAUDE_CONFIG_DIR` path containing spaces. I searched that file and `tests/` for "space", "blank" and `CLAUDE_CONFIG_DIR`. Every config root is a `tempfile` directory, a `{config}` placeholder, or the literal `relative-config` (`:86`, `:112`, `:151-153`, `:243`, `:535`, `:610-612`, `:725`).
