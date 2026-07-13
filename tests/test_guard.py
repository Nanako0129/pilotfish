"""Contract tests for the pilotfish PreToolUse guard.

The guard exists because instructions do not hold and capability removal does. These
tests pin the two asymmetries it enforces — both established empirically (2026-07-13),
not assumed:

  * The main session MUST keep `run_in_background` and detaching. That is the path that
    works: a background-spawned agent's promoted process survives, completes, is
    captured, and notifies. Break this and the orchestrator can no longer run long jobs.
  * A subagent MUST NOT detach. `nohup`/`setsid` escape the harness's task tracking (no
    task id, no captured output, no notification), and a foreground-spawned agent's
    promoted command is SIGTERMed seconds after it returns.

The discriminator is the presence of `agent_type` in the hook payload — absent for the
main session, present for a subagent. Verified against real captured payloads.

The shell-detach leg is best-effort (a hook sees only a string), so the evasion cases
below document what it does and does NOT catch, and the false-positive cases guard the
line the docstring warns about: a guard that blocks legitimate work gets disabled.
"""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "scripts" / "guard.py"

MAIN: dict = {"session_id": "s"}  # real shape: NO agent_type
SUB: dict = {"session_id": "s", "agent_id": "a1", "agent_type": "executor"}


def decide(payload) -> str:
    result = subprocess.run(
        ["python3", str(GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"guard crashed: {result.stderr}"
    assert result.stderr == "", f"guard wrote to stderr: {result.stderr}"
    if not result.stdout.strip():
        return "ALLOW"
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"].upper()


def bash(base: dict, command: str, background: bool | None = None) -> dict:
    tool_input: dict = {"command": command}
    if background is not None:
        tool_input["run_in_background"] = background
    return {**base, "tool_name": "Bash", "tool_input": tool_input}


def agent(base: dict, subagent_type: str) -> dict:
    return {**base, "tool_name": "Agent", "tool_input": {"subagent_type": subagent_type}}


class MainSessionKeepsItsCapabilities(unittest.TestCase):
    """The orchestrator's backgrounding is the mechanism that works. Never block it."""

    def test_main_may_background(self) -> None:
        self.assertEqual(decide(bash(MAIN, "cargo build", background=True)), "ALLOW")

    def test_main_may_detach(self) -> None:
        for command in ("nohup ./long.sh &", "./x.sh & disown", "setsid python3 t.py"):
            with self.subTest(command=command):
                self.assertEqual(decide(bash(MAIN, command)), "ALLOW")


class SubagentsCannotBackground(unittest.TestCase):
    """The structural leg — a typed parameter, so there is no spelling around it."""

    def test_run_in_background_true_is_denied(self) -> None:
        self.assertEqual(decide(bash(SUB, "cargo build", background=True)), "DENY")

    def test_run_in_background_false_is_allowed(self) -> None:
        self.assertEqual(decide(bash(SUB, "pytest -q", background=False)), "ALLOW")


class SubagentsCannotDetach(unittest.TestCase):
    """The best-effort leg — catches the natural `nohup … &` habit and its neighbours."""

    def test_natural_detach_forms_are_denied(self) -> None:
        for command in (
            "nohup ./long.sh > log 2>&1 &",  # the classic
            "setsid python3 train.py",
            "./x.sh & disown",
            "./build.sh &",  # trailing &
            "cd /tmp; nohup ./x.sh &",  # after ;
            "make || nohup ./x.sh",  # after ||
            "/usr/bin/nohup ./x.sh",  # full path — was an evasion pre-fix
            "(nohup ./x.sh &)",  # subshell — was an evasion pre-fix
            "./long.sh & sleep 1",  # mid-line backgrounding — was an evasion pre-fix
            "./long.sh & echo done",
        ):
            with self.subTest(command=command):
                self.assertEqual(decide(bash(SUB, command)), "DENY")

    def test_documented_evasions_are_known_gaps(self) -> None:
        """A string-matching hook cannot see inside a subshell or an exotic launcher.
        These pass; they are deliberate circumvention, not the accidental pattern the
        guard defends against, and the structural run_in_background leg is unaffected.
        This test documents the gaps so a future tightening is a deliberate choice."""
        for command in (
            "bash -c 'nohup ./x.sh &'",
            "eval 'nohup ./x.sh &'",
            "screen -dmS job ./x.sh",
            "systemd-run --user ./x.sh",
        ):
            with self.subTest(command=command):
                self.assertEqual(decide(bash(SUB, command)), "ALLOW")

    def test_legitimate_commands_are_not_false_positives(self) -> None:
        """A guard that blocks legitimate work gets disabled, and then protects nothing.
        Every one of these was a false-positive DENY before the command-position +
        quote-stripping fix."""
        for command in (
            "pytest -q",
            "make && pytest -q",  # && is not a background &
            "pytest -q > out.log 2>&1",  # fd redirect, not a background &
            "cat file 2>&1 | tee log",
            "grep nohup logs/",  # nohup as a search term, not a command
            "cat nohup.out",  # reading nohup's own output file
            "rm -f nohup.out",
            "git commit -m 'drop nohup usage'",  # inside a quoted string
            "echo 'run in background & wait'",  # & inside quotes
            'grep "a && b" src/',  # && inside double quotes
            "cat src/disowned_notes.md",  # substring in a path
            "echo tenohuptest",  # substring inside a word
        ):
            with self.subTest(command=command):
                self.assertEqual(decide(bash(SUB, command)), "ALLOW")


class BuiltinExploreIsUnreachable(unittest.TestCase):
    def test_builtin_explore_is_denied(self) -> None:
        self.assertEqual(decide(agent(MAIN, "Explore")), "DENY")

    def test_remediation_names_a_role_that_resolves(self) -> None:
        """A fresh install registers roles only under the `pilotfish:` namespace; bare
        `scout` does not resolve. The deny message must send the caller to the name that
        actually works, or following it fails."""
        result = subprocess.run(
            ["python3", str(GUARD)],
            input=json.dumps(agent(MAIN, "Explore")),
            capture_output=True,
            text=True,
        )
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("pilotfish:scout", reason)
        # And it must not carry a bare-name instruction that would fail if followed.
        self.assertNotIn('subagent_type: "scout"', reason)
        self.assertNotIn("`scout`", reason)

    def test_our_roles_are_allowed(self) -> None:
        for role in ("pilotfish:scout", "pilotfish:executor", "pilotfish:mech-executor",
                     "pilotfish:verifier", "pilotfish:security-executor"):
            with self.subTest(role=role):
                self.assertEqual(decide(agent(MAIN, role)), "ALLOW")


class GuardFailsOpen(unittest.TestCase):
    def test_malformed_or_odd_payloads_never_break_the_session(self) -> None:
        """Fail open on every shape — including structurally-valid-but-odd JSON, which
        an earlier version crashed on (traceback to stderr on every such call)."""
        for raw in (
            "not json",
            "",
            "[]",  # valid JSON, wrong type
            json.dumps({"tool_name": "Bash", "tool_input": "a string not a dict"}),
            json.dumps({"tool_name": "Bash", "tool_input": {"command": 123}, "agent_type": "x"}),
            json.dumps({"tool_name": "Bash", "tool_input": {}, "agent_type": "x"}),
        ):
            with self.subTest(raw=raw):
                result = subprocess.run(
                    ["python3", str(GUARD)], input=raw, capture_output=True, text=True
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "", f"crashed on {raw!r}: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
