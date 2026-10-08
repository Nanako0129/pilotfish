**H1.** `tests/test_policy.py` has 12 methods ending in `_source_bound`. No other file under `tests/` has one.
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

**H2.** The earliest version is **v1.2.0 — 2026-07-14** (`CHANGELOG.md:218`). The mention is at `CHANGELOG.md:224`, which introduces the write-capable `security-executor`. It also appears at `:226` in the same entry. Later mentions are in v1.3.1 (`:192`) and v1.4.2 (`:10`, `:16`). I did not find it in the entries below v1.2.0 (v1.1.5 and older).

**H3.** The call order is `main` → `write` → `generated` → `version` → `build_manifest` → `json_bytes`, all in `tools/render_plugin_spike.py`.
1. `main()` is at `:369`. I did not read its body.
2. `write()` is at `:360`. It loops over `generated().items()` at `:361` and calls `path.write_bytes(data)` at `:363`.
3. `generated()` is at `:301`. It calls `version()` at `:304` and `build_manifest(release_version)` at `:306`, keyed by `MANIFEST`.
4. `version()` is at `:157`. It reads `VERSION_FILE` (`:13`, `ROOT / "VERSION"`) with `.read_text().strip()` at `:158`. It checks the value against `X.Y.Z` at `:159-160` and returns it.
5. `build_manifest()` is at `:168`. It puts the value in the `"version": release_version` field at `:174`.
6. `json_bytes()` is at `:164`. It serialises the document to bytes.
7. `MANIFEST` is `plugin/.claude-plugin/plugin.json` (`:14`).

**H4.** Each agent's restricting line is on line 6 of its file. Five use `disallowedTools`, which is a denylist, not a tool allowlist.
- `plugin/agents/scout.md:6`: `tools: Read, Glob, Grep`
- `plugin/agents/plan-verifier.md:6`: `tools: Read, Glob, Grep`
- `plugin/agents/security-reviewer.md:6`: `tools: Read, Glob, Grep, WebSearch, WebFetch`
- `plugin/agents/mech-executor.md:6`: `disallowedTools: Agent, Workflow`
- `plugin/agents/executor.md:6`: `disallowedTools: Agent, Workflow`
- `plugin/agents/security-executor.md:6`: `disallowedTools: Agent, Workflow`
- `plugin/agents/verifier.md:6`: `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`

**H5.** The test is `test_nonempty_model_override_fails_closed_without_value_or_policy` (`tests/test_plugin_hook.py:198`). It sets `CLAUDE_CODE_SUBAGENT_MODEL` to `secret` (`:205`). Its assertions are:
- `:207` `assertEqual(result.returncode, 0)`
- `:208` `assertEqual(result.stdout, MODEL_OVERRIDE_DIAGNOSTIC)`
- `:209` `assertNotIn(secret.encode(), result.stdout + result.stderr)`
- `:210` `assertNotIn(SENTINEL, result.stdout)`
- `:211` `assertNotIn(POLICY, result.stdout)`
- `:212` `assertEqual(result.stderr, b"")`

Other tests also use a non-empty value. `test_hook_ignores_hostile_inherited_path_for_all_output_classes` (`:282`, value at `:292`) and the preflight matrix (`:511`, `:538`) do. The test above is the dedicated one.

**H6.** No version moved `Explore` from Haiku to Sonnet. v1.4.2 (2026-09-26) moved `scout`, not `Explore`, from Haiku to Sonnet (`CHANGELOG.md:9`). The same entry says "`Explore` stays on Haiku in the legacy global install" (`:12`). I grepped `CHANGELOG.md` for `Explore` with Haiku or Sonnet and found no other such move.

**H7.** The group is Explore／scout／mech-executor (`docs/field-report-tokscale-2026-07.zh-TW.md:71`). It took **0.41M output tokens, 1.9%**, on the **Luna** model profile (the execution profile). The report's summary at `:73` puts Luna in total at 7.2%.

**H8.** The verifier REFUTED rate was **42% in Session A** (CONFIRMED 78 / REFUTED 59) and **41% in Session B** (CONFIRMED 34 / REFUTED 25), per `docs/field-report-tokscale-2026-07.zh-TW.md:99`.

**H9.** There are exactly **14** `self.assertIn(` calls in `tests/test_plugin.py`. This is a ripgrep count of matching lines, and I did not check for multiple calls on one line.

**H10.** **I found no such test.** `tests/test_plugin_hook.py` has no test with a space in a `CLAUDE_CONFIG_DIR` path, and no test or case name mentions "space". The tests set `CLAUDE_CONFIG_DIR` in these places:
- `str(config_root)` (`:86`, `:112`)
- `config_value.replace("{config}", ...)` (`:151`)
- `str(config)` (`:535`, `:611`, `:725`)
- the string `"relative"` (`:576`, `:611`)

The temp dirs come from `tempfile.TemporaryDirectory()`, with subdirectories named `config` and `fake-bin`. I searched for `spac`, quoted spaces and space-containing path literals and found nothing.
