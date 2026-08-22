from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
HOOK = PLUGIN / "hooks" / "emit-sessionstart.sh"
INSTALL = ROOT / "install" / "PLUGIN-INSTALL.md"
INSTALL_ZH = ROOT / "install" / "PLUGIN-INSTALL.zh-TW.md"
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
UNSAFE_DIAGNOSTIC = (
    f"pilotfish Plugin blocked: the effective CLAUDE.md cannot be checked "
    f"safely. Follow {MIGRATION_URL} and restart Claude Code.\n"
).encode()
MODEL_OVERRIDE_DIAGNOSTIC = (
    "pilotfish Plugin blocked: CLAUDE_CODE_SUBAGENT_MODEL is non-empty and "
    "overrides every agent model frontmatter. Unset it, then restart or "
    "relaunch Claude Code.\n"
).encode()


def snapshot(root: Path) -> dict[str, tuple[str, int, bytes | str | None]]:
    result = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        mode = stat.S_IMODE(path.lstat().st_mode)
        if path.is_symlink():
            result[relative] = ("symlink", mode, os.readlink(path))
        elif path.is_file():
            result[relative] = ("file", mode, path.read_bytes())
        elif path.is_dir():
            result[relative] = ("directory", mode, None)
    return result


class PluginHookTests(unittest.TestCase):
    def run_hook(
        self,
        root: Path,
        *,
        config_value: str | None,
        claude_md: str | None,
        config_mode: int | None = None,
        dangling_claude_md: bool = False,
        inherited_path: str = "/usr/bin:/bin",
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[bytes]:
        config_root = root / "config"
        config_root.mkdir()
        if claude_md is not None and dangling_claude_md:
            raise ValueError("CLAUDE.md cannot be both regular and dangling")
        if claude_md is not None:
            (config_root / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
        elif dangling_claude_md:
            (config_root / "CLAUDE.md").symlink_to("missing-CLAUDE.md")
        env = {
            "CLAUDE_PLUGIN_ROOT": str(PLUGIN),
            "HOME": str(root / "home"),
            "PATH": inherited_path,
        }
        env.update(extra_env or {})
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
        if config_mode is not None:
            config_root.chmod(config_mode)
        try:
            if config_mode is not None and (
                os.geteuid() == 0 or os.access(config_root, os.X_OK)
            ):
                self.skipTest(
                    "current UID or filesystem cannot make the config root "
                    "non-searchable with chmod"
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
        finally:
            config_root.chmod(0o700)

    def test_no_legacy_config_emits_exact_policy_once(self) -> None:
        cases = (
            ("unset-none", None, None, None),
            ("empty-home-fallback", "", "# unrelated user policy\n", None),
            ("explicit-plugin-only", "{config}", "# no global pilotfish\n", None),
            ("empty-model-override", "{config}", None, {"CLAUDE_CODE_SUBAGENT_MODEL": ""}),
        )
        for name, config_value, claude_md, extra_env in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                result = self.run_hook(
                    Path(temporary),
                    config_value=config_value,
                    claude_md=claude_md,
                    extra_env=extra_env,
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, POLICY)
                self.assertEqual(result.stdout.count(SENTINEL), 1)
                self.assertEqual(result.stderr, b"")

    def test_nonempty_model_override_fails_closed_without_value_or_policy(self) -> None:
        secret = "secret-model-value"
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_hook(
                Path(temporary),
                config_value="{config}",
                claude_md="<!-- pilotfish:begin -->\n",
                extra_env={"CLAUDE_CODE_SUBAGENT_MODEL": secret},
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, MODEL_OVERRIDE_DIAGNOSTIC)
        self.assertNotIn(secret.encode(), result.stdout + result.stderr)
        self.assertNotIn(SENTINEL, result.stdout)
        self.assertNotIn(POLICY, result.stdout)
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

    def test_non_searchable_config_root_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_hook(
                Path(temporary),
                config_value="{config}",
                claude_md=None,
                config_mode=0o600,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, UNSAFE_DIAGNOSTIC)
        self.assertEqual(result.stdout.count(MIGRATION_URL.encode()), 1)
        self.assertNotIn(SENTINEL, result.stdout)
        self.assertNotIn(POLICY, result.stdout)
        self.assertEqual(result.stderr, b"")

    def test_dangling_claude_md_symlink_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_hook(
                Path(temporary),
                config_value="{config}",
                claude_md=None,
                dangling_claude_md=True,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, UNSAFE_DIAGNOSTIC)
        self.assertEqual(result.stdout.count(MIGRATION_URL.encode()), 1)
        self.assertNotIn(SENTINEL, result.stdout)
        self.assertNotIn(POLICY, result.stdout)
        self.assertEqual(result.stderr, b"")

    def test_hook_ignores_hostile_inherited_path_for_all_output_classes(self) -> None:
        cases = (
            ("clean", "# unrelated user policy\n", False, POLICY, {}),
            ("legacy", "<!-- pilotfish:begin -->\n", False, LEGACY_DIAGNOSTIC, {}),
            ("unsafe", None, True, UNSAFE_DIAGNOSTIC, {}),
            (
                "model-override",
                None,
                False,
                MODEL_OVERRIDE_DIAGNOSTIC,
                {"CLAUDE_CODE_SUBAGENT_MODEL": "secret-model-value"},
            ),
        )
        for name, claude_md, dangling, expected, case_env in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                fake_bin = root / "fake-bin"
                fake_bin.mkdir()
                marker = root / "fake-utility-ran"
                fake_script = (
                    "#!/bin/sh\n"
                    ': > "$PILOTFISH_FAKE_UTILITY_MARKER"\n'
                    "exit 99\n"
                )
                for utility in ("grep", "cat", "printf"):
                    path = fake_bin / utility
                    path.write_text(fake_script, encoding="utf-8")
                    path.chmod(0o755)

                result = self.run_hook(
                    root,
                    config_value="{config}",
                    claude_md=claude_md,
                    dangling_claude_md=dangling,
                    inherited_path=str(fake_bin),
                    extra_env={
                        "PILOTFISH_FAKE_UTILITY_MARKER": str(marker),
                        **case_env,
                    },
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, expected)
                self.assertEqual(result.stderr, b"")
                self.assertNotIn(b"secret-model-value", result.stdout + result.stderr)
                self.assertFalse(marker.exists())

    def test_documented_preflight_exact_client_and_legacy_matrix(self) -> None:
        document = INSTALL.read_text(encoding="utf-8")
        match = re.search(
            r"```bash\n(?P<body>   pilotfish_plugin_preflight\(\) \{.*?"
            r"\n   \}\n\n   pilotfish_plugin_preflight)\n   ```",
            document,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        function = match.group("body").rsplit(
            "\n   pilotfish_plugin_preflight", 1
        )[0]
        self.assertIn("PATH=/usr/bin:/bin grep -F -q", function)
        self.assertNotIn("/usr/bin/grep", function)
        self.assertNotIn("sort -V", function)

        client_cases = (
            ("below-floor", "2.1.218 (Claude Code)", 0, None, 1, b"requires Claude Code 2.1.219"),
            ("exact-floor", "2.1.219 (Claude Code)", 0, None, 0, b""),
            ("higher-minor", "2.2.0 (Claude Code)", 0, None, 0, b""),
            ("missing-minor-patch", "3", 0, None, 1, b"first-token numeric X.Y.Z"),
            ("missing-patch", "3.0", 0, None, 1, b"first-token numeric X.Y.Z"),
            ("malformed", "Claude Code 2.1.219", 0, None, 1, b"first-token numeric X.Y.Z"),
            ("command-nonzero", "ignored", 7, None, 1, b"claude --version failed"),
            ("command-unavailable", None, 0, None, 1, b"claude --version failed"),
            ("override-nonempty", "2.1.219", 0, "secret-model-value", 1, b"Unset it yourself"),
            ("override-unset", "2.1.219", 0, None, 0, b""),
            ("override-empty", "2.1.219", 0, "", 0, b""),
        )
        for name, version, command_status, override, status, diagnostic in client_cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                config = root / "config"
                config.mkdir()
                fake_bin = root / "fake-bin"
                fake_bin.mkdir()
                if version is not None:
                    fake_claude = fake_bin / "claude"
                    fake_claude.write_text(
                        "#!/bin/sh\n"
                        '[ "$#" -eq 1 ] && [ "$1" = "--version" ] || exit 98\n'
                        f'printf \'%s\\n\' "{version}"\n'
                        f"exit {command_status}\n",
                        encoding="utf-8",
                    )
                    fake_claude.chmod(0o755)
                env = {
                    "HOME": str(root / "home"),
                    "PATH": str(fake_bin),
                    "CLAUDE_CONFIG_DIR": str(config),
                }
                if override is not None:
                    env["CLAUDE_CODE_SUBAGENT_MODEL"] = override
                script = (
                    f"{function}\n"
                    "inherited_path=$PATH\n"
                    "inherited_override_state=${CLAUDE_CODE_SUBAGENT_MODEL+x}\n"
                    "inherited_override_value=${CLAUDE_CODE_SUBAGENT_MODEL-}\n"
                    "pilotfish_plugin_preflight\n"
                    "status=$?\n"
                    '[ "$PATH" = "$inherited_path" ] || exit 97\n'
                    '[ "${CLAUDE_CODE_SUBAGENT_MODEL+x}" = "$inherited_override_state" ] || exit 96\n'
                    '[ "${CLAUDE_CODE_SUBAGENT_MODEL-}" = "$inherited_override_value" ] || exit 95\n'
                    'exit "$status"\n'
                )
                before = snapshot(root)
                result = subprocess.run(
                    ["/bin/sh", "-c", script],
                    cwd=root,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(snapshot(root), before)
                self.assertEqual(result.returncode, status)
                self.assertEqual(
                    result.stdout,
                    b"No legacy global pilotfish policy detected.\n" if status == 0 else b"",
                )
                self.assertIn(diagnostic, result.stderr)
                self.assertNotIn(b"secret-model-value", result.stdout + result.stderr)

        cases = (
            ("missing", None, None, b"No legacy global pilotfish policy detected.\n", b"", 0),
            ("unrelated", "# unrelated\n", None, b"No legacy global pilotfish policy detected.\n", b"", 0),
            ("begin", "<!-- pilotfish:begin -->\n", None, b"", b"Stop: legacy global pilotfish detected; migrate before installing.\n", 1),
            ("end", "<!-- pilotfish:end -->\n", None, b"", b"Stop: legacy global pilotfish detected; migrate before installing.\n", 1),
            ("version", "<!-- pilotfish v1.3.10 -->\n", None, b"", b"Stop: legacy global pilotfish detected; migrate before installing.\n", 1),
            ("header", "Main-session policy. Named roles (`scout`)\n", None, b"", b"Stop: legacy global pilotfish detected; migrate before installing.\n", 1),
            ("relative", None, "relative", b"", b"Stop: CLAUDE_CONFIG_DIR must be absolute.\n", 1),
            ("symlink", None, "symlink", b"", b"Stop: CLAUDE.md must not be a symlink; replace it with a regular readable file or remove it.\n", 1),
        )
        for name, claude_md, special, stdout, stderr, status in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                config = root / "config"
                config.mkdir()
                if claude_md is not None:
                    (config / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
                elif special == "symlink":
                    (config / "CLAUDE.md").symlink_to("missing-CLAUDE.md")
                fake_bin = root / "fake-bin"
                fake_bin.mkdir()
                fake_claude = fake_bin / "claude"
                fake_claude.write_text(
                    "#!/bin/sh\n"
                    '[ "$#" -eq 1 ] && [ "$1" = "--version" ] || exit 98\n'
                    "printf '%s\\n' '2.1.219 (Claude Code)'\n",
                    encoding="utf-8",
                )
                fake_claude.chmod(0o755)
                fake_marker = root / "fake-grep-ran"
                fake_grep = fake_bin / "grep"
                fake_grep.write_text(
                    "#!/bin/sh\n"
                    ': > "$PILOTFISH_FAKE_UTILITY_MARKER"\n'
                    "exit 99\n",
                    encoding="utf-8",
                )
                fake_grep.chmod(0o755)
                env = {
                    "HOME": str(root / "home"),
                    "PATH": str(fake_bin),
                    "CLAUDE_CONFIG_DIR": (
                        "relative" if special == "relative" else str(config)
                    ),
                    "PILOTFISH_FAKE_UTILITY_MARKER": str(fake_marker),
                }
                script = (
                    f"{function}\n"
                    "inherited_path=$PATH\n"
                    "pilotfish_plugin_preflight\n"
                    "status=$?\n"
                    "[ \"$PATH\" = \"$inherited_path\" ] || exit 97\n"
                    "exit \"$status\"\n"
                )
                before = snapshot(root)
                result = subprocess.run(
                    ["/bin/sh", "-c", script],
                    cwd=root,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(snapshot(root), before)
                self.assertEqual(result.returncode, status)
                self.assertEqual(result.stdout, stdout)
                self.assertEqual(result.stderr, stderr)
                self.assertFalse(fake_marker.exists())

    def test_documented_migration_backup_is_verified_and_fail_closed(self) -> None:
        def backup_block(path: Path) -> str:
            blocks = re.findall(
                r"```bash\n(?P<body>.*?)\n```",
                path.read_text(encoding="utf-8"),
                re.DOTALL,
            )
            matches = [
                block
                for block in blocks
                if 'BACKUP="$CFG/backups/pilotfish-global-$STAMP"' in block
            ]
            self.assertEqual(len(matches), 1)
            return matches[0]

        script = backup_block(INSTALL)
        self.assertEqual(script, backup_block(INSTALL_ZH))
        self.assertIn('CFG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"', script)

        english = INSTALL.read_text(encoding="utf-8")
        chinese = INSTALL_ZH.read_text(encoding="utf-8")
        self.assertIn("If any required backup copy", english)
        self.assertIn("stop before removing or installing anything", english)
        self.assertIn("若任何必要的 backup copy 或 verification 失敗", chinese)
        self.assertIn("移除或安裝任何內容之前停止", chinese)

        stamp = "20260823-010203"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)

            def execute(
                name: str,
                *,
                settings: bool = True,
                fail_utility: str | None = None,
                collision: bool = False,
            ) -> tuple[subprocess.CompletedProcess[bytes], Path, Path, dict[str, bytes]]:
                root = base / name
                config = root / "config"
                agents = config / "agents"
                agents.mkdir(parents=True)
                sources = {
                    "CLAUDE.md": b"user policy\n",
                    "agents/scout.md": b"agent bytes\n",
                }
                if settings:
                    sources["settings.json"] = b'{"model":"custom"}\n'
                for relative, content in sources.items():
                    path = config / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)

                collision_marker = config / "backups" / f"pilotfish-global-{stamp}"
                if collision:
                    collision_marker.mkdir(parents=True)
                    (collision_marker / "keep").write_bytes(b"existing\n")

                fake_bin = root / "fake-bin"
                fake_bin.mkdir()
                fake_date = fake_bin / "date"
                fake_date.write_text(
                    "#!/bin/sh\n"
                    f"printf '%s\\n' '{stamp}'\n",
                    encoding="utf-8",
                )
                fake_date.chmod(0o755)
                if fail_utility is not None:
                    fake_failure = fake_bin / fail_utility
                    fake_failure.write_text("#!/bin/sh\nexit 71\n", encoding="utf-8")
                    fake_failure.chmod(0o755)

                sentinel = root / "mutation-sentinel"
                env = {
                    "CLAUDE_CONFIG_DIR": str(config),
                    "HOME": str(root / "home"),
                    "PATH": f"{fake_bin}:/usr/bin:/bin",
                    "PILOTFISH_MUTATION_SENTINEL": str(sentinel),
                }
                completed = subprocess.run(
                    [
                        "/bin/sh",
                        "-c",
                        script
                        + "\nprintf '%s\\n' mutated > \"$PILOTFISH_MUTATION_SENTINEL\"\n",
                    ],
                    cwd=root,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                return completed, config, sentinel, sources

            complete, config, sentinel, sources = execute("complete")
            self.assertEqual(complete.returncode, 0, complete.stderr)
            backup = config / "backups" / f"pilotfish-global-{stamp}"
            for relative, content in sources.items():
                self.assertEqual((config / relative).read_bytes(), content)
                self.assertEqual((backup / relative).read_bytes(), content)
            self.assertTrue(sentinel.exists())

            missing, config, sentinel, sources = execute("missing-settings", settings=False)
            self.assertEqual(missing.returncode, 0, missing.stderr)
            backup = config / "backups" / f"pilotfish-global-{stamp}"
            self.assertFalse((backup / "settings.json").exists())
            for relative, content in sources.items():
                self.assertEqual((backup / relative).read_bytes(), content)
            self.assertTrue(sentinel.exists())

            for utility in ("cp", "cmp"):
                with self.subTest(failure=utility):
                    failed, config, sentinel, sources = execute(
                        f"fail-{utility}", fail_utility=utility
                    )
                    self.assertNotEqual(failed.returncode, 0)
                    self.assertFalse(sentinel.exists())
                    for relative, content in sources.items():
                        self.assertEqual((config / relative).read_bytes(), content)

            collided, config, sentinel, sources = execute("collision", collision=True)
            self.assertNotEqual(collided.returncode, 0)
            self.assertIn(b"backup destination already exists", collided.stderr)
            self.assertFalse(sentinel.exists())
            collision_backup = config / "backups" / f"pilotfish-global-{stamp}"
            self.assertEqual((collision_backup / "keep").read_bytes(), b"existing\n")
            for relative, content in sources.items():
                self.assertEqual((config / relative).read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
