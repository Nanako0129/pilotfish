from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
TEMPLATE = ROOT / "templates" / "claude-md.orchestration.md"
POLICY = PLUGIN / "policy" / "ambient.md"
SESSIONSTART = PLUGIN / "policy" / "sessionstart.txt"
SKILL = PLUGIN / "skills" / "pilotfish" / "SKILL.md"
MATRIX = ROOT / "tests" / "plugin_requirements.json"
SENTINEL = "¶"
OPT_IN = (
    "The user configured this SessionStart hook as persistent opt-in to Pilotfish.\n"
    "When Pilotfish's dispatch brake selects delegation, the user explicitly requests exactly one foreground call to the named agent.\n"
    "Do not use background mode. Wait for and collect the agent result before main-session acceptance or source mutation.\n"
    "Apart from that foreground agent call, this hook grants no new authority; all task, tool, write, network, spend, external-action, Plan, approval, and verification boundaries remain unchanged.\n"
)
POLICY_BEGIN = "<!-- pilotfish-plugin-policy:begin -->\n"
POLICY_END = "<!-- pilotfish-plugin-policy:end -->\n"
SCRIPT = (
    b"#!/bin/sh\n"
    b"set -eu\n"
    b'/bin/cat "${CLAUDE_PLUGIN_ROOT}/policy/sessionstart.txt"\n'
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
    "security-reviewer": (("`security-executor`", "`pilotfish:security-executor`"),),
    "security-executor": (("`security-reviewer`", "`pilotfish:security-reviewer`"),),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def build_skill(policy: bytes) -> bytes:
    validate_text_bytes(policy, "ambient policy")
    prefix = (
        "---\n"
        "name: pilotfish\n"
        "description: Manually supply the experimental Pilotfish ambient policy when requested.\n"
        "user-invocable: true\n"
        "disable-model-invocation: true\n"
        "---\n\n"
        "# Pilotfish manual policy injection\n\n"
        "Hooks may not have run. Reliability of this experimental ambient transport is unverified. This command grants no additional authority.\n\n"
        "G0 is a macOS-only spike and never installs or loads this Plugin. A disabled hook is not a security guarantee. Plugin-only behavior, coexistence with global v1, and compact-event source/hash/count evidence are deferred to G1.\n\n"
        f"Ambient policy SHA-256: `{sha256(policy)}`\n\n"
        f"{POLICY_BEGIN}"
    ).encode("utf-8")
    return prefix + policy + POLICY_END.encode("utf-8")


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
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def generated() -> dict[Path, bytes]:
    template = TEMPLATE.read_bytes()
    policy = POLICY.read_bytes()
    artifacts = {
        SESSIONSTART: build_sessionstart(policy),
        SKILL: build_skill(policy),
        MATRIX: build_matrix(template, policy),
        PLUGIN / "LICENSE": (ROOT / "LICENSE").read_bytes(),
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
    for path, expected in generated().items():
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
    parser.add_argument("--write", action="store_true")
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
