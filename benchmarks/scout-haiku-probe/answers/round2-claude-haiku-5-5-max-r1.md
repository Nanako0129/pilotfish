**H1.** 12 test methods, all in `tests/test_policy.py`. A repo-wide case-insensitive search for `source.?bound` returns only these 12.
- :452 `test_baton_dispatch_effect_attempts_are_source_bound`
- :929 `test_cue_free_tui_attempts_are_source_bound`
- :1727 `test_issue_29_recovery_attempts_are_source_bound`
- :2177 `test_compact_policy_full_matrix_attempts_are_source_bound`
- :2552 `test_spontaneous_dispatch_attempts_are_source_bound`
- :3288 `test_verifier_boundary_attempts_are_source_bound`
- :3751 `test_verifier_paid_campaign_summary_is_source_bound`
- :4094 `test_current_derived_benchmark_prose_is_source_bound`
- :4631 `test_prompt_compression_attempts_are_source_bound`
- :4941 `test_dispatch_brake_attempts_are_source_bound`
- :5149 `test_dispatch_brake_positive_control_attempts_are_source_bound`
- :6789 `test_baton_compatibility_attempts_are_source_bound`

**H2.** v1.2.0, 2026-07-14. The heading is at `CHANGELOG.md:218`, and the first mention is at :224 (also :226). The later mentions are v1.3.1 (:192, 2026-07-23) and v1.4.2 (:10, :16, 2026-09-26).

**H3.** Everything is in `tools/render_plugin_spike.py`. `VERSION:1` is `1.4.2`, and `plugin/.claude-plugin/plugin.json:5` is `"version": "1.4.2"`. The `--write` path, in call order:
1. `main()` :369. On `--write` it calls `write()` (:375-376), then `check()` (:377).
2. `write()` :360. It iterates `generated()` (:361) and calls `path.write_bytes(data)` (:363).
3. `generated()` :301. It runs `release_version = version()` (:304), then `MANIFEST: build_manifest(release_version)` (:306).
4. `version()` :157. It reads `VERSION_FILE` (defined :13) at :158, strips it, validates `X.Y.Z` (:159-160), and returns (:161).
5. `build_manifest(release_version)` :168. It sets `"version": release_version` (:174) and returns `json_bytes(...)` (:169).
6. `json_bytes(document)` :164. It runs `json.dumps(..., indent=2)` plus `"\n"` and encodes as UTF-8 (:165).

The target is `MANIFEST` at :14. `write()` calls `generated()` a second time at :365. The verify path is `check()` :335, which calls `generated()` at :345 and compares bytes at :349-356. The test is `tests/test_plugin.py:79-94`.

**H4.** Each quote is line 6 of its file:
- `security-reviewer.md:6`: `tools: Read, Glob, Grep, WebSearch, WebFetch`
- `security-executor.md:6`: `disallowedTools: Agent, Workflow`
- `executor.md:6`: `disallowedTools: Agent, Workflow`
- `verifier.md:6`: `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`
- `mech-executor.md:6`: `disallowedTools: Agent, Workflow`
- `plan-verifier.md:6`: `tools: Read, Glob, Grep`
- `scout.md:6`: `tools: Read, Glob, Grep`

`tools:` is an allowlist and `disallowedTools:` is a denylist (`CHANGELOG.md:287`).

**H5.** `tests/test_plugin_hook.py:198`, `test_nonempty_model_override_fails_closed_without_value_or_policy`. It sets `CLAUDE_CODE_SUBAGENT_MODEL="secret-model-value"` (:199, :205). Its assertions:
- :207 `assertEqual(result.returncode, 0)`
- :208 `assertEqual(result.stdout, MODEL_OVERRIDE_DIAGNOSTIC)`
- :209 `assertNotIn(secret.encode(), result.stdout + result.stderr)`
- :210 `assertNotIn(SENTINEL, result.stdout)`
- :211 `assertNotIn(POLICY, result.stdout)`
- :212 `assertEqual(result.stderr, b"")`

The `run_hook` helper it calls also asserts `assertEqual(snapshot(root), before)` at :173. Two other tests also pass a non-empty override: :292 in `test_hook_ignores_hostile_inherited_path_for_all_output_classes`, and :511 in `test_documented_preflight_exact_client_and_legacy_matrix`, which exercises the documented preflight rather than the hook.

**H6.** None. No CHANGELOG entry moves `Explore` from Haiku to Sonnet. I searched every `Explore` mention (`CHANGELOG.md:12, 33, 214, 262, 287, 294, 305`) and read the whole file. The Haiku→Sonnet move in v1.4.2 is for `scout` (:9). Line :12 says `Explore` stays on Haiku.

**H7.** 0.41M output tokens and 1.9%, on the Luna profile. Source is `docs/field-report-tokscale-2026-07.zh-TW.md:71` (row "Explore／scout／mech-executor | Luna | 0.41M | 1.9%"). The table header at :63 names output tokens, and :23 identifies Luna as the execution-role model.

**H8.** Session A: 42% REFUTED (59 REFUTED, 78 CONFIRMED). Session B: 41% REFUTED (25 REFUTED, 34 CONFIRMED). Source is `…zh-TW.md:99`. Session A is TokenBar-Windows and Session B is TokenBar (:27). The printed percentages equal REFUTED divided by total verifier runs (59/140 and 25/61, per :57). Dividing by CONFIRMED+REFUTED would give 43% and 42%.

**H9.** 14 calls, at `tests/test_plugin.py` lines 89, 100, 101, 122, 127, 167, 245, 267, 271, 272, 310, 329, 358, 377. A bare `assertIn` count is also 14, so there are no variants.

**H10.** None. No test in `tests/test_plugin_hook.py` uses a CLAUDE_CONFIG_DIR path with spaces. I read the full file and searched `tests/` for "space" case-insensitively, which matched only "namespace" at `tests/test_plugin.py:326`. The CLAUDE_CONFIG_DIR values are either `str(...)` of a tempdir (:86, :112, :151-153, :535, :610-612, :725) or literals without spaces (`{config}`, `relative-config` at :243, `relative` at :576 and :611). The closest test is `test_relative_config_root_fails_closed_without_policy` at :240, which covers a relative path, not a spaced one.
