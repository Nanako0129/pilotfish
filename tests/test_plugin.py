from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import re
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
}
ROLE_REF = re.compile(
    r"(?<![\w:-])(scout|plan-verifier|security-reviewer|mech-executor|executor|verifier|security-executor)(?![\w-])",
    re.IGNORECASE,
)
QUOTED_ROLE_REF = re.compile(
    r"`(scout|plan-verifier|security-reviewer|mech-executor|executor|verifier|security-executor)`",
    re.IGNORECASE,
)


def frontmatter(path: Path) -> dict[str, str]:
    _, raw, _ = path.read_text(encoding="utf-8").split("---", 2)
    return {
        key.strip(): value.strip()
        for line in raw.strip().splitlines()
        for key, value in [line.split(":", 1)]
    }


def unqualified_role_refs(text: str, *, allow_frontmatter: bool = False) -> list[str]:
    if allow_frontmatter and text.startswith("---\n"):
        text = text.split("---", 2)[2]
    return [match.group(0) for match in ROLE_REF.finditer(text)]


class PluginArtifactTests(unittest.TestCase):
    def test_manifests_are_versioned_beta_metadata_from_version(self) -> None:
        release_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        manifest = json.loads(
            (PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["name"], "pilotfish")
        self.assertEqual(manifest["version"], release_version)
        self.assertEqual(manifest["displayName"], "pilotfish Plugin beta")
        self.assertEqual(manifest["repository"], "https://github.com/Nanako0129/pilotfish")
        self.assertEqual(manifest["license"], "MIT")
        self.assertIn("macOS and Linux", manifest["description"])
        self.assertNotIn("agent", manifest)
        self.assertEqual(
            (PLUGIN / ".claude-plugin" / "plugin.json").read_bytes(),
            RENDERER.build_manifest(release_version),
        )
        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual([(p["name"], p["source"]) for p in marketplace["plugins"]], [("pilotfish", "./plugin")])
        self.assertEqual(marketplace["plugins"][0]["version"], release_version)
        self.assertIn("macOS and Linux", marketplace["description"])
        self.assertIn("macOS and Linux", marketplace["plugins"][0]["description"])
        self.assertEqual(
            (ROOT / ".claude-plugin" / "marketplace.json").read_bytes(),
            RENDERER.build_marketplace(release_version),
        )
        self.assertNotIn("0.0.0", json.dumps((manifest, marketplace)))

    def test_renderer_and_transport_are_byte_exact_without_hook_execution(self) -> None:
        self.assertEqual(RENDERER.check(), [])
        hooks = (PLUGIN / "hooks" / "hooks.json").read_bytes()
        script = (PLUGIN / "hooks" / "emit-sessionstart.sh").read_bytes()
        RENDERER.validate_transport(hooks, script)
        self.assertEqual(script, RENDERER.SCRIPT)
        self.assertTrue(
            script.startswith(
                b"#!/bin/sh\nset -eu\nPATH=/usr/bin:/bin\nexport PATH\n"
            )
        )
        for hardcoded_utility in (b"/usr/bin/grep", b"/usr/bin/printf", b"/bin/cat"):
            with self.subTest(hardcoded_utility=hardcoded_utility):
                self.assertNotIn(hardcoded_utility, script)
        self.assertIn(b"\n    grep -F -q ", script)
        self.assertTrue(script.endswith(b'cat "${CLAUDE_PLUGIN_ROOT}/policy/sessionstart.txt"\n'))
        self.assertFalse(os.stat(PLUGIN / "hooks" / "emit-sessionstart.sh").st_mode & 0o111)

        installer = (ROOT / "install" / "PLUGIN-INSTALL.md").read_bytes()
        self.assertIn(b"PATH=/usr/bin:/bin grep -F -q", installer)
        self.assertNotIn(b"/usr/bin/grep", installer)
        for claim in (
            b"requires Claude Code 2.1.219 or newer",
            b"plan-verifier` and `security-reviewer` roles depend on those allowlists",
            b"CLAUDE_CODE_SUBAGENT_MODEL",
            b"overrides every agent `model` frontmatter",
            b"The Plugin does not edit `settings.json`",
            b'merge `"model": "opus"` into the effective `$CFG/settings.json`',
            b"preserving every other key",
            b"For either setup option below",
            b'`"opus"`, `"sonnet"`, and `"haiku"`',
            b"preserving every existing entry",
            b"common `availableModels` check above still applies",
            b"explicit user-approved main-model choice",
            b"claude --model opus",
            b"the advertised Opus-main tiering is not established",
        ):
            with self.subTest(claim=claim):
                self.assertIn(claim, installer)

    def test_sessionstart_bound_policy_bytes(self) -> None:
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
        security_review = (PLUGIN / "agents" / "security-reviewer.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("WebSearch and WebFetch provide outbound web egress", security_review)
        self.assertIn("never transmit secrets", security_review)

    def test_dispatch_targets_are_plugin_qualified_outside_frontmatter(self) -> None:
        self.assertEqual(unqualified_role_refs("Route to scout."), ["scout"])
        self.assertEqual(
            unqualified_role_refs(
                "---\nname: scout\n---\nRoute to pilotfish:scout.\n",
                allow_frontmatter=True,
            ),
            [],
        )
        targets = [PLUGIN / "policy" / "ambient.md", *(PLUGIN / "agents").glob("*.md")]
        for path in targets:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                if path.parent.name == "agents":
                    text = text.split("---", 2)[2]
                    refs = [match.group(0) for match in QUOTED_ROLE_REF.finditer(text)]
                else:
                    refs = unqualified_role_refs(text)
                self.assertEqual(refs, [])

    def test_plugin_tree_is_closed_regular_and_non_executable(self) -> None:
        files = {path.relative_to(PLUGIN).as_posix() for path in PLUGIN.rglob("*") if path.is_file()}
        self.assertEqual(files, PLUGIN_FILES)
        self.assertFalse((PLUGIN / "skills").exists())
        self.assertFalse(any(path.is_symlink() for path in PLUGIN.rglob("*")))
        for path in PLUGIN.rglob("*"):
            mode = stat.S_IMODE(path.stat().st_mode)
            self.assertEqual(mode, 0o755 if path.is_dir() else 0o644, path)
        forbidden = {"settings.json", "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", ".mcp.json"}
        self.assertFalse({path.name for path in PLUGIN.rglob("*")} & forbidden)
        self.assertFalse(any(path.name in {"bin", "monitors", "lsp", "mcp"} for path in PLUGIN.rglob("*")))

    def test_license_attribution_and_beta_claim_boundary(self) -> None:
        self.assertEqual((PLUGIN / "LICENSE").read_bytes(), (ROOT / "LICENSE").read_bytes())
        attribution = (PLUGIN / "ATTRIBUTION.md").read_text(encoding="utf-8")
        for commit in ("f636e298", "647fd5b4", "5067870b", "71d92bc"):
            self.assertIn(commit, attribution)
        for phrase in (
            "Plugin beta",
            "macOS and Linux",
            "Ubuntu 20.04+",
            "Debian 10+",
            "Alpine Linux 3.19+",
            "otherwise-working officially supported Claude Code installation",
            "https://code.claude.com/docs/en/setup#system-requirements",
            "checked 2026-08-22",
            "macOS with Claude Code 2.1.239 is live-observed",
            "Linux is contract-qualified only",
            "it has not been tested, verified, or live-observed",
            "Windows is excluded",
            "does not claim stable ambient reliability",
            "cross-version compatibility",
            "runtime namespace-collision proof",
            "equivalence to the legacy global install",
        ):
            self.assertIn(phrase, attribution)
        for stale in ("G0", "G1", "spike", "never installs or loads"):
            self.assertNotIn(stale, attribution)

    def test_platform_claims_preserve_exact_linux_floors_and_evidence_boundary(self) -> None:
        source = "https://code.claude.com/docs/en/setup#system-requirements"
        english_paths = (
            ROOT / "README.md",
            ROOT / "install" / "PLUGIN-INSTALL.md",
            PLUGIN / "ATTRIBUTION.md",
        )
        for path in english_paths:
            content = " ".join(path.read_text(encoding="utf-8").split())
            with self.subTest(path=path):
                for phrase in (
                    "macOS and Linux",
                    "Ubuntu 20.04+",
                    "Debian 10+",
                    "Alpine Linux 3.19+",
                    "otherwise-working officially supported Claude Code installation",
                    source,
                    "2026-08-22",
                    "macOS with Claude Code 2.1.239 is live-observed",
                    "Linux is contract-qualified only",
                    "not been tested, verified, or live-observed",
                    "Windows is excluded",
                    "stable",
                    "cross-version",
                ):
                    self.assertIn(" ".join(phrase.split()), content)

        chinese = " ".join(
            (ROOT / "README.zh-TW.md").read_text(encoding="utf-8").split()
        )
        for phrase in (
            "macOS 與 Linux",
            "Ubuntu 20.04+",
            "Debian 10+",
            "Alpine Linux 3.19+",
            source,
            "2026-08-22",
            "Claude Code 2.1.239 已有 live observation",
            "Linux 僅完成",
            "未經測試、驗證或 live observation",
            "Windows 不在範圍內",
            "stable reliability",
            "跨版本",
        ):
            self.assertIn(" ".join(phrase.split()), chinese)

        metadata = "\n".join(
            (
                (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"),
                (PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"),
                (PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"),
            )
        )
        self.assertNotIn("for macOS Claude Code", metadata)
        self.assertGreaterEqual(metadata.count("macOS and Linux"), 4)

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
