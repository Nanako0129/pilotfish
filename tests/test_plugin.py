"""Contract tests for the pilotfish plugin.

These replace the old policy tests, which enforced that four hand-maintained version
stamps moved together across a global-config install. A plugin has one version, in its
manifest, so that machinery is gone.

pilotfish ships no hooks and no runtime dependency of its own — it is pure markdown and
JSON, so it runs anywhere Claude Code runs, Windows included. What is worth pinning now
is the wiring: the manifest parses, every role the skill routes to is a real agent with
a pinned model, the skill routes to namespaced names, and no role teaches a subagent to
detach a process — that rule is policy now, not enforcement, but it must still hold.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("scout", "mech-executor", "executor", "verifier", "security-executor")
# Roles that can run commands. `scout` cannot — its tools allowlist has no `Bash` — so
# it is the one role whose inability to detach is structural rather than instructed.
SHELL_ROLES = tuple(r for r in ROLES if r != "scout")


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

    def test_skill_carries_the_two_unenforced_rules(self) -> None:
        """With no hook, the skill prompt is the *only* thing carrying these two rules —
        so a silent deletion would leave nothing behind and no test would notice. Both
        must read as prohibitions: an assertion that something is blocked would be a
        false claim of enforcement, which is worse than saying nothing at all."""
        skill = (ROOT / "skills/pilotfish/SKILL.md").read_text()

        # Rule 1: never route recon to the built-in Explore — it inherits the
        # main-session model and bills every search at frontier rates.
        explore_lines = [ln.lower() for ln in skill.splitlines() if "Explore" in ln]
        self.assertTrue(explore_lines, "skill no longer mentions the built-in Explore")
        for line in explore_lines:
            self.assertRegex(
                line,
                r"never|must not|do not|don't",
                "skill mentions Explore without forbidding it",
            )
            self.assertNotRegex(
                line,
                r"is blocked|is denied|cannot be (used|invoked)",
                "skill claims Explore is enforced — nothing blocks it",
            )

        # Rule 2: subagents must not detach a process.
        self.assertRegex(
            skill.lower(),
            r"(never|must not|do not|don't) detach",
            "skill does not forbid subagents detaching a process",
        )
        for marker in ("nohup", "setsid", "run_in_background"):
            self.assertIn(marker, skill, f"skill no longer names `{marker}`")

    def test_no_role_is_told_to_detach_a_process(self) -> None:
        """Verified empirically: a subagent's promoted background command is SIGTERMed
        when a foreground-spawned agent returns, and `nohup`/`setsid` dodge that only by
        escaping the harness's task tracking — which orphans the result instead. Nothing
        enforces this any more; it is policy only, in the skill prompt. No role may teach
        it either."""
        for role in ROLES:
            agent = (ROOT / "agents" / f"{role}.md").read_text().lower()
            for marker in ("nohup", "setsid", "disown"):
                self.assertNotIn(
                    marker,
                    agent.replace(f"`{marker}`", ""),  # naming it in a prohibition is fine
                    msg=f"{role} is told to detach a process",
                )

    def test_every_shell_role_is_told_not_to_detach_a_process(self) -> None:
        """The other half, and the one that actually carries the rule. With no hook, the
        prompt is the only thing standing between a subagent and a detached process — so
        a role that merely *omits* the instruction has no rule at all. Worse is a role
        that asserts detaching is "blocked": that states an enforcement which does not
        exist, and a model told the door is locked stops holding it shut itself.

        `scout` is exempt — its positive `tools: Read, Glob, Grep` allowlist means it has
        no `Bash` at all, so the capability is genuinely removed rather than merely asked
        for. That is the one place enforcement survives without a hook."""
        for role in SHELL_ROLES:
            agent = (ROOT / "agents" / f"{role}.md").read_text().lower()
            self.assertRegex(
                agent,
                r"(never|must not|do not|don't) detach",
                msg=f"{role} carries no prohibition on detaching",
            )
            self.assertNotIn(
                "blocked for subagents",
                agent,
                msg=f"{role} claims detaching is enforced — nothing enforces it",
            )


if __name__ == "__main__":
    unittest.main()
