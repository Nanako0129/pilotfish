from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
HOOK = PLUGIN / "hooks" / "emit-sessionstart.sh"
POLICY = (PLUGIN / "policy" / "sessionstart.txt").read_bytes()
SENTINEL = "¶".encode()
MIGRATION_URL = (
    "https://github.com/Nanako0129/pilotfish/blob/main/"
    "install/PLUGIN-INSTALL.md#migrate-from-global-v1"
)
LEGACY_DIAGNOSTIC = (
    f"pilotfish Plugin blocked: legacy global pilotfish detected. Follow "
    f"{MIGRATION_URL} to migrate, then restart Claude Code.\n"
).encode()


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class PluginHookTests(unittest.TestCase):
    def run_hook(
        self, root: Path, *, config_value: str | None, claude_md: str | None
    ) -> subprocess.CompletedProcess[bytes]:
        config_root = root / "config"
        config_root.mkdir()
        if claude_md is not None:
            (config_root / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
        env = {
            "CLAUDE_PLUGIN_ROOT": str(PLUGIN),
            "HOME": str(root / "home"),
            "PATH": "/usr/bin:/bin",
        }
        (root / "home" / ".claude").mkdir(parents=True)
        if not config_value:
            fallback = root / "home" / ".claude"
            if claude_md is not None:
                (fallback / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
                (config_root / "CLAUDE.md").unlink()
        if config_value is not None:
            env["CLAUDE_CONFIG_DIR"] = (
                config_value.replace("{config}", str(config_root))
            )
        before = snapshot(root)
        result = subprocess.run(
            ["/bin/sh", str(HOOK)],
            cwd=root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(snapshot(root), before)
        return result

    def test_no_legacy_config_emits_exact_policy_once(self) -> None:
        cases = (
            ("unset-none", None, None),
            ("empty-home-fallback", "", "# unrelated user policy\n"),
            ("explicit-plugin-only", "{config}", "# no global pilotfish\n"),
        )
        for name, config_value, claude_md in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                result = self.run_hook(
                    Path(temporary), config_value=config_value, claude_md=claude_md
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, POLICY)
                self.assertEqual(result.stdout.count(SENTINEL), 1)
                self.assertEqual(result.stderr, b"")

    def test_legacy_global_config_fails_closed_with_one_migration_diagnostic(self) -> None:
        cases = (
            ("legacy-marker-explicit", "{config}", "<!-- pilotfish:begin -->\n"),
            (
                "known-markerless-policy-home-fallback",
                None,
                "Main-session policy. Named roles (`scout`)\n",
            ),
            (
                "both-markers-explicit",
                "{config}",
                "<!-- pilotfish:begin -->\n<!-- pilotfish v1.3.10 -->\n",
            ),
        )
        for name, config_value, claude_md in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                result = self.run_hook(
                    Path(temporary), config_value=config_value, claude_md=claude_md
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, LEGACY_DIAGNOSTIC)
                self.assertEqual(result.stdout.count(MIGRATION_URL.encode()), 1)
                self.assertNotIn(SENTINEL, result.stdout)
                self.assertNotIn(POLICY, result.stdout)
                self.assertEqual(result.stderr, b"")

    def test_relative_config_root_fails_closed_without_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_hook(
                Path(temporary), config_value="relative-config", claude_md=None
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn(b"CLAUDE_CONFIG_DIR must be absolute", result.stdout)
        self.assertEqual(result.stdout.count(MIGRATION_URL.encode()), 1)
        self.assertNotIn(SENTINEL, result.stdout)
        self.assertNotIn(POLICY, result.stdout)
        self.assertEqual(result.stderr, b"")


if __name__ == "__main__":
    unittest.main()
