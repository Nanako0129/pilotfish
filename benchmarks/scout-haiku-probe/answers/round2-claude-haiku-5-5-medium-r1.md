**H1. `_source_bound` tests (12, all in `tests/test_policy.py`)**
- `test_policy.py:452` baton_dispatch_effect_attempts_are_source_bound
- `test_policy.py:929` cue_free_tui_attempts_are_source_bound
- `test_policy.py:1727` issue_29_recovery_attempts_are_source_bound
- `test_policy.py:2177` compact_policy_full_matrix_attempts_are_source_bound
- `test_policy.py:2552` spontaneous_dispatch_attempts_are_source_bound
- `test_policy.py:3288` verifier_boundary_attempts_are_source_bound
- `test_policy.py:3751` verifier_paid_campaign_summary_is_source_bound
- `test_policy.py:4094` current_derived_benchmark_prose_is_source_bound
- `test_policy.py:4631` prompt_compression_attempts_are_source_bound
- `test_policy.py:4941` dispatch_brake_attempts_are_source_bound
- `test_policy.py:5149` dispatch_brake_positive_control_attempts_are_source_bound
- `test_policy.py:6789` baton_compatibility_attempts_are_source_bound

(Each name is prefixed `test_`.)

**H2. Earliest `security-executor` mention: v1.2.0, 2026-07-14.**
- `CHANGELOG.md:218` heading `## v1.2.0 — 2026-07-14`; first mentions at `:224` and `:226`, inside that section.
- No earlier section (v1.1.x and before) names it.

**H3. VERSION → plugin.json `version`** (`tools/render_plugin_spike.py`), in call order:
1. `main()` `:369` → `write()` `:360` (`--write`) or `check()` `:335`
2. `generated()` `:301`, which calls `version()` at `:304`
3. `version()` `:157` reads `VERSION_FILE` (`:13`) at `:158`, validates `X.Y.Z` at `:159`
4. `build_manifest(release_version)` `:168`, which sets `"version": release_version` at `:174`
5. `json_bytes()` `:164` serializes the dict
6. Result stored as `artifacts[MANIFEST]` at `:306` (`MANIFEST` = `plugin/.claude-plugin/plugin.json`, `:14`); `write()` writes it at `:363`, `check()` compares it at `:355`

**H4. Tool-restriction frontmatter (all `plugin/agents/*.md`, line 6)**
- `scout.md:6` — `tools: Read, Glob, Grep`
- `plan-verifier.md:6` — `tools: Read, Glob, Grep`
- `security-reviewer.md:6` — `tools: Read, Glob, Grep, WebSearch, WebFetch`
- `mech-executor.md:6` — `disallowedTools: Agent, Workflow`
- `executor.md:6` — `disallowedTools: Agent, Workflow`
- `security-executor.md:6` — `disallowedTools: Agent, Workflow`
- `verifier.md:6` — `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`

**H5. Non-empty `CLAUDE_CODE_SUBAGENT_MODEL` test:** `tests/test_plugin_hook.py:198` `test_nonempty_model_override_fails_closed_without_value_or_policy`. Assertions:
- `:207` `returncode == 0`
- `:208` `stdout == MODEL_OVERRIDE_DIAGNOSTIC`
- `:209` secret value `"secret-model-value"` not in stdout+stderr
- `:210` `SENTINEL` not in stdout
- `:211` `POLICY` not in stdout
- `:212` `stderr == b""`

Other tests also set it (non-exhaustive): `:292` (hostile-path test), `:511` (preflight matrix).

**H6. No version moved `Explore` from Haiku to Sonnet.** `CHANGELOG.md:12` (v1.4.2) says "`Explore` stays on Haiku in the legacy global install." No other CHANGELOG entry changes Explore's model.

**H7. Explore/scout/mech-executor group:** 0.41M output tokens, 1.9%, on the Luna profile (執行檔). Source: `docs/field-report-tokscale-2026-07.zh-TW.md:71` (row "Explore／scout／mech-executor | Luna | 0.41M | 1.9%"); the table is combined across both sessions (`:65`, "兩場合計"). Profile label defined at `:73`.

**H8. verifier REFUTED rates** (`docs/field-report-tokscale-2026-07.zh-TW.md:99`):
- Session A: 42% (CONFIRMED 78 / REFUTED 59)
- Session B: 41% (CONFIRMED 34 / REFUTED 25)

**H9. `self.assertIn(` in `tests/test_plugin.py`: 14 occurrences** (grep count).

**H10. CLAUDE_CONFIG_DIR path with spaces: none found.** `tests/test_plugin_hook.py` sets `CLAUDE_CONFIG_DIR` at `:86, :112, :151, :535, :610, :725`, all from `tempfile` or `root / "config"` paths; searches for "space" and quoted paths with spaces returned no matches. Test names are listed at `:75–:638`; none targets spaces.
