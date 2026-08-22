from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import stat
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
SPEC = importlib.util.spec_from_file_location(
    "render_plugin_spike", ROOT / "tools" / "render_plugin_spike.py"
)
assert SPEC and SPEC.loader
RENDERER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RENDERER)

ROUTING = {
    "scout": ("haiku", "low"),
    "plan-verifier": ("opus", "medium"),
    "security-reviewer": ("opus", "high"),
    "mech-executor": ("sonnet", "low"),
    "executor": ("sonnet", "medium"),
    "verifier": ("opus", "medium"),
    "security-executor": ("opus", "high"),
}
READ_ONLY = {
    "scout": {"Read", "Glob", "Grep"},
    "plan-verifier": {"Read", "Glob", "Grep"},
    "security-reviewer": {"Read", "Glob", "Grep", "WebSearch", "WebFetch"},
}
PLUGIN_FILES = {
    ".claude-plugin/plugin.json",
    "ATTRIBUTION.md",
    "LICENSE",
    "agents/executor.md",
    "agents/mech-executor.md",
    "agents/plan-verifier.md",
    "agents/scout.md",
    "agents/security-executor.md",
    "agents/security-reviewer.md",
    "agents/verifier.md",
    "hooks/emit-sessionstart.sh",
    "hooks/hooks.json",
    "policy/ambient.md",
    "policy/sessionstart.txt",
    "skills/pilotfish/SKILL.md",
}


def frontmatter(path: Path) -> dict[str, str]:
    _, raw, _ = path.read_text(encoding="utf-8").split("---", 2)
    return {
        key.strip(): value.strip()
        for line in raw.strip().splitlines()
        for key, value in [line.split(":", 1)]
    }


