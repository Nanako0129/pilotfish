from __future__ import annotations

import os
import re
import socket
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
PREFLIGHT_NO_LEGACY = b"No legacy global pilotfish policy detected.\n"
PREFLIGHT_LEGACY = (
    b"Stop: legacy global pilotfish detected; migrate before installing.\n"
)
PREFLIGHT_UNSAFE = b"Stop: CLAUDE.md cannot be checked safely.\n"


def documented_preflight(path: Path) -> str:
    match = re.search(
        r"```bash\n(?P<body>[ ]*pilotfish_plugin_preflight\(\) \{.*?"
        r"\n[ ]*\}\n\n[ ]*pilotfish_plugin_preflight)\n[ ]*```",
        path.read_text(encoding="utf-8"),
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"preflight block not found in {path}")
    lines = match.group("body").splitlines()
    margin = len(lines[0]) - len(lines[0].lstrip())
    body = "\n".join(
        line[margin:] if line.startswith(" " * margin) else line for line in lines
    )
    return body.rsplit("\npilotfish_plugin_preflight", 1)[0]


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
    def invoke_hook(
        self, root: Path, config_root: Path, hook: Path = HOOK
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["/bin/sh", str(hook)],
            cwd=root,
            env={
                "CLAUDE_PLUGIN_ROOT": str(PLUGIN),
                "HOME": str(root / "home"),
                "PATH": "/usr/bin:/bin",
                "CLAUDE_CONFIG_DIR": str(config_root),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def run_preflight(
        self, function: str, root: Path, config_root: Path
    ) -> subprocess.CompletedProcess[bytes]:
        fake_bin = root / "fake-bin"
        fake_bin.mkdir(exist_ok=True)
        fake_claude = fake_bin / "claude"
        fake_claude.write_text(
            "#!/bin/sh\n"
            '[ "$#" -eq 1 ] && [ "$1" = "--version" ] || exit 98\n'
            "printf '%s\\n' '2.1.219 (Claude Code)'\n",
            encoding="utf-8",
        )
        fake_claude.chmod(0o755)
        return subprocess.run(
            ["/bin/sh", "-c", f"{function}\npilotfish_plugin_preflight\n"],
            cwd=root,
            env={
                "HOME": str(root / "home"),
                "PATH": str(fake_bin),
                "CLAUDE_CONFIG_DIR": str(config_root),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

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

    def test_claude_md_symlink_target_matrix(self) -> None:
        preflights = {
            INSTALL.name: documented_preflight(INSTALL),
            INSTALL_ZH.name: documented_preflight(INSTALL_ZH),
        }
        self.assertEqual(*preflights.values())
        cases = (
            (
                "clean-regular",
                "file",
                "# unrelated user policy\n",
                POLICY,
                (0, PREFLIGHT_NO_LEGACY, b""),
            ),
            (
                "legacy-regular",
                "file",
                "<!-- pilotfish:begin -->\n",
                LEGACY_DIAGNOSTIC,
                (1, b"", PREFLIGHT_LEGACY),
            ),
            (
                "dangling",
                "dangling",
                None,
                UNSAFE_DIAGNOSTIC,
                (1, b"", PREFLIGHT_UNSAFE),
            ),
            (
                "directory",
                "directory",
                None,
                UNSAFE_DIAGNOSTIC,
                (1, b"", PREFLIGHT_UNSAFE),
            ),
            (
                "unix-socket",
                "socket",
                None,
                UNSAFE_DIAGNOSTIC,
                (1, b"", PREFLIGHT_UNSAFE),
            ),
        )
        for name, kind, content, hook_stdout, preflight_result in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                config = root / "config"
                config.mkdir()
                target = root / "target"
                listener = None
                if kind == "file":
                    target.write_text(content or "", encoding="utf-8")
                elif kind == "directory":
                    target.mkdir()
                elif kind == "socket":
                    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    listener.bind(str(target))
                (config / "CLAUDE.md").symlink_to(target)
                try:
                    hook_result = self.invoke_hook(root, config)
                    self.assertEqual(hook_result.returncode, 0)
                    self.assertEqual(hook_result.stdout, hook_stdout)
                    self.assertEqual(hook_result.stderr, b"")
                    if hook_stdout == POLICY:
                        self.assertEqual(hook_result.stdout.count(SENTINEL), 1)
                    else:
                        self.assertNotIn(SENTINEL, hook_result.stdout)
                        self.assertNotIn(POLICY, hook_result.stdout)

                    observed = []
                    for document, function in preflights.items():
                        with self.subTest(document=document):
                            result = self.run_preflight(function, root, config)
                            actual = (result.returncode, result.stdout, result.stderr)
                            self.assertEqual(actual, preflight_result)
                            observed.append(actual)
                    self.assertEqual(observed[0], observed[1])
                finally:
                    if listener is not None:
                        listener.close()

    def test_unreadable_claude_md_symlink_target_fails_closed(self) -> None:
        preflights = {
            INSTALL.name: documented_preflight(INSTALL),
            INSTALL_ZH.name: documented_preflight(INSTALL_ZH),
        }
        self.assertEqual(*preflights.values())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config"
            config.mkdir()
            target = root / "target"
            target.write_text("# unrelated user policy\n", encoding="utf-8")
            target.chmod(0)
            (config / "CLAUDE.md").symlink_to(target)
            try:
                if os.geteuid() == 0 or os.access(target, os.R_OK):
                    self.skipTest(
                        "current UID or filesystem cannot enforce unreadability "
                        "for a chmod-000 regular target"
                    )

                hook_result = self.invoke_hook(root, config)
                self.assertEqual(hook_result.returncode, 0)
                self.assertEqual(hook_result.stdout, UNSAFE_DIAGNOSTIC)
                self.assertEqual(hook_result.stderr, b"")
                self.assertNotIn(SENTINEL, hook_result.stdout)
                self.assertNotIn(POLICY, hook_result.stdout)

                observed = []
                for document, function in preflights.items():
                    with self.subTest(document=document):
                        result = self.run_preflight(function, root, config)
                        actual = (result.returncode, result.stdout, result.stderr)
                        self.assertEqual(actual, (1, b"", PREFLIGHT_UNSAFE))
                        observed.append(actual)
                self.assertEqual(observed[0], observed[1])
            finally:
                target.chmod(0o600)

    def test_grep_error_fails_closed_for_hook_and_documented_preflights(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config"
            config.mkdir()
            (config / "CLAUDE.md").write_text(
                "# unrelated user policy\n", encoding="utf-8"
            )

            hook_source = HOOK.read_text(encoding="utf-8")
            hook_needle = "    grep -F -q \\\n"
            self.assertEqual(hook_source.count(hook_needle), 1)
            forced_hook = root / "forced-grep-error-hook.sh"
            forced_hook.write_text(
                hook_source.replace(
                    hook_needle, "    /bin/sh -c 'exit 2' -- \\\n", 1
                ),
                encoding="utf-8",
            )
            hook_result = self.invoke_hook(root, config, forced_hook)
            self.assertEqual(hook_result.returncode, 0)
            self.assertEqual(hook_result.stdout, UNSAFE_DIAGNOSTIC)
            self.assertEqual(hook_result.stderr, b"")
            self.assertNotIn(SENTINEL, hook_result.stdout)
            self.assertNotIn(POLICY, hook_result.stdout)

            observed = []
            preflight_needle = "PATH=/usr/bin:/bin grep -F -q \\\n"
            for document in (INSTALL, INSTALL_ZH):
                function = documented_preflight(document)
                self.assertEqual(function.count(preflight_needle), 1)
                forced_function = function.replace(
                    preflight_needle,
                    "PATH=/usr/bin:/bin /bin/sh -c 'exit 2' -- \\\n",
                    1,
                )
                result = self.run_preflight(forced_function, root, config)
                actual = (result.returncode, result.stdout, result.stderr)
                self.assertEqual(actual, (1, b"", PREFLIGHT_UNSAFE))
                observed.append(actual)
            self.assertEqual(observed[0], observed[1])

    def test_documented_preflight_exact_client_and_legacy_matrix(self) -> None:
        function = documented_preflight(INSTALL)
        self.assertEqual(function, documented_preflight(INSTALL_ZH))
        self.assertIn("PATH=/usr/bin:/bin grep -F -q", function)
        self.assertIn(
            '[ ! -e "$CFG/CLAUDE.md" ] && [ ! -L "$CFG/CLAUDE.md" ]',
            function,
        )
        self.assertNotIn('elif [ -L "$CFG/CLAUDE.md" ]', function)
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
            ("dangling-symlink", None, "symlink", b"", PREFLIGHT_UNSAFE, 1),
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
                claude: bool = True,
                settings: bool = True,
                fail_utility: str | None = None,
                collision: bool = False,
                temp_collision: bool = False,
            ) -> tuple[subprocess.CompletedProcess[bytes], Path, Path, dict[str, bytes]]:
                root = base / name
                config = root / "config"
                agents = config / "agents"
                agents.mkdir(parents=True)
                sources = {"agents/scout.md": b"agent bytes\n"}
                if claude:
                    sources["CLAUDE.md"] = b"user policy\n"
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
                if temp_collision:
                    temp = config / "backups" / f".pilotfish-global-{stamp}.tmp"
                    temp.parent.mkdir(parents=True, exist_ok=True)
                    temp.symlink_to("missing-temporary-backup")

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
                    fake_failure.write_text(
                        (
                            "#!/bin/sh\n"
                            "printf '%s\\n' partial > \"$3\"\n"
                            "exit 71\n"
                        )
                        if fail_utility == "cp"
                        else "#!/bin/sh\nexit 71\n",
                        encoding="utf-8",
                    )
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
            self.assertEqual(list((config / "backups").glob(".pilotfish-global-*")), [])
            self.assertTrue(sentinel.exists())

            missing, config, sentinel, sources = execute("missing-settings", settings=False)
            self.assertEqual(missing.returncode, 0, missing.stderr)
            backup = config / "backups" / f"pilotfish-global-{stamp}"
            self.assertFalse((backup / "settings.json").exists())
            for relative, content in sources.items():
                self.assertEqual((backup / relative).read_bytes(), content)
            self.assertEqual(list((config / "backups").glob(".pilotfish-global-*")), [])
            self.assertTrue(sentinel.exists())

            for utility, source, without_claude in (
                ("cp", "CLAUDE.md", False),
                ("cmp", "CLAUDE.md", False),
                ("cp", "settings.json", True),
                ("cmp", "settings.json", True),
                ("diff", "agents", False),
            ):
                with self.subTest(failure=utility, source=source):
                    failed, config, sentinel, sources = execute(
                        f"fail-{utility}-{source}",
                        claude=not without_claude,
                        fail_utility=utility,
                    )
                    self.assertNotEqual(failed.returncode, 0)
                    self.assertFalse(sentinel.exists())
                    self.assertEqual(
                        list((config / "backups").glob("pilotfish-global-*")), []
                    )
                    self.assertEqual(
                        list((config / "backups").glob(".pilotfish-global-*")), []
                    )
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

            collided, config, sentinel, sources = execute(
                "temp-collision", temp_collision=True
            )
            self.assertNotEqual(collided.returncode, 0)
            self.assertIn(b"backup temporary path already exists", collided.stderr)
            self.assertFalse(sentinel.exists())
            self.assertEqual(
                list((config / "backups").glob("pilotfish-global-*")), []
            )
            for relative, content in sources.items():
                self.assertEqual((config / relative).read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
