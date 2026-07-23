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
        self.assertEqual(current_policy, snapshot_policy)
        self.assertEqual(
            hashlib.sha256(current_policy).hexdigest(),
            runtime["release_candidate_orchestration_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(completed.stdout.rstrip(b"\n")).hexdigest(),
            runtime["release_candidate_agents_json_sha256"],
        )
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(runtime["final_gate_candidate_version_stamp"], version)
        self.assertEqual(runtime["release_candidate_version"], version)
        self.assertEqual(
            runtime["release_candidate_policy_delta_from_final_gate"],
            "none; exact policy bytes",
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
        self.assertEqual(snapshot_executor["model"], "opus")
        self.assertEqual(candidate_executor["model"], "sonnet")
        snapshot_executor["model"] = candidate_executor["model"]
        self.assertEqual(snapshot_executor, candidate_executor)
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
        self.assertIn("Claude Code 2.1.207 or newer", installer)
        self.assertIn("stop before presenting a write plan or changing anything", installer)
        self.assertIn("depend on enforced tool exclusion", installer)

        for readme in ("README.md", "README.zh-TW.md"):
            content = (ROOT / readme).read_text(encoding="utf-8")
            self.assertIn("2.1.207", content)
            self.assertIn("remove the eight pilotfish agent files", content)
            self.assertIn("`mech-executor`", content)
            self.assertIn("`verifier`", content)

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
        # Regression for #18: the main session runs "best" (Fable 5, or Opus on
        # fallback). The default delegated implementation role must stay below
        # an Opus main loop. Review and security roles deliberately remain on
        # Opus for their separate capability and trust-boundary requirements.
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
        # a fallback Opus main loop. verifier deliberately retains its separate
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
        self.assertIn("eligible rather than mandatory", policy)
        self.assertIn("net benefit remains positive", policy)

    def test_policy_preserves_positive_delegation_paths(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("choose by net benefit", policy)
        self.assertIn("lower model cost or quota use", policy)
        self.assertIn("preserving scarce main-session context", policy)
        self.assertIn("direct execution being slightly faster is not a veto", policy)
        self.assertIn("smallest read-only structure", policy)
        self.assertIn("stays in the main session by default", policy)
        self.assertIn("surfaces are genuinely independent and substantial", policy)
        self.assertIn("external or tool latency overlaps", policy)
        self.assertIn("independent evidence or perspectives", policy)
        self.assertIn("stable multi-file repetition", policy)

    def test_policy_uses_backend_neutral_recurrence_conditions(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "stable brief",
            "one-shot brief",
            "independent and the same shape",
            "done criteria",
            "ownership",
            "per-item acceptance",
            "Delegation is conditional, not mandatory",
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
        self.assertIn("A delegation-planning skill may shape discovery questions", policy)
        self.assertIn("This policy remains the source for the available named roles", policy)
        self.assertIn("The two layers compose", policy)
        self.assertIn("final judgment and synthesis in the main session", policy)

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
            "v1.3.0",
            "v1.2.1",
            "v1.2.0",
            "40f3815",
            "runtime-tested",
            "CONFIRMED",
        ):
            self.assertIn(phrase, snapshot)

    def test_baton_evidence_record_granularity_and_totals(self) -> None:
        results = json.loads(
            (
                ROOT / "benchmarks/baton-compatibility/results.json"
            ).read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        self.assertEqual(results["schema_version"], 3)
        self.assertEqual(results["final_gate_status"], "complete")
        final = results["final_gate"]
        self.assertEqual(final["status"], "passed")
        self.assertEqual(final["granularity"], "invocation")
        self.assertEqual(len(final["turns"]), final["total_cli_invocations"])
        self.assertEqual(final["source_base_head"], "a38dd2dde000441b24881fa49495e545ff21b9e6")
        self.assertEqual(final["transcript_sha256"], "98724de501d714dcb58b315b2260147f9cdd43975f16e52297a84ed258a83ac4")
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
        self.assertEqual(final["total_duration_ms"], 323978)
        self.assertEqual(final["total_duration_api_ms"], 458056)
        self.assertEqual(final["total_num_turns"], 6)
        self.assertEqual(
            sum(
                (turn["client_reported_cost_usd"] for turn in final["turns"]),
                Decimal("0"),
            ),
            final["total_client_reported_cost_usd"],
        )
        self.assertEqual(final["total_client_reported_cost_usd"], Decimal("3.5088455"))
        self.assertTrue(final["result_collection_runtime_exercised"])
        self.assertFalse(final["security_reviewer_runtime_exercised"])
        self.assertNotIn(
            "result_collection_background_recon_triggered",
            results["unexercised_controls"],
        )
        self.assertNotIn("result_collection_evidence", results["unexercised_controls"])
        self.assertTrue(final["passed"])
        self.assertEqual(
            [call["role"] for call in final["agent_calls"]],
            ["scout", "scout", "plan-verifier", "mech-executor", "verifier"],
        )
        self.assertTrue(all(call["invocation_model"] is None for call in final["agent_calls"]))
        self.assertTrue(all(call["background"] for call in final["agent_calls"][:2]))
        self.assertEqual(final["agent_calls"][0]["observed_tools"], ["Read"])
        self.assertEqual(final["agent_calls"][1]["observed_tools"], ["Read", "Glob"])
        self.assertEqual(final["agent_calls"][3]["observed_model"], "claude-sonnet-5")
        self.assertEqual(final["agent_calls"][3]["observed_tools"], ["Write", "Bash"])
        self.assertEqual(final["agent_calls"][-1]["verdicts"], ["CONFIRMED"])

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

        for record in (final, failed, candidate):
            self.assertFalse(
                any(
                    find_nested_metric_invocation(turn, True)
                    for turn in record["turns"]
                )
            )
        self.assertNotIn("interrupted_invocation", json.dumps(results, default=str))


if __name__ == "__main__":
    unittest.main()
