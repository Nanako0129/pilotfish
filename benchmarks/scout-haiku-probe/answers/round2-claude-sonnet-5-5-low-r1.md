Nearly done. I checked the test files and the changelog, and these are the answers.

**H1.** There are 12 `_source_bound` test methods, all in `tests/test_policy.py`. No other file in `tests/` has one.
- `:452` `test_baton_dispatch_effect_attempts_are_source_bound`
- `:929` `test_cue_free_tui_attempts_are_source_bound`
- `:1727` `test_issue_29_recovery_attempts_are_source_bound`
- `:2177` `test_compact_policy_full_matrix_attempts_are_source_bound`
- `:2552` `test_spontaneous_dispatch_attempts_are_source_bound`
- `:3288` `test_verifier_boundary_attempts_are_source_bound`
- `:3751` `test_verifier_paid_campaign_summary_is_source_bound`
- `:4094` `test_current_derived_benchmark_prose_is_source_bound`
- `:4631` `test_prompt_compression_attempts_are_source_bound`
- `:4941` `test_dispatch_brake_attempts_are_source_bound`
- `:5149` `test_dispatch_brake_positive_control_attempts_are_source_bound`
- `:6789` `test_baton_compatibility_attempts_are_source_bound`

**H2.** The earliest entry is **v1.2.0 — 2026-07-14** (header at `CHANGELOG.md:218`). `security-executor` appears on 6 lines: 10, 12, 16, 192, 224 and 226. The lowest-numbered line in the v1.2.0 section is `CHANGELOG.md:224`. Line 226 is also in it, and line 192 is in v1.3.1. Line 224 is the last of the matches before the v1.2.1 header at 212 in file order, so the v1.2.0 section holds the oldest ones. I didn't read lines 224 and 226 in full, because the search tool omitted them as long lines.

**H3.** The call order is:
1. `main()` at `tools/render_plugin_spike.py:369`. I saw only this definition line, not its body. I'm assuming it calls `write()` or `check()`.
2. `write()` at `:360` loops over `generated().items()` at `:361`.
3. `generated()` at `:301` calls `version()` at `:304`.
4. `version()` at `:157` reads `VERSION_FILE` (`ROOT / "VERSION"`, `:13`) with `.read_text().strip()` at `:158`. It checks that the value matches X.Y.Z at `:159`.
5. `build_manifest(release_version)` at `:168`, called from `generated()` at `:306`, sets `"version": release_version` at `:174`.
6. `json_bytes()` at `:164` serialises the manifest. `generated()` keys the result to `MANIFEST`, which is `plugin/.claude-plugin/plugin.json` (`:14`).

`check()` at `:335` calls `generated()` at `:345` to compare against the files on disk. `tests/test_plugin.py:79-93` asserts that `manifest["version"]` equals the contents of `VERSION`.

**H4.** The restriction is on line 6 of each file.
- `scout.md:6`: `tools: Read, Glob, Grep`
- `plan-verifier.md:6`: `tools: Read, Glob, Grep`
- `security-reviewer.md:6`: `tools: Read, Glob, Grep, WebSearch, WebFetch`
- `mech-executor.md:6`: `disallowedTools: Agent, Workflow`
- `executor.md:6`: `disallowedTools: Agent, Workflow`
- `security-executor.md:6`: `disallowedTools: Agent, Workflow`
- `verifier.md:6`: `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`

**H5.** The test is `test_nonempty_model_override_fails_closed_without_value_or_policy` (`tests/test_plugin_hook.py:198`). Its assertions are:
- `:207` `assertEqual(result.returncode, 0)`
- `:208` `assertEqual(result.stdout, MODEL_OVERRIDE_DIAGNOSTIC)`
- `:209` `assertNotIn(secret.encode(), result.stdout + result.stderr)`
- `:210` `assertNotIn(SENTINEL, result.stdout)`
- `:211` `assertNotIn(POLICY, result.stdout)`
- `:212` `assertEqual(result.stderr, b"")`

Two other tests also set a non-empty override. `:282` sets `secret-model-value` at `:292` and asserts at `:322-326`. The client-case matrix at `:511` includes `override-nonempty`, and its assertions are at `:561-567`. The one at `:198` is the dedicated test.

**H6.** No version did. The only Haiku→Sonnet move in the changelog is `scout`, in **v1.4.2** (`CHANGELOG.md:9`). `CHANGELOG.md:12` says `Explore` stays on Haiku in the legacy global install. I searched `CHANGELOG.md` for `Explore` and for Haiku/Sonnet pairings.

**H7.** The group is "Explore／scout／mech-executor". It took **0.41M output tokens, 1.9%**, on the **Luna** model profile, which the report calls the execution tier (`docs/field-report-tokscale-2026-07.zh-TW.md:71`).

**H8.** The verifier verdicts are at `docs/field-report-tokscale-2026-07.zh-TW.md:99`.
- **Session 1:** CONFIRMED 78 / REFUTED 59, so **42%** REFUTED.
- **Session 2:** CONFIRMED 34 / REFUTED 25, so **41%** REFUTED.

I took these to be the first and second columns of the table.

**H9.** There are exactly **14** `self.assertIn(` calls in `tests/test_plugin.py`.

**H10.** No test in `tests/test_plugin_hook.py` matches. Searches for "space", "spaces", and `CLAUDE_CONFIG_DIR` values containing a space found nothing. The file's `CLAUDE_CONFIG_DIR` values are `{config}` substitutions of a temp-dir path (`:86`, `:112`, `:151`), a relative path (`:576`) and `str(config)` (`:610`). The temp directories don't have spaces in their names, so none of these tests covers one.
