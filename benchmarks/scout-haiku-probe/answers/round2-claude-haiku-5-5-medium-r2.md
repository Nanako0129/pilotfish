**Direct answers**

- **H1:** 12 `_source_bound` test methods, all in `tests/test_policy.py`: 452, 929, 1727, 2177, 2552, 3288, 3751, 4094, 4631, 4941, 5149, 6789. Names are `test_baton_dispatch_effect_attempts_are_source_bound`, `test_cue_free_tui_attempts_are_source_bound`, `test_issue_29_recovery_attempts_are_source_bound`, `test_compact_policy_full_matrix_attempts_are_source_bound`, `test_spontaneous_dispatch_attempts_are_source_bound`, `test_verifier_boundary_attempts_are_source_bound`, `test_verifier_paid_campaign_summary_is_source_bound`, `test_current_derived_benchmark_prose_is_source_bound`, `test_prompt_compression_attempts_are_source_bound`, `test_dispatch_brake_attempts_are_source_bound`, `test_dispatch_brake_positive_control_attempts_are_source_bound`, `test_baton_compatibility_attempts_are_source_bound`.
- **H2:** v1.2.0, dated 2026-07-14. It is the first entry naming `security-executor` (`CHANGELOG.md:224`, also `:226`). Earlier-listed entries (v1.3.x and later) only mention it afterwards.
- **H3:** VERSION → plugin.json, in call order (`tools/render_plugin_spike.py`):
  1. `main()` :369. With `--write`, calls `write()` (:375–376); then always calls `check()` (:377).
  2. `write()` :360 → `generated()` :361, or `check()` :335 → `generated()` :345.
  3. `generated()` :301 calls `version()` :304.
  4. `version()` :157 reads `VERSION` (:158), validates `X.Y.Z` (:159–160), and returns it.
  5. `generated()` passes the value to `build_manifest(release_version)` :306.
  6. `build_manifest()` :168 puts it in the dict key `"version"` (:174) and calls `json_bytes()` :164 (:169).
  The MANIFEST path is `plugin/.claude-plugin/plugin.json` (:14). The committed file has `"version": "1.4.2"` at `plugin/.claude-plugin/plugin.json:5`.
- **H4:** Frontmatter line 6 in each file, the only tool-restriction line:
  - `plugin/agents/scout.md:6`: `tools: Read, Glob, Grep`
  - `plugin/agents/plan-verifier.md:6`: `tools: Read, Glob, Grep`
  - `plugin/agents/security-reviewer.md:6`: `tools: Read, Glob, Grep, WebSearch, WebFetch`
  - `plugin/agents/mech-executor.md:6`: `disallowedTools: Agent, Workflow`
  - `plugin/agents/executor.md:6`: `disallowedTools: Agent, Workflow`
  - `plugin/agents/security-executor.md:6`: `disallowedTools: Agent, Workflow`
  - `plugin/agents/verifier.md:6`: `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`
- **H5:** `test_nonempty_model_override_fails_closed_without_value_or_policy`, `tests/test_plugin_hook.py:198–212`. It sets `CLAUDE_CODE_SUBAGENT_MODEL` to `secret-model-value` (:199, :205). Its assertions:
  1. `assertEqual(result.returncode, 0)` :207
  2. `assertEqual(result.stdout, MODEL_OVERRIDE_DIAGNOSTIC)` :208
  3. `assertNotIn(secret.encode(), result.stdout + result.stderr)` :209
  4. `assertNotIn(SENTINEL, result.stdout)` :210
  5. `assertNotIn(POLICY, result.stdout)` :211
  6. `assertEqual(result.stderr, b"")` :212

  The helper `run_hook` also asserts the directory snapshot is unchanged (:173).
- **H6:** Not found. No CHANGELOG entry says `Explore` moved from Haiku to Sonnet. The only `Explore` model statement is v1.4.2: "`Explore` stays on Haiku in the legacy global install" (`CHANGELOG.md:12`). I searched all `Explore` and `Haiku` mentions in CHANGELOG.md.
- **H7:** The "Explore／scout／mech-executor" row (`docs/field-report-tokscale-2026-07.zh-TW.md:71`) shows 0.41M output tokens, 1.9%, on the Luna model profile. Luna is the GPT-5.6 execution-tier model; the report says it runs via the remora/GPT-5.6 gateway (:23).
- **H8:** `docs/field-report-tokscale-2026-07.zh-TW.md:99`:
  - Session A: REFUTED 59 (42%), with CONFIRMED 78.
  - Session B: REFUTED 25 (41%), with CONFIRMED 34.
- **H9:** 14 `self.assertIn(` calls in `tests/test_plugin.py`, from a grep count.
- **H10:** Not found. No test in `tests/test_plugin_hook.py` uses a `CLAUDE_CONFIG_DIR` path containing spaces. Searched for `CLAUDE_CONFIG_DIR`, `config_value=`, "space(s)", and quoted strings with spaces. The config paths are `root / "config"` (e.g., :130) and `str(config_root)`.
