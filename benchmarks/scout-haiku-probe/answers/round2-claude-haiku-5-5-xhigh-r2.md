**H1.** 12 methods, all in `tests/test_policy.py` (none in `test_plugin.py` or `test_plugin_hook.py`; searched `source_bound\b` across `tests/`):
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

**H2.** v1.2.0, 2026-07-14 (`CHANGELOG.md:218`). Its `security-executor` mentions are at `:224` and `:226`. The earlier-listed mentions at `:10`, `:12`, `:16` (v1.4.2) and `:192` (v1.3.1) are all newer.

**H3.** `VERSION` → `plugin/.claude-plugin/plugin.json` via `tools/render_plugin_spike.py`, in call order:
1. `main()` `:369`: with `--write`, calls `write()` `:376`, then `check()` `:377`.
2. `write()` `:360`: loops over `generated()` `:361`, writes each artifact (`:363`), including `MANIFEST`.
3. `generated()` `:301`: calls `version()` `:304`, then `build_manifest(release_version)` `:306`.
4. `version()` `:157`: reads `VERSION_FILE` `:158`, strips, validates `X.Y.Z` `:159-161`, returns the value.
5. `build_manifest()` `:168`: sets `"version": release_version` at `:174`.
6. `json_bytes()` `:164`: `json.dumps(indent=2)` plus trailing newline `:165`, called from `:169`.

Constants: `VERSION_FILE` `:13`, `MANIFEST` `:14`. Verification path: `check()` `:335` → `generated()` `:345` → byte compare `:355`. Test at `tests/test_plugin.py:80-85` asserts `manifest["version"] == VERSION`.

**H4.** All seven are frontmatter line 6:
- scout.md: `tools: Read, Glob, Grep`
- plan-verifier.md: `tools: Read, Glob, Grep`
- security-reviewer.md: `tools: Read, Glob, Grep, WebSearch, WebFetch`
- executor.md: `disallowedTools: Agent, Workflow`
- mech-executor.md: `disallowedTools: Agent, Workflow`
- security-executor.md: `disallowedTools: Agent, Workflow`
- verifier.md: `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`

**H5.** `tests/test_plugin_hook.py:198` `test_nonempty_model_override_fails_closed_without_value_or_policy`. It sets `CLAUDE_CODE_SUBAGENT_MODEL="secret-model-value"` (`:199`, `:205`). Its assertions:
- `:207` returncode == 0
- `:208` stdout == `MODEL_OVERRIDE_DIAGNOSTIC`
- `:209` secret not in stdout+stderr
- `:210` SENTINEL not in stdout
- `:211` POLICY not in stdout
- `:212` stderr == b""

The `run_hook` helper also asserts the filesystem snapshot is unchanged (`:173`). Two other tests also cover a non-empty override: `:282` (case at `:288-293`) and `:490` (case at `:511`).

**H6.** Not found. No `CHANGELOG.md` entry records `Explore` moving from Haiku to Sonnet. The only `Explore` model statement is `:12` (v1.4.2, `:5`): "`Explore` stays on Haiku in the legacy global install." I searched case-insensitively for `explore` and for Haiku/Sonnet mentions.

**H7.** `docs/field-report-tokscale-2026-07.zh-TW.md:71`: Explore／scout／mech-executor = **0.41M output tokens, 1.9%**, model profile **Luna**. `:23` says Luna is the execution-type profile (GPT-5.6 via remora gateway, not native Claude).

**H8.** `docs/field-report-tokscale-2026-07.zh-TW.md:99`:
- Session A: REFUTED **42%** (CONFIRMED 78 / REFUTED 59)
- Session B: REFUTED **41%** (CONFIRMED 34 / REFUTED 25)

Note: the printed counts compute to 59/137 = 43.1% and 25/59 = 42.4%, not 42% and 41%. Figures are reported as printed.

**H9.** **14** `self.assertIn(` calls in `tests/test_plugin.py`, at lines 89, 100, 101, 122, 127, 167, 245, 267, 271, 272, 310, 329, 358, 377.

**H10.** Not found. No `CLAUDE_CONFIG_DIR` value in `tests/test_plugin_hook.py` contains spaces. Values are `{config}` placeholders, the literal `relative-config`, or temp paths (`:86`, `:112`, `:151-152`, `:535`, `:610-611`, `:725`). A search of `tests/` for "space" found no path-related match. The only space-related hit in `test_plugin_hook.py` is the indentation code at `:56`. `tests/test_policy.py:5511` and `:5556` use `str(config)` temp paths.
