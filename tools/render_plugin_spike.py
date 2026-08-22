from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
VERSION_FILE = ROOT / "VERSION"
MANIFEST = PLUGIN / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
TEMPLATE = ROOT / "templates" / "claude-md.orchestration.md"
POLICY = PLUGIN / "policy" / "ambient.md"
SESSIONSTART = PLUGIN / "policy" / "sessionstart.txt"
MATRIX = ROOT / "tests" / "plugin_requirements.json"
SENTINEL = "¶"
OPT_IN = (
    "SessionStart is the user's persistent pilotfish opt-in.\n"
    "On delegation, call exactly one named pilotfish:<role> in foreground; collect it before main acceptance or source mutation.\n"
    "Grants no other authority; task/tool/write/network/spend/external-action/Plan/approval/verification boundaries remain.\n"
)
SCRIPT = (
    b"#!/bin/sh\n"
    b"set -eu\n"
    b"PATH=/usr/bin:/bin\n"
    b"export PATH\n"
    b"\n"
    b'MIGRATION_URL="https://github.com/Nanako0129/pilotfish/blob/main/install/PLUGIN-INSTALL.md#migrate-from-global-v1"\n'
    b"\n"
    b'if [ -n "${CLAUDE_CONFIG_DIR:-}" ]; then\n'
    b'    case "$CLAUDE_CONFIG_DIR" in\n'
    b'        /*) config_root=$CLAUDE_CONFIG_DIR ;;\n'
    b'        *) printf \'%s\\n\' "pilotfish Plugin blocked: CLAUDE_CONFIG_DIR must be absolute. Fix it, then follow $MIGRATION_URL and restart Claude Code."; exit 0 ;;\n'
    b"    esac\n"
    b"else\n"
    b'    case "${HOME:-}" in\n'
    b'        /*) config_root=$HOME/.claude ;;\n'
    b'        *) printf \'%s\\n\' "pilotfish Plugin blocked: HOME must be absolute when CLAUDE_CONFIG_DIR is empty. Fix it, then follow $MIGRATION_URL and restart Claude Code."; exit 0 ;;\n'
    b"    esac\n"
    b"fi\n"
    b"\n"
    b'if [ ! -d "$config_root" ] || [ ! -r "$config_root" ] || [ ! -x "$config_root" ]; then\n'
    b'    printf \'%s\\n\' "pilotfish Plugin blocked: the effective CLAUDE.md cannot be checked safely. Follow $MIGRATION_URL and restart Claude Code."\n'
    b"    exit 0\n"
    b"fi\n"
    b"\n"
    b'config_file=$config_root/CLAUDE.md\n'
    b'if [ -L "$config_file" ]; then\n'
    b'    printf \'%s\\n\' "pilotfish Plugin blocked: the effective CLAUDE.md cannot be checked safely. Follow $MIGRATION_URL and restart Claude Code."\n'
    b"    exit 0\n"
    b"fi\n"
    b'if [ -e "$config_file" ]; then\n'
    b'    if [ ! -f "$config_file" ] || [ ! -r "$config_file" ]; then\n'
    b'        printf \'%s\\n\' "pilotfish Plugin blocked: the effective CLAUDE.md cannot be checked safely. Follow $MIGRATION_URL and restart Claude Code."\n'
    b"        exit 0\n"
    b"    fi\n"
    b"    set +e\n"
    b"    grep -F -q \\\n"
    b"        -e '<!-- pilotfish:begin -->' \\\n"
    b"        -e '<!-- pilotfish:end -->' \\\n"
    b"        -e '<!-- pilotfish v' \\\n"
    b"        -e 'Main-session policy. Named roles (' \\\n"
    b'        "$config_file"\n'
    b"    grep_status=$?\n"
    b"    set -e\n"
    b"    case $grep_status in\n"
    b"        0)\n"
    b'            printf \'%s\\n\' "pilotfish Plugin blocked: legacy global pilotfish detected. Follow $MIGRATION_URL to migrate, then restart Claude Code."\n'
    b"            exit 0\n"
    b"            ;;\n"
    b"        1) ;;\n"
    b"        *)\n"
    b'            printf \'%s\\n\' "pilotfish Plugin blocked: the effective CLAUDE.md cannot be checked safely. Follow $MIGRATION_URL and restart Claude Code."\n'
    b"            exit 0\n"
    b"            ;;\n"
    b"    esac\n"
    b"fi\n"
    b"\n"
    b'cat "${CLAUDE_PLUGIN_ROOT}/policy/sessionstart.txt"\n'
)
HOOK_COMMAND = '/bin/sh "${CLAUDE_PLUGIN_ROOT}/hooks/emit-sessionstart.sh"'
MAX_CHARS = 9_000

