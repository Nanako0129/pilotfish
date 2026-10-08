**H1.** 12 methods, all in `tests/test_policy.py`:
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

**H2.** **v1.2.0 — 2026-07-14.** `CHANGELOG.md:218` is its header; `security-executor` appears at `:224` and `:226`. The only earlier mentions are in later releases (`:10`, `:16`, `:192`).

**H3.** VERSION → plugin.json runs through `tools/render_plugin_spike.py`, in call order:
1. `main()` `:369`, which calls `write()` under `--write`.
2. `write()` `:360`, which calls `generated()` at `:361`.
3. `generated()` `:301`, which sets `release_version = version()` at `:304`.
4. `version()` `:157`, which reads `VERSION_FILE` (`:158`) and checks `X.Y.Z` (`:159`).
5. `build_manifest(release_version)` `:168`, which puts the value in the `"version"` key at `:174`.
6. `json_bytes()` `:164`, which serializes it. `:306` maps the bytes to `MANIFEST` (`:14`).

`main()` then calls `check()` `:335`, which calls `generated()` again at `:345`. The result is `plugin/.claude-plugin/plugin.json:5` = `"1.4.2"`, matching `VERSION:1`.

**H4.** Frontmatter tool-restricting lines (all on line 6):
- `scout.md:6`: `tools: Read, Glob, Grep`
- `plan-verifier.md:6`: `tools: Read, Glob, Grep`
- `security-reviewer.md:6`: `tools: Read, Glob, Grep, WebSearch, WebFetch`
- `executor.md:6`: `disallowedTools: Agent, Workflow`
- `mech-executor.md:6`: `disallowedTools: Agent, Workflow`
- `security-executor.md:6`: `disallowedTools: Agent, Workflow`
- `verifier.md:6`: `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`

**H5.** `tests/test_plugin_hook.py:198`, `test_nonempty_model_override_fails_closed_without_value_or_policy`. It sets `CLAUDE_CODE_SUBAGENT_MODEL` to `"secret-model-value"` (`:199`, `:205`). Its assertions:
1. `:207` `returncode == 0`
2. `:208` `stdout == MODEL_OVERRIDE_DIAGNOSTIC`
3. `:209` the secret value is absent from stdout+stderr
4. `:210` `SENTINEL` is absent from stdout
5. `:211` `POLICY` is absent from stdout
6. `:212` `stderr == b""`

**H6.** Not found. No CHANGELOG entry moves `Explore` to Sonnet. `CHANGELOG.md:12` says "`Explore` stays on Haiku in the legacy global install," and `templates/agents/Explore.md:4` is `model: haiku`. The only Haiku→Sonnet move in the CHANGELOG is for `scout` in v1.4.2 (`CHANGELOG.md:9`).

**H7.** `docs/field-report-tokscale-2026-07.zh-TW.md:71`: **0.41M output tokens, 1.9%, model profile "Luna"** (the execution-tier model; `:23` says execution roles use Luna).

**H8.** `docs/field-report-tokscale-2026-07.zh-TW.md:99`:
- Session A: REFUTED 59 (stated 42%)
- Session B: REFUTED 25 (stated 41%)

The listed CONFIRMED+REFUTED counts sum to 137 and 59. The stated percentages match REFUTED ÷ 140 and ÷ 61, the verifier call counts in `:57`.

**H9.** **14** `self.assertIn(` calls in `tests/test_plugin.py` (`:89, 100, 101, 122, 127, 167, 245, 267, 271, 272, 310, 329, 358, 377`).

**H10.** Not found. Searching `tests/test_plugin_hook.py` for "space" and for `CLAUDE_CONFIG_DIR` values (`:86, 112, 151, 246, 535, 576, 610, 655, 725`) found no path with spaces. The closest is `test_relative_config_root_fails_closed_without_policy` (`:240`), which tests a relative path.
