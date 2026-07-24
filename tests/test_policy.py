from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROLES = (
    "scout",
    "Explore",
    "plan-verifier",
    "security-reviewer",
    "mech-executor",
    "executor",
    "verifier",
    "security-executor",
)


class PolicyContractTests(unittest.TestCase):
    def test_baton_dispatch_matrix_prompts_are_neutral_and_recorded(self) -> None:
        benchmark = ROOT / "benchmarks" / "baton-dispatch-effect"
        results = json.loads(
            (benchmark / "results.json").read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        self.assertEqual(results["schema_version"], 3)
        cue_pattern = re.compile(
            r"baton|agent|subagent|worker|\brole\b|policy|skill|delegat|"
            r"orchestrat|parallel|independent|fan-out",
            re.IGNORECASE,
        )
        prompt_contracts = (
            (
                benchmark / "prompts" / "task.txt",
                results["small_availability_observation"],
            ),
            (
                benchmark / "prompts" / "large-audit.txt",
                results["large_policy_activation_gate"],
            ),
        )
        for path, contract in prompt_contracts:
            prompt = path.read_bytes()
            self.assertIsNone(cue_pattern.search(prompt.decode("utf-8")))
            self.assertEqual(
                hashlib.sha256(prompt).hexdigest(),
                contract["prompt_file_sha256"],
            )
            self.assertEqual(
                hashlib.sha256(prompt.rstrip(b"\n")).hexdigest(),
                contract["prompt_runtime_input_sha256"],
            )

        runtime = results["shared_runtime"]
        self.assertEqual(
            results["client"]["versions_observed"], ["2.1.217", "2.1.218"]
        )
        self.assertEqual(runtime["requested_model"], "opus")
        self.assertEqual(runtime["observed_main_model"], "claude-opus-4-8")
        self.assertEqual(runtime["setting_sources"], "project,local")
        large = results["large_policy_activation_gate"]
        self.assertIn("user prompt only", large["claim_boundary"])
        self.assertIn("fully cue-free", large["claim_boundary"])
        self.assertEqual(
            large["policy_sha256"],
            "17d272b6ddd6d95a749a802f5e29dfd4625c884f8a84bf817ffc20bfca6b39bf",
        )
        self.assertEqual(large["fixture"]["domain_file_count"], 45)
        self.assertEqual(large["fixture"]["domain_total_lines"], 3032)
        baseline_ref = "refs/heads/benchmark/v1.3.1-baton-large-fixture"
        baseline_commit = "34ebabe2a26dd53de1a019607992f1ac10af245f"
        baseline_tree = "3773149bae5c514abe6d141d6fc5216e86d02574"
        self.assertEqual(large["fixture"]["baseline_ref"], baseline_ref)
        self.assertEqual(large["fixture"]["baseline_commit"], baseline_commit)
        self.assertEqual(large["fixture"]["baseline_tree"], baseline_tree)
        self.assertEqual(
            large["fixture"]["baseline_url"],
            f"https://github.com/Nanako0129/pilotfish/tree/{baseline_commit}",
        )
        replay = results["release_payload_replay"]
        self.assertEqual(replay["fixture_baseline_ref"], baseline_ref)
        self.assertEqual(replay["fixture_baseline_commit"], baseline_commit)
        self.assertEqual(replay["fixture_baseline_tree"], baseline_tree)
        self.assertEqual(
            replay["fixture_baseline_url"], large["fixture"]["baseline_url"]
        )
        for readme_name in ("README.md", "README.zh-TW.md"):
            readme = (benchmark / readme_name).read_text(encoding="utf-8")
            self.assertIn(baseline_ref.removeprefix("refs/heads/"), readme)
            self.assertIn(f"tree/{baseline_commit}", readme)
            self.assertIn("git fetch origin", readme)
        self.assertEqual(
            set(large["fixture"]["construction"]),
            {"domain-a", "domain-b", "domain-c", "domain-d"},
        )
        package = json.loads(
            (benchmark / "large-fixture" / "package.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(package["scripts"]["test"], "node verify-audit.mjs")
        harness = (benchmark / "large-fixture" / "verify-audit.mjs").read_text(
            encoding="utf-8"
        )
        for domain in ("domain-a", "domain-b", "domain-c", "domain-d"):
            self.assertIn(domain, harness)

    def test_baton_dispatch_matrix_records_activation_and_complete_dispatch(self) -> None:
        benchmark = ROOT / "benchmarks" / "baton-dispatch-effect"
        results = json.loads(
            (benchmark / "results.json").read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        traces = json.loads((benchmark / "traces.json").read_text(encoding="utf-8"))
        calls = json.loads(
            (benchmark / "agent-calls.json").read_text(encoding="utf-8")
        )
        small = results["small_availability_observation"]
        cells = {cell["name"]: cell for cell in small["cells"]}
        control = cells["control"]
        treatment = cells["treatment"]

        self.assertFalse(control["baton_listed_at_init"])
        self.assertTrue(treatment["baton_listed_at_init"])
        for cell in (control, treatment):
            self.assertTrue(cell["test_passed"])
            self.assertEqual(cell["only_change"], "?? REPORT.md")
            self.assertEqual(cell["baton_skill_call_count"], 0)
            self.assertEqual(cell["agent_call_count"], 0)
            self.assertEqual(cell["topology"], "direct main-session execution")

        self.assertEqual(
            small["gate"]["status"], "no_activation_observed_for_bounded_task"
        )
        self.assertIn("not presented as a cue-free causal A/B", small["claim_boundary"])
        self.assertEqual(
            traces["small_availability_observation"]["control"]["skill_calls"],
            [],
        )
        self.assertEqual(
            traces["small_availability_observation"]["treatment"]["skill_calls"],
            [],
        )
        self.assertEqual(calls["small_availability_observation"]["control"], [])
        self.assertEqual(calls["small_availability_observation"]["treatment"], [])
        self.assertEqual(
            sum((cell["client_reported_cost_usd"] for cell in cells.values()), Decimal("0")),
            small["total_client_reported_cost_usd"],
        )

        large = results["large_policy_activation_gate"]
        attempts = {attempt["name"]: attempt for attempt in large["attempts"]}
        self.assertEqual(small["client_version"], "2.1.217")
        self.assertEqual(
            [attempts[f"large-v131-{n}"]["client_version"] for n in (1, 2, 3, 4)],
            ["2.1.217", "2.1.217", "2.1.217", "2.1.218"],
        )
        self.assertEqual(
            sum(
                (
                    attempt["client_reported_cost_usd"]
                    for attempt in large["attempts"]
                ),
                Decimal("0"),
            ),
            large["total_client_reported_cost_usd"],
        )
        self.assertTrue(attempts["large-v131-1"]["status"].endswith("ownership_fail"))
        self.assertTrue(attempts["large-v131-2"]["status"].endswith("ownership_fail"))
        self.assertEqual(
            attempts["large-v131-3"]["status"],
            "topology_pass_runtime_limit_outcome_incomplete",
        )
        final = attempts["large-v131-4"]
        self.assertEqual(
            final["status"],
            "passed_activation_dispatch_ownership_collection_correctness",
        )
        self.assertEqual(final["baton_skill_call_count"], 1)
        self.assertEqual(final["agent_call_count"], 4)
        self.assertEqual(final["completed_agent_count"], 4)
        self.assertTrue(final["all_agents_background"])
        self.assertTrue(final["all_agent_invocations_omit_model"])
        self.assertTrue(final["agent_calls_back_to_back"])
        self.assertTrue(final["all_results_collected_before_cross_domain_check"])
        self.assertFalse(final["active_scope_overlap_observed"])
        self.assertTrue(final["test_passed"])
        self.assertFalse(final["terminal_is_error"])
        self.assertEqual(final["only_change"], "?? AUDIT.md")
        self.assertEqual(
            final["in_session_test"]["status"], "passed_before_final_edit"
        )
        self.assertLess(
            final["in_session_test"]["test_event_index"],
            final["in_session_test"]["final_edit_event_index"],
        )
        post_run = final["post_run_verification"]
        self.assertEqual(post_run["exit_code"], 0)
        self.assertEqual(post_run["audit_sha256"], final["audit_sha256"])
        self.assertEqual(post_run["only_change"], "?? AUDIT.md")
        self.assertEqual(large["effect_gate"]["status"], "passed")

        final_trace = traces["large_policy_activation_gate"]["attempts"][
            "large-v131-4"
        ]
        self.assertEqual(final_trace["top_level_tools"].count("Skill"), 1)
        self.assertEqual(final_trace["top_level_tools"].count("Agent"), 4)
        self.assertEqual(final_trace["main_domain_content_tools_while_agents_active"], [])
        self.assertTrue(final_trace["in_session_test_preceded_final_edit"])
        self.assertEqual(final_trace["post_run_verification"]["exit_code"], 0)
        self.assertLess(
            max(final_trace["completion_event_indexes"]),
            min(final_trace["post_collection_cross_domain_check_event_indexes"]),
        )
        final_calls = calls["large_policy_activation_gate"]["large-v131-4"]
        self.assertEqual(len(final_calls), 4)
        self.assertEqual(
            {call["exclusive_read_scope"] for call in final_calls},
            {"domain-a", "domain-b", "domain-c", "domain-d"},
        )
        for call in final_calls:
            self.assertEqual(call["subagent_type"], "scout")
            self.assertTrue(call["run_in_background"])
            self.assertFalse(call["invocation_model_present"])
            self.assertEqual(call["status"], "completed")
            self.assertEqual(call["observed_model"], "claude-haiku-4-5-20251001")

        release = results["release_payload_replay"]
        self.assertIn("user prompt only", release["claim_boundary"])
        self.assertIn("fully cue-free", release["claim_boundary"])
        self.assertEqual(
            release["status"],
            "passed_activation_dispatch_ownership_collection_final_byte_correctness",
        )
        self.assertEqual(release["policy_sha256"], large["policy_sha256"])
        self.assertEqual(
            release["agents_json_sha256"],
            "0b42c137daf4006a9c85b201c9434e13640fce69fb10fcf0fba6ba2b1379723c",
        )
        self.assertEqual(release["baton_skill_call_count"], 1)
        self.assertEqual(release["agent_call_count"], 4)
        self.assertEqual(release["completed_agent_count"], 4)
        self.assertTrue(release["all_agents_background"])
        self.assertTrue(release["all_agent_invocations_omit_model"])
        self.assertTrue(release["agent_calls_back_to_back"])
        self.assertTrue(release["all_results_collected_before_cross_domain_check"])
        self.assertFalse(release["active_scope_overlap_observed"])
        self.assertEqual(release["only_change"], "?? AUDIT.md")
        self.assertTrue(release["test_passed"])
        self.assertFalse(release["terminal_is_error"])
        self.assertEqual(
            release["in_session_test"]["status"], "passed_after_final_write"
        )
        self.assertLess(
            release["in_session_test"]["write_event_index"],
            release["in_session_test"]["test_event_index"],
        )
        self.assertEqual(
            release["post_run_verification"]["audit_sha256"],
            release["audit_sha256"],
        )

        release_trace = traces["release_payload_replay"][
            "large-v131-release-payload-replay"
        ]
        self.assertEqual(release_trace["top_level_tools"].count("Skill"), 1)
        self.assertEqual(release_trace["top_level_tools"].count("Agent"), 4)
        self.assertEqual(
            release_trace["main_domain_content_tools_while_agents_active"], []
        )
        self.assertTrue(release_trace["in_session_test_followed_final_write"])
        self.assertLess(
            max(release_trace["completion_event_indexes"]),
            min(release_trace["post_collection_cross_domain_check_event_indexes"]),
        )
        release_calls = calls["release_payload_replay"][
            "large-v131-release-payload-replay"
        ]
        self.assertEqual(len(release_calls), 4)
        self.assertEqual(
            {call["exclusive_read_scope"] for call in release_calls},
            {"domain-a", "domain-b", "domain-c", "domain-d"},
        )
        for call in release_calls:
            self.assertEqual(call["subagent_type"], "scout")
            self.assertTrue(call["run_in_background"])
            self.assertFalse(call["invocation_model_present"])
            self.assertEqual(call["status"], "completed")
            self.assertEqual(call["observed_model"], "claude-haiku-4-5-20251001")

        for readme in ("README.md", "README.zh-TW.md"):
            content = (benchmark / readme).read_text(encoding="utf-8")
            self.assertIn("large-v131-4", content)
            self.assertIn("0b42c137", content)
            self.assertIn("release-payload", content)
            self.assertIn("0.1.1", content)
            self.assertIn("results.json", content)

    def test_spontaneous_dispatch_inputs_are_cue_free_and_recorded(self) -> None:
        benchmark = ROOT / "benchmarks" / "spontaneous-dispatch"
        results = json.loads((benchmark / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(results["schema_version"], 2)
        contract = results["input_contract"]
        prompts = {
            "mechanical": benchmark / "prompts" / "mechanical.txt",
            "bug": benchmark / "prompts" / "bug.txt",
        }
        cue_pattern = re.compile(
            r"agent|subagent|worker|\brole\b|policy|baton|parallel|independent|"
            r"delegat|orchestrat|fan-out",
            re.IGNORECASE,
        )

        for name, path in prompts.items():
            prompt = path.read_bytes()
            self.assertIsNone(cue_pattern.search(prompt.decode("utf-8")))
            self.assertEqual(
                hashlib.sha256(prompt).hexdigest(),
                contract[f"{name}_prompt_file_sha256"],
            )
            self.assertEqual(
                hashlib.sha256(prompt.rstrip(b"\n")).hexdigest(),
                contract[f"{name}_runtime_prompt_sha256"],
            )

        fixtures = {
            "mechanical": (
                ROOT
                / "benchmarks"
                / "dispatch-brake"
                / "positive-controls"
                / "mechanical"
                / "fixture"
            ),
            "bug": ROOT / "benchmarks" / "dispatch-brake" / "fixture",
        }
        for name, fixture in fixtures.items():
            fixture_hash_lines = []
            for path in sorted(path for path in fixture.rglob("*") if path.is_file()):
                self.assertIsNone(cue_pattern.search(path.read_text(encoding="utf-8")))
                relative = path.relative_to(ROOT)
                fixture_hash_lines.append(
                    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}\n"
                )
            fixture_digest = hashlib.sha256(
                "".join(fixture_hash_lines).encode()
            ).hexdigest()
            self.assertEqual(fixture_digest, contract[f"{name}_fixture_digest"])
        self.assertNotIn(
            "Do not optimize for or against delegation",
            (benchmark / "README.md").read_text(encoding="utf-8"),
        )

    def test_spontaneous_dispatch_baseline_is_additive_and_evidence_bound(self) -> None:
        benchmark = ROOT / "benchmarks" / "spontaneous-dispatch"
        results = json.loads((benchmark / "results.json").read_text(encoding="utf-8"))
        traces = json.loads((benchmark / "traces.json").read_text(encoding="utf-8"))
        calls = json.loads((benchmark / "agent-calls.json").read_text(encoding="utf-8"))
        runs = {run["name"]: run for run in results["runs"]}

        fable = runs["fable-v1.3.0-mechanical-baseline"]
        self.assertEqual(fable["observed_main_model"], "claude-fable-5")
        self.assertEqual(fable["status"], "usage_credits_required")
        self.assertEqual(fable["duration_api_ms"], 0)
        self.assertEqual(fable["reported_cost_usd"], 0)
        self.assertEqual(fable["agent_call_count"], 0)
        self.assertFalse(fable["source_mutation_observed"])
        self.assertIn("No behavior", fable["claim"])

        opus = runs["opus-v1.3.0-mechanical-baseline"]
        self.assertEqual(opus["observed_main_model"], "claude-opus-4-8")
        self.assertEqual(opus["status"], "success_topology_fail")
        self.assertEqual((opus["tests_passed"], opus["tests_failed"]), (12, 0))
        self.assertEqual(opus["agent_call_count"], 0)
        self.assertTrue(opus["source_mutation_observed"])
        self.assertIn("topology failed", opus["claim"])

        candidate_mechanical = runs["opus-v1.3.1-candidate-1-mechanical"]
        self.assertEqual(candidate_mechanical["status"], "passed")
        self.assertEqual(
            candidate_mechanical["observed_main_model"], "claude-opus-4-8"
        )
        self.assertEqual(candidate_mechanical["agent_call_count"], 1)
        self.assertEqual(candidate_mechanical["agent_type"], "mech-executor")
        self.assertFalse(candidate_mechanical["agent_invocation_model_present"])
        self.assertFalse(candidate_mechanical["main_source_mutation_observed"])
        self.assertTrue(candidate_mechanical["worker_is_sole_source_mutation_path"])
        self.assertEqual(candidate_mechanical["tests_after"], "12/12 passed")

        candidate_bug = runs["opus-v1.3.1-candidate-1-bug"]
        self.assertEqual(candidate_bug["status"], "passed")
        self.assertEqual(candidate_bug["agent_call_count"], 0)
        self.assertTrue(candidate_bug["main_owned_first_minimal_fix"])
        self.assertTrue(candidate_bug["main_observed_post_fix_pass"])
        self.assertEqual(candidate_bug["tests_after"], "2/2 passed")

        release_input = results["policy_inputs"]["v1.3.1-release-payload"]
        self.assertEqual(
            release_input["policy_sha256"],
            "17d272b6ddd6d95a749a802f5e29dfd4625c884f8a84bf817ffc20bfca6b39bf",
        )
        self.assertEqual(
            release_input["agents_json_sha256"],
            "0b42c137daf4006a9c85b201c9434e13640fce69fb10fcf0fba6ba2b1379723c",
        )

        release_mechanical = runs["opus-v1.3.1-release-payload-mechanical"]
        self.assertEqual(release_mechanical["status"], "passed")
        self.assertEqual(release_mechanical["agent_call_count"], 1)
        self.assertEqual(release_mechanical["agent_type"], "mech-executor")
        self.assertFalse(release_mechanical["agent_invocation_model_present"])
        self.assertEqual(
            release_mechanical["observed_agent_model"], "claude-sonnet-5"
        )
        self.assertFalse(release_mechanical["main_source_mutation_observed"])
        self.assertTrue(release_mechanical["worker_is_sole_source_mutation_path"])
        self.assertEqual(release_mechanical["tests_after"], "12/12 passed")
        self.assertEqual(
            release_mechanical["independent_post_run_test"]["tests_failed"], 0
        )

        release_bug = runs["opus-v1.3.1-release-payload-bug"]
        self.assertEqual(release_bug["status"], "passed")
        self.assertEqual(release_bug["agent_call_count"], 0)
        self.assertTrue(release_bug["main_owned_first_minimal_fix"])
        self.assertTrue(release_bug["main_observed_post_fix_pass"])
        self.assertEqual(release_bug["tests_after"], "2/2 passed")
        self.assertEqual(release_bug["independent_post_run_test"]["tests_failed"], 0)

        for run_name in runs:
            self.assertIn(run_name, traces["runs"])
            self.assertIn(run_name, calls["runs"])
        self.assertEqual(calls["runs"]["fable-v1.3.0-mechanical-baseline"], [])
        self.assertEqual(calls["runs"]["opus-v1.3.0-mechanical-baseline"], [])
        self.assertEqual(
            calls["runs"]["opus-v1.3.1-candidate-1-mechanical"][0][
                "subagent_type"
            ],
            "mech-executor",
        )
        self.assertFalse(
            calls["runs"]["opus-v1.3.1-candidate-1-mechanical"][0][
                "invocation_model_present"
            ]
        )
        self.assertEqual(calls["runs"]["opus-v1.3.1-candidate-1-bug"], [])
        self.assertIn(
            "Bash",
            traces["runs"]["opus-v1.3.0-mechanical-baseline"][
                "main_source_write_tools"
            ],
        )
        candidate_trace = traces["runs"]["opus-v1.3.1-candidate-1-mechanical"]
        self.assertEqual(candidate_trace["top_level_source_write_tools"], [])
        self.assertEqual(candidate_trace["top_level_tools"].count("Agent"), 1)
        bug_trace = traces["runs"]["opus-v1.3.1-candidate-1-bug"]
        self.assertEqual(bug_trace["agent_calls"], [])
        self.assertLess(
            bug_trace["first_minimal_fix_tool_index"],
            bug_trace["post_fix_passing_test_tool_index"],
        )
        release_call = calls["runs"][
            "opus-v1.3.1-release-payload-mechanical"
        ][0]
        self.assertEqual(release_call["observed_model"], "claude-sonnet-5")
        release_mechanical_trace = traces["runs"][
            "opus-v1.3.1-release-payload-mechanical"
        ]
        self.assertEqual(
            release_mechanical_trace["top_level_source_write_tools"], []
        )
        self.assertEqual(
            release_mechanical_trace["top_level_tools"].count("Agent"), 1
        )
        release_bug_trace = traces["runs"]["opus-v1.3.1-release-payload-bug"]
        self.assertEqual(release_bug_trace["agent_calls"], [])
        self.assertLess(
            release_bug_trace["first_minimal_fix_tool_index"],
            release_bug_trace["post_fix_passing_test_tool_index"],
        )

    def test_baton_gate_snapshot_matches_recorded_hashes(self) -> None:
        gate = ROOT / "benchmarks" / "baton-compatibility"
        results = json.loads(
            (gate / "results.json").read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        runtime = results["runtime"]
        self.assertEqual(results["final_gate_status"], "complete")
        self.assertEqual(results["final_gate"]["status"], "passed")

        superseded_policy = (gate / runtime["superseded_gate_snapshot_policy"]).read_bytes()
        superseded_agents = (
            gate / runtime["superseded_gate_snapshot_agents_json"]
        ).read_text(encoding="utf-8").rstrip("\n").encode()
        self.assertEqual(
            hashlib.sha256(superseded_policy).hexdigest(),
            runtime["superseded_gate_orchestration_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(superseded_agents).hexdigest(),
            runtime["superseded_gate_agents_json_sha256"],
        )

        current_policy = (ROOT / "templates/claude-md.orchestration.md").read_bytes()
        snapshot_policy = (gate / runtime["final_gate_snapshot_policy"]).read_bytes()
        snapshot_agents = (
            gate / runtime["final_gate_snapshot_agents_json"]
        ).read_bytes().rstrip(b"\n")
        completed = subprocess.run(
            [
                sys.executable,
                str(gate / "build-agents-json.py"),
                str(ROOT / "templates/agents"),
            ],
            check=True,
            capture_output=True,
        )
        self.assertNotEqual(current_policy, snapshot_policy)
        self.assertEqual(
            runtime["release_candidate_orchestration_sha256"],
            "17d272b6ddd6d95a749a802f5e29dfd4625c884f8a84bf817ffc20bfca6b39bf",
        )
        self.assertEqual(
            runtime["release_candidate_agents_json_sha256"],
            "0b42c137daf4006a9c85b201c9434e13640fce69fb10fcf0fba6ba2b1379723c",
        )
        self.assertEqual(
            hashlib.sha256(current_policy).hexdigest(),
            "b42bd2f0d6c4be23472020cc107d6ceb4ab0eb34553ccfcac5fe6e65c9164b4b",
        )
        self.assertEqual(
            hashlib.sha256(completed.stdout.rstrip(b"\n")).hexdigest(),
            "f272948d82cd4320f24ca849f884f5e1b74c04c23d28271753281bfdd9ffcaba",
        )
        release = results["v1_3_2_release_gate"]
        post_gate = results["v1_3_2_post_gate_role_change"]
        release_policy = (gate / release["snapshot_policy"]).read_bytes()
        release_agents_file = (gate / release["snapshot_agents_json"]).read_bytes()
        self.assertEqual(release_policy, current_policy)
        self.assertNotEqual(
            release_agents_file.rstrip(b"\n"), completed.stdout.rstrip(b"\n")
        )
        self.assertEqual(
            hashlib.sha256(completed.stdout.rstrip(b"\n")).hexdigest(),
            post_gate["agents_json_runtime_sha256_after"],
        )
        self.assertEqual(
            release["agents_json_runtime_sha256"],
            post_gate["agents_json_runtime_sha256_before"],
        )
        self.assertEqual(
            hashlib.sha256(release_policy).hexdigest(),
            release["orchestration_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(release_agents_file).hexdigest(),
            release["agents_json_file_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(release_agents_file.rstrip(b"\n")).hexdigest(),
            release["agents_json_runtime_sha256"],
        )
        for prompt_name, expected in release["prompt_file_hashes"].items():
            prompt = (gate / "prompts" / prompt_name).read_bytes()
            self.assertEqual(hashlib.sha256(prompt).hexdigest(), expected)
            self.assertEqual(
                hashlib.sha256(prompt.rstrip(b"\n")).hexdigest(),
                release["prompt_runtime_input_hashes"][prompt_name],
            )
        opus5 = results["v1_3_2_opus5_release_gate"]
        opus5_policy = (gate / opus5["snapshot_policy"]).read_bytes()
        opus5_agents = (gate / opus5["snapshot_agents_json"]).read_bytes()
        opus5_settings = (gate / opus5["snapshot_settings"]).read_bytes()
        self.assertEqual(opus5_policy, current_policy)
        self.assertEqual(
            hashlib.sha256(opus5_policy).hexdigest(),
            opus5["orchestration_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(opus5_agents).hexdigest(),
            opus5["agents_json_file_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(opus5_agents.rstrip(b"\n")).hexdigest(),
            opus5["agents_json_runtime_sha256"],
        )
        self.assertEqual(
            opus5_agents.rstrip(b"\n"),
            completed.stdout.rstrip(b"\n"),
        )
        self.assertEqual(
            hashlib.sha256(opus5_settings).hexdigest(),
            opus5["settings_sha256"],
        )
        self.assertEqual(
            json.loads(opus5_settings),
            {"model": "opus", "fallbackModel": ["sonnet"]},
        )
        for prompt_name, expected in opus5["prompt_file_hashes"].items():
            prompt = (gate / "prompts" / prompt_name).read_bytes()
            self.assertEqual(hashlib.sha256(prompt).hexdigest(), expected)
            self.assertEqual(
                hashlib.sha256(prompt.rstrip(b"\n")).hexdigest(),
                opus5["prompt_runtime_input_hashes"][prompt_name],
            )
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(runtime["final_gate_candidate_version_stamp"], "1.3.1")
        self.assertEqual(runtime["release_candidate_version"], "1.3.1")
        self.assertEqual(version, "1.3.2")
        self.assertTrue(
            runtime["release_candidate_policy_delta_from_final_gate"].startswith(
                "non-empty"
            )
        )
        self.assertEqual(
            runtime["release_candidate_agents_json_delta_from_final_gate"],
            "executor role model changed opus to sonnet (issue #18, tier-collapse fix); every other role frontmatter is unchanged",
        )
        final_policy = (gate / runtime["final_gate_snapshot_policy"]).read_bytes()
        self.assertEqual(
            hashlib.sha256(final_policy).hexdigest(),
            runtime["final_gate_orchestration_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(snapshot_agents).hexdigest(),
            runtime["final_gate_agents_json_sha256"],
        )
        self.assertEqual(
            runtime["final_gate_candidate_agents_json_sha256"],
            runtime["final_gate_agents_json_sha256"],
        )
        self.assertNotEqual(snapshot_agents, completed.stdout.rstrip(b"\n"))
        snapshot_payload = json.loads(snapshot_agents)
        candidate_payload = json.loads(completed.stdout)
        snapshot_executor = snapshot_payload.pop("executor")
        candidate_executor = candidate_payload.pop("executor")
        snapshot_plan_verifier = snapshot_payload.pop("plan-verifier")
        candidate_plan_verifier = candidate_payload.pop("plan-verifier")
        self.assertEqual(snapshot_executor["model"], "opus")
        self.assertEqual(candidate_executor["model"], "sonnet")
        snapshot_executor["model"] = candidate_executor["model"]
        self.assertEqual(snapshot_executor, candidate_executor)
        self.assertEqual(
            snapshot_plan_verifier["model"], candidate_plan_verifier["model"]
        )
        self.assertEqual(
            snapshot_plan_verifier["tools"], candidate_plan_verifier["tools"]
        )
        self.assertNotEqual(
            snapshot_plan_verifier["prompt"], candidate_plan_verifier["prompt"]
        )
        self.assertIn("program envelope", candidate_plan_verifier["prompt"])
        self.assertIn("Blocker:", candidate_plan_verifier["prompt"])
        self.assertEqual(snapshot_payload, candidate_payload)
        prompt_1 = (gate / "prompts" / "turn-1.txt").read_bytes()
        prompt_2 = (gate / "prompts" / "turn-2.txt").read_bytes()
        prompt_1_file_hash = hashlib.sha256(prompt_1).hexdigest()
        prompt_2_file_hash = hashlib.sha256(prompt_2).hexdigest()
        prompt_1_runtime_hash = hashlib.sha256(prompt_1.rstrip(b"\n")).hexdigest()
        prompt_2_runtime_hash = hashlib.sha256(prompt_2.rstrip(b"\n")).hexdigest()
        self.assertEqual(
            prompt_1_file_hash,
            "45dbe7b6b24cb5838ebf4219011797b61f172fcc18f0ca5039144017e93fcca7",
        )
        self.assertEqual(
            prompt_2_file_hash,
            "82d833090ba91982651de9ac4beed8fc96311119c6eb9c6f0304c292821918e7",
        )
        self.assertEqual(
            prompt_1_runtime_hash,
            "d2ad46b7ecfb503f8f7185d6d68f404d326f1a4a480b9141d1a80318a746bb73",
        )
        self.assertEqual(
            prompt_2_runtime_hash,
            "93ae95d1cd4eebca91ab42a06d484e180f46dd1f327e471a5a4fd2a27ca2f344",
        )
        self.assertEqual(
            prompt_1_file_hash, runtime["final_gate_prompt_turn_1_file_sha256"]
        )
        self.assertEqual(
            prompt_2_file_hash, runtime["final_gate_prompt_turn_2_file_sha256"]
        )
        self.assertEqual(
            prompt_1_runtime_hash,
            runtime["final_gate_prompt_turn_1_runtime_input_sha256"],
        )
        self.assertEqual(
            prompt_2_runtime_hash,
            runtime["final_gate_prompt_turn_2_runtime_input_sha256"],
        )
        self.assertEqual(
            results["final_gate"]["prompt_file_hashes"]["turn-1.txt"],
            prompt_1_file_hash,
        )
        self.assertEqual(
            results["final_gate"]["prompt_file_hashes"]["turn-2.txt"],
            prompt_2_file_hash,
        )
        self.assertEqual(
            results["final_gate"]["prompt_runtime_input_hashes"]["turn-1.txt"],
            prompt_1_runtime_hash,
        )
        self.assertEqual(
            results["final_gate"]["prompt_runtime_input_hashes"]["turn-2.txt"],
            prompt_2_runtime_hash,
        )

        gate_readme = (gate / "README.md").read_text(encoding="utf-8")
        self.assertIn("SESSION_ID=\"$(python3 -c", gate_readme)
        self.assertIn('--session-id "$SESSION_ID"', gate_readme)
        self.assertIn('--resume "$SESSION_ID"', gate_readme)

        turn_1_prompt = (gate / "prompts" / "turn-1.txt").read_text(encoding="utf-8")
        self.assertIn("The Plan must require", turn_1_prompt)
        self.assertIn("fresh existing named `verifier`", turn_1_prompt)
        self.assertIn("`plan-verifier` must return REVISE", turn_1_prompt)

        controls = (
            ROOT
            / "benchmarks"
            / "dispatch-brake"
            / "positive-controls"
            / "README.md"
        ).read_text(encoding="utf-8")
        self.assertIn("--model claude-opus-4-8", controls)

    def test_version_stamps_move_together(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"<!-- pilotfish v{version} -->", policy)

        for readme in ("README.md", "README.zh-TW.md"):
            content = (ROOT / readme).read_text(encoding="utf-8")
            self.assertIn(f"git clone --branch v{version} --depth 1", content)

    def test_installer_requires_tool_enforcing_runtime(self) -> None:
        installer = (ROOT / "install/AGENT-INSTALL.md").read_text(encoding="utf-8")
        self.assertIn("claude --version", installer)
        self.assertIn("Claude Code 2.1.219 or newer", installer)
        self.assertIn("does not guarantee one exact backend", installer)
        self.assertIn("stop before presenting a write plan or changing anything", installer)
        self.assertIn("depend on enforced tool exclusion", installer)

        for readme in ("README.md", "README.zh-TW.md"):
            content = (ROOT / readme).read_text(encoding="utf-8")
            self.assertIn("2.1.219", content)
            self.assertIn("remove the eight pilotfish agent files", content)
            self.assertIn("`mech-executor`", content)
            self.assertIn("`verifier`", content)

    def test_fresh_install_defaults_to_opus_with_sonnet_fallback(self) -> None:
        settings = json.loads(
            (ROOT / "templates/settings.snippet.json").read_text(encoding="utf-8")
        )
        self.assertEqual(settings["model"], "opus")
        self.assertEqual(settings["fallbackModel"], ["sonnet"])

        installer = (ROOT / "install/AGENT-INSTALL.md").read_text(encoding="utf-8")
        self.assertIn('If absent → set `"opus"`', installer)
        self.assertIn('If absent → add `["sonnet"]`', installer)
        self.assertIn("Never replace an existing", installer)
        self.assertIn("Claude Code 2.1.219", installer)
        self.assertIn("provider, account, and settings", installer)

    def test_mechanical_replay_fetches_pinned_snapshot(self) -> None:
        pinned = "863b117b9da42179c5bb77a05158920fbc092ee2"
        for readme in (
            "benchmarks/dispatch-brake/positive-controls/README.md",
            "benchmarks/dispatch-brake/positive-controls/README.zh-TW.md",
        ):
            content = (ROOT / readme).read_text(encoding="utf-8")
            fetch = f'fetch --depth 1 origin "$PINNED"'
            worktree = 'worktree add --detach "$SNAPSHOT" "$PINNED"'
            self.assertIn(f"PINNED={pinned}", content)
            self.assertIn(fetch, content)
            self.assertIn(worktree, content)
            self.assertLess(content.index(fetch), content.index(worktree))

    def test_every_named_role_owns_its_model(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("omit the `model` argument entirely", policy)
        self.assertIn("invocation-level model overrides the role definition", policy)
        self.assertIn("ad-hoc agent that has no named role definition", policy)

        for role in ROLES:
            agent = (ROOT / "templates" / "agents" / f"{role}.md").read_text(
                encoding="utf-8"
            )
            frontmatter = agent.split("---", 2)[1]
            self.assertRegex(frontmatter, rf"(?m)^name:\s*{re.escape(role)}\s*$")
            self.assertRegex(frontmatter, r"(?m)^model:\s*\S+\s*$")
            self.assertIn(f"`{role}`", policy)

    def test_default_implementation_tier_stays_below_opus_main_loop(self) -> None:
        # Regression for #18: the main session defaults to Opus. The default
        # delegated implementation role must stay below that tier. Review and
        # security roles deliberately remain on Opus for their separate
        # capability and trust-boundary requirements.
        expected_models = {
            "scout": "haiku",
            "Explore": "haiku",
            "plan-verifier": "opus",
            "security-reviewer": "opus",
            "mech-executor": "sonnet",
            "executor": "sonnet",
            "verifier": "opus",
            "security-executor": "opus",
        }
        for role, expected_model in expected_models.items():
            frontmatter = (
                (ROOT / "templates" / "agents" / f"{role}.md")
                .read_text(encoding="utf-8")
                .split("---", 2)[1]
            )
            self.assertRegex(
                frontmatter,
                rf"(?m)^model:\s*{re.escape(expected_model)}\s*$",
                f"{role} should default to {expected_model}",
            )
        # executor now shares mech-executor's Sonnet tier: it is the default
        # delegated implementation path, and must not sit at the same tier as
        # the Opus main loop. verifier deliberately retains its separate
        # Opus binding for the acceptance-boundary role.
        self.assertEqual(expected_models["executor"], expected_models["mech-executor"])
        self.assertNotEqual(expected_models["executor"], expected_models["verifier"])

    def test_policy_uses_phase_specific_dispatch_brakes(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("phase-aware lifecycle", policy)
        self.assertIn("Discovery needs a stable research contract", policy)
        self.assertIn("not a pre-decided implementation outcome", policy)
        self.assertIn("No source edit or implementation brief before required approval", policy)
        self.assertIn("A broad initial request is not approval", policy)
        self.assertIn("Main session synthesizes the evidence into one Plan", policy)
        self.assertIn("workers would repeatedly depend", policy)
        self.assertIn("main session's evolving evidence", policy)

    def test_policy_brakes_tightly_coupled_execution(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("root-cause discovery", policy)
        self.assertIn("trace-driven debugging", policy)
        self.assertIn("tightly coupled state propagation", policy)
        self.assertIn("single unknown bug", policy)
        self.assertIn("sequential `scout` → `executor` pipeline", policy)
        self.assertIn("does not own or block the main diagnosis", policy)
        self.assertIn("without rediscovery", policy)
        self.assertIn("non-positive net benefit", policy)

    def test_policy_uses_rebuttable_mechanical_default(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("stable multi-file mechanical repetition", policy)
        self.assertIn("complete one-shot brief", policy)
        self.assertIn("exclusive ownership", policy)
        self.assertIn("per-item acceptance", policy)
        self.assertIn(
            "dispatch exactly one `mech-executor` before the main session edits by default",
            policy,
        )
        self.assertIn("before editing", policy)
        for blocker in (
            "evolving/coupled evidence",
            "ownership or integration conflict",
            "worker unavailable",
            "non-positive net benefit",
        ):
            self.assertIn(blocker, policy)
        self.assertIn(
            "main session owns per-item triage, exceptions, integration, and acceptance",
            policy,
        )
        self.assertIn("default is rebuttable, not unconditional", policy)
        self.assertNotIn("eligible rather than mandatory", policy)
        self.assertNotIn("direct execution being slightly faster is not a veto", policy)

    def test_policy_preserves_single_bug_and_task_local_read_guards(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("single unknown bug", policy)
        self.assertIn("initial root-cause discovery", policy)
        self.assertIn("first minimal fix", policy)
        self.assertIn("bounded task-local search/read pass stays in the main session by default", policy)
        self.assertIn("does not own or block the main diagnosis", policy)

    def test_policy_prevents_duplicate_recon_after_dispatch(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("declared read scope is temporarily exclusive", policy)
        self.assertIn("must not read or analyze that same scope", policy)
        self.assertIn("cancels or redirects the agent", policy)
        self.assertIn("declare the main-owned and agent-owned read scopes", policy)
        self.assertIn("Check every path in each subsequent Read, Glob, Grep, or Bash call", policy)
        self.assertIn("a mixed-scope command violates ownership", policy)
        self.assertIn("Do not begin cross-surface comparison", policy)
        self.assertIn("Post-result sanity checks", policy)
        self.assertIn("launch every call back-to-back", policy)
        self.assertIn("before beginning the main session's remaining work", policy)
        self.assertIn("do not interleave duplicated reconnaissance", policy)

    def test_policy_preserves_positive_delegation_paths(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("choose by net benefit", policy)
        self.assertIn("lower model cost or quota use", policy)
        self.assertIn("preserving scarce main-session context", policy)
        self.assertIn("smallest read-only structure", policy)
        self.assertIn("stays in the main session by default", policy)
        self.assertIn("surfaces are genuinely independent and substantial", policy)
        self.assertIn("external or tool latency overlaps", policy)
        self.assertIn("independent evidence or perspectives", policy)
        self.assertIn("stable multi-file mechanical repetition", policy)

    def test_policy_uses_backend_neutral_recurrence_conditions(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "stable brief",
            "one-shot brief",
            "independent and the same shape",
            "done criteria",
            "exclusive ownership",
            "per-item acceptance",
            "default is rebuttable, not unconditional",
            "main session",
            "diagnosis",
            "integration",
            "known remedy",
            "Execution work",
        ):
            self.assertIn(phrase, policy)

        for phrase in (
            "about three times",
            "feature or PR closure",
            "two REVISE rounds per Plan",
            "plan documents",
        ):
            self.assertNotIn(phrase, policy)

    def test_policy_verifies_at_coherent_boundary(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "smallest coherent integration boundary",
            "independently refuted",
            "two consecutive `REFUTED` verdicts for that claim",
            "stop automatic fix-and-reverify cycling",
            "the cap is not `CONFIRMED`",
            "user-directed continuation remains allowed",
            "substantially unchanged implementation",
            "Tests, builds, and static checks are intermediate evidence",
            "security",
            "cross-language or FFI",
            "serialization or pre-aggregation",
            "irreversible operation",
            "block later integration",
        ):
            self.assertIn(phrase, policy)
        self.assertNotIn("tests are sufficient evidence", policy)
        self.assertNotIn("tests are sufficient", policy)

    def test_policy_requires_plan_convergence_or_escalation(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "program envelope",
            "next executable slice",
            "scope, non-goals",
            "acceptance that proves the slice outcome",
            "Blocker:",
            "Evidence:",
            "Minimum revision:",
            "Acceptance check:",
            "two automatic `REVISE` verdicts for the same unit",
            "surface the blockers and options to the user",
            "substantially unchanged Plan",
            "material revision or new evidence",
            "simplify it",
            "surface the blocker to the user",
            "defer the blocked scope",
            "never silently overrule",
        ):
            self.assertIn(phrase, policy)
        self.assertNotIn("main session decides the residual disagreements", policy)

    def test_planning_skills_compose_with_role_routing(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "inspect the session's available skill names",
            policy,
        )
        self.assertIn("before applying the dispatch brake", policy)
        self.assertIn("deciding between direct and delegated work", policy)
        self.assertIn("if `baton-dispatch` is listed, invoke it", policy)
        self.assertIn("Do not pre-screen it away", policy)
        self.assertIn("topology selection is why the planning skill is present", policy)
        self.assertIn("Loading Baton is not a command to delegate", policy)
        self.assertIn("Baton may still select direct work", policy)
        self.assertIn("If it is not listed, apply this policy directly", policy)
        self.assertIn("do not search for or install it during the task", policy)
        self.assertIn("Baton may shape discovery questions", policy)
        self.assertIn("This policy remains the source for the available named roles", policy)
        self.assertIn("The two layers compose", policy)
        self.assertIn("final judgment and synthesis in the main session", policy)
        self.assertLess(
            policy.index("inspect the session's available skill names"),
            policy.index("not every task needs a ceremony"),
        )

    def test_plan_and_outcome_verification_have_separate_capabilities(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        plan_verifier = (
            ROOT / "templates/agents/plan-verifier.md"
        ).read_text(encoding="utf-8")
        verifier = (ROOT / "templates/agents/verifier.md").read_text(encoding="utf-8")
        self.assertIn("A `plan-verifier` brief requests only", policy)
        self.assertIn("an outcome `verifier` brief requests only", policy)
        self.assertIn("Never swap the two roles", policy)
        self.assertIn("tools: Read, Glob, Grep", plan_verifier)
        self.assertIn("excludes Bash, Write, Edit", plan_verifier)
        self.assertIn("READY", plan_verifier)
        self.assertIn("REVISE", plan_verifier)
        self.assertIn("explicit outcome, scope and non-goals", plan_verifier)
        self.assertIn("acceptance that proves the slice outcome", plan_verifier)
        self.assertIn("a slice-local budget", plan_verifier)
        self.assertIn("explicit stop conditions", plan_verifier)
        self.assertNotIn("CONFIRMED", plan_verifier)
        self.assertIn("CONFIRMED", verifier)
        self.assertIn("REFUTED", verifier)
        self.assertNotIn("READY", verifier)
        self.assertNotIn("REVISE", verifier)
        self.assertIn("Never plan, edit, or fix anything", verifier)

    def test_baton_harness_builds_exact_agent_definitions(self) -> None:
        builder = ROOT / "benchmarks" / "baton-compatibility" / "build-agents-json.py"
        completed = subprocess.run(
            [sys.executable, str(builder), str(ROOT / "templates" / "agents")],
            check=True,
            capture_output=True,
            text=True,
        )
        agents = json.loads(completed.stdout)
        self.assertEqual(set(agents), set(ROLES))

        for role in ROLES:
            template = (ROOT / "templates" / "agents" / f"{role}.md").read_text(
                encoding="utf-8"
            )
            _, frontmatter, prompt = template.split("---", 2)
            fields = dict(
                line.split(":", 1) for line in frontmatter.strip().splitlines()
            )
            self.assertEqual(agents[role]["model"], fields["model"].strip())
            self.assertEqual(agents[role]["effort"], fields["effort"].strip())
            self.assertEqual(agents[role]["prompt"], prompt.strip())

    def test_subagents_never_detach_long_running_processes(self) -> None:
        for role in ("executor", "mech-executor", "verifier", "security-executor"):
            agent = (ROOT / "templates" / "agents" / f"{role}.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("run commands in the foreground", agent)
            self.assertIn("Never detach", agent)
            self.assertIn("absolute working directory", agent)
            self.assertIn("required environment variable", agent)
            self.assertIn("the orchestrator runs it in that exact context", agent)
            self.assertNotIn("launch it detached", agent)

        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Long-running processes are yours, not a subagent's", policy)
        self.assertIn("spawned that agent with `run_in_background: false`", policy)
        self.assertIn("spawn any agent that might run a long command", policy)
        self.assertIn("absolute working directory or isolated worktree", policy)
        self.assertIn("rather than the parent checkout", policy)
        self.assertIn("Bash(run_in_background: true)", policy)

    def test_result_collection_and_agent_continuation_are_distinct(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Read completed output directly", policy)
        self.assertIn(
            "only resume when the task itself has changed or needs more work", policy
        )
        self.assertIn(
            "does not prevent the orchestrator from redirecting or resuming", policy
        )
        self.assertIn("Resume only for genuinely new or redirected work", policy)
        self.assertNotIn("resuming one merely makes it re-run", policy)

        for role in ("scout", "Explore"):
            agent = (ROOT / "templates" / "agents" / f"{role}.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("final message for each run", agent)
            self.assertIn("genuinely new follow-up work", agent)
            self.assertIn("another self-contained final message", agent)
            self.assertNotIn("answer a follow-up", agent)

    def test_security_role_preserves_the_approval_boundary(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        reviewer = (ROOT / "templates/agents/security-reviewer.md").read_text(
            encoding="utf-8"
        )
        executor = (ROOT / "templates/agents/security-executor.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Before required approval", policy)
        self.assertIn("tool-enforced read-only `security-reviewer`", policy)
        self.assertIn("Never send pre-approval work", policy)
        self.assertIn("tools: Read, Glob, Grep, WebSearch, WebFetch", reviewer)
        self.assertIn("excludes Bash, Write, Edit", reviewer)
        self.assertIn("approved, stable execution contract", executor)
        self.assertIn("pre-approval analysis belongs to `security-reviewer`", executor)

    def test_bilingual_docs_and_field_report_claim_boundaries(self) -> None:
        report = ROOT / "docs/field-report-tokscale-2026-07.zh-TW.md"
        self.assertTrue(report.is_file())
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("./docs/field-report-tokscale-2026-07.zh-TW.md", changelog)

        report_text = report.read_text(encoding="utf-8")
        self.assertIn("remora", report_text)
        self.assertIn("GPT-5.6", report_text)
        self.assertIn("backend-neutral", report_text)
        self.assertIn("native-Claude efficiency A/B", report_text)
        self.assertNotIn("native Claude 的最佳", report_text)

        english = (ROOT / "benchmarks/baton-compatibility/README.md").read_text(
            encoding="utf-8"
        )
        chinese = (
            ROOT / "benchmarks/baton-compatibility/README.zh-TW.md"
        ).read_text(encoding="utf-8")
        rejected_hash = (
            "64376ea52a4e67192df29d8595c180dd"
            "c5017638029759a8ac13aff87d5cca81"
        )
        for content in (english, chinese):
            self.assertIn("results.json", content)
            self.assertEqual(content.count("--max-budget-usd 6"), 2)
            self.assertNotIn("--max-budget-usd 3", content)
            self.assertIn(rejected_hash, content)
        self.assertIn("compatibility/provenance", english)
        self.assertIn("remora", english)
        self.assertIn("GPT-5.6", english)
        self.assertIn("CONFIRMED", english)
        self.assertIn("compatibility／provenance", chinese)
        self.assertIn("remora／GPT-5.6", chinese)
        self.assertIn("CONFIRMED", chinese)
        self.assertNotIn("prove native-Claude efficiency", english)
        self.assertNotIn("原生 Claude 效率提升", chinese)

        snapshot = (
            ROOT / "benchmarks/baton-compatibility/final-gate-snapshot/README.md"
        ).read_text(encoding="utf-8")
        for phrase in (
            "v1.3.1",
            "Claude Code 2.1.217",
            "--model opus",
            "runtime-tested",
            "CONFIRMED",
        ):
            self.assertIn(phrase, snapshot)
        self.assertIn("previous_final_gate", english)
        self.assertIn("previous_final_gate", chinese)
        self.assertIn("v1.3.0", english)
        self.assertIn("v1.3.0", chinese)

    def test_baton_evidence_record_granularity_and_totals(self) -> None:
        results = json.loads(
            (
                ROOT / "benchmarks/baton-compatibility/results.json"
            ).read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        self.assertEqual(results["schema_version"], 4)
        self.assertEqual(results["final_gate_status"], "complete")
        final = results["final_gate"]
        self.assertEqual(final["status"], "passed")
        self.assertEqual(final["granularity"], "invocation")
        self.assertEqual(len(final["turns"]), final["total_cli_invocations"])
        self.assertEqual(final["source_base_head"], "4d65cc94b59acec2debec37983ad0a021440d643")
        self.assertEqual(final["release_candidate_version"], "1.3.1")
        self.assertEqual(final["requested_main_model"], "opus")
        self.assertEqual(final["observed_main_model"], "claude-opus-4-8")
        self.assertEqual(final["transcript_sha256"], "6563b1c5f3d15f2640688a8509fa093364c5534f9246e0ee700e67c3469ac0b5")
        self.assertEqual(final["total_cli_invocations"], 2)
        final_metric_keys = {
            "duration_ms",
            "duration_api_ms",
            "num_turns",
            "client_reported_cost_usd",
            "models",
            "disposition",
        }
        for expected, turn in enumerate(final["turns"], 1):
            self.assertEqual(turn["cli_invocation"], expected)
            self.assertIn("prompt_turn", turn)
            self.assertEqual(turn["max_budget_usd"], 6)
            self.assertTrue(final_metric_keys <= turn.keys())
        for field, total_field in (
            ("duration_ms", "total_duration_ms"),
            ("duration_api_ms", "total_duration_api_ms"),
            ("num_turns", "total_num_turns"),
        ):
            self.assertEqual(
                sum((turn[field] for turn in final["turns"]), 0),
                final[total_field],
            )
        self.assertEqual(final["total_duration_ms"], 443281)
        self.assertEqual(final["total_duration_api_ms"], 440965)
        self.assertEqual(final["total_num_turns"], 13)
        self.assertEqual(
            sum(
                (turn["client_reported_cost_usd"] for turn in final["turns"]),
                Decimal("0"),
            ),
            final["total_client_reported_cost_usd"],
        )
        self.assertEqual(final["total_client_reported_cost_usd"], Decimal("2.8822337"))
        self.assertFalse(final["result_collection_runtime_exercised"])
        self.assertFalse(final["security_reviewer_runtime_exercised"])
        self.assertIn(
            "result_collection_background_recon_triggered",
            results["unexercised_controls"],
        )
        self.assertIn("result_collection_evidence", results["unexercised_controls"])
        self.assertTrue(final["passed"])
        self.assertEqual(
            [call["role"] for call in final["agent_calls"]],
            ["plan-verifier", "mech-executor", "verifier"],
        )
        executor_evidence = results["unexercised_controls"][
            "executor_role_evidence"
        ]
        for role in ("plan-verifier", "mech-executor", "verifier"):
            self.assertIn(role, executor_evidence)
        self.assertNotIn("scout, scout", executor_evidence)
        self.assertIn("executor and scout roles were not dispatched", executor_evidence)
        post_gate_note = results["post_gate_role_frontmatter_change"]["note"]
        self.assertIn("changed executor itself was not live-exercised", post_gate_note)
        self.assertIn("distinct mech-executor or scout roles", post_gate_note)
        self.assertTrue(all(call["invocation_model"] is None for call in final["agent_calls"]))
        self.assertTrue(all(not call["background"] for call in final["agent_calls"]))
        self.assertEqual(final["agent_calls"][0]["observed_tools"], ["Read", "Grep"])
        self.assertEqual(final["agent_calls"][1]["observed_model"], "claude-sonnet-5")
        self.assertEqual(final["agent_calls"][1]["observed_tools"], ["Bash", "Write"])
        self.assertTrue(final["agent_calls"][1]["direct_write_blocked_by_hook"])
        self.assertEqual(final["turns"][1]["integration_write_owner"], "main_session")
        self.assertEqual(final["agent_calls"][-1]["verdicts"], ["CONFIRMED"])

        release = results["v1_3_2_release_gate"]
        self.assertEqual(release["status"], "passed")
        self.assertEqual(release["granularity"], "invocation")
        self.assertEqual(release["release_candidate_version"], "1.3.2")
        self.assertEqual(len(release["turns"]), release["total_cli_invocations"])
        self.assertEqual(release["total_cli_invocations"], 2)
        self.assertEqual(release["total_duration_ms"], 445010)
        self.assertEqual(release["total_duration_api_ms"], 443416)
        self.assertEqual(release["total_num_turns"], 19)
        self.assertEqual(
            sum(
                (turn["client_reported_cost_usd"] for turn in release["turns"]),
                Decimal("0"),
            ),
            release["total_client_reported_cost_usd"],
        )
        self.assertEqual(
            release["total_client_reported_cost_usd"], Decimal("2.77709775")
        )
        self.assertEqual(
            [
                unit["id"]
                for unit in release["turns"][0]["readiness_units"]
            ],
            ["ENV-report-audit", "S1-report"],
        )
        self.assertTrue(
            all(
                unit["verdict"] == "READY"
                and unit["invocation_model"] is None
                and not unit["background"]
                for unit in release["turns"][0]["readiness_units"]
            )
        )
        self.assertEqual(
            release["turns"][1]["verifier"]["verdict"], "CONFIRMED"
        )
        self.assertTrue(release["turns"][1]["independent_final_byte_test_passed"])
        self.assertFalse(release["turns"][1]["deferred_unit_executed"])
        self.assertTrue(release["passed"])
        opus5 = results["v1_3_2_opus5_release_gate"]
        self.assertEqual(opus5["status"], "passed_with_corrective_verification")
        self.assertEqual(opus5["observed_main_model"], "claude-opus-5")
        self.assertEqual(opus5["claude_code"], "2.1.219")
        self.assertEqual(len(opus5["turns"]), opus5["total_cli_invocations"])
        self.assertEqual(opus5["total_cli_invocations"], 3)
        self.assertEqual(opus5["total_duration_ms"], 453853)
        self.assertEqual(opus5["total_duration_api_ms"], 969791)
        self.assertEqual(opus5["total_num_turns"], 12)
        self.assertEqual(
            sum(
                (turn["client_reported_cost_usd"] for turn in opus5["turns"]),
                Decimal("0"),
            ),
            opus5["total_client_reported_cost_usd"],
        )
        self.assertEqual(
            opus5["total_client_reported_cost_usd"], Decimal("5.54877495")
        )
        self.assertEqual(
            [
                unit["verdicts"]
                for unit in opus5["turns"][0]["readiness_units"]
            ],
            [["REVISE", "READY"], ["REVISE", "READY"]],
        )
        self.assertTrue(
            all(
                unit["invocation_model"] is None
                and unit["observed_model"] == "claude-opus-5"
                for unit in opus5["turns"][0]["readiness_units"]
            )
        )
        self.assertTrue(opus5["turns"][1]["post_verdict_edit"])
        self.assertFalse(opus5["turns"][1]["initial_verdict_covers_final_bytes"])
        self.assertFalse(opus5["turns"][1]["accepted_as_final"])
        self.assertEqual(opus5["turns"][2]["verifier"]["verdict"], "CONFIRMED")
        self.assertTrue(opus5["turns"][2]["independent_final_byte_test_passed"])
        self.assertFalse(opus5["exact_two_cli_invocation_contract_passed"])
        self.assertTrue(opus5["corrective_verification_closed_final_bytes"])
        self.assertTrue(opus5["result_collection_runtime_exercised"])
        self.assertFalse(opus5["fallback_model_runtime_exercised"])
        self.assertTrue(opus5["passed"])

        rejected_opus5 = results["v1_3_2_opus5_rejected_user_source_attempt"]
        self.assertEqual(rejected_opus5["status"], "rejected")
        self.assertEqual(rejected_opus5["observed_main_model"], "claude-opus-4-8")
        self.assertFalse(rejected_opus5["turn_1"]["turn_2_started"])
        self.assertEqual(
            rejected_opus5["total_client_reported_cost_usd"],
            Decimal("1.7603425"),
        )
        self.assertFalse(rejected_opus5["passed"])
        post_gate = results["v1_3_2_post_gate_role_change"]
        self.assertEqual(post_gate["role"], "plan-verifier")
        self.assertTrue(post_gate["recorded_gate_role_exercised"])
        self.assertFalse(post_gate["live_gate_rerun"])
        self.assertIn("slice-local budget", post_gate["change"])
        self.assertIn("explicit stop conditions", post_gate["change"])
        self.assertIn("static contract coverage only", post_gate["note"])

        previous_final = results["previous_final_gate"]
        self.assertEqual(previous_final["granularity"], "invocation")
        self.assertEqual(previous_final["status"], "passed")
        self.assertEqual(previous_final["release_candidate_version"], "1.3.0")
        self.assertEqual(previous_final["total_cli_invocations"], 2)
        self.assertEqual(
            previous_final["transcript_sha256"],
            "98724de501d714dcb58b315b2260147f9cdd43975f16e52297a84ed258a83ac4",
        )

        failed = results["failed_candidate_gate"]
        self.assertEqual(failed["granularity"], "invocation")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(len(failed["turns"]), failed["total_cli_invocations"])
        self.assertEqual(failed["total_cli_invocations"], 1)
        self.assertEqual(failed["total_duration_ms"], 218040)
        self.assertEqual(failed["total_duration_api_ms"], 186738)
        self.assertEqual(failed["total_num_turns"], 13)
        self.assertEqual(failed["total_client_reported_cost_usd"], Decimal("4.12912975"))
        self.assertEqual(failed["turns"][0]["disposition"], "budget_exhausted")
        self.assertEqual(failed["turns"][0]["terminal_status"], "budget_exhausted")
        self.assertEqual(failed["turns"][0]["max_budget_usd"], 3)
        self.assertTrue(failed["prompt_fix_applied_to_release_candidate"])
        self.assertTrue(failed["failure_led_to_prompt_fix"])
        self.assertEqual(
            failed["prompt_turn_1_file_sha256"],
            "edce6a591e5879769b89b0fff0f4aa8c64e038f79b93e6a804161e4f9914624f",
        )
        self.assertEqual(
            failed["prompt_turn_1_runtime_input_sha256"],
            "8aa4459acbb2f96df4617dcbf2b147c91222252a48c8fac754f344bc2d32d2fb",
        )
        self.assertEqual(
            failed["transcript_sha256"],
            "250b8cd8b53e758299b233d16c2753890a46c6284a99a8d21ba5d5e907bf7ebc",
        )

        candidate = results["superseded_candidate_gate"]
        self.assertEqual(candidate["granularity"], "invocation")
        self.assertEqual(len(candidate["turns"]), candidate["total_cli_invocations"])
        self.assertEqual(candidate["source_commit"], "40f38151581b890c7aec64218a95758045dfec57")
        metric_keys = {
            "duration_ms",
            "duration_api_ms",
            "num_turns",
            "client_reported_cost_usd",
            "models",
            "disposition",
        }
        for expected, turn in enumerate(candidate["turns"], 1):
            self.assertEqual(turn["cli_invocation"], expected)
            self.assertIn("prompt_turn", turn)
            self.assertTrue(metric_keys <= turn.keys())

        for field, total_field in (
            ("duration_ms", "total_duration_ms"),
            ("duration_api_ms", "total_duration_api_ms"),
            ("num_turns", "total_num_turns"),
        ):
            self.assertEqual(
                sum((turn[field] for turn in candidate["turns"]), 0),
                candidate[total_field],
            )
        self.assertEqual(
            sum(
                (turn["client_reported_cost_usd"] for turn in candidate["turns"]),
                Decimal("0"),
            ),
            candidate["total_client_reported_cost_usd"],
        )
        self.assertEqual(candidate["total_client_reported_cost_usd"], Decimal("4.60368875"))

        summary_keys = (
            "previous_release_gate",
            "historical_release_gate",
            "superseded_gate",
            "rejected_harness_run",
            "unexercised_controls",
        )
        for key in summary_keys:
            self.assertEqual(results[key]["granularity"], "summary")
            self.assertNotIn("turns", results[key])
        self.assertEqual(
            results["rejected_harness_run"]["transcript_sha256"],
            "64376ea52a4e67192df29d8595c180ddc5017638029759a8ac13aff87d5cca81",
        )
        self.assertEqual(results["previous_release_gate"]["release_candidate_version"], "1.2.1")
        historical = results["historical_release_gate"]
        self.assertEqual(historical["release_candidate_version"], "1.2.0")
        self.assertEqual(historical["source_commit"], "125146508587d69eab1265b00210a59d1e5b375f")
        self.assertEqual(historical["total_duration_ms"], 448148)
        self.assertEqual(historical["total_num_turns"], 22)
        self.assertEqual(historical["total_client_reported_cost_usd"], Decimal("3.7890481"))

        metric_names = {
            "duration_ms",
            "duration_api_ms",
            "num_turns",
            "client_reported_cost_usd",
        }

        def find_nested_metric_invocation(value: object, top_level_turn: bool = False) -> bool:
            if isinstance(value, dict):
                if not top_level_turn and (
                    "interrupted_invocation" in value
                    or "invocation" in value
                    or ("cli_invocation" in value and metric_names & value.keys())
                ):
                    return True
                return any(
                    find_nested_metric_invocation(child, False)
                    for child in value.values()
                )
            if isinstance(value, list):
                return any(find_nested_metric_invocation(child, False) for child in value)
            return False

        for record in (final, previous_final, failed, candidate):
            self.assertFalse(
                any(
                    find_nested_metric_invocation(turn, True)
                    for turn in record["turns"]
                )
            )
        self.assertNotIn("interrupted_invocation", json.dumps(results, default=str))


if __name__ == "__main__":
    unittest.main()