REQUIREMENTS = (
    ("PLUG-AUTHORITY-LEAF", "authority", 5),
    ("PLUG-AUTHORITY-MAIN", "authority", 7),
    ("PLUG-DISPATCH-SHAPE", "dispatch", 11),
    ("PLUG-APPROVAL-DISCOVERY", "approval", 12),
    ("PLUG-DISPATCH-BATON", "dispatch", 13),
    ("PLUG-SEVERITY-RISK", "severity", 14),
    ("PLUG-DISPATCH-DIRECT", "dispatch", 15),
    ("PLUG-DISPATCH-DISCOVERY", "dispatch", 16),
    ("PLUG-APPROVAL-PLAN", "approval", 17),
    ("PLUG-APPROVAL-GATE", "approval", 18),
    ("PLUG-AUTHORITY-EXECUTION", "authority", 19),
    ("PLUG-VERIFICATION-GATE", "verification", 20),
    ("PLUG-DISPATCH-BRAKE", "dispatch", 24),
    ("PLUG-DISPATCH-SEARCH", "dispatch", 25),
    ("PLUG-DISPATCH-READ-SCOPE", "dispatch", 26),
    ("PLUG-DISPATCH-COLLECT", "dispatch", 27),
    ("PLUG-DISPATCH-MECHANICAL", "dispatch", 28),
    ("PLUG-DISPATCH-WRITE-SCOPE", "dispatch", 29),
    ("PLUG-DISPATCH-DIRECT-EXCEPTION", "dispatch", 30),
    ("PLUG-DISPATCH-VALUE", "dispatch", 31),
    ("PLUG-DISPATCH-RECURRENCE", "dispatch", 32),
    ("PLUG-DISPATCH-BUG", "dispatch", 33),
    ("PLUG-DISPATCH-INVESTIGATION", "dispatch", 34),
    ("PLUG-DISPATCH-BRIEF", "dispatch", 35),
    ("PLUG-SECURITY-ROUTING", "security", 36),
    ("PLUG-SECURITY-MANDATORY-REVIEW", "security", 37),
    ("PLUG-AUTHORITY-MODEL", "authority", 38),
    ("PLUG-VERIFICATION-PROTOCOL", "verification", 39),
    ("PLUG-APPROVAL-SEQUENCE", "approval", 40),
    ("PLUG-RECOVERY-READINESS", "recovery", 41),
    ("PLUG-VERIFICATION-BOUNDARY", "verification", 42),
    ("PLUG-SEVERITY-DISPOSITION", "severity", 43),
    ("PLUG-RECOVERY-POST-VERDICT", "recovery", 44),
    ("PLUG-VERIFICATION-SCOUT", "verification", 45),
    ("PLUG-RECOVERY-IDENTITY", "recovery", 49),
    ("PLUG-LIVENESS-MODE", "liveness", 50),
    ("PLUG-AUTHORITY-AUTO", "authority", 51),
    ("PLUG-LIVENESS-ASK", "liveness", 52),
    ("PLUG-DISPATCH-PARALLEL", "dispatch", 56),
    ("PLUG-LIVENESS-RUNTIME", "liveness", 57),
)
ROLES = (
    "scout",
    "plan-verifier",
    "security-reviewer",
    "mech-executor",
    "executor",
    "verifier",
    "security-executor",
)
NAMESPACE_REPLACEMENTS = {
    "plan-verifier": (("`security-reviewer`", "`pilotfish:security-reviewer`"),),
    "security-reviewer": (
        ("`security-executor`", "`pilotfish:security-executor`"),
        (
            "Tool allowlist excludes Bash, Write, Edit, NotebookEdit, Agent, Workflow — pre-approval boundary enforced by capability, not prompt text.\n",
            "Tool allowlist excludes Bash, Write, Edit, NotebookEdit, Agent, Workflow — pre-approval boundary enforced by capability, not prompt text. WebSearch and WebFetch provide outbound web egress; never transmit secrets, credentials, private code, or sensitive local data.\n",
        ),
    ),
    "security-executor": (("`security-reviewer`", "`pilotfish:security-reviewer`"),),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def version() -> str:
    value = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise ValueError("VERSION: expected X.Y.Z")
    return value


def json_bytes(document: object) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build_manifest(release_version: str) -> bytes:
    return json_bytes(
        {
            "$schema": "https://json.schemastore.org/claude-code-plugin-manifest.json",
            "name": "pilotfish",
            "displayName": "pilotfish Plugin beta",
            "version": release_version,
            "description": "macOS and Linux Claude Code Plugin beta with hook-based ambient policy activation and namespaced role agents.",
            "author": {
                "name": "Nanako0129",
                "url": "https://github.com/Nanako0129",
            },
            "repository": "https://github.com/Nanako0129/pilotfish",
            "license": "MIT",
            "keywords": [
                "orchestration",
                "ambient-activation",
                "subagents",
                "delegation",
                "beta",
            ],
        }
    )


def build_marketplace(release_version: str) -> bytes:
    return json_bytes(
        {
            "$schema": "https://json.schemastore.org/claude-code-marketplace.json",
            "name": "pilotfish",
            "owner": {
                "name": "Nanako0129",
                "url": "https://github.com/Nanako0129",
            },
            "description": "Marketplace for the pilotfish macOS and Linux Claude Code Plugin beta.",
            "plugins": [
                {
                    "name": "pilotfish",
                    "source": "./plugin",
                    "version": release_version,
                    "description": "Hook-based ambient orchestration beta for macOS and Linux Claude Code.",
                    "category": "productivity",
                    "tags": [
                        "orchestration",
                        "subagents",
                        "delegation",
                        "beta",
                    ],
                }
            ],
        }
    )


def validate_text_bytes(data: bytes, label: str) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"{label}: invalid UTF-8") from error
    if not text.endswith("\n"):
        raise ValueError(f"{label}: final LF required")
    for character in text:
        codepoint = ord(character)
        if (codepoint < 32 and character != "\n") or codepoint == 127:
            raise ValueError(f"{label}: control character U+{codepoint:04X}")
    return text


