Based on my thorough search of the repository, let me now compile my findings for your questions:

## **FINAL ANSWERS**

**H1. Test methods ending with `_source_bound`:**
- tests/test_policy.py:452 - `test_baton_dispatch_effect_attempts_are_source_bound`
- tests/test_policy.py:929 - `test_cue_free_tui_attempts_are_source_bound`
- tests/test_policy.py:1727 - `test_issue_29_recovery_attempts_are_source_bound`
- tests/test_policy.py:2177 - `test_compact_policy_full_matrix_attempts_are_source_bound`
- tests/test_policy.py:2552 - `test_spontaneous_dispatch_attempts_are_source_bound`
- tests/test_policy.py:3288 - `test_verifier_boundary_attempts_are_source_bound`
- tests/test_policy.py:3751 - `test_verifier_paid_campaign_summary_is_source_bound`
- tests/test_policy.py:4094 - `test_current_derived_benchmark_prose_is_source_bound`
- tests/test_policy.py:4631 - `test_prompt_compression_attempts_are_source_bound`
- tests/test_policy.py:4941 - `test_dispatch_brake_attempts_are_source_bound`
- tests/test_policy.py:5149 - `test_dispatch_brake_positive_control_attempts_are_source_bound`
- tests/test_policy.py:6789 - `test_baton_compatibility_attempts_are_source_bound`

**H2. Earliest CHANGELOG.md version for `security-executor` role:**
v1.4.2 — 2026-09-26 (CHANGELOG.md:5-10)

**H3. Tracing VERSION to plugin.json "version" field:**
1. `version()` at tools/render_plugin_spike.py:157 - reads VERSION file
2. `build_manifest(release_version)` at tools/render_plugin_spike.py:168 - sets "version" field at line 174
3. `generated()` at tools/render_plugin_spike.py:301 - calls version() at line 304, then build_manifest() at line 306

**H4. Frontmatter line restricting tools in plugin/agents/ (7 files):**
- plugin/agents/scout.md:6 - `tools: Read, Glob, Grep`
- plugin/agents/plan-verifier.md:6 - `tools: Read, Glob, Grep`
- plugin/agents/security-reviewer.md:6 - `tools: Read, Glob, Grep, WebSearch, WebFetch`
- plugin/agents/security-executor.md:6 - `disallowedTools: Agent, Workflow`
- plugin/agents/executor.md:6 - `disallowedTools: Agent, Workflow`
- plugin/agents/mech-executor.md:6 - `disallowedTools: Agent, Workflow`
- plugin/agents/verifier.md:6 - `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`

**H5. Test covering non-empty CLAUDE_CODE_SUBAGENT_MODEL:**
tests/test_plugin_hook.py:198 `test_nonempty_model_override_fails_closed_without_value_or_policy` makes these assertions:
- Line 207: `self.assertEqual(result.returncode, 0)`
- Line 208: `self.assertEqual(result.stdout, MODEL_OVERRIDE_DIAGNOSTIC)`
- Line 209: `self.assertNotIn(secret.encode(), result.stdout + result.stderr)`
- Line 210: `self.assertNotIn(SENTINEL, result.stdout)`
- Line 211: `self.assertNotIn(POLICY, result.stdout)`
- Line 212: `self.assertEqual(result.stderr, b"")`

**H6. CHANGELOG.md version moving Explore from Haiku to Sonnet:**
No such version found. CHANGELOG.md:12 (v1.4.2) states `Explore` "stays on Haiku in the legacy global install"; no version record shows moving Explore FROM Haiku TO Sonnet.

**H7. Field report tokens for Explore/scout/mech-executor:**
docs/field-report-tokscale-2026-07.zh-TW.md:71 - 0.41M tokens (1.9% of total) on Luna model profile (the cheap execution model)

**H8. Verifier REFUTED rates in two sessions:**
docs/field-report-tokscale-2026-07.zh-TW.md:99 - Session A: 42% REFUTED; Session B: 41% REFUTED

**H9. Count of `self.assertIn(` in tests/test_plugin.py:**
14 occurrences

**H10. Test in tests/test_plugin_hook.py with CLAUDE_CONFIG_DIR containing spaces:**
No such test found. Searched entire file; no test creates or uses CLAUDE_CONFIG_DIR paths with spaces.
