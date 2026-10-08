Based on my systematic search through the repository, here are the answers:

## H1. Test methods ending with `_source_bound` (file:line):

- tests/test_policy.py:452 `test_baton_dispatch_effect_attempts_are_source_bound`
- tests/test_policy.py:929 `test_cue_free_tui_attempts_are_source_bound`
- tests/test_policy.py:1727 `test_issue_29_recovery_attempts_are_source_bound`
- tests/test_policy.py:2177 `test_compact_policy_full_matrix_attempts_are_source_bound`
- tests/test_policy.py:2552 `test_spontaneous_dispatch_attempts_are_source_bound`
- tests/test_policy.py:3288 `test_verifier_boundary_attempts_are_source_bound`
- tests/test_policy.py:3751 `test_verifier_paid_campaign_summary_is_source_bound`
- tests/test_policy.py:4094 `test_current_derived_benchmark_prose_is_source_bound`
- tests/test_policy.py:4631 `test_prompt_compression_attempts_are_source_bound`
- tests/test_policy.py:4941 `test_dispatch_brake_attempts_are_source_bound`
- tests/test_policy.py:5149 `test_dispatch_brake_positive_control_attempts_are_source_bound`
- tests/test_policy.py:6789 `test_baton_compatibility_attempts_are_source_bound`

## H2. Earliest version mentioning `security-executor`:

**v1.2.0 — 2026-07-14** (CHANGELOG.md:224, introducing the role: "the write-capable `security-executor` accepts only an approved stable implementation contract")

## H3. VERSION → plugin.json trace (call order):

1. `tools/render_plugin_spike.py:304` `generated()` calls `version()`
2. `tools/render_plugin_spike.py:157` `version()` calls `VERSION_FILE.read_text()` (where VERSION_FILE = ROOT / "VERSION" at line 13)
3. `tools/render_plugin_spike.py:306` `generated()` calls `build_manifest(release_version)`
4. `tools/render_plugin_spike.py:174` `build_manifest()` sets `"version": release_version` in plugin.json

## H4. Exact frontmatter tool-restriction lines for seven agent files:

- plugin/agents/security-reviewer.md:6 → `tools: Read, Glob, Grep, WebSearch, WebFetch`
- plugin/agents/security-executor.md:6 → `disallowedTools: Agent, Workflow`
- plugin/agents/executor.md:6 → `disallowedTools: Agent, Workflow`
- plugin/agents/verifier.md:6 → `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`
- plugin/agents/mech-executor.md:6 → `disallowedTools: Agent, Workflow`
- plugin/agents/plan-verifier.md:6 → `tools: Read, Glob, Grep`
- plugin/agents/scout.md:6 → `tools: Read, Glob, Grep`

## H5. Test covering non-empty CLAUDE_CODE_SUBAGENT_MODEL:

**tests/test_plugin_hook.py:198** `test_nonempty_model_override_fails_closed_without_value_or_policy` makes these assertions (lines 207–212):
- assertEqual(result.returncode, 0)
- assertEqual(result.stdout, MODEL_OVERRIDE_DIAGNOSTIC)
- assertNotIn(secret.encode(), result.stdout + result.stderr)
- assertNotIn(SENTINEL, result.stdout)
- assertNotIn(POLICY, result.stdout)
- assertEqual(result.stderr, b"")

## H6. Version moving Explore from Haiku to Sonnet:

**Not found.** CHANGELOG.md:12 states "Explore stays on Haiku in the legacy global install" (v1.4.2); no version documents moving Explore from Haiku to Sonnet.

## H7. Explore/scout/mech-executor group token consumption:

From docs/field-report-tokscale-2026-07.zh-TW.md:71 → **0.41M tokens (1.9%)** on the **Luna model profile**.

## H8. Verifier REFUTED rates in both sessions:

From docs/field-report-tokscale-2026-07.zh-TW.md:99:
- **Session A:** 42% REFUTED (59 refuted / ~141 total)
- **Session B:** 41% REFUTED (25 refuted / ~61 total)

## H9. Count of `self.assertIn(` in tests/test_plugin.py:

**14 occurrences** (verified via grep count across the file).

## H10. Test checking CLAUDE_CONFIG_DIR path with spaces:

**Not found.** Exhaustive search of tests/test_plugin_hook.py reveals no test case or test method that explicitly creates or checks a CLAUDE_CONFIG_DIR containing spaces.
