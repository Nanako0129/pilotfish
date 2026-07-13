"""Contract tests for the pilotfish plugin.

These replace the old policy tests, which enforced that four hand-maintained version
stamps moved together across a global-config install. A plugin has one version, in its
manifest, so that machinery is gone.

What is worth pinning now is the wiring: the manifest parses, the hook the plugin
promises actually exists and is executable, every role the skill routes to is a real
agent with a pinned model, and no role is told to detach a process.
"""

from __future__ import annotations

import json
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("scout", "mech-executor", "executor", "verifier", "security-executor")


class Manifest(unittest.TestCase):
    def test_plugin_manifest_is_valid(self) -> None:
        manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], "pilotfish")
        # Kebab-case, no uppercase — the name is used for namespacing.
        self.assertRegex(manifest["name"], r"^[a-z0-9-]+$")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")

    def test_marketplace_manifest_is_valid(self) -> None:
        market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        self.assertEqual(market["name"], "pilotfish")
        self.assertTrue(market["owner"]["name"])
        names = [p["name"] for p in market["plugins"]]
        self.assertIn("pilotfish", names)


class Wiring(unittest.TestCase):
    def test_hook_script_exists_and_is_executable(self) -> None:
        """A hook that points at a missing or non-executable script fails silently,
        which would turn every guarantee in this plugin back into a suggestion."""
        hooks = json.loads((ROOT / "hooks/hooks.json").read_text())
        entries = hooks["hooks"]["PreToolUse"]
        self.assertTrue(entries)
        for entry in entries:
            for hook in entry["hooks"]:
                self.assertIn("${CLAUDE_PLUGIN_ROOT}", hook["command"])
                rel = hook["command"].split("${CLAUDE_PLUGIN_ROOT}")[1].strip('"/')
                script = ROOT / rel
                self.assertTrue(script.is_file(), f"hook script missing: {rel}")
                self.assertTrue(
                    os.access(script, os.X_OK), f"hook script not executable: {rel}"
                )

    def test_guard_covers_both_tools_it_polices(self) -> None:
        hooks = json.loads((ROOT / "hooks/hooks.json").read_text())
        matchers = " ".join(e["matcher"] for e in hooks["hooks"]["PreToolUse"])
        self.assertIn("Bash", matchers)  # subagent detaching
        self.assertIn("Agent", matchers)  # the built-in Explore


class Roles(unittest.TestCase):
    def test_every_role_pins_its_own_model(self) -> None:
        """Model routing lives in the agent definition and nowhere else. If a role
        stops pinning a model it silently inherits the main session's — which is the
        entire cost problem this project exists to solve."""
        for role in ROLES:
            agent = (ROOT / "agents" / f"{role}.md").read_text()
            frontmatter = agent.split("---", 2)[1]
            self.assertRegex(frontmatter, rf"(?m)^name:\s*{re.escape(role)}\s*$")
            self.assertRegex(frontmatter, r"(?m)^model:\s*\S+\s*$")

    def test_skill_routes_to_namespaced_role_names(self) -> None:
        """A plugin registers its agents only under the `pilotfish:` prefix; a fresh
        install cannot resolve a bare `scout`. So the skill must route to the namespaced
        names, or every delegation it instructs fails on a clean machine."""
        skill = (ROOT / "skills/pilotfish/SKILL.md").read_text()
        for role in ROLES:
            self.assertIn(f"`pilotfish:{role}`", skill, f"skill never routes to pilotfish:{role}")
        # And it must not instruct a bare name that won't resolve.
        table = skill.split("| Role |")[1].split("##")[0]
        for role in ROLES:
            self.assertNotIn(f"| `{role}` ", table, f"skill routing table uses bare `{role}`")

    def test_skill_forbids_passing_model_at_invocation(self) -> None:
        skill = (ROOT / "skills/pilotfish/SKILL.md").read_text()
        self.assertIn("Never pass `model`", skill)

    def test_no_role_is_told_to_detach_a_process(self) -> None:
        """Verified empirically: a subagent's promoted background command is SIGTERMed
        when a foreground-spawned agent returns, and `nohup`/`setsid` dodge that only by
        escaping the harness's task tracking — which orphans the result instead. The
        guard blocks both; no role may teach them either."""
        for role in ROLES:
            agent = (ROOT / "agents" / f"{role}.md").read_text().lower()
            for marker in ("nohup", "setsid", "disown"):
                self.assertNotIn(
                    marker,
                    agent.replace(f"`{marker}`", ""),  # naming it in a prohibition is fine
                    msg=f"{role} is told to detach a process",
                )


if __name__ == "__main__":
    unittest.main()
