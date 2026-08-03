#!/usr/bin/env python3
"""Extract sanitized topology evidence from Claude stream-json output."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
from pathlib import Path


SAFE_REDIRECT = re.compile(
    r"(?:\d*|&)>>?\|?\s*/dev/null(?=$|[\s;&|()<>])|"
    r"(?:\d*)?>\s*&\d+(?=$|[\s;&|()<>])"
)
REDIRECT = re.compile(r"(?:\d*|&)>>?\|?\s*[^&|\s>]")
WRITE_COMMAND = re.compile(
    r"\btee\b|\bsed\s+-i|\bdd\b|\btruncate\b|\bmv\b|\bcp\b|"
    r"set \+o noclobber|setopt.*clobber"
)
READ_ONLY_COMMANDS = {
    "[",
    "basename",
    "cat",
    "cd",
    "date",
    "dirname",
    "echo",
    "false",
    "grep",
    "head",
    "jq",
    "ls",
    "md5",
    "md5sum",
    "pwd",
    "printf",
    "realpath",
    "rg",
    "sha256sum",
    "sort",
    "stat",
    "tail",
    "test",
    "true",
    "uname",
    "wc",
}
SAFE_GIT_SUBCOMMANDS = {"rev-parse"}
SHELL_SEPARATOR_CHARS = frozenset(";&|\n")
SHELL_PREFIXES = {"!", "do", "elif", "else", "if", "then", "until", "while"}
SHELL_ONLY_SEGMENTS = {"done", "esac", "fi"}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
SAFE_SED_PRINT = re.compile(r"^(?:\d+|\$)(?:,(?:\d+|\$))?[pP]$")
WRITE_REDIRECT_TARGET = re.compile(
    r"(?:\d*|&)>>?\|?\s*(?!&)([^\s;&|<>]+)"
)


def fixture_test_source_digest(root: Path) -> str | None:
    package = root / "package.json"
    tests = root / "test"
    if not package.is_file() or package.is_symlink() or not tests.is_dir():
        return None
    paths = [package, *sorted(path for path in tests.rglob("*") if path.is_file())]
    if any(path.is_symlink() for path in paths):
        return None
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
        f"{path.relative_to(root).as_posix()}\n"
        for path in paths
    ]
    return hashlib.sha256("".join(lines).encode()).hexdigest()


def strip_shell_comments(command: str) -> str:
    output: list[str] = []
    quote = None
    index = 0
    while index < len(command):
        char = command[index]
        if char == "\\" and quote != "'" and index + 1 < len(command):
            output.extend(command[index : index + 2])
            index += 2
            continue
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
        if (
            char == "#"
            and quote is None
            and (index == 0 or command[index - 1] in " \t\r\n;&|")
        ):
            newline = command.find("\n", index)
            if newline < 0:
                break
            output.append("\n")
            index = newline + 1
            continue
        output.append(char)
        index += 1
    return "".join(output)


def split_shell_segments(command: str) -> list[str]:
    segments: list[str] = []
    current: list[str] = []
    quote = None
    index = 0
    while index < len(command):
        char = command[index]
        if char == "\\" and quote != "'" and index + 1 < len(command):
            current.extend(command[index : index + 2])
            index += 2
            continue
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
        if (
            quote is None
            and char in ";&|\n"
            and not (char == "|" and current and current[-1] == ">")
        ):
            if current:
                segments.append("".join(current))
                current = []
            while index + 1 < len(command) and command[index + 1] in ";&|\n":
                index += 1
        else:
            current.append(char)
        index += 1
    if current:
        segments.append("".join(current))
    return segments


def is_shell_separator(token: str) -> bool:
    return bool(token) and set(token) <= SHELL_SEPARATOR_CHARS


def has_unquoted_redirect(command: str) -> bool:
    quote = None
    index = 0
    while index < len(command):
        char = command[index]
        if char == "\\" and quote != "'" and index + 1 < len(command):
            index += 2
            continue
        if char in {"'", '"'}:
            quote = None if quote == char else char if quote is None else quote
        elif char == ">" and quote is None:
            return True
        index += 1
    return False


def bash_writes(command: str, trusted_test_sources: bool = False) -> bool:
    sanitized = SAFE_REDIRECT.sub(" ", strip_shell_comments(command))
    if REDIRECT.search(sanitized) or WRITE_COMMAND.search(sanitized):
        return True
    if any(operator in sanitized for operator in ("$(", "`", "<(", ">(")):
        return True
    try:
        lexer = shlex.shlex(sanitized, posix=True, punctuation_chars=";&|\n")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return True

    segment: list[str] = []
    for token in tokens + [";"]:
        if not is_shell_separator(token):
            segment.append(token)
            continue
        if not segment:
            continue
        if segment[0] == "for":
            segment = []
            continue
        while segment and segment[0] in SHELL_PREFIXES:
            segment.pop(0)
        has_environment = False
        while segment and ASSIGNMENT.fullmatch(segment[0]):
            has_environment = True
            segment.pop(0)
        if has_environment:
            return True
        if segment and segment[0] not in SHELL_ONLY_SEGMENTS:
            program = segment[0]
            args = segment[1:]
            if program == "git":
                read_only = (
                    bool(args)
                    and args[0] in SAFE_GIT_SUBCOMMANDS
                )
            elif program == "npm":
                read_only = trusted_test_sources and args == ["test"]
            elif program == "node":
                read_only = args in (["--version"], ["-v"]) or (
                    trusted_test_sources and args == ["--test"]
                )
            elif program == "rg":
                read_only = not any(
                    arg in {"--pre", "--hostname-bin"}
                    or arg.startswith(("--pre=", "--hostname-bin="))
                    for arg in args
                )
            elif program == "sed":
                read_only = (
                    len(args) >= 2
                    and args[0] in {"-n", "--quiet", "--silent"}
                    and SAFE_SED_PRINT.fullmatch(args[1]) is not None
                    and not any(
                        arg.startswith("-") and arg != "-" for arg in args[2:]
                    )
                )
            elif program == "find":
                read_only = not any(
                    arg in {"-delete", "-exec", "-execdir", "-ok", "-okdir"}
                    or arg.startswith(("-fprint", "-fls"))
                    for arg in args
                )
            elif program == "sort":
                read_only = not any(
                    (
                        arg.startswith("--")
                        and len(arg.split("=", 1)[0]) > 2
                        and any(
                            option.startswith(arg.split("=", 1)[0])
                            for option in ("--output", "--compress-program")
                        )
                    )
                    or (
                        arg.startswith("-")
                        and not arg.startswith("--")
                        and "o" in arg[1:]
                    )
                    for arg in args
                )
            else:
                read_only = program in READ_ONLY_COMMANDS
            if not read_only:
                return True
        segment = []
    return False


def bash_proves_fixture_source_write(command: str, cwd: Path | None) -> bool:
    if cwd is None:
        return False
    sanitized = SAFE_REDIRECT.sub(" ", strip_shell_comments(command))
    source = (cwd / "src").resolve()
    directory = cwd.resolve()
    for segment in split_shell_segments(sanitized):
        for match in WRITE_REDIRECT_TARGET.finditer(segment):
            token = match.group(1).strip("'\"")
            if "/" in token and "$" in token:
                continue
            target = Path(token)
            target = target.resolve() if target.is_absolute() else (directory / target).resolve()
            if target != source and source in target.parents:
                return True
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        while tokens and tokens[0] in SHELL_PREFIXES:
            tokens.pop(0)
        if len(tokens) >= 2 and tokens[0] == "cd":
            target = Path(tokens[1])
            directory = (
                target.resolve()
                if target.is_absolute()
                else (directory / target).resolve()
            )
    return False


def classify(
    path: Path, trusted_test_source_sha256: str | None = None
) -> dict[str, object]:
    top_tools: list[str] = []
    worker_tools: list[str] = []
    top_writes: list[str] = []
    worker_writes: list[str] = []
    agent_calls: list[dict[str, object]] = []
    agent_tool_ids: set[str] = set()
    collected_agent_ids: set[str] = set()
    worker_write_candidates: dict[str, str] = {}
    main_model = client_version = None
    cwd = None
    trusted_test_sources = False
    cost = None
    model_costs: dict[str, float] = {}

    raw = path.read_bytes()
    for raw_line in raw.splitlines():
        if not raw_line.strip():
            continue
        event = json.loads(raw_line)
        if event.get("subtype") == "init":
            main_model = event.get("model")
            client_version = event.get("claude_code_version")
            cwd = Path(event["cwd"]) if event.get("cwd") else None
            trusted_test_sources = bool(
                trusted_test_source_sha256
                and cwd
                and fixture_test_source_digest(cwd) == trusted_test_source_sha256
            )
        if event.get("type") == "assistant":
            is_worker = event.get("parent_tool_use_id") is not None
            tools = worker_tools if is_worker else top_tools
            writes = worker_writes if is_worker else top_writes
            for item in event.get("message", {}).get("content", []):
                if item.get("type") != "tool_use":
                    continue
                name = item["name"]
                inputs = item.get("input", {})
                tools.append(name)
                if not is_worker and name in ("Agent", "Task"):
                    if item.get("id"):
                        agent_tool_ids.add(item["id"])
                    agent_calls.append(
                        {
                            "subagent_type": inputs.get("subagent_type"),
                            "run_in_background": inputs.get("run_in_background"),
                            "invocation_model_present": bool(inputs.get("model")),
                        }
                    )
                if is_worker:
                    tool_id = item.get("id")
                    if not tool_id:
                        continue
                    if name in ("Write", "Edit"):
                        write_path = inputs.get("file_path", "")
                        target = Path(write_path)
                        target = (
                            target.resolve()
                            if target.is_absolute()
                            else (cwd / target).resolve() if cwd else None
                        )
                        source = (cwd / "src").resolve() if cwd else None
                        if target and source and source in target.parents:
                            worker_write_candidates[tool_id] = (
                                f"{name} {target.name}"
                            )
                    elif name == "Bash" and bash_proves_fixture_source_write(
                        inputs.get("command", ""), cwd
                    ):
                        worker_write_candidates[tool_id] = "Bash"
                elif name in ("Write", "Edit", "NotebookEdit"):
                    write_path = inputs.get("file_path") or inputs.get(
                        "notebook_path", ""
                    )
                    writes.append(f"{name} {Path(write_path).name}")
                elif name == "Bash":
                    command = inputs.get("command", "")
                    if bash_writes(command, trusted_test_sources):
                        writes.append("Bash")
        if event.get("type") == "user":
            for item in event.get("message", {}).get("content", []):
                if item.get("type") != "tool_result":
                    continue
                candidate = worker_write_candidates.pop(
                    item.get("tool_use_id"), None
                )
                if candidate and item.get("is_error") is False:
                    worker_writes.append(candidate)
        if event.get("type") == "user" and event.get("parent_tool_use_id") is None:
            result = event.get("tool_use_result") or {}
            if not isinstance(result, dict):
                result = {}
            for item in event.get("message", {}).get("content", []):
                if (
                    result.get("status") == "completed"
                    and item.get("type") == "tool_result"
                    and item.get("tool_use_id") in agent_tool_ids
                ):
                    collected_agent_ids.add(item["tool_use_id"])
        if event.get("type") == "result":
            cost = event.get("total_cost_usd")
            model_costs = {
                model: round(usage.get("costUSD", 0), 7)
                for model, usage in (event.get("modelUsage") or {}).items()
            }

    text = raw.decode("utf-8")
    return {
        "source": path.name,
        "raw_stream_sha256": hashlib.sha256(raw).hexdigest(),
        "client_version": client_version,
        "observed_main_model": main_model,
        "client_reported_cost_usd": cost,
        "model_costs_usd": model_costs,
        "top_level_tools": top_tools,
        "top_level_source_write_tools": [entry.split(" ", 1)[0] for entry in top_writes],
        "main_session_mutation_paths": top_writes,
        "main_session_mutated": bool(top_writes),
        "agent_calls": agent_calls,
        "worker_tools": worker_tools,
        "worker_source_write_tools": [entry.split(" ", 1)[0] for entry in worker_writes],
        "worker_mutation_paths": worker_writes,
        "trusted_test_sources": trusted_test_sources,
        "async_launch_observed": "Async agent launched" in text,
        "subagent_result_collected": bool(collected_agent_ids),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trusted-test-source-sha256")
    parser.add_argument("streams", nargs="+", type=Path)
    args = parser.parse_args()
    if args.trusted_test_source_sha256 and not re.fullmatch(
        r"[0-9a-f]{64}", args.trusted_test_source_sha256
    ):
        parser.error("--trusted-test-source-sha256 must be lowercase SHA-256")
    print(
        json.dumps(
            [
                classify(path, args.trusted_test_source_sha256)
                for path in args.streams
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
