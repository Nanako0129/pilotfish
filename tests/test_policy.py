from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROLES = (
    "scout",
    "Explore",
    "mech-executor",
    "executor",
    "verifier",
    "security-executor",
)


class PolicyContractTests(unittest.TestCase):
    def test_version_stamps_move_together(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"<!-- pilotfish v{version} -->", policy)

        for readme in ("README.md", "README.zh-TW.md"):
            content = (ROOT / readme).read_text(encoding="utf-8")
            self.assertIn(f"git clone --branch v{version} --depth 1", content)

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


if __name__ == "__main__":
    unittest.main()
