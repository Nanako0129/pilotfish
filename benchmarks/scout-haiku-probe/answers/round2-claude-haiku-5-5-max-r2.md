Paths are relative to the repo root. All ten questions are answered from files; none needed guessing.

**H1: 12 methods, all in `tests/test_policy.py`**
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

**H2: v1.2.0, dated 2026-07-14.** The heading is at `CHANGELOG.md:218`, and `security-executor` appears in its body at :224 and :226. No older entry mentions it. Later mentions are in v1.3.1 (:192) and v1.4.2 (:10, :12, :16).

**H3: VERSION to plugin.json.** `VERSION:1` holds `1.4.2`, and `plugin/.claude-plugin/plugin.json:5` holds `"version": "1.4.2",`. The only writer is `tools/render_plugin_spike.py`, run via `python3 tools/render_plugin_spike.py --write` (`RELEASING.md:10`). Call order:
1. `main()` (`:369`) calls `write()` at :376.
2. `write()` (`:360`) iterates `generated()` at :361.
3. `generated()` (`:301`) calls `version()` at :304.
4. `version()` (`:157`) reads `VERSION_FILE` (`:13`) and strips it at :158, checks `X.Y.Z` at :159–160, and returns at :161.
5. `generated()` calls `build_manifest(release_version)` at :306.
6. `build_manifest()` (`:168`) calls `json_bytes()` at :169 and sets `"version": release_version` at :174.
7. `json_bytes()` (`:164`) serializes with indent=2 and a trailing LF at :165.
8. `write()` runs `path.write_bytes(data)` at :363 for `MANIFEST` (`:14`).

Afterwards, `main()` calls `check()` (`:377`, defined at :335). It re-runs `generated()` (:345) and byte-compares the output with the on-disk file (:349–356).

**H4: frontmatter tool line (line 6 of each file; fences at lines 1 and 7)**
- `plugin/agents/scout.md:6`: `tools: Read, Glob, Grep`
- `plugin/agents/plan-verifier.md:6`: `tools: Read, Glob, Grep`
- `plugin/agents/security-reviewer.md:6`: `tools: Read, Glob, Grep, WebSearch, WebFetch`
- `plugin/agents/mech-executor.md:6`: `disallowedTools: Agent, Workflow`
- `plugin/agents/executor.md:6`: `disallowedTools: Agent, Workflow`
- `plugin/agents/security-executor.md:6`: `disallowedTools: Agent, Workflow`
- `plugin/agents/verifier.md:6`: `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow`

**H5: `tests/test_plugin_hook.py:198` `test_nonempty_model_override_fails_closed_without_value_or_policy`** (value `"secret-model-value"` at :199). Its assertions:
1. :207 `assertEqual(result.returncode, 0)`
2. :208 `assertEqual(result.stdout, MODEL_OVERRIDE_DIAGNOSTIC)`
3. :209 `assertNotIn(secret.encode(), result.stdout + result.stderr)`
4. :210 `assertNotIn(SENTINEL, result.stdout)`
5. :211 `assertNotIn(POLICY, result.stdout)`
6. :212 `assertEqual(result.stderr, b"")`

The helper `run_hook` (called at :201) also asserts the filesystem snapshot is unchanged (:173). Two other tests use non-empty overrides only inside subtests: :292 (in `test_hook_ignores_hostile_inherited_path_for_all_output_classes`, :282) and :511 (in `test_documented_preflight_exact_client_and_legacy_matrix`, :490).

**H6: None.** No CHANGELOG entry moves `Explore` from Haiku to Sonnet. The v1.4.2 entry says `Explore` "stays on Haiku in the legacy global install" (`CHANGELOG.md:12`, heading :5, dated 2026-09-26). The Haiku→Sonnet change in v1.4.2 was for `scout` (`CHANGELOG.md:9`). A case-insensitive search for "explore" found no other model change. The renderer also rejects `Explore` in shipped agents (`tools/render_plugin_spike.py:262–263`).

**H7: 0.41M output tokens, 1.9%, on the Luna profile.** See `docs/field-report-tokscale-2026-07.zh-TW.md:71` (columns at :63). Luna is the execution-type profile (:23). This row has no per-session split. Line :59 is a different group (Explore／scout／security-reviewer, in agent-hours, 5%).

**H8: Session A 42%, Session B 41%.** See `docs/field-report-tokscale-2026-07.zh-TW.md:99` (columns labeled Session A | Session B at :97). A is CONFIRMED 78／REFUTED 59（42%), and B is CONFIRMED 34／REFUTED 25（41%). The report gives no denominator. The listed counts yield 59/137 ≈ 43% (A) and 25/59 ≈ 42% (B).

**H9: 14.** The `self.assertIn(` calls in `tests/test_plugin.py` are on lines 89, 100, 101, 122, 127, 167, 245, 267, 271, 272, 310, 329, 358, 377.

**H10: None.** I searched `tests/test_plugin_hook.py` for "space" (case-insensitive), and there were no matches. Every `CLAUDE_CONFIG_DIR` value in the file is either a temp-dir path with fixed names (:86, :112, :151–153, :535, :610–612, :725) or a literal without spaces (`"relative-config"` at :243, `"relative"` at :611).