def build_sessionstart(policy: bytes) -> bytes:
    text = validate_text_bytes(policy, "ambient policy")
    if SENTINEL in text or "SESSIONSTART_AB_ARM" in text:
        raise ValueError("ambient policy: reserved transport marker")
    rendered = (
        f"{SENTINEL}\n"
        "\n"
        f"{OPT_IN}"
        "\n"
        f"{text}"
    )
    if rendered.count(SENTINEL) != 1 or rendered.count(text) != 1:
        raise ValueError("sessionstart: sentinel or policy multiplicity")
    if "SESSIONSTART_AB_ARM" in rendered:
        raise ValueError("sessionstart: study marker forbidden")
    if len(rendered) > MAX_CHARS or len(rendered) + rendered.count("\n") > MAX_CHARS:
        raise ValueError("sessionstart: 9000-character LF/CRLF bound exceeded")
    return rendered.encode("utf-8")


def transform_agent(role: str, source: bytes) -> bytes:
    text = validate_text_bytes(source, f"template agent {role}")
    for old, new in NAMESPACE_REPLACEMENTS.get(role, ()):
        if text.count(old) != 1:
            raise ValueError(f"template agent {role}: expected one {old}")
        text = text.replace(old, new)
    if "Explore" in text:
        raise ValueError(f"template agent {role}: Explore is not shipped")
    return text.encode("utf-8")


