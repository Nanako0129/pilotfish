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
    r"(?:\d*|&)>>?\|?\s*/dev/null|(?:\d*)?>\s*&\d+"
)
REDIRECT = re.compile(r"(?:\d*|&)>>?\|?\s*[^&|\s>]")
WRITE_COMMAND = re.compile(
    r"\btee\b|\bsed\s+-i|\bdd\b|\btruncate\b|\bmv\b|\bcp\b|"
    r"set \+o noclobber|setopt.*clobber"
)
RUN_ROOT = re.compile(r"/private/tmp/[^\s\"']*|/tmp/[^\s\"']*")
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
SAFE_GIT_SUBCOMMANDS = {"diff", "log", "ls-files", "rev-parse", "show", "status"}
SHELL_SEPARATORS = {";", "&&", "||", "|", "&", "\n"}
SHELL_PREFIXES = {"!", "do", "elif", "if", "then", "until", "while"}
SHELL_ONLY_SEGMENTS = {"done", "else", "esac", "fi"}
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")


def bash_writes(command: str) -> bool:
    sanitized = SAFE_REDIRECT.sub(" ", command)
    if REDIRECT.search(sanitized) or WRITE_COMMAND.search(command):
        return True
    if "$(" in sanitized or "`" in sanitized:
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
        if token not in SHELL_SEPARATORS:
            segment.append(token)
            continue
        if not segment:
            continue
        if segment[0] == "for":
            segment = []
            continue
        while segment and (
            segment[0] in SHELL_PREFIXES or ASSIGNMENT.fullmatch(segment[0])
        ):
            segment.pop(0)
        if segment and segment[0] not in SHELL_ONLY_SEGMENTS:
            program = Path(segment[0]).name
            args = segment[1:]
            if program == "git":
                read_only = (
                    bool(args)
                    and args[0] in SAFE_GIT_SUBCOMMANDS
                    and not any(
                        arg == "--output" or arg.startswith("--output=")
                        for arg in args[1:]
                    )
                )
            elif program == "npm":
                read_only = bool(args) and args[0] == "test"
            elif program == "node":
                read_only = bool(args) and args[0] in {"--test", "--version", "-v"}
            elif program == "sed":
                read_only = not any(
                    arg.startswith(("-i", "--in-place")) for arg in args
                )
            elif program == "find":
                read_only = not any(
                    arg in {"-delete", "-exec", "-execdir", "-ok", "-okdir"}
                    or arg.startswith(("-fprint", "-fls"))
                    for arg in args
                )
            elif program == "sort":
                read_only = not any(
                    arg.startswith("-o")
                    or arg == "--output"
                    or arg.startswith("--output=")
                    for arg in args
                )
            else:
                read_only = program in READ_ONLY_COMMANDS
            if not read_only:
                return True
        segment = []
    return False


def summarize(command: str) -> str:
    text = re.sub(r"\s+", " ", RUN_ROOT.sub("RUN_ROOT", command)).strip()
    match = REDIRECT.search(SAFE_REDIRECT.sub(" ", text)) or WRITE_COMMAND.search(text)
    if not match:
        return text[:240]
    start = max(0, match.start() - 100)
    return text[start : match.end() + 140]


def classify(path: Path) -> dict[str, object]:
    top_tools: list[str] = []
    worker_tools: list[str] = []
    top_writes: list[str] = []
    worker_writes: list[str] = []
    agent_calls: list[dict[str, object]] = []
    agent_tool_ids: set[str] = set()
    collected_agent_ids: set[str] = set()
    main_model = client_version = None
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
                if name in ("Write", "Edit"):
                    writes.append(f"{name} {Path(inputs.get('file_path', '')).name}")
                elif name == "Bash" and bash_writes(inputs.get("command", "")):
                    writes.append(f"Bash {summarize(inputs.get('command', ''))}")
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
        "async_launch_observed": "Async agent launched" in text,
        "subagent_result_collected": bool(collected_agent_ids),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("streams", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps([classify(path) for path in args.streams], indent=2))


if __name__ == "__main__":
    main()
