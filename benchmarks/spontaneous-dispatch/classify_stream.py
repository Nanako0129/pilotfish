#!/usr/bin/env python3
"""Extract dispatch reachability evidence from Claude stream-json output."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def classify(path: Path) -> dict[str, object]:
    top_tools: list[str] = []
    worker_tools: list[str] = []
    agent_calls: list[dict[str, object]] = []
    agent_tool_ids: set[str] = set()
    collected_agent_ids: set[str] = set()
    main_model = client_version = cost = None
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
            for item in event.get("message", {}).get("content", []):
                if item.get("type") != "tool_use":
                    continue
                name = item["name"]
                tools.append(name)
                if not is_worker and name in ("Agent", "Task"):
                    inputs = item.get("input", {})
                    if item.get("id"):
                        agent_tool_ids.add(item["id"])
                    agent_calls.append(
                        {
                            "subagent_type": inputs.get("subagent_type"),
                            "run_in_background": inputs.get("run_in_background"),
                            "invocation_model_present": bool(inputs.get("model")),
                        }
                    )
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

    return {
        "source": path.name,
        "raw_stream_sha256": hashlib.sha256(raw).hexdigest(),
        "client_version": client_version,
        "observed_main_model": main_model,
        "client_reported_cost_usd": cost,
        "model_costs_usd": model_costs,
        "top_level_tools": top_tools,
        "agent_calls": agent_calls,
        "worker_tools": worker_tools,
        "async_launch_observed": b"Async agent launched" in raw,
        "subagent_result_collected": bool(collected_agent_ids),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("streams", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps([classify(path) for path in args.streams], indent=2))


if __name__ == "__main__":
    main()