def build_matrix(template: bytes, policy: bytes) -> bytes:
    source = validate_text_bytes(template, "orchestration template").splitlines()
    ambient = [
        line
        for line in validate_text_bytes(policy, "ambient policy").splitlines()
        if line
    ]
    if len(ambient) != len(REQUIREMENTS):
        raise ValueError("ambient policy: mapped-line count drift")
    entries = []
    for (requirement_id, category, line_number), ambient_line in zip(
        REQUIREMENTS, ambient, strict=True
    ):
        entries.append(
            {
                "id": requirement_id,
                "category": category,
                "source_line": line_number,
                "source_clause": source[line_number - 1],
                "ambient_line": ambient_line,
                "focused_test": "tests.test_plugin.PluginArtifactTests.test_policy_requirement_matrix",
            }
        )
    document = {
        "schema_version": 1,
        "source": {
            "path": "templates/claude-md.orchestration.md",
            "sha256": sha256(template),
        },
        "requirements": entries,
    }
    return json_bytes(document)


def generated() -> dict[Path, bytes]:
    template = TEMPLATE.read_bytes()
    policy = POLICY.read_bytes()
    release_version = version()
    artifacts = {
        MANIFEST: build_manifest(release_version),
        MARKETPLACE: build_marketplace(release_version),
        SESSIONSTART: build_sessionstart(policy),
        MATRIX: build_matrix(template, policy),
        PLUGIN / "LICENSE": (ROOT / "LICENSE").read_bytes(),
        PLUGIN / "hooks" / "emit-sessionstart.sh": SCRIPT,
    }
    for role in ROLES:
        source = ROOT / "templates" / "agents" / f"{role}.md"
        artifacts[PLUGIN / "agents" / f"{role}.md"] = transform_agent(
            role, source.read_bytes()
        )
    return artifacts


def validate_transport(hooks: bytes, script: bytes) -> None:
    config = json.loads(hooks)
    if set(config.get("hooks", {})) != {"SessionStart"}:
        raise ValueError("hooks: only SessionStart is allowed")
    groups = config["hooks"]["SessionStart"]
    if len(groups) != 1 or groups[0].get("matcher") != "startup|resume|clear|compact":
        raise ValueError("hooks: SessionStart matcher drift")
    handlers = groups[0].get("hooks", [])
    if len(handlers) != 1 or handlers[0] != {"type": "command", "command": HOOK_COMMAND}:
        raise ValueError("hooks: command drift or hostile path substitution")
    if script != SCRIPT:
        raise ValueError("hook script: content drift or hostile path substitution")


def check() -> list[str]:
    errors = []
    try:
        validate_transport(
            (PLUGIN / "hooks" / "hooks.json").read_bytes(),
            (PLUGIN / "hooks" / "emit-sessionstart.sh").read_bytes(),
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
    try:
        artifacts = generated()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(str(error))
        return errors
    for path, expected in artifacts.items():
        try:
            actual = path.read_bytes()
        except OSError as error:
            errors.append(f"{path.relative_to(ROOT)}: {error}")
            continue
        if actual != expected:
            errors.append(f"{path.relative_to(ROOT)}: generated bytes drift")
    return errors


def write() -> None:
    for path, data in generated().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        os.chmod(path, 0o644)
    for directory in sorted({path.parent for path in generated()}):
        os.chmod(directory, 0o755)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write:
        write()
    errors = check()
    if errors:
        for error in errors:
            print(error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
