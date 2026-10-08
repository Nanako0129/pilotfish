**H1. `_source_bound` test methods (12, all in `tests/test_policy.py`)**
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

**H2. Earliest `security-executor` mention: v1.2.0, 2026-07-14.** `CHANGELOG.md:218` (`## v1.2.0 — 2026-07-14`), with matches at `:224` and `:226`. No earlier version section matches. The `:224` and `:226` lines were shown as "[Omitted long matching line]" in one grep, but a full Read confirmed them.

**H3. VERSION → plugin.json `version` (call order)**
1. `VERSION_FILE` is `ROOT / "VERSION"` at `tools/render_plugin_spike.py:13`.
2. `version()` reads and validates the file at `:157–161`.
3. `generated()` calls `version()` into `release_version` at `:304`.
4. `generated()` passes that value to `build_manifest(release_version)` at `:306`.
5. `build_manifest()` writes `"version": release_version` at `:168–174`.
6. `json_bytes()` serializes the document at `:164–165`.
7. `MANIFEST` is `PLUGIN / ".claude-plugin" / "plugin.json"` at `:14`.
8. `main()` (`:369`) calls `write()` at `:376`, which calls `generated()` and writes bytes at `:360–363`. It then calls `check()` at `:377`, which compares against `generated()` at `:335–356`.

**H4. Tool-restricting frontmatter lines**
- `plugin/agents/security-reviewer.md:6` `tools: Read, Glob, Grep, WebSearch, WebFetch`
- `plugin/agents/security-executor.md:6` `disallowedTools: Agent, Workflow`
- `plugin/agents/executor.md:6` `disallowedTools: Agent, Workflow`
- `plugin/agents/verifier.md:6` `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`
- `plugin/agents/mech-executor.md:6` `disallowedTools: Agent, Workflow`
- `plugin/agents/plan-verifier.md:6` `tools: Read, Glob, Grep`
- `plugin/agents/scout.md:6` `tools: Read, Glob, Grep`

**H5. Non-empty `CLAUDE_CODE_SUBAGENT_MODEL` test:** `tests/test_plugin_hook.py:198` `test_nonempty_model_override_fails_closed_without_value_or_policy`. Its assertions:
1. `:207` `assertEqual(result.returncode, 0)`
2. `:208` `assertEqual(result.stdout, MODEL_OVERRIDE_DIAGNOSTIC)`
3. `:209` `assertNotIn(secret.encode(), result.stdout + result.stderr)` (secret is `"secret-model-value"`, `:199`)
4. `:210` `assertNotIn(SENTINEL, result.stdout)`
5. `:211` `assertNotIn(POLICY, result.stdout)`
6. `:212` `assertEqual(result.stderr, b"")`

**H6. Not found.** `CHANGELOG.md` has no entry moving `Explore` from Haiku to Sonnet. The closest is `CHANGELOG.md:12` (v1.4.2, 2026-09-26), which says "`Explore` stays on Haiku in the legacy global install." I searched every `Explore` and `Sonnet`/`sonnet` mention in the file.

**H7. Explore/scout/mech-executor token group:** 0.41M output tokens, 1.9%, on the **Luna** model profile. Source: `docs/field-report-tokscale-2026-07.zh-TW.md:71`. The Luna profile is the cheap execution tier in the report's GPT-5.6 gateway setup (`:23`).

**H8. Verifier REFUTED rates** (`docs/field-report-tokscale-2026-07.zh-TW.md:99`)
- Session A: 59 REFUTED (42%), against 78 CONFIRMED
- Session B: 25 REFUTED (41%), against 34 CONFIRMED

**H9. `self.assertIn(` count in `tests/test_plugin.py`: 14.** Counted by grep, which matches the literal text `self.assertIn(`.

**H10. Not found.** I searched `tests/test_plugin_hook.py` for "space", "Space", "with spaces", "spaced", "%20", and escaped `\ `, and found no matches. `CLAUDE_CONFIG_DIR` is set from `config_root = root / "config"` (`:130`, also `:374`, `:417`, and others), and `:151` and `:610` set it from paths with no spaces. The one relative-path case is `:611`.
