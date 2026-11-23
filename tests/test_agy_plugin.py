from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin-agy"

# Tier per role. flash = Hydrogen (High), inherit = the main agent's model
# (measured on agy 1.5.15, 2026-11-23). pro (Hydrogen XHigh) is unused by choice.
ROUTING = {
    "pilotfish-scout": "flash",
    "pilotfish-mech-executor": "flash",
    "pilotfish-executor": "flash",
    "pilotfish-plan-verifier": "inherit",
    "pilotfish-verifier": "inherit",
    "pilotfish-security-reviewer": "inherit",
    "pilotfish-security-executor": "inherit",
}
# Names the agy 1.5.15 loader resolved in a live run. An alias next to its
# canonical name (view_file + read_file) fails with "tool name conflict", and
# manage_task is always granted, so neither belongs in a role file.
KNOWN_TOOLS = {"read_file", "edit_file", "write_file", "run_command", "search_web"}
WRITE_TOOLS = {"edit_file", "write_file"}
NON_WRITERS = {
    "pilotfish-scout",
    "pilotfish-plan-verifier",
    "pilotfish-verifier",
    "pilotfish-security-reviewer",
}
LEAF = "You are a leaf agent. Do the whole assignment yourself in this conversation and never delegate."
RULE_FILE_CAP = 24_000  # bytes; agy truncates a rule file above this


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, f"{path.name}: no frontmatter"
    return dict(line.split(": ", 1) for line in match.group(1).splitlines())


class AgyPluginTest(unittest.TestCase):
    def test_manifest_parses_and_is_versioned(self) -> None:
        manifest = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "pilotfish")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")

    def test_roles_are_leaf_subagents_with_pinned_tier_and_tools(self) -> None:
        files = {p.stem: p for p in (PLUGIN / "agents").glob("*.md")}
        self.assertEqual(set(files), set(ROUTING))
        for name, path in files.items():
            with self.subTest(role=name):
                meta = frontmatter(path)
                self.assertEqual(meta["name"], name)
                self.assertEqual(meta["model"], ROUTING[name])
                self.assertEqual(meta["subagent"], "true")
                self.assertEqual(meta["mainAgent"], "false")
                tools = re.fullmatch(r"\[(.*)\]", meta["tools"]).group(1).split(", ")
                self.assertEqual(len(tools), len(set(tools)))
                self.assertLessEqual(set(tools), KNOWN_TOOLS)
                if name in NON_WRITERS:
                    self.assertFalse(set(tools) & WRITE_TOOLS)
                    # The only capability boundary these roles have: run_command can write.
                    self.assertEqual(meta.get("commandExecutionPolicy"), "sandbox")
                self.assertIn(LEAF, path.read_text(encoding="utf-8"))

    def test_policy_fits_the_rule_cap_and_names_only_real_roles(self) -> None:
        policy = (PLUGIN / "rules" / "AGENTS.md").read_bytes()
        self.assertLessEqual(len(policy), RULE_FILE_CAP)
        pattern = r"pilotfish-[a-z]+(?:-[a-z]+)?"
        self.assertEqual(set(re.findall(pattern, policy.decode("utf-8"))), set(ROUTING))
        for path in (PLUGIN / "agents").glob("*.md"):
            body = path.read_text(encoding="utf-8")
            self.assertLessEqual(set(re.findall(pattern, body)), set(ROUTING), path.name)

    def test_model_floor_hook_warns_only_on_the_weak_tiers(self) -> None:
        hooks = json.loads((PLUGIN / "hooks.json").read_text(encoding="utf-8"))
        (handler,) = hooks["pilotfish-model-floor"]["SessionStart"]
        compact, spaced = (",", ":"), (", ", ": ")
        cases = [
            ("gemini-4-hydrogen-tiered-high", compact, True),
            ("gemini-3.8-flash-high", compact, True),
            ("models/Gemini-4-Hydrogen (High)", compact, True),
            ("gemini-4-hydrogen-medium", spaced, True),
            ("gemini-4-neon-high", compact, False),
            ("auto", spaced, False),
        ]
        for model, separators, warns in cases:
            with self.subTest(model=model, separators=separators):
                # A decoy inside the user's text must not decide the result.
                payload = json.dumps(
                    {"lastUserInput": 'x "modelName":"flash"', "modelName": model, "transcriptPath": "/t"},
                    separators=separators,
                )
                # agy runs a plugin hook with the plugin folder as its directory.
                out = subprocess.run(
                    handler["command"], shell=True, cwd=PLUGIN, input=payload,
                    capture_output=True, text=True, check=True,
                ).stdout
                steps = json.loads(out).get("injectSteps", [])
                self.assertEqual(bool(steps), warns)
                if warns:
                    self.assertIn(model, steps[0]["systemMessage"]["systemMessage"])

if __name__ == "__main__":
    unittest.main()
