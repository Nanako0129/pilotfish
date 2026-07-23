#!/usr/bin/env python3
"""Build Claude Code --agents JSON from pilotfish agent templates."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def build_agents(directory: Path) -> dict[str, dict[str, object]]:
    agents: dict[str, dict[str, object]] = {}

    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        try:
            _, frontmatter, prompt = text.split("---", 2)
        except ValueError as error:
            raise SystemExit(f"invalid agent template: {path}") from error

        values: dict[str, str] = {}
        for line in frontmatter.strip().splitlines():
            key, value = line.split(":", 1)
            values[key] = value.strip()

        agent: dict[str, object] = {
            "description": values["description"],
            "prompt": prompt.strip(),
            "model": values["model"],
            "effort": values["effort"],
        }
        for field in ("tools", "disallowedTools"):
            if field in values:
                agent[field] = [item.strip() for item in values[field].split(",")]

        agents[values["name"]] = agent

    return agents


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: build-agents-json.py PATH_TO_TEMPLATES_AGENTS")

    agents = build_agents(Path(sys.argv[1]))
    print(json.dumps(agents, separators=(",", ":")))


if __name__ == "__main__":
    main()
