from __future__ import annotations

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
        results = json.loads((gate / "results.json").read_text(encoding="utf-8"))
        runtime = results["runtime"]

        for prefix in ("superseded_gate", "final_gate"):
            policy = (gate / runtime[f"{prefix}_snapshot_policy"]).read_bytes()
            agents = (gate / runtime[f"{prefix}_snapshot_agents_json"]).read_text(
                encoding="utf-8"
            ).rstrip("\n").encode()

            self.assertEqual(
                hashlib.sha256(policy).hexdigest(),
                runtime[f"{prefix}_orchestration_sha256"],
            )
            self.assertEqual(
                hashlib.sha256(agents).hexdigest(),
                runtime[f"{prefix}_agents_json_sha256"],
            )

        current_policy = (ROOT / "templates/claude-md.orchestration.md").read_bytes()
        final_gate_policy = (gate / runtime["final_gate_snapshot_policy"]).read_bytes()
        completed = subprocess.run(
            [
                sys.executable,
                str(gate / "build-agents-json.py"),
                str(ROOT / "templates/agents"),
            ],
            check=True,
            capture_output=True,
        )
        self.assertEqual(
            hashlib.sha256(current_policy).hexdigest(),
            runtime["release_candidate_orchestration_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(completed.stdout.rstrip(b"\n")).hexdigest(),
            runtime["release_candidate_agents_json_sha256"],
        )
        version_stamp = re.compile(rb"pilotfish v\d+\.\d+\.\d+")
        self.assertEqual(
            version_stamp.sub(b"pilotfish v<release>", current_policy),
            version_stamp.sub(b"pilotfish v<release>", final_gate_policy),
        )
        self.assertEqual(runtime["final_gate_candidate_version_stamp"], "1.1.6")
        self.assertEqual(runtime["release_candidate_version"], "1.2.0")
        self.assertIn("version-stamp comment only", runtime["release_candidate_policy_delta_from_final_gate"])

        gate_readme = (gate / "README.md").read_text(encoding="utf-8")
        self.assertIn("SESSION_ID=\"$(python3 -c", gate_readme)
        self.assertIn('--session-id "$SESSION_ID"', gate_readme)
        self.assertIn('--resume "$SESSION_ID"', gate_readme)

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


if __name__ == "__main__":
    unittest.main()