class PluginArtifactTests(unittest.TestCase):
    def test_manifests_describe_only_the_experimental_plugin(self) -> None:
        manifest = json.loads(
            (PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "pilotfish")
        self.assertEqual(manifest["version"], "0.0.0")
        self.assertIn("Experimental Ambient Spike", manifest["displayName"])
        self.assertEqual(manifest["repository"], "https://github.com/Nanako0129/pilotfish")
        self.assertEqual(manifest["license"], "MIT")
        self.assertNotIn("agent", manifest)
        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual([(p["name"], p["source"]) for p in marketplace["plugins"]], [("pilotfish", "./plugin")])

    def test_renderer_and_transport_are_byte_exact_without_hook_execution(self) -> None:
        self.assertEqual(RENDERER.check(), [])
        hooks = (PLUGIN / "hooks" / "hooks.json").read_bytes()
        script = (PLUGIN / "hooks" / "emit-sessionstart.sh").read_bytes()
        RENDERER.validate_transport(hooks, script)
        self.assertEqual(script, RENDERER.SCRIPT)
        self.assertFalse(os.stat(PLUGIN / "hooks" / "emit-sessionstart.sh").st_mode & 0o111)

    def test_sessionstart_bound_hash_and_manual_policy_bytes(self) -> None:
        policy = (PLUGIN / "policy" / "ambient.md").read_bytes()
        output = (PLUGIN / "policy" / "sessionstart.txt").read_bytes()
        text = output.decode("utf-8")
        self.assertEqual(output, RENDERER.build_sessionstart(policy))
        self.assertEqual(text.count(RENDERER.SENTINEL), 1)
        self.assertEqual(text.count(policy.decode("utf-8")), 1)
        self.assertEqual(text.count(RENDERER.OPT_IN), 1)
        self.assertNotIn("SESSIONSTART_AB_ARM", text)
        self.assertLessEqual(len(text), 9_000)
        self.assertLessEqual(len(text) + text.count("\n"), 9_000)
        skill = (PLUGIN / "skills" / "pilotfish" / "SKILL.md").read_bytes()
        fields = frontmatter(PLUGIN / "skills" / "pilotfish" / "SKILL.md")
        self.assertEqual(fields["disable-model-invocation"], "true")
        self.assertIn(b"Hooks may not have run", skill)
        self.assertIn(b"Reliability of this experimental ambient transport is unverified", skill)
        embedded = skill.split(RENDERER.POLICY_BEGIN.encode(), 1)[1].split(
            RENDERER.POLICY_END.encode(), 1
        )[0]
        self.assertEqual(embedded, policy)
        self.assertIn(hashlib.sha256(policy).hexdigest().encode(), skill)
        lower = skill.split(RENDERER.POLICY_BEGIN.encode(), 1)[0].lower()
        for claim in (b"fallback", b"replacement", b"v1-equivalence", b"equivalent to v1"):
            self.assertNotIn(claim, lower)

    def test_policy_byte_validation_preserves_shell_metacharacters_and_unicode(self) -> None:
        payload = "pilotfish's $value `literal` path\\segment Unicode 雪\n".encode()
        self.assertEqual(RENDERER.validate_text_bytes(payload, "probe").encode(), payload)
        rendered = RENDERER.build_sessionstart(payload)
        self.assertEqual(rendered.count(payload), 1)
        for payload in (b"line\r\n", b"line\0\n", b"line\tvalue\n", b"line\x1bvalue\n", b"line\x7fvalue\n"):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    RENDERER.validate_text_bytes(payload, "probe")

    def test_transport_rejects_hostile_path_substitution(self) -> None:
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"] = "/bin/sh \"$(id)\""
        with self.assertRaises(ValueError):
            RENDERER.validate_transport(json.dumps(hooks).encode(), RENDERER.SCRIPT)
        hostile = RENDERER.SCRIPT.replace(b"sessionstart.txt", b"$(id)")
        with self.assertRaises(ValueError):
            RENDERER.validate_transport(
                (PLUGIN / "hooks" / "hooks.json").read_bytes(), hostile
            )

    def test_policy_requirement_matrix(self) -> None:
        matrix = json.loads(
            (ROOT / "tests" / "plugin_requirements.json").read_text(encoding="utf-8")
        )
        template = (ROOT / matrix["source"]["path"]).read_bytes()
        policy = (PLUGIN / "policy" / "ambient.md").read_bytes()
        self.assertEqual(matrix["source"]["sha256"], hashlib.sha256(template).hexdigest())
        self.assertEqual(
            (ROOT / "tests" / "plugin_requirements.json").read_bytes(),
            RENDERER.build_matrix(template, policy),
        )
        requirements = matrix["requirements"]
        self.assertEqual(len(requirements), len(RENDERER.REQUIREMENTS))
        self.assertEqual(
            {item["category"] for item in requirements},
            {"approval", "security", "recovery", "authority", "severity", "verification", "liveness", "dispatch"},
        )
        self.assertEqual(len({item["id"] for item in requirements}), len(requirements))

    def test_recovery_identity_preserves_every_source_subclause(self) -> None:
        matrix = json.loads(
            (ROOT / "tests" / "plugin_requirements.json").read_text(encoding="utf-8")
        )
        recovery = next(
            item
            for item in matrix["requirements"]
            if item["id"] == "PLUG-RECOVERY-IDENTITY"
        )["ambient_line"]
        for clause in (
            "Every next pass requires material Δ",
            "candidate|claim|acceptance|contract|external evidence/prerequisites|environment",
            "verdict/output alone≠Δ",
            "Complete candidate ID",
            "committed HEAD",
            "tracked+staged diff",
            "untracked input paths+content",
            "each submodule HEAD+recursive worktree content",
            "applicable tested-artifact digest",
            "artifact digest replaces source iff explicit sole deliverable",
            "Never repeat ID",
            "stop early if next pass only seeks adjacent risk",
        ):
            with self.subTest(clause=clause):
                self.assertIn(clause, recovery)

    def test_agents_are_current_template_derivations_with_pinned_capabilities(self) -> None:
        actual = {path.stem for path in (PLUGIN / "agents").glob("*.md")}
        self.assertEqual(actual, set(ROUTING))
        self.assertNotIn("Explore", actual)
        for role, routing in ROUTING.items():
            path = PLUGIN / "agents" / f"{role}.md"
            source = ROOT / "templates" / "agents" / f"{role}.md"
            self.assertEqual(path.read_bytes(), RENDERER.transform_agent(role, source.read_bytes()))
            fields = frontmatter(path)
            self.assertEqual((fields["model"].strip(), fields["effort"].strip()), routing)
            if role in READ_ONLY:
                self.assertEqual(
                    {tool.strip() for tool in fields["tools"].split(",")}, READ_ONLY[role]
                )
            else:
                denied = {tool.strip() for tool in fields["disallowedTools"].split(",")}
                self.assertTrue({"Agent", "Workflow"} <= denied)
                if role == "verifier":
                    self.assertTrue({"Write", "Edit", "NotebookEdit"} <= denied)
        policy = (PLUGIN / "policy" / "ambient.md").read_text(encoding="utf-8")
        self.assertIn("Never pass model at invocation", policy)

    def test_plugin_tree_is_closed_regular_and_non_executable(self) -> None:
        files = {path.relative_to(PLUGIN).as_posix() for path in PLUGIN.rglob("*") if path.is_file()}
        self.assertEqual(files, PLUGIN_FILES)
        self.assertFalse(any(path.is_symlink() for path in PLUGIN.rglob("*")))
        for path in PLUGIN.rglob("*"):
            mode = stat.S_IMODE(path.stat().st_mode)
            self.assertEqual(mode, 0o755 if path.is_dir() else 0o644, path)
        forbidden = {"settings.json", "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", ".mcp.json"}
        self.assertFalse({path.name for path in PLUGIN.rglob("*")} & forbidden)
        self.assertFalse(any(path.name in {"bin", "monitors", "lsp", "mcp"} for path in PLUGIN.rglob("*")))

    def test_license_attribution_and_g0_claim_boundary(self) -> None:
        self.assertEqual((PLUGIN / "LICENSE").read_bytes(), (ROOT / "LICENSE").read_bytes())
        attribution = (PLUGIN / "ATTRIBUTION.md").read_text(encoding="utf-8")
        for commit in ("f636e298", "647fd5b4", "5067870b", "71d92bc"):
            self.assertIn(commit, attribution)
        for phrase in (
            "brand-new G0 Plugin artifact",
            "macOS-only spike",
            "never installs or loads",
            "disabled hook is not a security guarantee",
            "coexistence with a global v1 installation",
            "deferred to G1",
            "no ambient reliability, authority, v1-equivalence, or product-readiness claim",
        ):
            self.assertIn(phrase, attribution)

    def test_focused_tests_do_not_execute_or_mutate_external_runtime(self) -> None:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertFalse(imports & {"subprocess", "socket", "urllib", "requests", "httpx"})
        write_calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertFalse(write_calls & {"write_bytes", "write_text", "unlink", "rename"})


if __name__ == "__main__":
    unittest.main()
