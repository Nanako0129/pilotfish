**H1.** 12 methods, all in `tests/test_policy.py`:
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

**H2.** v1.2.0, 2026-07-14 (`CHANGELOG.md:218`). It names `security-executor` at :224 and :226. No earlier entry (v1.1.x, v1.0.0) mentions it.

**H3.** `VERSION` → `plugin.json` `"version"`, in call order:
1. `main()` — `tools/render_plugin_spike.py:369`
2. `write()` — :360 (only with `--write`)
3. `generated()` — :301, which sets `release_version = version()` at :304
4. `version()` — :157; reads `VERSION` at :158, checks `X.Y.Z` at :159–160, returns at :161
5. `build_manifest(release_version)` — :168; sets `"version"` at :174
6. `json_bytes()` — :164; `json.dumps(indent=2)` plus LF at :165
7. `write()` — :363; `path.write_bytes(data)` writes `plugin/.claude-plugin/plugin.json`

The check path is `main()` → `check()` (:335, called at :377) → `generated()` (:345) → byte compare (:349–356). The test side is `tests/test_plugin.py:79–94`. Current values: `VERSION:1` is `1.4.2`, and `plugin/.claude-plugin/plugin.json:5` is `"version": "1.4.2"`.

**H4.** Frontmatter line 6 of each file:
- `scout.md:6` — `tools: Read, Glob, Grep`
- `plan-verifier.md:6` — `tools: Read, Glob, Grep`
- `security-reviewer.md:6` — `tools: Read, Glob, Grep, WebSearch, WebFetch`
- `executor.md:6` — `disallowedTools: Agent, Workflow`
- `mech-executor.md:6` — `disallowedTools: Agent, Workflow`
- `security-executor.md:6` — `disallowedTools: Agent, Workflow`
- `verifier.md:6` — `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`

**H5.** `tests/test_plugin_hook.py:198`, `test_nonempty_model_override_fails_closed_without_value_or_policy`. Its assertions:
1. `assertEqual(result.returncode, 0)` — :207
2. `assertEqual(result.stdout, MODEL_OVERRIDE_DIAGNOSTIC)` — :208
3. `assertNotIn(secret.encode(), result.stdout + result.stderr)` — :209 (secret is `"secret-model-value"`, :199)
4. `assertNotIn(SENTINEL, result.stdout)` — :210
5. `assertNotIn(POLICY, result.stdout)` — :211
6. `assertEqual(result.stderr, b"")` — :212

It also calls `run_hook`, which asserts snapshot unchanged at :173. Two other tests also set a non-empty value: :282 (`secret-model-value` at :292) and the preflight matrix (`override-nonempty` at :511, env set at :538).

**H6.** Not found. I read all of `CHANGELOG.md` and grepped it case-insensitively for Explore, haiku, and sonnet. The only Haiku→Sonnet move is `scout`, in v1.4.2 (`CHANGELOG.md:9`). That same entry says "`Explore` stays on Haiku in the legacy global install" (:12). The Plugin does not ship `Explore` (`tools/render_plugin_spike.py:262–263`).

**H7.** The "Explore／scout／mech-executor" row (`docs/field-report-tokscale-2026-07.zh-TW.md:71`) reports **0.41M output tokens, 1.9%**, on model profile **Luna**. Luna is the execution-tier model under the GPT-5.6 gateway (:23).

**H8.** From the verifier verdict row (:99):
- Session A: **REFUTED 59, stated as 42%**
- Session B: **REFUTED 25, stated as 41%**

The same row's counts give 59/137 = 43.1% and 25/59 = 42.4%, so the stated percentages do not match the counts.

**H9.** **14** `self.assertIn(` calls in `tests/test_plugin.py`, at lines 89, 100, 101, 122, 127, 167, 245, 267, 271, 272, 310, 329, 358, 377.

**H10.** None in `tests/test_plugin_hook.py`. I read the whole file and grepped it case-insensitively for "space". Every `CLAUDE_CONFIG_DIR` value is a `tempfile` path, the `{config}` placeholder, or a relative value (:86, :112, :151–153, :246, :610–612, :725). The nearest is `test_relative_config_root_fails_closed_without_policy` (:240), which uses a relative path.
