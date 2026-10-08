H1 12 tests, all tests/test_policy.py: 452 baton_dispatch_effect_attempts, 929 cue_free_tui_attempts, 1727 issue_29_recovery_attempts, 2177 compact_policy_full_matrix_attempts, 2552 spontaneous_dispatch_attempts, 3288 verifier_boundary_attempts, 3751 verifier_paid_campaign_summary_is_source_bound, 4094 current_derived_benchmark_prose_is_source_bound, 4631 prompt_compression_attempts, 4941 dispatch_brake_attempts, 5149 dispatch_brake_positive_control_attempts, 6789 baton_compatibility_attempts
H2 v1.2.0 — 2026-07-14 (CHANGELOG.md:218; mention :224)
H3 version() render_plugin_spike.py:157 (reads VERSION_FILE) <- generated() :301 calls version() then build_manifest(release_version) :168 sets "version"; json_bytes :164; write() :360 writes MANIFEST (:14 = plugin/.claude-plugin/plugin.json). Entry main() :369 --write.
H4 plan-verifier/scout: `tools: Read, Glob, Grep`; security-reviewer: `tools: Read, Glob, Grep, WebSearch, WebFetch`; executor/mech-executor/security-executor: `disallowedTools: Agent, Workflow`; verifier: `disallowedTools: Write, Edit, NotebookEdit, Agent, Workflow` (all line 6)
H5 test_nonempty_model_override_fails_closed_without_value_or_policy :198; asserts returncode==0, stdout==MODEL_OVERRIDE_DIAGNOSTIC, secret not in stdout+stderr, SENTINEL not in stdout, POLICY not in stdout, stderr==b"" (6 assertions)
H6 TRAP: none. CHANGELOG.md:12 says Explore stays on Haiku; it was scout that moved (v1.4.2)
H7 0.41M, 1.9%, Luna (field report :71)
H8 42% (CONFIRMED 78/REFUTED 59) and 41% (34/25) (:99)
H9 14
H10 TRAP: none
