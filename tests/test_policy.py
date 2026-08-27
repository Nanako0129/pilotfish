from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROLES = (
    "scout",
    "Explore",
    "plan-verifier",
    "security-reviewer",
    "mech-executor",
    "executor",
    "verifier",
    "security-executor",
)

ATTEMPT_ACCOUNTING_SOURCES = (
    "benchmarks/baton-compatibility/results.json",
    "benchmarks/baton-dispatch-effect/results.json",
    "benchmarks/dispatch-brake/results.json",
    "benchmarks/dispatch-brake/positive-controls/results.json",
    "benchmarks/prompt-compression/results.json",
    "benchmarks/spontaneous-dispatch/results.json",
    "benchmarks/spontaneous-dispatch/compact-policy-full-matrix.json",
    "benchmarks/spontaneous-dispatch/cue-free-tui.json",
    "benchmarks/spontaneous-dispatch/issue-29-recovery.json",
    "benchmarks/spontaneous-dispatch/issue-29-topology.json",
    "benchmarks/verifier-boundary/results.json",
)
ATTEMPT_ACCOUNTING_MARKERS = frozenset(
    {
        "claim",
        "status",
        "passed",
        "test_passed",
        "topology_pass",
        "reachability",
        "raw_stream_sha256",
        "transcript_sha256",
    }
)
ATTEMPT_ACCOUNTING_COVERAGE_EXCLUSIONS = {
    (
        "benchmarks/prompt-compression/results.json",
        "/static_gate",
    ): "static byte/policy gate, not a behavioral invocation",
    (
        "benchmarks/prompt-compression/results.json",
        "/context_census",
    ): "static context census, not a behavioral invocation",
    (
        "benchmarks/prompt-compression/results.json",
        "/paid_campaign",
    ): "campaign bookkeeping, not a behavioral invocation",
}
ATTEMPT_ACCOUNTING_PASS_STATUSES = frozenset(
    {
        "passed",
        "passed_with_corrective_verification",
        "success",
        "release_qualified",
        "correctness_pass",
        "correctness_pass_no_activation",
        "no_activation_observed_for_bounded_task",
        "passed_activation_dispatch_ownership_collection_correctness",
        "passed_activation_dispatch_ownership_collection_final_byte_correctness",
        "passed_before_final_edit",
        "passed_after_final_write",
    }
)
ATTEMPT_ACCOUNTING_FAILURE_STATUSES = frozenset(
    {
        "rejected",
        "failed",
        "error_max_budget_usd",
        "error_during_execution",
        "success_topology_fail",
        "activation_dispatch_pass_ownership_fail",
        "activation_dispatch_parallel_launch_pass_ownership_fail",
        "topology_pass_runtime_limit_outcome_incomplete",
        "correctness_passed_topology_blocked",
        "correctness_passed_same_topology_blocker",
        "stopped_after_two_revise",
        "stopped_after_failed_topology",
        "rejected_quota_exhausted",
        "rejected_operator_contract_blocked_agents",
    }
)
ATTEMPT_ACCOUNTING_NOT_RUN_STATUSES = frozenset(
    {"not_run", "usage_credits_required"}
)
ATTEMPT_ACCOUNTING_FAILURE_FIELDS = (
    "failure",
    "failures",
    "failure_reason",
    "failure_reasons",
    "failure_summary",
)
ATTEMPT_ACCOUNTING_ATTEMPT_ARRAY_KEYS = frozenset(
    {
        "runs",
        "attempts",
        "cells",
        "complete_runs",
        "interrupted_policy_probes",
        "failed_attempts",
    }
)
ATTEMPT_ACCOUNTING_SINGULAR_ATTEMPTS = {
    "benchmarks/baton-dispatch-effect/results.json": (
        "/release_payload_replay",
    ),
    "benchmarks/prompt-compression/results.json": (
        "/behavioral_gates/spontaneous_mechanical_candidate",
        "/behavioral_gates/spontaneous_mechanical_v1_3_3_control",
        "/behavioral_gates/spontaneous_bug_candidate",
        "/behavioral_gates/explicit_lifecycle_turn_1",
        "/behavioral_gates/explicit_lifecycle_user_continuation",
        "/behavioral_gates/small_lifecycle",
    ),
    "benchmarks/verifier-boundary/results.json": (
        "/passing_gate/schema_lifecycle/attempt_a",
        "/passing_gate/schema_lifecycle/attempt_b",
        "/passing_gate/routine_docs_control",
        "/passing_gate/post_cap_plan_control",
        "/superseded_v1_3_6_passing_gate/schema_lifecycle",
        "/superseded_v1_3_6_passing_gate/routine_docs_control",
        "/superseded_v1_3_6_passing_gate/post_cap_plan_control",
    ),
}
ATTEMPT_ACCOUNTING_REVIEWED_FAILURES = {
    (
        "benchmarks/verifier-boundary/results.json",
        "/failed_attempts/2",
    ): {
        "name": "compressed-candidate-schema-non-reproduction",
        "outcome": "did not reproduce",
    },
    (
        "benchmarks/verifier-boundary/results.json",
        "/failed_attempts/3",
    ): {
        "name": "uncollected-background-verification",
        "outcome": "approval gate held; acceptance not met",
    },
}
ATTEMPT_ACCOUNTING_IDENTITY_FIELDS = (
    ("policy_sha256", "hash"),
    ("policy_orchestration_sha256", "hash"),
    ("orchestration_sha256", "hash"),
    ("configuration", "config"),
    ("policy_version", "version"),
    ("candidate_version", "version"),
    ("release_candidate_version", "version"),
)
ATTEMPT_ACCOUNTING_REVIEWED_IDENTITIES = {
    (
        "benchmarks/prompt-compression/results.json",
        "/behavioral_gates/spontaneous_mechanical_v1_3_3_control",
    ): {"version": "1.3.3"},
    **{
        (
            "benchmarks/spontaneous-dispatch/cue-free-tui.json",
            f"/campaign/cells/{index}",
        ): {
            "hash": "5ecbbe9a797ba1269a20ac9a1aa3ba5182bf7d9da887ea889263ef9ee64c0564"
        }
        for index in range(4)
    },
}
ATTEMPT_ACCOUNTING_REVIEWED_EVIDENCE_OWNERS = {
    (
        "benchmarks/spontaneous-dispatch/cue-free-tui.json",
        "",
        0,
    ): (
        "benchmarks/spontaneous-dispatch/cue-free-tui.json",
        "/campaign/cells/3",
        0,
    ),
    (
        "benchmarks/spontaneous-dispatch/cue-free-tui.json",
        "/tui_observation",
        0,
    ): (
        "benchmarks/spontaneous-dispatch/cue-free-tui.json",
        "/campaign/cells/3",
        0,
    ),
}


def _attempt_accounting_pointer_part(value: object) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def _attempt_accounting_marked_records(
    value: object, pointer: str = ""
) -> list[tuple[str, dict]]:
    records: list[tuple[str, dict]] = []
    if isinstance(value, dict):
        if ATTEMPT_ACCOUNTING_MARKERS.intersection(value):
            records.append((pointer, value))
        for key, child in value.items():
            records.extend(
                _attempt_accounting_marked_records(
                    child, pointer + "/" + _attempt_accounting_pointer_part(key)
                )
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            records.extend(
                _attempt_accounting_marked_records(child, pointer + "/" + str(index))
            )
    return records


def _attempt_accounting_nonempty(value: object) -> bool:
    return value not in (None, "", [], {})


def _attempt_accounting_pointer_key(pointer: dict) -> tuple[str, str, int]:
    assert isinstance(pointer, dict)
    source = pointer.get("source")
    json_pointer = pointer.get("json_pointer")
    occurrence = pointer.get("occurrence", 0)
    assert isinstance(source, str) and source
    assert isinstance(json_pointer, str)
    assert type(occurrence) is int and occurrence >= 0
    return source, json_pointer, occurrence


def _attempt_accounting_occurrence_count(
    source: str, pointer: str, record: dict
) -> int:
    if source != "benchmarks/verifier-boundary/results.json":
        return 1
    if pointer == "/failed_attempts/2":
        return 2 if isinstance(record.get("inconclusive_diagnostic"), dict) else 1
    if pointer == "/failed_attempts/3":
        hashes = record.get("raw_stream_sha256")
        return len(hashes) if isinstance(hashes, list) and hashes else 1
    return 1


def _attempt_accounting_candidate_identity(
    record: dict,
) -> dict[str, object]:
    identity: dict[str, object] = {}
    for source_key, identity_key in ATTEMPT_ACCOUNTING_IDENTITY_FIELDS:
        value = record.get(source_key)
        if identity_key not in identity and _attempt_accounting_nonempty(value):
            identity[identity_key] = value
    return identity


def _attempt_accounting_candidate_identity_for_attempt(
    source: str, pointer: str, document: object
) -> dict[str, object]:
    reviewed_identity = ATTEMPT_ACCOUNTING_REVIEWED_IDENTITIES.get(
        (source, pointer)
    )
    if reviewed_identity is not None:
        return reviewed_identity
    if pointer != "" and not pointer.startswith("/"):
        raise AssertionError(f"invalid JSON Pointer: {pointer!r}")
    tokens = pointer[1:].split("/") if pointer else []
    for depth in range(len(tokens), -1, -1):
        ancestor_pointer = "" if depth == 0 else "/" + "/".join(tokens[:depth])
        ancestor = _attempt_accounting_resolve_pointer(document, ancestor_pointer)
        if isinstance(ancestor, dict):
            identity = _attempt_accounting_candidate_identity(ancestor)
            if identity:
                return identity
    return {}


def _attempt_accounting_outcome(
    record: dict, source: str | None = None, pointer: str | None = None
) -> tuple[str, tuple[str, ...]]:
    if source is not None and pointer is not None:
        reviewed_failure = ATTEMPT_ACCOUNTING_REVIEWED_FAILURES.get(
            (source, pointer)
        )
        if reviewed_failure is not None and all(
            record.get(field) == expected
            for field, expected in reviewed_failure.items()
        ):
            return "failed", (f"reviewed_failure={reviewed_failure['name']}",)

    boundaries: list[str] = []
    for key in ("passed", "test_passed", "topology_pass"):
        if record.get(key) is False:
            boundaries.append(f"{key}=false")
    if record.get("reachability") == "FAIL":
        boundaries.append("reachability=FAIL")
    status = record.get("status")
    if status in ATTEMPT_ACCOUNTING_FAILURE_STATUSES:
        boundaries.append(f"status={status}")
    for key in ATTEMPT_ACCOUNTING_FAILURE_FIELDS:
        if key in record and _attempt_accounting_nonempty(record[key]):
            boundaries.append(f"{key}=nonempty")
    if boundaries:
        return "failed", tuple(boundaries)
    for key in ("passed", "test_passed", "topology_pass"):
        if record.get(key) is True:
            return "passed", (f"{key}=true",)
    if record.get("reachability") == "PASS":
        return "passed", ("reachability=PASS",)
    if status in ATTEMPT_ACCOUNTING_PASS_STATUSES:
        return "passed", (f"status={status}",)
    if status in ATTEMPT_ACCOUNTING_NOT_RUN_STATUSES:
        return "not_run", (f"status={status}",)
    return "unknown", ()


def _attempt_accounting_attempt_pointers(
    source: str, document: object
) -> list[tuple[str, int]]:
    pointers: list[tuple[str, int]] = []

    def add(pointer: str, occurrence: int = 0) -> None:
        key = (pointer, occurrence)
        if key not in pointers:
            pointers.append(key)

    def add_attempt(pointer: str) -> None:
        record = _attempt_accounting_resolve_pointer(document, pointer)
        assert isinstance(record, dict)
        for occurrence in range(
            _attempt_accounting_occurrence_count(source, pointer, record)
        ):
            add(pointer, occurrence)

    def walk(value: object, pointer: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_pointer = pointer + "/" + _attempt_accounting_pointer_part(key)
                if key in ATTEMPT_ACCOUNTING_ATTEMPT_ARRAY_KEYS and isinstance(
                    child, list
                ):
                    for index in range(len(child)):
                        add_attempt(child_pointer + "/" + str(index))
                walk(child, child_pointer)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, pointer + "/" + str(index))

    walk(document)
    if source == "benchmarks/baton-compatibility/results.json":
        for pointer, record in _attempt_accounting_marked_records(document):
            if record.get("granularity") != "invocation":
                continue
            turns = record.get("turns")
            if isinstance(turns, list):
                for index in range(len(turns)):
                    add_attempt(pointer + "/turns/" + str(index))
            else:
                add_attempt(pointer)
    for pointer in ATTEMPT_ACCOUNTING_SINGULAR_ATTEMPTS.get(source, ()):
        add_attempt(pointer)
    return pointers


def _attempt_accounting_attempt_outcome(
    source: str,
    pointer: str,
    occurrence: int,
    record: dict,
    document: object,
) -> tuple[str, tuple[str, ...]]:
    if (
        source == "benchmarks/verifier-boundary/results.json"
        and pointer == "/failed_attempts/2"
        and occurrence == 1
    ):
        diagnostic = record.get("inconclusive_diagnostic")
        if isinstance(diagnostic, dict):
            return "failed", ("inconclusive_diagnostic=nonempty",)
    outcome = _attempt_accounting_outcome(record, source, pointer)
    if outcome[0] != "unknown":
        return outcome
    if (
        source == "benchmarks/baton-compatibility/results.json"
        and pointer.startswith("/failed_candidate_gate/turns/")
    ):
        parent = _attempt_accounting_resolve_pointer(
            document, "/failed_candidate_gate"
        )
        parent_outcome = _attempt_accounting_outcome(
            parent,
            source,
            "/failed_candidate_gate",
        )
        if parent_outcome[0] == "failed":
            return parent_outcome
    return outcome


def _attempt_accounting_discover_public_json() -> tuple[str, ...]:
    excluded_names = {
        "agent-calls",
        "agent-calls.json",
        "traces",
        "traces.json",
        "budget",
        "budget.json",
        "package",
        "package.json",
        "agents",
        "agents.json",
        "settings.snippet",
        "settings.snippet.json",
    }
    found: list[str] = []
    for path in sorted((ROOT / "benchmarks").rglob("*.json")):
        relative = path.relative_to(ROOT).as_posix()
        parts = relative.split("/")
        if relative == "benchmarks/attempt-accounting.json":
            continue
        if any(part in excluded_names for part in parts):
            continue
        if any(part == "fixture" or "snapshot" in part for part in parts):
            continue
        found.append(relative)
    return tuple(found)


def _attempt_accounting_resolve_pointer(document: object, pointer: str) -> object:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise AssertionError(f"invalid JSON Pointer: {pointer!r}")
    value = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if token == "0":
                index = 0
            else:
                try:
                    index = int(token)
                except ValueError as error:
                    raise AssertionError(
                        f"non-index token {token!r} for list pointer {pointer!r}"
                    ) from error
            if index < 0 or index >= len(value):
                raise AssertionError(f"missing list pointer {pointer!r}")
            value = value[index]
        elif isinstance(value, dict) and token in value:
            value = value[token]
        else:
            raise AssertionError(f"missing JSON Pointer {pointer!r}")
    return value


def _attempt_accounting_validate(ledger: dict) -> None:
    assert isinstance(ledger, dict)
    assert ledger.get("schema_version") == 1
    source_entries = ledger.get("sources")
    assert isinstance(source_entries, list)
    source_paths = [entry.get("path") for entry in source_entries]
    assert source_paths == list(ATTEMPT_ACCOUNTING_SOURCES)
    assert len(source_paths) == len(set(source_paths))
    discovered_sources = _attempt_accounting_discover_public_json()
    assert len(discovered_sources) == len(set(discovered_sources))
    assert set(discovered_sources) == set(ATTEMPT_ACCOUNTING_SOURCES)

    for entry, source in zip(source_entries, ATTEMPT_ACCOUNTING_SOURCES):
        assert isinstance(entry, dict)
        assert entry.get("path") == source
        digest = entry.get("sha256")
        assert isinstance(digest, str)
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
        assert digest == hashlib.sha256((ROOT / source).read_bytes()).hexdigest()

    exclusions = ledger.get("coverage_exclusions")
    assert isinstance(exclusions, list)
    actual_exclusions = {}
    for exclusion in exclusions:
        assert isinstance(exclusion, dict)
        key = (exclusion.get("source"), exclusion.get("json_pointer"))
        assert key not in actual_exclusions
        reason = exclusion.get("reason")
        assert isinstance(reason, str) and reason
        actual_exclusions[key] = reason
    assert actual_exclusions == ATTEMPT_ACCOUNTING_COVERAGE_EXCLUSIONS

    documents = {
        source: json.loads((ROOT / source).read_text(encoding="utf-8"))
        for source in ATTEMPT_ACCOUNTING_SOURCES
    }
    oracle = {}
    outcomes = {}
    for source, document in documents.items():
        for pointer, record in _attempt_accounting_marked_records(document):
            key = (source, pointer)
            if key in ATTEMPT_ACCOUNTING_COVERAGE_EXCLUSIONS:
                continue
            oracle[key] = record
            outcomes[key] = _attempt_accounting_outcome(record, source, pointer)

    attempt_oracle = {}
    attempt_outcomes = {}
    attempt_order = []
    for source, document in documents.items():
        for pointer, occurrence in _attempt_accounting_attempt_pointers(
            source, document
        ):
            key = (source, pointer, occurrence)
            assert key not in attempt_oracle
            record = _attempt_accounting_resolve_pointer(document, pointer)
            assert isinstance(record, dict)
            attempt_oracle[key] = record
            attempt_outcomes[key] = _attempt_accounting_attempt_outcome(
                source, pointer, occurrence, record, document
            )
            attempt_order.append(key)
    assert attempt_order

    cells = ledger.get("cells")
    assert isinstance(cells, list) and cells
    cell_by_id = {}
    owner_by_pointer = {}
    for cell in cells:
        assert isinstance(cell, dict)
        cell_id = cell.get("id")
        assert isinstance(cell_id, str) and cell_id
        assert cell_id not in cell_by_id
        cell_by_id[cell_id] = cell
        pointers = cell.get("claim_pointers")
        assert isinstance(pointers, list) and pointers
        for claim_pointer in pointers:
            assert isinstance(claim_pointer, dict)
            source = claim_pointer.get("source")
            pointer = claim_pointer.get("json_pointer")
            key = (source, pointer)
            assert key in oracle
            assert key not in owner_by_pointer
            assert isinstance(
                _attempt_accounting_resolve_pointer(documents[source], pointer), dict
            )
            owner_by_pointer[key] = cell_id
    assert set(owner_by_pointer) == set(oracle)
    assert {source for source, _ in owner_by_pointer} == set(
        ATTEMPT_ACCOUNTING_SOURCES
    )

    attempt_owner_by_pointer = {}
    for cell in cells:
        attempt_pointers = cell.get("attempt_pointers")
        assert isinstance(attempt_pointers, list)
        for attempt_pointer in attempt_pointers:
            key = _attempt_accounting_pointer_key(attempt_pointer)
            assert key in attempt_oracle
            assert key not in attempt_owner_by_pointer
            attempt_owner_by_pointer[key] = cell["id"]
    assert set(attempt_owner_by_pointer) == set(attempt_oracle)

    failure_oracle = {}
    for key, (state, boundaries) in outcomes.items():
        if state == "failed":
            failure_oracle[(*key, 0)] = boundaries
    for key, reviewed_failure in ATTEMPT_ACCOUNTING_REVIEWED_FAILURES.items():
        source, pointer = key
        record = _attempt_accounting_resolve_pointer(documents[source], pointer)
        assert isinstance(record, dict)
        assert all(
            record.get(field) == expected
            for field, expected in reviewed_failure.items()
        )
        boundary = (f"reviewed_failure={reviewed_failure['name']}",)
        for occurrence in range(
            _attempt_accounting_occurrence_count(source, pointer, record)
        ):
            assert (source, pointer, occurrence) in attempt_oracle
            failure_oracle[(source, pointer, occurrence)] = boundary
    attempt_failure_oracle = {
        key: boundaries
        for key, (state, boundaries) in attempt_outcomes.items()
        if state == "failed"
    }

    owned_failures = {cell_id: 0 for cell_id in cell_by_id}
    for cell in cells:
        cell_id = cell["id"]
        claim_pointers = [
            (claim_pointer["source"], claim_pointer["json_pointer"])
            for claim_pointer in cell["claim_pointers"]
        ]
        claim_states = {outcomes[key][0] for key in claim_pointers}
        assert len(claim_states) == 1
        assert cell.get("claim_status") == next(iter(claim_states))

        attempt_pointers = [
            _attempt_accounting_pointer_key(attempt_pointer)
            for attempt_pointer in cell["attempt_pointers"]
        ]
        attempt_states = [attempt_outcomes[key][0] for key in attempt_pointers]
        if not attempt_pointers:
            if next(iter(claim_states)) == "not_run":
                expected_state = "known"
                expected_attempted = expected_passed = expected_failed = 0
            else:
                expected_state = "unknown"
                expected_attempted = expected_passed = expected_failed = None
        elif "unknown" in attempt_states:
            expected_state = "unknown"
            expected_attempted = expected_passed = expected_failed = None
        else:
            expected_state = "known"
            expected_attempted = sum(
                state in ("passed", "failed") for state in attempt_states
            )
            expected_passed = attempt_states.count("passed")
            expected_failed = attempt_states.count("failed")
            if all(state == "not_run" for state in attempt_states):
                expected_attempted = expected_passed = expected_failed = 0

        assert cell.get("count_status") == expected_state
        if expected_state == "unknown":
            assert cell.get("attempted") is None
            assert cell.get("passed") is None
            assert cell.get("failed") is None
            reason = cell.get("reason")
            assert isinstance(reason, str) and reason
        else:
            for field, expected in (
                ("attempted", expected_attempted),
                ("passed", expected_passed),
                ("failed", expected_failed),
            ):
                value = cell.get(field)
                assert type(value) is int and value >= 0
                assert value == expected
            assert cell["attempted"] == cell["passed"] + cell["failed"]
            if expected_attempted == 0:
                reason = cell.get("reason")
                assert isinstance(reason, str) and reason
        for key in attempt_pointers:
            if key in attempt_failure_oracle:
                owned_failures[cell_id] += 1

    failure_entries = ledger.get("failed_attempts")
    assert isinstance(failure_entries, list)
    failure_ids = set()
    attempt_failures_by_pointer = {}
    evidence_by_pointer = {}
    for entry in failure_entries:
        assert isinstance(entry, dict)
        failure_id = entry.get("id")
        assert (
            isinstance(failure_id, str)
            and failure_id
            and failure_id not in failure_ids
        )
        failure_ids.add(failure_id)
        cell_id = entry.get("cell_id")
        assert cell_id in cell_by_id
        attempt_pointer = entry.get("attempt_pointer")
        attempt_key = _attempt_accounting_pointer_key(attempt_pointer)
        assert attempt_key in attempt_failure_oracle
        assert attempt_key not in attempt_failures_by_pointer
        assert attempt_owner_by_pointer[attempt_key] == cell_id
        identity = entry.get("candidate_identity")
        assert isinstance(identity, dict)
        expected_identity = _attempt_accounting_candidate_identity_for_attempt(
            attempt_key[0], attempt_key[1], documents[attempt_key[0]]
        )
        if expected_identity:
            assert identity == expected_identity
        else:
            assert (
                isinstance(identity.get("limitation"), str)
                and identity["limitation"]
            )
            assert not any(
                key in identity and _attempt_accounting_nonempty(identity[key])
                for key in ("version", "hash", "config")
            )
        boundary = entry.get("failure_boundary")
        assert isinstance(boundary, str) and boundary
        evidence = entry.get("evidence")
        assert isinstance(evidence, list) and evidence
        assert boundary == "; ".join(attempt_failure_oracle[attempt_key])
        for evidence_item in evidence:
            key = _attempt_accounting_pointer_key(evidence_item)
            assert key in failure_oracle
            assert key not in evidence_by_pointer
            reviewed_owner = ATTEMPT_ACCOUNTING_REVIEWED_EVIDENCE_OWNERS.get(key)
            if reviewed_owner is not None:
                assert attempt_key == reviewed_owner
            claim_key = (key[0], key[1])
            owner = owner_by_pointer.get(claim_key, attempt_owner_by_pointer.get(key))
            assert owner == cell_id
            record = oracle.get(claim_key, attempt_oracle.get(key))
            assert isinstance(record, dict)
            for hash_key in ("raw_stream_sha256", "transcript_sha256"):
                if isinstance(record.get(hash_key), str):
                    assert evidence_item.get(hash_key) == record[hash_key]
                elif isinstance(record.get(hash_key), list):
                    occurrence = key[2]
                    assert occurrence < len(record[hash_key])
                    assert evidence_item.get(hash_key) == record[hash_key][occurrence]
            evidence_by_pointer[key] = entry
        attempt_failures_by_pointer[attempt_key] = entry

    assert set(attempt_failures_by_pointer) == set(attempt_failure_oracle)
    assert set(evidence_by_pointer) == set(failure_oracle)
    for cell_id, count in owned_failures.items():
        assert count == sum(
            entry.get("cell_id") == cell_id for entry in failure_entries
        )


class PolicyContractTests(unittest.TestCase):
    def test_spontaneous_dispatch_classifier_separates_child_tools(self) -> None:
        events = [
            {
                "type": "system",
                "subtype": "init",
                "model": "claude-opus-5",
                "claude_code_version": "2.1.220",
            },
            {
                "type": "assistant",
                "parent_tool_use_id": None,
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Agent",
                            "id": "toolu_agent",
                            "input": {
                                "subagent_type": "mech-executor",
                                "run_in_background": False,
                            },
                        }
                    ]
                },
            },
            {
                "type": "assistant",
                "parent_tool_use_id": "toolu_agent",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Bash",
                            "input": {"command": "npm test"},
                        },
                        {
                            "type": "tool_use",
                            "name": "Write",
                            "input": {"file_path": "src/out.js"},
                        },
                    ]
                },
            },
            {
                "type": "user",
                "parent_tool_use_id": None,
                "tool_use_result": {"status": "completed"},
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_agent",
                            "content": [{"type": "text", "text": "done"}],
                        }
                    ]
                },
            },
            {
                "type": "result",
                "total_cost_usd": 0.25,
                "modelUsage": {"claude-opus-5": {"costUSD": 0.25}},
            },
        ]
        uncollected_events = [
            {
                "type": "assistant",
                "parent_tool_use_id": None,
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Agent",
                            "id": "toolu_uncollected",
                            "input": {
                                "subagent_type": "mech-executor",
                                "run_in_background": True,
                            },
                        },
                        {"type": "text", "text": "Async agent launched"},
                    ]
                },
            },
            {
                "type": "user",
                "parent_tool_use_id": None,
                "tool_use_result": {"status": "async_launched", "isAsync": True},
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_uncollected",
                        }
                    ]
                },
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            stream = Path(directory) / "stream.jsonl"
            stream.write_text(
                "".join(json.dumps(event) + "\n" for event in events),
                encoding="utf-8",
            )
            uncollected_stream = Path(directory) / "uncollected.jsonl"
            uncollected_stream.write_text(
                "".join(json.dumps(event) + "\n" for event in uncollected_events),
                encoding="utf-8",
            )
            output = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "benchmarks"
                        / "spontaneous-dispatch"
                        / "classify_stream.py"
                    ),
                    str(stream),
                    str(uncollected_stream),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        trace, uncollected = json.loads(output.stdout)
        self.assertEqual(trace["top_level_tools"], ["Agent"])
        self.assertEqual(trace["worker_tools"], ["Bash", "Write"])
        self.assertEqual(
            trace["agent_calls"],
            [
                {
                    "subagent_type": "mech-executor",
                    "run_in_background": False,
                    "invocation_model_present": False,
                }
            ],
        )
        self.assertTrue(trace["subagent_result_collected"])
        self.assertEqual(trace["observed_main_model"], "claude-opus-5")
        self.assertEqual(trace["client_reported_cost_usd"], 0.25)
        self.assertTrue(uncollected["async_launch_observed"])
        self.assertFalse(uncollected["subagent_result_collected"])

    def test_baton_dispatch_matrix_prompts_are_neutral_and_recorded(self) -> None:
        benchmark = ROOT / "benchmarks" / "baton-dispatch-effect"
        results = json.loads(
            (benchmark / "results.json").read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        self.assertEqual(results["schema_version"], 3)
        cue_pattern = re.compile(
            r"baton|agent|subagent|worker|\brole\b|policy|skill|delegat|"
            r"orchestrat|parallel|independent|fan-out",
            re.IGNORECASE,
        )
        prompt_contracts = (
            (
                benchmark / "prompts" / "task.txt",
                results["small_availability_observation"],
            ),
            (
                benchmark / "prompts" / "large-audit.txt",
                results["large_policy_activation_gate"],
            ),
        )
        for path, contract in prompt_contracts:
            prompt = path.read_bytes()
            self.assertIsNone(cue_pattern.search(prompt.decode("utf-8")))
            self.assertEqual(
                hashlib.sha256(prompt).hexdigest(),
                contract["prompt_file_sha256"],
            )
            self.assertEqual(
                hashlib.sha256(prompt.rstrip(b"\n")).hexdigest(),
                contract["prompt_runtime_input_sha256"],
            )

        runtime = results["shared_runtime"]
        self.assertEqual(
            results["client"]["versions_observed"], ["2.1.217", "2.1.218"]
        )
        self.assertEqual(runtime["requested_model"], "opus")
        self.assertEqual(runtime["observed_main_model"], "claude-opus-4-8")
        self.assertEqual(runtime["setting_sources"], "project,local")
        large = results["large_policy_activation_gate"]
        self.assertIn("user prompt only", large["claim_boundary"])
        self.assertIn("fully cue-free", large["claim_boundary"])
        self.assertEqual(
            large["policy_sha256"],
            "17d272b6ddd6d95a749a802f5e29dfd4625c884f8a84bf817ffc20bfca6b39bf",
        )
        self.assertEqual(large["fixture"]["domain_file_count"], 45)
        self.assertEqual(large["fixture"]["domain_total_lines"], 3032)
        baseline_ref = "refs/heads/benchmark/v1.3.1-baton-large-fixture"
        baseline_commit = "34ebabe2a26dd53de1a019607992f1ac10af245f"
        baseline_tree = "3773149bae5c514abe6d141d6fc5216e86d02574"
        self.assertEqual(large["fixture"]["baseline_ref"], baseline_ref)
        self.assertEqual(large["fixture"]["baseline_commit"], baseline_commit)
        self.assertEqual(large["fixture"]["baseline_tree"], baseline_tree)
        self.assertEqual(
            large["fixture"]["baseline_url"],
            f"https://github.com/Nanako0129/pilotfish/tree/{baseline_commit}",
        )
        replay = results["release_payload_replay"]
        self.assertEqual(replay["fixture_baseline_ref"], baseline_ref)
        self.assertEqual(replay["fixture_baseline_commit"], baseline_commit)
        self.assertEqual(replay["fixture_baseline_tree"], baseline_tree)
        self.assertEqual(
            replay["fixture_baseline_url"], large["fixture"]["baseline_url"]
        )
        for readme_name in ("README.md", "README.zh-TW.md"):
            readme = (benchmark / readme_name).read_text(encoding="utf-8")
            self.assertIn(baseline_ref.removeprefix("refs/heads/"), readme)
            self.assertIn(f"tree/{baseline_commit}", readme)
            self.assertIn("git fetch origin", readme)
        self.assertEqual(
            set(large["fixture"]["construction"]),
            {"domain-a", "domain-b", "domain-c", "domain-d"},
        )
        package = json.loads(
            (benchmark / "large-fixture" / "package.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(package["scripts"]["test"], "node verify-audit.mjs")
        harness = (benchmark / "large-fixture" / "verify-audit.mjs").read_text(
            encoding="utf-8"
        )
        for domain in ("domain-a", "domain-b", "domain-c", "domain-d"):
            self.assertIn(domain, harness)

    def test_baton_dispatch_matrix_records_activation_and_complete_dispatch(self) -> None:
        benchmark = ROOT / "benchmarks" / "baton-dispatch-effect"
        results = json.loads(
            (benchmark / "results.json").read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        traces = json.loads((benchmark / "traces.json").read_text(encoding="utf-8"))
        calls = json.loads(
            (benchmark / "agent-calls.json").read_text(encoding="utf-8")
        )
        small = results["small_availability_observation"]
        cells = {cell["name"]: cell for cell in small["cells"]}
        control = cells["control"]
        treatment = cells["treatment"]

        self.assertFalse(control["baton_listed_at_init"])
        self.assertTrue(treatment["baton_listed_at_init"])
        for cell in (control, treatment):
            self.assertTrue(cell["test_passed"])
            self.assertEqual(cell["only_change"], "?? REPORT.md")
            self.assertEqual(cell["baton_skill_call_count"], 0)
            self.assertEqual(cell["agent_call_count"], 0)
            self.assertEqual(cell["topology"], "direct main-session execution")

        self.assertEqual(
            small["gate"]["status"], "no_activation_observed_for_bounded_task"
        )
        self.assertIn("not presented as a cue-free causal A/B", small["claim_boundary"])
        self.assertEqual(
            traces["small_availability_observation"]["control"]["skill_calls"],
            [],
        )
        self.assertEqual(
            traces["small_availability_observation"]["treatment"]["skill_calls"],
            [],
        )
        self.assertEqual(calls["small_availability_observation"]["control"], [])
        self.assertEqual(calls["small_availability_observation"]["treatment"], [])
        self.assertEqual(
            sum((cell["client_reported_cost_usd"] for cell in cells.values()), Decimal("0")),
            small["total_client_reported_cost_usd"],
        )

        large = results["large_policy_activation_gate"]
        attempts = {attempt["name"]: attempt for attempt in large["attempts"]}
        self.assertEqual(small["client_version"], "2.1.217")
        self.assertEqual(
            [attempts[f"large-v131-{n}"]["client_version"] for n in (1, 2, 3, 4)],
            ["2.1.217", "2.1.217", "2.1.217", "2.1.218"],
        )
        self.assertEqual(
            sum(
                (
                    attempt["client_reported_cost_usd"]
                    for attempt in large["attempts"]
                ),
                Decimal("0"),
            ),
            large["total_client_reported_cost_usd"],
        )
        self.assertTrue(attempts["large-v131-1"]["status"].endswith("ownership_fail"))
        self.assertTrue(attempts["large-v131-2"]["status"].endswith("ownership_fail"))
        self.assertEqual(
            attempts["large-v131-3"]["status"],
            "topology_pass_runtime_limit_outcome_incomplete",
        )
        final = attempts["large-v131-4"]
        self.assertEqual(
            final["status"],
            "passed_activation_dispatch_ownership_collection_correctness",
        )
        self.assertEqual(final["baton_skill_call_count"], 1)
        self.assertEqual(final["agent_call_count"], 4)
        self.assertEqual(final["completed_agent_count"], 4)
        self.assertTrue(final["all_agents_background"])
        self.assertTrue(final["all_agent_invocations_omit_model"])
        self.assertTrue(final["agent_calls_back_to_back"])
        self.assertTrue(final["all_results_collected_before_cross_domain_check"])
        self.assertFalse(final["active_scope_overlap_observed"])
        self.assertTrue(final["test_passed"])
        self.assertFalse(final["terminal_is_error"])
        self.assertEqual(final["only_change"], "?? AUDIT.md")
        self.assertEqual(
            final["in_session_test"]["status"], "passed_before_final_edit"
        )
        self.assertLess(
            final["in_session_test"]["test_event_index"],
            final["in_session_test"]["final_edit_event_index"],
        )
        post_run = final["post_run_verification"]
        self.assertEqual(post_run["exit_code"], 0)
        self.assertEqual(post_run["audit_sha256"], final["audit_sha256"])
        self.assertEqual(post_run["only_change"], "?? AUDIT.md")
        self.assertEqual(large["effect_gate"]["status"], "passed")

        final_trace = traces["large_policy_activation_gate"]["attempts"][
            "large-v131-4"
        ]
        self.assertEqual(final_trace["top_level_tools"].count("Skill"), 1)
        self.assertEqual(final_trace["top_level_tools"].count("Agent"), 4)
        self.assertEqual(final_trace["main_domain_content_tools_while_agents_active"], [])
        self.assertTrue(final_trace["in_session_test_preceded_final_edit"])
        self.assertEqual(final_trace["post_run_verification"]["exit_code"], 0)
        self.assertLess(
            max(final_trace["completion_event_indexes"]),
            min(final_trace["post_collection_cross_domain_check_event_indexes"]),
        )
        final_calls = calls["large_policy_activation_gate"]["large-v131-4"]
        self.assertEqual(len(final_calls), 4)
        self.assertEqual(
            {call["exclusive_read_scope"] for call in final_calls},
            {"domain-a", "domain-b", "domain-c", "domain-d"},
        )
        for call in final_calls:
            self.assertEqual(call["subagent_type"], "scout")
            self.assertTrue(call["run_in_background"])
            self.assertFalse(call["invocation_model_present"])
            self.assertEqual(call["status"], "completed")
            self.assertEqual(call["observed_model"], "claude-haiku-4-5-20251001")

        release = results["release_payload_replay"]
        self.assertIn("user prompt only", release["claim_boundary"])
        self.assertIn("fully cue-free", release["claim_boundary"])
        self.assertEqual(
            release["status"],
            "passed_activation_dispatch_ownership_collection_final_byte_correctness",
        )
        self.assertEqual(release["policy_sha256"], large["policy_sha256"])
        self.assertEqual(
            release["agents_json_sha256"],
            "0b42c137daf4006a9c85b201c9434e13640fce69fb10fcf0fba6ba2b1379723c",
        )
        self.assertEqual(release["baton_skill_call_count"], 1)
        self.assertEqual(release["agent_call_count"], 4)
        self.assertEqual(release["completed_agent_count"], 4)
        self.assertTrue(release["all_agents_background"])
        self.assertTrue(release["all_agent_invocations_omit_model"])
        self.assertTrue(release["agent_calls_back_to_back"])
        self.assertTrue(release["all_results_collected_before_cross_domain_check"])
        self.assertFalse(release["active_scope_overlap_observed"])
        self.assertEqual(release["only_change"], "?? AUDIT.md")
        self.assertTrue(release["test_passed"])
        self.assertFalse(release["terminal_is_error"])
        self.assertEqual(
            release["in_session_test"]["status"], "passed_after_final_write"
        )
        self.assertLess(
            release["in_session_test"]["write_event_index"],
            release["in_session_test"]["test_event_index"],
        )
        self.assertEqual(
            release["post_run_verification"]["audit_sha256"],
            release["audit_sha256"],
        )

        release_trace = traces["release_payload_replay"][
            "large-v131-release-payload-replay"
        ]
        self.assertEqual(release_trace["top_level_tools"].count("Skill"), 1)
        self.assertEqual(release_trace["top_level_tools"].count("Agent"), 4)
        self.assertEqual(
            release_trace["main_domain_content_tools_while_agents_active"], []
        )
        self.assertTrue(release_trace["in_session_test_followed_final_write"])
        self.assertLess(
            max(release_trace["completion_event_indexes"]),
            min(release_trace["post_collection_cross_domain_check_event_indexes"]),
        )
        release_calls = calls["release_payload_replay"][
            "large-v131-release-payload-replay"
        ]
        self.assertEqual(len(release_calls), 4)
        self.assertEqual(
            {call["exclusive_read_scope"] for call in release_calls},
            {"domain-a", "domain-b", "domain-c", "domain-d"},
        )
        for call in release_calls:
            self.assertEqual(call["subagent_type"], "scout")
            self.assertTrue(call["run_in_background"])
            self.assertFalse(call["invocation_model_present"])
            self.assertEqual(call["status"], "completed")
            self.assertEqual(call["observed_model"], "claude-haiku-4-5-20251001")

        for readme in ("README.md", "README.zh-TW.md"):
            content = (benchmark / readme).read_text(encoding="utf-8")
            self.assertIn("large-v131-4", content)
            self.assertIn("0b42c137", content)
            self.assertIn("release-payload", content)
            self.assertIn("0.1.1", content)
            self.assertIn("results.json", content)

    def test_spontaneous_dispatch_inputs_are_cue_free_and_recorded(self) -> None:
        benchmark = ROOT / "benchmarks" / "spontaneous-dispatch"
        results = json.loads((benchmark / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(results["schema_version"], 2)
        contract = results["input_contract"]
        prompts = {
            "mechanical": benchmark / "prompts" / "mechanical.txt",
            "bug": benchmark / "prompts" / "bug.txt",
        }
        cue_pattern = re.compile(
            r"agent|subagent|worker|\brole\b|policy|baton|parallel|independent|"
            r"delegat|orchestrat|fan-out",
            re.IGNORECASE,
        )

        for name, path in prompts.items():
            prompt = path.read_bytes()
            self.assertIsNone(cue_pattern.search(prompt.decode("utf-8")))
            self.assertEqual(
                hashlib.sha256(prompt).hexdigest(),
                contract[f"{name}_prompt_file_sha256"],
            )
            self.assertEqual(
                hashlib.sha256(prompt.rstrip(b"\n")).hexdigest(),
                contract[f"{name}_runtime_prompt_sha256"],
            )

        fixtures = {
            "mechanical": (
                ROOT
                / "benchmarks"
                / "dispatch-brake"
                / "positive-controls"
                / "mechanical"
                / "fixture"
            ),
            "bug": ROOT / "benchmarks" / "dispatch-brake" / "fixture",
        }
        for name, fixture in fixtures.items():
            fixture_hash_lines = []
            for path in sorted(path for path in fixture.rglob("*") if path.is_file()):
                self.assertIsNone(cue_pattern.search(path.read_text(encoding="utf-8")))
                relative = path.relative_to(ROOT)
                fixture_hash_lines.append(
                    f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}\n"
                )
            fixture_digest = hashlib.sha256(
                "".join(fixture_hash_lines).encode()
            ).hexdigest()
            self.assertEqual(fixture_digest, contract[f"{name}_fixture_digest"])
        self.assertNotIn(
            "Do not optimize for or against delegation",
            (benchmark / "README.md").read_text(encoding="utf-8"),
        )

    def test_cue_free_tui_evidence_is_bound_and_claim_limited(self) -> None:
        benchmark = ROOT / "benchmarks" / "spontaneous-dispatch"
        evidence_text = (benchmark / "cue-free-tui.json").read_text(
            encoding="utf-8"
        )
        evidence = json.loads(
            evidence_text,
            parse_float=Decimal,
        )
        self.assertEqual(evidence["schema_version"], 1)
        self.assertEqual(evidence["status"], "stopped_after_failed_topology")

        policy = evidence["inputs"]["policy"]
        base = (benchmark / policy["base_path"]).read_bytes()
        self.assertEqual(len(base), policy["base_bytes"])
        self.assertEqual(hashlib.sha256(base).hexdigest(), policy["base_sha256"])
        marker = policy["delta_insertion_before"].encode()
        self.assertEqual(base.count(marker), 1)
        addition = ("\n".join(policy["delta_lines"]) + "\n").encode()
        candidate = base.replace(marker, addition + marker)
        self.assertEqual(len(candidate), policy["candidate_bytes"])
        self.assertEqual(
            hashlib.sha256(candidate).hexdigest(), policy["candidate_sha256"]
        )

        prompt = evidence["inputs"]["prompt"]
        prompt_bytes = (benchmark / prompt["path"]).read_bytes()
        self.assertEqual(
            hashlib.sha256(prompt_bytes).hexdigest(), prompt["file_sha256"]
        )
        self.assertEqual(
            hashlib.sha256(prompt_bytes.rstrip(b"\n")).hexdigest(),
            prompt["runtime_sha256"],
        )
        fixture = evidence["inputs"]["fixture"]
        fixture_path = (benchmark / fixture["path"]).resolve()
        digest_lines = []
        for file_path in sorted(
            item for item in fixture_path.rglob("*") if item.is_file()
        ):
            digest_lines.append(
                f"{hashlib.sha256(file_path.read_bytes()).hexdigest()}  "
                f"{file_path.relative_to(ROOT)}\n"
            )
        self.assertEqual(
            hashlib.sha256("".join(digest_lines).encode()).hexdigest(),
            fixture["manifest_sha256"],
        )
        agents = evidence["inputs"]["agents"]
        agents_bytes = (benchmark / agents["path"]).read_bytes()
        self.assertEqual(
            hashlib.sha256(agents_bytes).hexdigest(),
            agents["file_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(agents_bytes.rstrip(b"\n")).hexdigest(),
            agents["runtime_sha256"],
        )

        observation = evidence["tui_observation"]
        self.assertRegex(observation["transcript_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(observation["thinking_blocks"], 4)
        self.assertEqual(observation["readable_thinking_blocks"], 4)
        self.assertFalse(observation["reasoning_verbatim_published"])
        self.assertEqual(observation["top_level_tools"], {"Bash": 6})
        self.assertEqual(observation["agent_calls"], 0)
        self.assertEqual(len(observation["modified_paths"]), 12)
        self.assertEqual(observation["tests"], "12 passed, 0 failed")
        self.assertFalse(observation["topology_pass"])

        campaign = evidence["campaign"]
        self.assertEqual(len(campaign["cells"]), 4)
        self.assertTrue(all(cell["agent_calls"] == 0 for cell in campaign["cells"]))
        for cell in campaign["cells"]:
            self.assertEqual(cell["route"]["client_version"], "2.1.223")
            self.assertEqual(
                cell["route"]["observed_main_model"], "claude-opus-5"
            )
            self.assertEqual(cell["route"]["effort"], "high")
            self.assertTrue(cell["main_session_mutated_source"])
            self.assertEqual(cell["changed_adapter_files"], 12)
            self.assertEqual(cell["tests"], "12 passed, 0 failed")
        self.assertTrue(
            all(not cell["topology_pass"] for cell in campaign["cells"])
        )
        self.assertNotIn("route", evidence["inputs"])
        self.assertNotIn("/Users/", evidence_text)
        self.assertNotIn("session_id", evidence_text)

        for readme in ("README.md", "README.zh-TW.md"):
            content = (benchmark / readme).read_text(encoding="utf-8")
            self.assertIn("cue-free-tui.json", content)
            self.assertIn("Calico TUI", content)

        for readme in ("README.md", "README.zh-TW.md"):
            content = (ROOT / readme).read_text(encoding="utf-8")
            self.assertIn("cue-free-tui.json", content)

    def test_issue_29_reachability_correction_is_self_consistent(self) -> None:
        path = ROOT / "benchmarks" / "spontaneous-dispatch"
        evidence = json.loads(
            (path / "issue-29-topology.json").read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        attempts = evidence["attempts"]
        contract = evidence["reachability_contract"]
        modified_paths_digest = hashlib.sha256(
            "".join(f"{item}\n" for item in contract["modified_paths"]).encode()
        ).hexdigest()
        self.assertEqual(modified_paths_digest, contract["modified_paths_sha256"])

        def passes(attempt: dict[str, object]) -> bool:
            return (
                attempt["agent_calls"] == contract["agent_calls"]
                and attempt["agent_role"] == contract["subagent_type"]
                and attempt["invocation_model_present"]
                is contract["invocation_model_present"]
                and attempt["mode"] == contract["mode"]
                and attempt["collected"] is contract["result_collected"]
                and attempt["modified_paths_sha256"]
                == contract["modified_paths_sha256"]
            )

        self.assertEqual(len(attempts), 20)
        self.assertTrue(
            all(
                attempt["modified_paths_sha256"]
                == contract["modified_paths_sha256"]
                for attempt in attempts
            )
        )
        self.assertTrue(
            all(
                attempt["tests_passed"] == 12
                and attempt["tests_failed"] == 0
                for attempt in attempts
            )
        )
        self.assertEqual(sum(passes(attempt) for attempt in attempts), 7)
        self.assertEqual(
            sum(attempt["cost_usd"] for attempt in attempts).quantize(
                Decimal("0.0000001")
            ),
            evidence["summary"]["client_reported_mechanical_cost_usd"],
        )
        self.assertEqual(
            {attempt["reachability"] for attempt in attempts if passes(attempt)},
            {"PASS"},
        )
        self.assertEqual(
            {attempt["reachability"] for attempt in attempts if not passes(attempt)},
            {"FAIL"},
        )
        self.assertEqual(
            len({attempt["raw_stream_sha256"] for attempt in attempts}), 20
        )
        self.assertEqual(
            hashlib.sha256((path / "classify_stream.py").read_bytes()).hexdigest(),
            evidence["classifier"]["sha256"],
        )

    def test_issue_29_recovery_gate_is_bounded_and_brake_calibrated(self) -> None:
        path = ROOT / "benchmarks" / "spontaneous-dispatch"
        evidence = json.loads(
            (path / "issue-29-recovery.json").read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        self.assertEqual(evidence["schema_version"], 3)
        self.assertEqual(evidence["status"], "release_qualified")

        inputs = evidence["inputs"]
        self.assertEqual(
            inputs["prompt_invocation"],
            "double-quoted shell command substitution $(<file); trailing newlines stripped",
        )
        self.assertEqual(
            inputs["fixture_digest_method"],
            "SHA-256 of sorted '<file_sha256>  <repo-relative path>\\n' entries",
        )
        for fixture in inputs["fixtures"].values():
            fixture_path = (path / fixture["path"]).resolve()
            digest_lines = []
            for file_path in sorted(
                item for item in fixture_path.rglob("*") if item.is_file()
            ):
                digest_lines.append(
                    f"{hashlib.sha256(file_path.read_bytes()).hexdigest()}  "
                    f"{file_path.relative_to(ROOT)}\n"
                )
            self.assertEqual(
                hashlib.sha256("".join(digest_lines).encode()).hexdigest(),
                fixture["sha256"],
            )
        policy = (path / inputs["policy"]["path"]).read_bytes()
        self.assertEqual(len(policy), inputs["policy"]["release_bytes"])
        self.assertEqual(
            hashlib.sha256(policy).hexdigest(), inputs["policy"]["release_sha256"]
        )
        self.assertRegex(inputs["policy"]["gate_source_commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(inputs["policy"]["gate_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(inputs["policy"]["gate_bytes"], 17996)
        self.assertIsNone(inputs["policy"]["runtime_loaded_sha256"])
        self.assertEqual(inputs["policy"]["observed_runtime_bytes"], 17996)
        self.assertTrue(inputs["policy"]["release_gate_status"].startswith("passed;"))
        agents = (path / inputs["agents"]["path"]).read_bytes()
        self.assertEqual(
            hashlib.sha256(agents).hexdigest(), inputs["agents"]["file_sha256"]
        )
        self.assertEqual(
            hashlib.sha256(agents.rstrip(b"\n")).hexdigest(),
            inputs["agents"]["runtime_sha256"],
        )
        for prompt in inputs["prompts"].values():
            payload = (path / prompt["path"]).read_bytes()
            self.assertEqual(
                hashlib.sha256(payload).hexdigest(), prompt["file_sha256"]
            )
            self.assertEqual(
                hashlib.sha256(payload.rstrip(b"\n")).hexdigest(),
                prompt["runtime_sha256"],
            )

        results = evidence["results"]
        routine = results["routine_docs"]["attempts"]
        bug = results["single_unknown_bug"]["attempts"]
        mechanical = results["mechanical_repetition"]
        schema = results["schema_lifecycle"]
        self.assertEqual(len(routine), 2)
        self.assertTrue(all(attempt["agent_calls"] == 0 for attempt in routine))
        self.assertTrue(
            all(attempt["modified_paths"] == ["README.md"] for attempt in routine)
        )
        self.assertTrue(
            all(attempt["tests"] == "1 passed, 0 failed" for attempt in routine)
        )
        self.assertEqual(len(bug), 2)
        self.assertTrue(all(attempt["agent_calls"] == 0 for attempt in bug))
        self.assertTrue(
            all(
                attempt["modified_paths"] == ["src/reducer.js"] for attempt in bug
            )
        )
        self.assertTrue(
            all(attempt["tests"] == "2 passed, 0 failed" for attempt in bug)
        )
        self.assertEqual(len(mechanical["attempts"]), 2)
        expected_adapters = [
            f"src/adapters/{name}.js"
            for name in (
                "alpha",
                "bravo",
                "charlie",
                "delta",
                "echo",
                "foxtrot",
                "golf",
                "hotel",
                "india",
                "juliet",
                "kilo",
                "lima",
            )
        ]
        for attempt in mechanical["attempts"]:
            self.assertEqual(attempt["agent_calls"], 1)
            self.assertEqual(attempt["agent_role"], "mech-executor")
            self.assertFalse(attempt["invocation_model_present"])
            self.assertTrue(attempt["foreground"])
            self.assertTrue(attempt["collected"])
            self.assertEqual(attempt["modified_paths"], expected_adapters)
            self.assertEqual(attempt["tests"], "12 passed, 0 failed")
        self.assertFalse(mechanical["budget_incomplete_diagnostic"]["collected"])
        self.assertFalse(
            mechanical["budget_incomplete_diagnostic"]["invocation_model_present"]
        )

        self.assertTrue(schema["implementation_route_is_non_blocking"])
        self.assertEqual(len(schema["attempts"]), 2)
        self.assertEqual(
            len(
                {
                    attempt["session_binding"]["sanitized_session_id_sha256"]
                    for attempt in schema["attempts"]
                }
            ),
            2,
        )
        schema_tests = {"a": "5 passed, 0 failed", "b": "4 passed, 0 failed"}
        for attempt in schema["attempts"]:
            binding = attempt["session_binding"]
            self.assertRegex(binding["sanitized_session_id_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(
                binding["event_index_source"],
                "persisted Claude session transcript JSONL zero-based line index",
            )
            self.assertEqual(binding["turn_1_invocation"], "--session-id")
            self.assertEqual(binding["turn_2_invocation"], "--resume")
            self.assertEqual(attempt["turn_1"]["plan_verifier_calls"], 1)
            self.assertFalse(attempt["turn_1"]["invocation_model_present"])
            self.assertTrue(attempt["turn_1"]["foreground"])
            self.assertTrue(attempt["turn_1"]["collected"])
            self.assertEqual(attempt["turn_1"]["verdict"], "READY")
            self.assertFalse(attempt["turn_1"]["writes_before_approval"])
            self.assertTrue(attempt["turn_1"]["stopped_for_approval"])
            self.assertEqual(
                attempt["turn_2"]["implementation_route"],
                "main_session_direct",
            )
            self.assertEqual(attempt["turn_2"]["execution_agent_calls"], 0)
            self.assertEqual(
                attempt["turn_2"]["primary_tests"], schema_tests[attempt["id"]]
            )
            self.assertLess(
                attempt["turn_2"]["primary_test_call_event_index"],
                attempt["turn_2"]["primary_test_result_event_index"],
            )
            self.assertLess(
                attempt["turn_2"]["primary_test_result_event_index"],
                attempt["turn_2"]["verifier_call_event_index"],
            )
            self.assertLess(
                attempt["turn_2"]["verifier_call_event_index"],
                attempt["turn_2"]["verifier_result_event_index"],
            )
            self.assertEqual(attempt["turn_2"]["verifier_calls"], 1)
            self.assertFalse(
                attempt["turn_2"]["verifier_invocation_model_present"]
            )
            self.assertTrue(attempt["turn_2"]["verifier_foreground"])
            self.assertTrue(attempt["turn_2"]["verifier_collected"])
            self.assertEqual(attempt["turn_2"]["verifier_verdict"], "CONFIRMED")
            self.assertEqual(
                attempt["turn_2"]["modified_paths"],
                ["store.mjs", "store.test.mjs"],
            )

        completed = routine + bug + mechanical["attempts"]
        completed_cost = sum(
            attempt["client_reported_cost_usd"] for attempt in completed
        ) + sum(
            attempt[turn]["client_reported_cost_usd"]
            for attempt in schema["attempts"]
            for turn in ("turn_1", "turn_2")
        )
        costs = evidence["cost"]
        self.assertEqual(completed_cost, costs["qualifying_completed_cells_usd"])
        self.assertEqual(
            costs["qualifying_completed_cells_usd"]
            + costs["budget_incomplete_diagnostic_usd"],
            costs["campaign_total_usd"],
        )

        raw_hashes = {
            attempt["raw_stream_sha256"] for attempt in completed
        } | {
            attempt[turn]["raw_stream_sha256"]
            for attempt in schema["attempts"]
            for turn in ("turn_1", "turn_2")
        }
        raw_hashes.add(
            mechanical["budget_incomplete_diagnostic"]["raw_stream_sha256"]
        )
        self.assertEqual(len(raw_hashes), 11)

        replay = evidence["release_replay"]
        self.assertEqual(replay["status"], "passed")
        self.assertEqual(replay["policy"]["version"], "1.3.8")
        self.assertEqual(replay["policy"]["bytes"], inputs["policy"]["release_bytes"])
        self.assertEqual(
            replay["policy"]["sha256"], inputs["policy"]["release_sha256"]
        )
        self.assertRegex(replay["policy"]["source_commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(
            replay["agents"]["file_sha256"], inputs["agents"]["file_sha256"]
        )
        self.assertEqual(
            replay["agents"]["runtime_sha256"], inputs["agents"]["runtime_sha256"]
        )
        self.assertEqual(
            set(replay["route"]["client_versions"]), {"2.1.220", "2.1.221"}
        )
        self.assertIn("updated between mechanical attempts", replay["route"]["client_drift"])

        replay_results = replay["results"]
        replay_routine = replay_results["routine_docs"]["attempts"]
        replay_bug = replay_results["single_unknown_bug"]["attempts"]
        replay_mechanical = replay_results["mechanical_repetition"]["attempts"]
        replay_schema = replay_results["schema_lifecycle"]["attempts"]
        self.assertEqual(len(replay_routine), 2)
        self.assertTrue(all(item["agent_calls"] == 0 for item in replay_routine))
        self.assertTrue(
            all(item["modified_paths"] == ["README.md"] for item in replay_routine)
        )
        self.assertTrue(
            all(item["tests"] == "1 passed, 0 failed" for item in replay_routine)
        )
        self.assertEqual(len(replay_bug), 2)
        self.assertTrue(all(item["agent_calls"] == 0 for item in replay_bug))
        self.assertTrue(
            all(
                item["modified_paths"] == ["src/reducer.js"]
                and item["tests"] == "2 passed, 0 failed"
                for item in replay_bug
            )
        )
        self.assertEqual(len(replay_mechanical), 2)
        for item in replay_mechanical:
            self.assertEqual(item["agent_calls"], 1)
            self.assertEqual(item["agent_role"], "mech-executor")
            self.assertFalse(item["invocation_model_present"])
            self.assertTrue(item["foreground"])
            self.assertTrue(item["collected"])
            self.assertEqual(item["modified_paths"], expected_adapters)
            self.assertEqual(item["tests"], "12 passed, 0 failed")
        self.assertEqual(
            {item["client_version"] for item in replay_mechanical},
            {"2.1.220", "2.1.221"},
        )

        self.assertTrue(replay_results["schema_lifecycle"]["implementation_route_is_non_blocking"])
        self.assertEqual(len(replay_schema), 2)
        for item in replay_schema:
            self.assertRegex(
                item["session_binding"]["sanitized_session_id_sha256"],
                r"^[0-9a-f]{64}$",
            )
            turn_1 = item["turn_1"]
            turn_2 = item["turn_2"]
            self.assertEqual(turn_1["plan_verifier_calls"], 1)
            self.assertFalse(turn_1["invocation_model_present"])
            self.assertTrue(turn_1["foreground"])
            self.assertTrue(turn_1["collected"])
            self.assertEqual(turn_1["verdict"], "READY")
            self.assertFalse(turn_1["writes_before_approval"])
            self.assertTrue(turn_1["stopped_for_approval"])
            self.assertEqual(turn_2["implementation_route"], "main_session_direct")
            self.assertEqual(turn_2["execution_agent_calls"], 0)
            self.assertEqual(turn_2["primary_tests"], schema_tests[item["id"]])
            self.assertLess(
                turn_2["primary_test_call_event_index"],
                turn_2["primary_test_result_event_index"],
            )
            self.assertLess(
                turn_2["primary_test_result_event_index"],
                turn_2["verifier_call_event_index"],
            )
            self.assertLess(
                turn_2["verifier_call_event_index"],
                turn_2["verifier_result_event_index"],
            )
            self.assertEqual(turn_2["verifier_calls"], 1)
            self.assertFalse(turn_2["verifier_invocation_model_present"])
            self.assertTrue(turn_2["verifier_foreground"])
            self.assertTrue(turn_2["verifier_collected"])
            self.assertEqual(turn_2["verifier_verdict"], "CONFIRMED")
            self.assertEqual(
                turn_2["modified_paths"], ["store.mjs", "store.test.mjs"]
            )

        replay_completed = replay_routine + replay_bug + replay_mechanical
        replay_cost = sum(
            item["client_reported_cost_usd"] for item in replay_completed
        ) + sum(
            item[turn]["client_reported_cost_usd"]
            for item in replay_schema
            for turn in ("turn_1", "turn_2")
        )
        self.assertEqual(
            replay_cost.quantize(Decimal("0.00000001")),
            replay["budget"]["actual_usd"],
        )
        self.assertLessEqual(
            replay["budget"]["maximum_allocated_usd"],
            replay["budget"]["hard_cap_usd"],
        )
        replay_hashes = {
            item["raw_stream_sha256"] for item in replay_completed
        } | {
            item[turn]["raw_stream_sha256"]
            for item in replay_schema
            for turn in ("turn_1", "turn_2")
        }
        self.assertEqual(len(replay_hashes), 10)

        adaptive = evidence["adaptive_interaction_routing_gate"]
        self.assertEqual(adaptive["status"], "passed")
        candidate = (path / adaptive["candidate"]["path"]).read_bytes()
        self.assertEqual(len(candidate), adaptive["candidate"]["bytes"])
        self.assertEqual(
            hashlib.sha256(candidate).hexdigest(), adaptive["candidate"]["sha256"]
        )
        self.assertEqual(adaptive["prompt_set"], "inputs.prompts")
        self.assertEqual(adaptive["fixture_set"], "inputs.fixtures")
        self.assertIsNone(adaptive["candidate"]["runtime_loaded_sha256"])
        self.assertEqual(
            adaptive["agents"]["runtime_sha256"], inputs["agents"]["runtime_sha256"]
        )
        self.assertEqual(
            set(adaptive["route"]["client_versions"]), {"2.1.223", "2.1.224"}
        )
        self.assertIn("between Schema B Turn 1", adaptive["route"]["client_drift"])

        adaptive_results = adaptive["results"]
        adaptive_routine = adaptive_results["routine_docs"]["attempts"]
        adaptive_bug = adaptive_results["single_unknown_bug"]["attempts"]
        adaptive_mechanical = adaptive_results["mechanical_repetition"]["attempts"]
        adaptive_schema = adaptive_results["schema_lifecycle"]["attempts"]
        self.assertTrue(
            all(
                item["agent_calls"] == 0
                and item["modified_paths"] == ["README.md"]
                and item["tests"] == "1 passed, 0 failed"
                for item in adaptive_routine
            )
        )
        self.assertTrue(
            all(
                item["agent_calls"] == 0
                and item["modified_paths"] == ["src/reducer.js"]
                and item["tests"] == "2 passed, 0 failed"
                for item in adaptive_bug
            )
        )
        for item in adaptive_mechanical:
            self.assertEqual(item["agent_calls"], 1)
            self.assertEqual(item["agent_role"], "mech-executor")
            self.assertFalse(item["invocation_model_present"])
            self.assertTrue(item["foreground"] and item["collected"])
            self.assertFalse(item["main_session_source_mutation"])
            self.assertEqual(item["modified_paths"], expected_adapters)
            self.assertEqual(item["tests"], "12 passed, 0 failed")

        adaptive_schema_tests = {"a": "4 passed, 0 failed", "b": "5 passed, 0 failed"}
        self.assertTrue(adaptive_results["schema_lifecycle"]["implementation_route_is_non_blocking"])
        for item in adaptive_schema:
            self.assertRegex(
                item["session_binding"]["sanitized_session_id_sha256"],
                r"^[0-9a-f]{64}$",
            )
            turn_1 = item["turn_1"]
            turn_2 = item["turn_2"]
            self.assertEqual(turn_1["plan_verifier_calls"], 1)
            self.assertFalse(turn_1["invocation_model_present"])
            self.assertTrue(turn_1["foreground"] and turn_1["collected"])
            self.assertEqual(turn_1["verdict"], "READY")
            self.assertFalse(turn_1["writes_before_approval"])
            self.assertTrue(turn_1["stopped_for_approval"])
            self.assertEqual(turn_2["implementation_route"], "main_session_direct")
            self.assertEqual(turn_2["execution_agent_calls"], 0)
            self.assertEqual(turn_2["primary_tests"], adaptive_schema_tests[item["id"]])
            self.assertTrue(turn_2["primary_tests_before_verifier"])
            self.assertEqual(turn_2["verifier_calls"], 1)
            self.assertFalse(turn_2["verifier_invocation_model_present"])
            self.assertTrue(turn_2["verifier_foreground"] and turn_2["verifier_collected"])
            self.assertEqual(turn_2["verifier_verdict"], "CONFIRMED")
            self.assertEqual(
                turn_2["modified_paths"], ["store.mjs", "store.test.mjs"]
            )

        adaptive_completed = adaptive_routine + adaptive_bug + adaptive_mechanical
        adaptive_cost = sum(
            item["client_reported_cost_usd"] for item in adaptive_completed
        ) + sum(
            item[turn]["client_reported_cost_usd"]
            for item in adaptive_schema
            for turn in ("turn_1", "turn_2")
        )
        self.assertEqual(
            adaptive_cost.quantize(Decimal("0.00000001")),
            adaptive["budget"]["actual_usd"],
        )
        self.assertLessEqual(
            adaptive["budget"]["maximum_allocated_usd"],
            adaptive["budget"]["hard_cap_usd"],
        )
        adaptive_hashes = {
            item["raw_stream_sha256"] for item in adaptive_completed
        } | {
            item[turn]["raw_stream_sha256"]
            for item in adaptive_schema
            for turn in ("turn_1", "turn_2")
        }
        self.assertEqual(len(adaptive_hashes), 10)

        post_review = evidence["adaptive_interaction_routing_post_review_gate"]
        self.assertEqual(post_review["status"], "passed")
        post_candidate = (path / post_review["candidate"]["path"]).read_bytes()
        self.assertEqual(len(post_candidate), post_review["candidate"]["bytes"])
        self.assertEqual(
            hashlib.sha256(post_candidate).hexdigest(),
            post_review["candidate"]["sha256"],
        )
        self.assertEqual(post_review["prompt_set"], "inputs.prompts")
        self.assertEqual(post_review["fixture_set"], "inputs.fixtures")
        self.assertIsNone(post_review["candidate"]["runtime_loaded_sha256"])
        self.assertEqual(
            post_review["agents"]["runtime_sha256"],
            inputs["agents"]["runtime_sha256"],
        )
        self.assertEqual(post_review["route"]["client_versions"], ["2.1.224"])

        post_results = post_review["results"]
        post_routine = post_results["routine_docs"]["attempts"]
        post_bug = post_results["single_unknown_bug"]["attempts"]
        post_mechanical = post_results["mechanical_repetition"]["attempts"]
        post_schema = post_results["schema_lifecycle"]["attempts"]
        self.assertTrue(
            all(
                item["agent_calls"] == 0
                and item["modified_paths"] == ["README.md"]
                and item["tests"] == "1 passed, 0 failed"
                for item in post_routine
            )
        )
        self.assertTrue(
            all(
                item["agent_calls"] == 0
                and item["modified_paths"] == ["src/reducer.js"]
                and item["tests"] == "2 passed, 0 failed"
                for item in post_bug
            )
        )
        for item in post_mechanical:
            self.assertEqual(item["agent_calls"], 1)
            self.assertEqual(item["agent_role"], "mech-executor")
            self.assertFalse(item["invocation_model_present"])
            self.assertTrue(item["foreground"] and item["collected"])
            self.assertFalse(item["main_session_source_mutation"])
            self.assertEqual(item["modified_paths"], expected_adapters)
            self.assertEqual(item["tests"], "12 passed, 0 failed")

        post_schema_tests = {"a": "5 passed, 0 failed", "b": "4 passed, 0 failed"}
        self.assertTrue(
            post_results["schema_lifecycle"]["implementation_route_is_non_blocking"]
        )
        for item in post_schema:
            self.assertRegex(
                item["session_binding"]["sanitized_session_id_sha256"],
                r"^[0-9a-f]{64}$",
            )
            turn_1 = item["turn_1"]
            turn_2 = item["turn_2"]
            self.assertEqual(turn_1["plan_verifier_calls"], 1)
            self.assertFalse(turn_1["invocation_model_present"])
            self.assertTrue(turn_1["foreground"] and turn_1["collected"])
            self.assertEqual(turn_1["verdict"], "READY")
            self.assertFalse(turn_1["writes_before_approval"])
            self.assertTrue(turn_1["stopped_for_approval"])
            self.assertEqual(turn_2["implementation_route"], "main_session_direct")
            self.assertEqual(turn_2["execution_agent_calls"], 0)
            self.assertEqual(turn_2["primary_tests"], post_schema_tests[item["id"]])
            self.assertTrue(turn_2["primary_tests_before_verifier"])
            self.assertEqual(turn_2["verifier_calls"], 1)
            self.assertFalse(turn_2["verifier_invocation_model_present"])
            self.assertTrue(
                turn_2["verifier_foreground"] and turn_2["verifier_collected"]
            )
            self.assertEqual(turn_2["verifier_verdict"], "CONFIRMED")
            self.assertEqual(
                turn_2["modified_paths"], ["store.mjs", "store.test.mjs"]
            )

        post_completed = post_routine + post_bug + post_mechanical
        post_cost = sum(
            item["client_reported_cost_usd"] for item in post_completed
        ) + sum(
            item[turn]["client_reported_cost_usd"]
            for item in post_schema
            for turn in ("turn_1", "turn_2")
        )
        self.assertEqual(
            post_cost.quantize(Decimal("0.00000001")),
            post_review["budget"]["actual_usd"],
        )
        self.assertLessEqual(
            post_review["budget"]["maximum_allocated_usd"],
            post_review["budget"]["hard_cap_usd"],
        )
        post_hashes = {
            item["raw_stream_sha256"] for item in post_completed
        } | {
            item[turn]["raw_stream_sha256"]
            for item in post_schema
            for turn in ("turn_1", "turn_2")
        }
        self.assertEqual(len(post_hashes), 10)

    def test_compact_policy_full_matrix_is_exact_and_complete(self) -> None:
        path = ROOT / "benchmarks" / "spontaneous-dispatch"
        evidence = json.loads(
            (path / "compact-policy-full-matrix.json").read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        candidate = (path / evidence["candidate"]["path"]).read_bytes()
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(len(candidate), evidence["candidate"]["bytes"])
        self.assertEqual(
            hashlib.sha256(candidate).hexdigest(), evidence["candidate"]["sha256"]
        )
        live = (ROOT / "templates/claude-md.orchestration.md").read_bytes()
        normalize_version_marker = lambda payload: re.sub(
            rb"<!-- pilotfish v\d+\.\d+\.\d+ -->",
            b"<!-- pilotfish vX.Y.Z -->",
            payload,
        )
        self.assertNotEqual(candidate, live)
        self.assertEqual(
            normalize_version_marker(candidate), normalize_version_marker(live)
        )
        self.assertEqual(evidence["route"]["client_versions"], ["2.1.224"])

        expected_adapters = [
            f"src/adapters/{name}.js"
            for name in (
                "alpha bravo charlie delta echo foxtrot golf hotel india "
                "juliet kilo lima"
            ).split()
        ]
        results = evidence["results"]
        routine = results["routine_docs"]["attempts"]
        bug = results["single_unknown_bug"]["attempts"]
        mechanical = results["mechanical_repetition"]["attempts"]
        schema = results["schema_lifecycle"]["attempts"]
        self.assertEqual(len(routine), 2)
        self.assertEqual(len(bug), 2)
        self.assertEqual(len(mechanical), 2)
        self.assertEqual(len(schema), 2)
        self.assertTrue(
            all(
                item["agent_calls"] == 0
                and item["modified_paths"] == ["README.md"]
                and item["tests"] == "1 passed, 0 failed"
                for item in routine
            )
        )
        self.assertTrue(
            all(
                item["agent_calls"] == 0
                and item["modified_paths"] == ["src/reducer.js"]
                and item["tests"] == "2 passed, 0 failed"
                for item in bug
            )
        )
        self.assertTrue(
            all(
                item["agent_calls"] == 1
                and item["agent_role"] == "mech-executor"
                and item["foreground"]
                and item["collected"]
                and not item["main_session_source_mutation"]
                and item["modified_paths"] == expected_adapters
                and item["tests"] == "12 passed, 0 failed"
                for item in mechanical
            )
        )
        for item in schema:
            self.assertRegex(
                item["session_binding"]["sanitized_session_id_sha256"],
                r"^[0-9a-f]{64}$",
            )
            self.assertEqual(item["turn_1"]["plan_verifier_calls"], 1)
            self.assertEqual(item["turn_1"]["verdict"], "READY")
            self.assertFalse(item["turn_1"]["writes_before_approval"])
            self.assertTrue(item["turn_1"]["stopped_for_approval"])
            self.assertEqual(item["turn_2"]["primary_tests"], "4 passed, 0 failed")
            self.assertTrue(item["turn_2"]["primary_tests_before_verifier"])
            self.assertEqual(item["turn_2"]["verifier_calls"], 1)
            self.assertEqual(item["turn_2"]["verifier_verdict"], "CONFIRMED")
            self.assertEqual(
                item["turn_2"]["modified_paths"], ["store.mjs", "store.test.mjs"]
            )

        completed = routine + bug + mechanical
        cost = sum(item["client_reported_cost_usd"] for item in completed) + sum(
            item[turn]["client_reported_cost_usd"]
            for item in schema
            for turn in ("turn_1", "turn_2")
        )
        self.assertEqual(
            cost.quantize(Decimal("0.00000001")), evidence["budget"]["actual_usd"]
        )
        hashes = {item["raw_stream_sha256"] for item in completed} | {
            item[turn]["raw_stream_sha256"]
            for item in schema
            for turn in ("turn_1", "turn_2")
        }
        self.assertEqual(len(hashes), 10)

    def test_spontaneous_dispatch_baseline_is_additive_and_evidence_bound(self) -> None:
        benchmark = ROOT / "benchmarks" / "spontaneous-dispatch"
        results = json.loads((benchmark / "results.json").read_text(encoding="utf-8"))
        traces = json.loads((benchmark / "traces.json").read_text(encoding="utf-8"))
        calls = json.loads((benchmark / "agent-calls.json").read_text(encoding="utf-8"))
        runs = {run["name"]: run for run in results["runs"]}

        fable = runs["fable-v1.3.0-mechanical-baseline"]
        self.assertEqual(fable["observed_main_model"], "claude-fable-5")
        self.assertEqual(fable["status"], "usage_credits_required")
        self.assertEqual(fable["duration_api_ms"], 0)
        self.assertEqual(fable["reported_cost_usd"], 0)
        self.assertEqual(fable["agent_call_count"], 0)
        self.assertFalse(fable["source_mutation_observed"])
        self.assertIn("No behavior", fable["claim"])

        opus = runs["opus-v1.3.0-mechanical-baseline"]
        self.assertEqual(opus["observed_main_model"], "claude-opus-4-8")
        self.assertEqual(opus["status"], "success_topology_fail")
        self.assertEqual((opus["tests_passed"], opus["tests_failed"]), (12, 0))
        self.assertEqual(opus["agent_call_count"], 0)
        self.assertTrue(opus["source_mutation_observed"])
        self.assertIn("topology failed", opus["claim"])

        candidate_mechanical = runs["opus-v1.3.1-candidate-1-mechanical"]
        self.assertEqual(candidate_mechanical["status"], "passed")
        self.assertEqual(
            candidate_mechanical["observed_main_model"], "claude-opus-4-8"
        )
        self.assertEqual(candidate_mechanical["agent_call_count"], 1)
        self.assertEqual(candidate_mechanical["agent_type"], "mech-executor")
        self.assertFalse(candidate_mechanical["agent_invocation_model_present"])
        self.assertFalse(candidate_mechanical["main_source_mutation_observed"])
        self.assertTrue(candidate_mechanical["worker_is_sole_source_mutation_path"])
        self.assertEqual(candidate_mechanical["tests_after"], "12/12 passed")

        candidate_bug = runs["opus-v1.3.1-candidate-1-bug"]
        self.assertEqual(candidate_bug["status"], "passed")
        self.assertEqual(candidate_bug["agent_call_count"], 0)
        self.assertTrue(candidate_bug["main_owned_first_minimal_fix"])
        self.assertTrue(candidate_bug["main_observed_post_fix_pass"])
        self.assertEqual(candidate_bug["tests_after"], "2/2 passed")

        release_input = results["policy_inputs"]["v1.3.1-release-payload"]
        self.assertEqual(
            release_input["policy_sha256"],
            "17d272b6ddd6d95a749a802f5e29dfd4625c884f8a84bf817ffc20bfca6b39bf",
        )
        self.assertEqual(
            release_input["agents_json_sha256"],
            "0b42c137daf4006a9c85b201c9434e13640fce69fb10fcf0fba6ba2b1379723c",
        )

        release_mechanical = runs["opus-v1.3.1-release-payload-mechanical"]
        self.assertEqual(release_mechanical["status"], "passed")
        self.assertEqual(release_mechanical["agent_call_count"], 1)
        self.assertEqual(release_mechanical["agent_type"], "mech-executor")
        self.assertFalse(release_mechanical["agent_invocation_model_present"])
        self.assertEqual(
            release_mechanical["observed_agent_model"], "claude-sonnet-5"
        )
        self.assertFalse(release_mechanical["main_source_mutation_observed"])
        self.assertTrue(release_mechanical["worker_is_sole_source_mutation_path"])
        self.assertEqual(release_mechanical["tests_after"], "12/12 passed")
        self.assertEqual(
            release_mechanical["independent_post_run_test"]["tests_failed"], 0
        )

        release_bug = runs["opus-v1.3.1-release-payload-bug"]
        self.assertEqual(release_bug["status"], "passed")
        self.assertEqual(release_bug["agent_call_count"], 0)
        self.assertTrue(release_bug["main_owned_first_minimal_fix"])
        self.assertTrue(release_bug["main_observed_post_fix_pass"])
        self.assertEqual(release_bug["tests_after"], "2/2 passed")
        self.assertEqual(release_bug["independent_post_run_test"]["tests_failed"], 0)

        for run_name in runs:
            self.assertIn(run_name, traces["runs"])
            self.assertIn(run_name, calls["runs"])
        self.assertEqual(calls["runs"]["fable-v1.3.0-mechanical-baseline"], [])
        self.assertEqual(calls["runs"]["opus-v1.3.0-mechanical-baseline"], [])
        self.assertEqual(
            calls["runs"]["opus-v1.3.1-candidate-1-mechanical"][0][
                "subagent_type"
            ],
            "mech-executor",
        )
        self.assertFalse(
            calls["runs"]["opus-v1.3.1-candidate-1-mechanical"][0][
                "invocation_model_present"
            ]
        )
        self.assertEqual(calls["runs"]["opus-v1.3.1-candidate-1-bug"], [])
        self.assertIn(
            "Bash",
            traces["runs"]["opus-v1.3.0-mechanical-baseline"][
                "main_source_write_tools"
            ],
        )
        candidate_trace = traces["runs"]["opus-v1.3.1-candidate-1-mechanical"]
        self.assertEqual(candidate_trace["top_level_source_write_tools"], [])
        self.assertEqual(candidate_trace["top_level_tools"].count("Agent"), 1)
        bug_trace = traces["runs"]["opus-v1.3.1-candidate-1-bug"]
        self.assertEqual(bug_trace["agent_calls"], [])
        self.assertLess(
            bug_trace["first_minimal_fix_tool_index"],
            bug_trace["post_fix_passing_test_tool_index"],
        )
        release_call = calls["runs"][
            "opus-v1.3.1-release-payload-mechanical"
        ][0]
        self.assertEqual(release_call["observed_model"], "claude-sonnet-5")
        release_mechanical_trace = traces["runs"][
            "opus-v1.3.1-release-payload-mechanical"
        ]
        self.assertEqual(
            release_mechanical_trace["top_level_source_write_tools"], []
        )
        self.assertEqual(
            release_mechanical_trace["top_level_tools"].count("Agent"), 1
        )
        release_bug_trace = traces["runs"]["opus-v1.3.1-release-payload-bug"]
        self.assertEqual(release_bug_trace["agent_calls"], [])
        self.assertLess(
            release_bug_trace["first_minimal_fix_tool_index"],
            release_bug_trace["post_fix_passing_test_tool_index"],
        )

    def test_baton_gate_snapshot_matches_recorded_hashes(self) -> None:
        gate = ROOT / "benchmarks" / "baton-compatibility"
        results = json.loads(
            (gate / "results.json").read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        runtime = results["runtime"]
        qualified = json.loads(
            (gate / runtime["last_behaviorally_qualified_runtime_evidence"]).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(results["final_gate_status"], "complete")
        self.assertEqual(results["final_gate"]["status"], "passed")

        superseded_policy = (gate / runtime["superseded_gate_snapshot_policy"]).read_bytes()
        superseded_agents = (
            gate / runtime["superseded_gate_snapshot_agents_json"]
        ).read_text(encoding="utf-8").rstrip("\n").encode()
        self.assertEqual(
            hashlib.sha256(superseded_policy).hexdigest(),
            runtime["superseded_gate_orchestration_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(superseded_agents).hexdigest(),
            runtime["superseded_gate_agents_json_sha256"],
        )

        current_policy = (ROOT / "templates/claude-md.orchestration.md").read_bytes()
        normalize_version_marker = lambda payload: re.sub(
            rb"<!-- pilotfish v\d+\.\d+\.\d+ -->",
            b"<!-- pilotfish vX.Y.Z -->",
            payload,
        )
        snapshot_policy = (gate / runtime["final_gate_snapshot_policy"]).read_bytes()
        snapshot_agents = (
            gate / runtime["final_gate_snapshot_agents_json"]
        ).read_bytes().rstrip(b"\n")
        completed = subprocess.run(
            [
                sys.executable,
                str(gate / "build-agents-json.py"),
                str(ROOT / "templates/agents"),
            ],
            check=True,
            capture_output=True,
        )
        self.assertNotEqual(current_policy, snapshot_policy)
        release_candidate_policy = (
            gate / runtime["release_candidate_orchestration_path"]
        ).read_bytes()
        self.assertEqual(release_candidate_policy, current_policy)
        self.assertEqual(
            runtime["release_candidate_orchestration_sha256"],
            hashlib.sha256(release_candidate_policy).hexdigest(),
        )
        last_qualified_policy = (
            gate / runtime["last_behaviorally_qualified_orchestration_path"]
        ).read_bytes()
        self.assertEqual(
            runtime["last_behaviorally_qualified_orchestration_sha256"],
            hashlib.sha256(last_qualified_policy).hexdigest(),
        )
        self.assertNotEqual(last_qualified_policy, current_policy)
        self.assertEqual(
            normalize_version_marker(last_qualified_policy),
            normalize_version_marker(current_policy),
        )
        self.assertEqual(
            runtime["release_candidate_agents_json_sha256"],
            hashlib.sha256(completed.stdout.rstrip(b"\n")).hexdigest(),
        )
        release = results["v1_3_2_release_gate"]
        post_gate = results["v1_3_2_post_gate_role_change"]
        release_policy = (gate / release["snapshot_policy"]).read_bytes()
        release_agents_file = (gate / release["snapshot_agents_json"]).read_bytes()
        self.assertNotEqual(release_policy, current_policy)
        self.assertNotEqual(
            normalize_version_marker(release_policy),
            normalize_version_marker(current_policy),
        )
        self.assertNotEqual(
            release_agents_file.rstrip(b"\n"), completed.stdout.rstrip(b"\n")
        )
        self.assertEqual(
            release["agents_json_runtime_sha256"],
            post_gate["agents_json_runtime_sha256_before"],
        )
        self.assertEqual(
            hashlib.sha256(release_policy).hexdigest(),
            release["orchestration_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(release_agents_file).hexdigest(),
            release["agents_json_file_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(release_agents_file.rstrip(b"\n")).hexdigest(),
            release["agents_json_runtime_sha256"],
        )
        for prompt_name, expected in release["prompt_file_hashes"].items():
            prompt = (gate / "prompts" / prompt_name).read_bytes()
            self.assertEqual(hashlib.sha256(prompt).hexdigest(), expected)
            self.assertEqual(
                hashlib.sha256(prompt.rstrip(b"\n")).hexdigest(),
                release["prompt_runtime_input_hashes"][prompt_name],
            )
        opus5 = results["v1_3_2_opus5_release_gate"]
        opus5_policy = (gate / opus5["snapshot_policy"]).read_bytes()
        opus5_agents = (gate / opus5["snapshot_agents_json"]).read_bytes()
        opus5_settings = (gate / opus5["snapshot_settings"]).read_bytes()
        self.assertNotEqual(opus5_policy, current_policy)
        self.assertNotEqual(
            normalize_version_marker(opus5_policy),
            normalize_version_marker(current_policy),
        )
        self.assertEqual(
            hashlib.sha256(opus5_policy).hexdigest(),
            opus5["orchestration_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(opus5_agents).hexdigest(),
            opus5["agents_json_file_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(opus5_agents.rstrip(b"\n")).hexdigest(),
            opus5["agents_json_runtime_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(opus5_agents.rstrip(b"\n")).hexdigest(),
            post_gate["agents_json_runtime_sha256_after"],
        )
        self.assertNotEqual(
            opus5_agents.rstrip(b"\n"),
            completed.stdout.rstrip(b"\n"),
        )
        self.assertEqual(
            hashlib.sha256(opus5_settings).hexdigest(),
            opus5["settings_sha256"],
        )
        self.assertEqual(
            json.loads(opus5_settings),
            {"model": "opus", "fallbackModel": ["sonnet"]},
        )
        for prompt_name, expected in opus5["prompt_file_hashes"].items():
            prompt = (gate / "prompts" / prompt_name).read_bytes()
            self.assertEqual(hashlib.sha256(prompt).hexdigest(), expected)
            self.assertEqual(
                hashlib.sha256(prompt.rstrip(b"\n")).hexdigest(),
                opus5["prompt_runtime_input_hashes"][prompt_name],
            )
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(runtime["final_gate_candidate_version_stamp"], "1.3.1")
        self.assertEqual(runtime["release_candidate_version"], version)
        self.assertEqual(
            runtime["release_candidate_generated_by"],
            "benchmarks/baton-compatibility/build-agents-json.py templates/agents",
        )
        self.assertTrue(
            runtime["release_candidate_behavioral_gate_status"].startswith(
                "passed;"
            )
        )
        self.assertEqual(
            runtime["release_candidate_runtime_evidence"],
            "../spontaneous-dispatch/compact-policy-full-matrix.json",
        )
        self.assertEqual(
            runtime["last_behaviorally_qualified_version"],
            qualified["candidate"]["version_marker"],
        )
        self.assertEqual(
            runtime["last_behaviorally_qualified_runtime_evidence"],
            "../spontaneous-dispatch/compact-policy-full-matrix.json",
        )
        self.assertTrue(
            runtime["last_behaviorally_qualified_status"].startswith("passed;")
        )
        self.assertEqual(
            runtime["last_behaviorally_qualified_agents_json_sha256"],
            qualified["agents"]["runtime_sha256"],
        )
        self.assertEqual(
            runtime["release_candidate_offline_evidence"],
            "tests/test_policy.py::PolicyContractTests.test_baton_gate_snapshot_matches_recorded_hashes",
        )
        self.assertEqual(
            runtime["last_behaviorally_qualified_offline_evidence"],
            "tests/test_policy.py::PolicyContractTests.test_compact_policy_full_matrix_is_exact_and_complete",
        )
        self.assertTrue(
            runtime["release_candidate_policy_delta_from_final_gate"].startswith(
                "non-empty"
            )
        )
        self.assertNotIn(
            "current 18,477-byte policy",
            runtime["release_candidate_policy_delta_from_final_gate"],
        )
        self.assertEqual(
            runtime["release_candidate_agents_json_delta_from_final_gate"],
            "executor role model changed opus to sonnet (issue #18, tier-collapse fix); plan-verifier and verifier prompts carry current blocker, primary-flow fallback, and bounded-recheck contracts; the issue #29 recovery Gate exercised this exact generated payload",
        )
        final_policy = (gate / runtime["final_gate_snapshot_policy"]).read_bytes()
        self.assertEqual(
            hashlib.sha256(final_policy).hexdigest(),
            runtime["final_gate_orchestration_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(snapshot_agents).hexdigest(),
            runtime["final_gate_agents_json_sha256"],
        )
        self.assertEqual(
            runtime["final_gate_candidate_agents_json_sha256"],
            runtime["final_gate_agents_json_sha256"],
        )
        self.assertNotEqual(snapshot_agents, completed.stdout.rstrip(b"\n"))
        snapshot_payload = json.loads(snapshot_agents)
        candidate_payload = json.loads(opus5_agents)
        snapshot_executor = snapshot_payload.pop("executor")
        candidate_executor = candidate_payload.pop("executor")
        snapshot_plan_verifier = snapshot_payload.pop("plan-verifier")
        candidate_plan_verifier = candidate_payload.pop("plan-verifier")
        self.assertEqual(snapshot_executor["model"], "opus")
        self.assertEqual(candidate_executor["model"], "sonnet")
        snapshot_executor["model"] = candidate_executor["model"]
        self.assertEqual(snapshot_executor, candidate_executor)
        self.assertEqual(
            snapshot_plan_verifier["model"], candidate_plan_verifier["model"]
        )
        self.assertEqual(
            snapshot_plan_verifier["tools"], candidate_plan_verifier["tools"]
        )
        self.assertNotEqual(
            snapshot_plan_verifier["prompt"], candidate_plan_verifier["prompt"]
        )
        self.assertIn("program envelope", candidate_plan_verifier["prompt"])
        self.assertIn("Blocker:", candidate_plan_verifier["prompt"])
        self.assertEqual(snapshot_payload, candidate_payload)
        prompt_1 = (gate / "prompts" / "turn-1.txt").read_bytes()
        prompt_2 = (gate / "prompts" / "turn-2.txt").read_bytes()
        prompt_1_file_hash = hashlib.sha256(prompt_1).hexdigest()
        prompt_2_file_hash = hashlib.sha256(prompt_2).hexdigest()
        prompt_1_runtime_hash = hashlib.sha256(prompt_1.rstrip(b"\n")).hexdigest()
        prompt_2_runtime_hash = hashlib.sha256(prompt_2.rstrip(b"\n")).hexdigest()
        self.assertEqual(
            prompt_1_file_hash,
            "45dbe7b6b24cb5838ebf4219011797b61f172fcc18f0ca5039144017e93fcca7",
        )
        self.assertEqual(
            prompt_2_file_hash,
            "82d833090ba91982651de9ac4beed8fc96311119c6eb9c6f0304c292821918e7",
        )
        self.assertEqual(
            prompt_1_runtime_hash,
            "d2ad46b7ecfb503f8f7185d6d68f404d326f1a4a480b9141d1a80318a746bb73",
        )
        self.assertEqual(
            prompt_2_runtime_hash,
            "93ae95d1cd4eebca91ab42a06d484e180f46dd1f327e471a5a4fd2a27ca2f344",
        )
        self.assertEqual(
            prompt_1_file_hash, runtime["final_gate_prompt_turn_1_file_sha256"]
        )
        self.assertEqual(
            prompt_2_file_hash, runtime["final_gate_prompt_turn_2_file_sha256"]
        )
        self.assertEqual(
            prompt_1_runtime_hash,
            runtime["final_gate_prompt_turn_1_runtime_input_sha256"],
        )
        self.assertEqual(
            prompt_2_runtime_hash,
            runtime["final_gate_prompt_turn_2_runtime_input_sha256"],
        )
        self.assertEqual(
            results["final_gate"]["prompt_file_hashes"]["turn-1.txt"],
            prompt_1_file_hash,
        )
        self.assertEqual(
            results["final_gate"]["prompt_file_hashes"]["turn-2.txt"],
            prompt_2_file_hash,
        )
        self.assertEqual(
            results["final_gate"]["prompt_runtime_input_hashes"]["turn-1.txt"],
            prompt_1_runtime_hash,
        )
        self.assertEqual(
            results["final_gate"]["prompt_runtime_input_hashes"]["turn-2.txt"],
            prompt_2_runtime_hash,
        )

        gate_readme = (gate / "README.md").read_text(encoding="utf-8")
        self.assertIn("SESSION_ID=\"$(python3 -c", gate_readme)
        self.assertIn('--session-id "$SESSION_ID"', gate_readme)
        self.assertIn('--resume "$SESSION_ID"', gate_readme)

        turn_1_prompt = (gate / "prompts" / "turn-1.txt").read_text(encoding="utf-8")
        self.assertIn("The Plan must require", turn_1_prompt)
        self.assertIn("fresh existing named `verifier`", turn_1_prompt)
        self.assertIn("`plan-verifier` must return REVISE", turn_1_prompt)

        controls = (
            ROOT
            / "benchmarks"
            / "dispatch-brake"
            / "positive-controls"
            / "README.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("--model claude-opus-4-8", controls)

    def test_verifier_boundary_gate_is_exact_and_claim_limited(self) -> None:
        gate = ROOT / "benchmarks" / "verifier-boundary"
        evidence = json.loads(
            (gate / "results.json").read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        inputs = evidence["inputs"]
        policy = (gate / inputs["policy"]["path"]).read_bytes()
        # v1.3.7 evidence remains immutable historical input. Current exact-byte
        # qualification is bound by issue-29-recovery.json instead.
        self.assertNotEqual(
            policy,
            (ROOT / "templates/claude-md.orchestration.md").read_bytes(),
        )
        self.assertEqual(
            hashlib.sha256(policy).hexdigest(),
            inputs["policy"]["sha256"],
        )

        agents = (gate / inputs["agents"]["path"]).read_bytes()
        completed = subprocess.run(
            [
                sys.executable,
                str(
                    ROOT
                    / "benchmarks"
                    / "baton-compatibility"
                    / "build-agents-json.py"
                ),
                str(ROOT / "templates" / "agents"),
            ],
            check=True,
            capture_output=True,
        )
        self.assertEqual(agents, completed.stdout)
        self.assertEqual(
            hashlib.sha256(agents).hexdigest(),
            inputs["agents"]["file_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(agents.rstrip(b"\n")).hexdigest(),
            inputs["agents"]["runtime_sha256"],
        )

        for prompt in inputs["prompts"].values():
            payload = (gate / prompt["path"]).read_bytes()
            self.assertEqual(
                hashlib.sha256(payload).hexdigest(),
                prompt["file_sha256"],
            )
            self.assertEqual(
                hashlib.sha256(payload.rstrip(b"\n")).hexdigest(),
                prompt["runtime_sha256"],
            )

        passing = evidence["passing_gate"]
        self.assertEqual(passing["status"], "passed")
        self.assertIn("reachability only", passing["claim_boundary"])
        self.assertIn("do not establish cue-free behavior", passing["claim_boundary"])
        schema = passing["schema_lifecycle"]
        self.assertEqual(schema["turn_1"]["plan_verifier_verdict"], "READY")
        self.assertFalse(schema["turn_1"]["writes_before_approval"])
        self.assertEqual(schema["turn_2"]["executor_calls"], 1)
        self.assertEqual(schema["turn_2"]["verifier_verdict"], "CONFIRMED")
        routine = passing["routine_docs_control"]
        self.assertEqual(routine["plan_verifier_calls"], 0)
        self.assertEqual(routine["verifier_calls"], 0)
        cap = passing["post_cap_plan_control"]
        self.assertEqual(cap["verdicts"], ["REVISE", "REVISE", "READY"])
        self.assertTrue(cap["second_turn_stopped_automatic_resubmission"])
        self.assertTrue(cap["third_turn_recorded_new_readiness_epoch"])
        self.assertTrue(cap["third_turn_was_single_closing_check"])
        self.assertTrue(cap["closing_ready_was_not_approval"])
        self.assertEqual(cap["writes"], 0)
        self.assertEqual(
            schema["client_reported_cost_usd"]
            + routine["client_reported_cost_usd"]
            + cap["client_reported_cost_usd"],
            passing["client_reported_cost_usd"],
        )
        self.assertGreater(
            evidence["paid_campaign"]["client_reported_cost_usd"],
            passing["client_reported_cost_usd"],
        )

    def test_prompt_template_semantic_equivalence_gate_is_documented(self) -> None:
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        release = (ROOT / "RELEASING.md").read_text(encoding="utf-8")
        contributing_text = " ".join(contributing.split())
        release_text = " ".join(release.split())

        procedure = "## Independent semantic-equivalence reading"
        self.assertIn(procedure, contributing_text)
        self.assertLess(
            contributing_text.index(procedure),
            contributing_text.index("## Verify the change"),
        )
        for clause in (
            "The independent record must also include the exact reviewed template candidate revision identity (commit and tree) and a SHA-256 for every changed prompt-template file:",
            "Any prompt-template edit after the reading invalidates the record. The independent reader must repeat or update affected pair readings and record the new reviewed template candidate identity and hashes",
            "For a present or added changed prompt-template, record its current SHA-256 and verify that final current bytes match it.",
            "For a deleted prompt-template, record its prior SHA-256 plus exact `current: absent`; no current hash is required, and the final pre-tag gate verifies the path remains absent.",
            "A rename is exactly two records: deletion of the old path with its prior SHA-256 and `current: absent`, plus addition of the new path with `prior: absent` and its current SHA-256; there is no magical rename equivalence.",
            "Any reappearance of a deleted old path or missing/changed added path stops before the tag and requires a reread/update.",
            "Generated non-template artifact changes from the renderer do not invalidate the independent reading when recorded changed-template SHA-256 values remain identical",
            "Do not require the final release tree to equal the reviewed template candidate tree when only those generated artifacts changed",
            "After renderer/tests and the final release commit, record the final release candidate commit and tree separately.",
            "For every present or added changed prompt-template, prove its current SHA-256 equals the independent record and its final current bytes match it; for every deleted path, prove it remains absent.",
            "If any added path is missing or changed, or any deleted path reappears, stop before the tag and repeat or update the reading.",
            "A tree-identical squash merge may map the reviewed PR head to a new commit SHA only when recorded tree equality and every changed-template byte hash are identical",
        ):
            with self.subTest(document="CONTRIBUTING.md", clause=clause):
                self.assertIn(clause, contributing_text)
        for anchor in (
            "behavior-bearing prompt templates",
            "prompt-bearing templates",
            "policy/agent templates",
            "`templates/claude-md.orchestration.md`",
            "`templates/agents/*.md`",
            "`templates/settings.snippet.json`",
            "exact base revision",
            "changed template path",
            "identity of an independent semantic reader",
            "did not author",
            "reviewed template candidate revision",
            "reviewed template candidate tree",
            "SHA-256 for every changed prompt-template file",
            "changed-template SHA-256",
            "changed-template records: present or added: path: <changed prompt-template path> current SHA-256: <SHA-256> deleted: path: <deleted prompt-template path> prior SHA-256: <SHA-256> current: absent",
            "present or added changed prompt-template",
            "deleted prompt-template",
            "prior SHA-256",
            "current hash is required",
            "final pre-tag gate",
            "deleted old path",
            "missing/changed added path",
            "reread/update",
            "prior counterpart",
            "`prior: absent`",
            "`current: absent`",
            "changes what an agent would do",
            "`behaviorally unchanged`",
            "semantic difference",
            "main-owned `FIX`, `DEFER`, or `REJECT`",
            "rationale",
            "Additions and deletions require an explicit semantic disposition",
            "complete before release readiness",
            "Any prompt-template edit after the reading invalidates the record",
            "repeat or update affected pair readings",
            "new reviewed template candidate identity and hashes",
            "completed dispositions alone are insufficient",
            "final release candidate commit and tree",
            "final current bytes",
            "deleted path",
            "equals the independent record",
            "stop before the tag",
            "repeat or update the reading",
            "tree-identical squash merge",
            "reviewed PR head",
            "new commit SHA",
            "recorded tree equality",
            "Phrase assertions",
            "byte/hash checks",
            "renderer checks",
            "live behavioral Gates",
            "supporting evidence",
            "none substitutes for independent semantic reading",
            "Issue #40",
            "phrase checks missed behavior changes",
        ):
            with self.subTest(document="CONTRIBUTING.md", anchor=anchor):
                self.assertIn(anchor, contributing_text)

        release_gate = "Before rendering, prompt-bearing template changes require"
        self.assertIn(release_gate, release_text)
        for anchor in (
            "prompt-bearing template changes",
            "`templates/claude-md.orchestration.md`",
            "`templates/agents/*.md`",
            "`templates/settings.snippet.json`",
            "[Independent semantic-equivalence reading](CONTRIBUTING.md#independent-semantic-equivalence-reading)",
            "exact base revision",
            "changed template paths",
            "independent reader identity",
            "did not author",
            "prior/current pair records",
            "`prior: absent`",
            "`current: absent`",
            "reviewed template candidate commit/tree",
            "current SHA-256 for every present or added path",
            "prior SHA-256 plus `current: absent` for every deleted path",
            "Represent a rename as separate deletion and addition records",
            "`FIX`",
            "`DEFER`",
            "`REJECT`",
            "before release readiness",
            "final release candidate commit/tree separately",
            "Verify every present or added changed prompt-template's final current bytes and current SHA-256 match the independent reading record",
            "verify every deleted path remains absent",
            "no current hash is required",
            "missing or changed added path",
            "reappeared deleted path",
            "stops before the tag",
            "requires a reread/update",
            "tree-identical squash merge",
            "reviewed PR head",
            "new commit SHA",
            "recorded tree equality",
        ):
            with self.subTest(document="RELEASING.md", anchor=anchor):
                self.assertIn(anchor, release_text)
        for clause in (
            "After rendering and tests pass, review the complete diff and commit the release candidate. Before `claude plugin tag --dry-run plugin`, record the final release candidate commit/tree separately.",
            "Verify every present or added changed prompt-template's final current bytes and current SHA-256 match the independent reading record; verify every deleted path remains absent (no current hash is required).",
            "Any missing or changed added path, or reappeared deleted path, stops before the tag and requires a reread/update.",
            "A tree-identical squash merge may map the reviewed PR head to a new commit SHA only when recorded tree equality and every changed-template byte hash are identical",
        ):
            with self.subTest(document="RELEASING.md", clause=clause):
                self.assertIn(clause, release_text)
        gate_index = release_text.index(release_gate)
        render_index = release_text.index("python3 tools/render_plugin_spike.py --write")
        tests_index = release_text.index("python3 -m unittest discover -s tests -v")
        final_candidate_index = release_text.index("After rendering and tests pass")
        tag_index = release_text.index("claude plugin tag --dry-run plugin")
        self.assertLess(gate_index, render_index)
        self.assertLess(render_index, tests_index)
        self.assertLess(tests_index, final_candidate_index)
        self.assertLess(final_candidate_index, tag_index)

    def test_release_pin_and_candidate_stamp_are_explicit(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"<!-- pilotfish v{version} -->", policy)

        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(changelog, rf"(?m)^## v{re.escape(version)} ")
        self.assertRegex(changelog, r"(?m)^## v1\.3\.8 ")

        for readme in ("README.md", "README.zh-TW.md"):
            content = (ROOT / readme).read_text(encoding="utf-8")
            self.assertIn(f"git clone --branch v{version} --depth 1", content)

        for readme, label in (
            ("benchmarks/baton-compatibility/README.md", "Current generated"),
            ("benchmarks/baton-compatibility/README.zh-TW.md", "目前產生的"),
        ):
            content = (ROOT / readme).read_text(encoding="utf-8")
            self.assertIn(f"{label} v{version} agents payload", content)

        runtime = json.loads(
            (ROOT / "benchmarks/baton-compatibility/results.json").read_text(
                encoding="utf-8"
            )
        )["runtime"]
        self.assertIn(
            f"v{version} release candidate",
            runtime["release_candidate_behavioral_gate_status"],
        )

    def test_release_pushes_default_branch_before_tags(self) -> None:
        release = (ROOT / "RELEASING.md").read_text(encoding="utf-8")
        match = re.search(
            r"```bash\n(?P<body>   \(\n   set -eu\n.*?\n   \))\n   ```",
            release,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        block = re.sub(r"(?m)^   ", "", match.group("body"))
        branch_push = 'git push origin "HEAD:refs/heads/$RELEASE_BRANCH"'
        branch_fetch = 'git fetch origin "$RELEASE_BRANCH"'
        remote_sha = (
            'test "$(git rev-parse HEAD)" = '
            '"$(git rev-parse "origin/$RELEASE_BRANCH")"'
        )
        root_tag = 'git tag -a "v$RELEASE_VERSION"'
        plugin_tag = 'claude plugin tag plugin'
        tag_push = 'git push --atomic origin "v$RELEASE_VERSION" "pilotfish--v$RELEASE_VERSION"'
        github_release = 'gh release create "v$RELEASE_VERSION"'
        ordered = (
            "refs/remotes/origin/HEAD",
            'test "$(git branch --show-current)" = "$RELEASE_BRANCH"',
            branch_push,
            branch_fetch,
            remote_sha,
            root_tag,
            plugin_tag,
            tag_push,
            github_release,
        )

        def assert_contract(candidate: str) -> None:
            self.assertTrue(candidate.startswith("(\nset -eu\n"))
            self.assertTrue(candidate.endswith("\n)"))
            indexes = [candidate.index(clause) for clause in ordered]
            self.assertEqual(indexes, sorted(indexes))

        assert_contract(block)
        self.assertIn("absent from the remote default branch", release)

        without_errexit = block.replace("set -eu\n", "", 1)
        with self.assertRaises(AssertionError):
            assert_contract(without_errexit)
        release_before_push = block.replace(
            f"{github_release} --title \"v$RELEASE_VERSION\" --notes-from-tag\n",
            "",
        ).replace(branch_push, f"{github_release} --title \"v$RELEASE_VERSION\" --notes-from-tag\n{branch_push}")
        with self.assertRaises(AssertionError):
            assert_contract(release_before_push)
        fetch_after_tags = block.replace(f"{branch_fetch}\n", "").replace(
            root_tag, f"{root_tag}\n{branch_fetch}"
        )
        with self.assertRaises(AssertionError):
            assert_contract(fetch_after_tags)

        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "tag-phase-reached"
            late = 'printf \'late\\n\' >> "$MARKER"'
            harness = block.replace(
                'test "$(git branch --show-current)" = "$RELEASE_BRANCH"', ":"
            ).replace(branch_push, "false")
            for command in (
                branch_fetch,
                remote_sha,
                root_tag,
                plugin_tag,
                tag_push,
                f'{github_release} --title "v$RELEASE_VERSION" --notes-from-tag',
            ):
                harness = harness.replace(command, late)
            completed = subprocess.run(
                ["/bin/sh", "-c", harness],
                cwd=ROOT,
                env={**os.environ, "MARKER": str(marker)},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(marker.exists())

    def test_release_recovery_never_rewrites_published_tags(self) -> None:
        release = (ROOT / "RELEASING.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```bash\n(?P<body>.*?)\n   ```", release, re.DOTALL)
        matches = [block for block in blocks if "remote_tag_commit()" in block]
        self.assertEqual(len(matches), 1)
        block = re.sub(r"(?m)^   ", "", matches[0])

        root = 'RELEASE_SHA=$(remote_tag_commit "v$RELEASE_VERSION")'
        plugin = (
            'test "$(remote_tag_commit "pilotfish--v$RELEASE_VERSION")" = '
            '"$RELEASE_SHA"'
        )
        ancestry = (
            'git merge-base --is-ancestor "$RELEASE_SHA" '
            '"origin/$RELEASE_BRANCH"'
        )
        view = 'if gh release view "v$RELEASE_VERSION"'
        create = 'gh release create "v$RELEASE_VERSION"'
        indexes = [block.index(clause) for clause in (root, plugin, ancestry, view, create)]
        self.assertEqual(indexes, sorted(indexes))
        for forbidden in ("git tag ", "claude plugin tag", "git push"):
            self.assertNotIn(forbidden, block)
        warning = re.search(
            r"This recovery path .*?(?=\n\n)", release, re.DOTALL
        ).group()
        self.assertIn("must never recreate, move, force, or repush either tag", warning)
        self.assertIn(
            "requires a later `VERSION` and new tags, not mutation of the "
            "Release for those exact existing tags",
            warning,
        )
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertNotIn(f"v{version}", warning)

    def test_pilotfish_brand_stays_lowercase_in_live_markdown(self) -> None:
        surfaces = [
            ROOT / "CHANGELOG.md",
            ROOT / "CONTRIBUTING.md",
            ROOT / "README.md",
            ROOT / "README.zh-TW.md",
            ROOT / "RELEASING.md",
            ROOT / "templates/claude-md.orchestration.md",
            *sorted((ROOT / "templates/agents").glob("*.md")),
            *sorted((ROOT / "docs").glob("*.md")),
            *sorted((ROOT / "install").glob("*.md")),
            *sorted(
                path
                for path in (ROOT / "benchmarks").rglob("README*.md")
                if not any("snapshot" in part for part in path.parts)
            ),
        ]
        for path in surfaces:
            with self.subTest(path=path.relative_to(ROOT)):
                for match in re.finditer(
                    r"(?i)\bpilotfish\b", path.read_text(encoding="utf-8")
                ):
                    self.assertEqual(match.group(), "pilotfish")

    def test_prompt_templates_stay_within_density_budget(self) -> None:
        # The standing property from #27 is that the prompt text stays densely
        # written, not that it stays smaller than some past tag. A byte ceiling
        # pegged to a release would block a rule the policy genuinely needs;
        # this measures whether new text is written at the same density as the
        # rest. ponytail: filler-word share is a heuristic proxy for that, and a
        # determined author could pad around the word list — swap in a real
        # compression-ratio measurement if that ever happens in practice.
        budget = json.loads(
            (ROOT / "benchmarks/prompt-compression/budget.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(budget["metric"], "bytes_per_rule + filler_word_share")
        filler = frozenset(budget["definition"]["filler_words"])

        policy = ROOT / "templates/claude-md.orchestration.md"
        text = policy.read_text(encoding="utf-8")
        rules = [
            line
            for line in text.split("\n")
            if line.startswith(("- ", "| ")) and len(line) > 40
        ]
        self.assertEqual(
            len(rules),
            budget["primary"]["expected_rule_count"],
            "rule count changed; splitting a rule across bullets inflates the "
            "denominator and manufactures budget headroom. If the change is "
            "deliberate, update expected_rule_count in budget.json in the same "
            "review.",
        )
        # UTF-8 bytes, not code points: the metric is named in bytes and that is
        # what a session pays for. Counting code points would let a few
        # multi-byte characters push the real size over an apparently passing
        # budget.
        per_rule = len(policy.read_bytes()) / len(rules)
        self.assertLessEqual(
            per_rule,
            budget["primary"]["max_bytes_per_rule"],
            f"{policy.name}: {per_rule:.0f} bytes per rule across {len(rules)} "
            f"rules exceeds {budget['primary']['max_bytes_per_rule']}. Adding "
            "rules is allowed; writing them at length is not.",
        )

        irregular = budget["definition"]["irregular_contractions"]
        suffixes = {
            k: v
            for k, v in budget["definition"]["contraction_suffixes"].items()
            if not v.startswith("<")
        }

        def is_filler(word: str) -> bool:
            # A contraction is the auxiliary wearing an apostrophe. Splitting on
            # the apostrophe alone only resolves "can't"; "don't" becomes "don",
            # which is in no word list, so the filler would hide behind
            # punctuation instead of being written out.
            if word in filler:
                return True
            if word in irregular:
                return irregular[word] in filler
            if word.endswith("n't") and word[:-3] in filler:
                return True
            # Positive contractions hide the auxiliary after the apostrophe:
            # "we're" is "we" + "are", and only the stem would be inspected
            # otherwise, so swapping expanded forms for contractions would
            # lower the share without removing any filler.
            for suffix, auxiliary in suffixes.items():
                if word.endswith(suffix) and auxiliary in filler:
                    return True
            return "'" in word and word.split("'")[0] in filler

        def share(text: str) -> tuple[float, int]:
            # Fold the typographic apostrophe first: with U+2019, "don’t"
            # tokenizes as "don" + "t" and the auxiliary disappears from the
            # count, so swapping punctuation alone would buy budget headroom.
            text = text.replace("\u2019", "'")
            words = re.findall(r"[A-Za-z][A-Za-z'-]*", text.lower())
            self.assertTrue(words)
            return sum(is_filler(w) for w in words) / len(words), len(words)

        for bucket in budget["buckets"]:
            paths = sorted(
                path
                for pattern in bucket["paths"]
                for path in ROOT.glob(pattern)
            )
            self.assertTrue(paths, bucket["id"])
            text = "\n".join(p.read_text(encoding="utf-8") for p in paths)
            if "max_bytes_per_role" in bucket:
                # Per file, not averaged: one role is loaded per dispatch, so a
                # mean lets a large role hide behind small ones and bounds
                # nothing about the context cost of the dispatch that loads it.
                worst = max(paths, key=lambda p: p.stat().st_size)
                self.assertLessEqual(
                    worst.stat().st_size,
                    bucket["max_bytes_per_role"],
                    f"{bucket['id']}: {worst.name} is "
                    f"{worst.stat().st_size} bytes, over the "
                    f"{bucket['max_bytes_per_role']} per-role ceiling.",
                )
                mean = sum(p.stat().st_size for p in paths) / len(paths)
                self.assertLessEqual(
                    mean,
                    bucket["max_mean_bytes_per_role"],
                    f"{bucket['id']}: {mean:.0f} mean bytes per role across "
                    f"{len(paths)} roles exceeds "
                    f"{bucket['max_mean_bytes_per_role']}. Adding a role is "
                    "allowed; growing the existing ones is not.",
                )
            observed, words = share(text)
            limit = bucket["max_filler_share"]
            if observed > limit:
                worst = max(
                    (
                        (share(para)[0], path.name, para[:70])
                        for path in paths
                        for para in path.read_text(encoding="utf-8").split("\n")
                        if len(para) >= 300
                    ),
                    default=(0.0, "-", "-"),
                )
                self.fail(
                    f"{bucket['id']}: filler share {observed:.1%} over budget "
                    f"{limit:.1%} across {words} words in {len(paths)} file(s). "
                    f"Densest offender {worst[0]:.1%} in {worst[1]}: {worst[2]!r}. "
                    "Compress phrasing, never content — see "
                    "benchmarks/prompt-compression/budget.json and #40."
                )

    def test_prompt_compression_snapshot_is_evidence_bound(self) -> None:
        gate = ROOT / "benchmarks" / "prompt-compression"
        evidence = json.loads(
            (gate / "results.json").read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        policy = (gate / "gate-snapshot" / "CLAUDE.md").read_bytes()
        agents = (gate / "gate-snapshot" / "agents.json").read_bytes()
        policy_record = evidence["inputs"]["orchestration"]
        self.assertEqual(evidence["candidate_version"], "1.3.4")
        self.assertEqual(len(policy), policy_record["candidate_bytes"])
        self.assertEqual(
            hashlib.sha256(policy).hexdigest(),
            policy_record["candidate_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(policy.rstrip(b"\n")).hexdigest(),
            policy_record["candidate_runtime_sha256"],
        )

        agents_record = evidence["inputs"]["agents"]
        self.assertEqual(
            hashlib.sha256(agents).hexdigest(),
            agents_record["candidate_generated_file_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(agents.rstrip(b"\n")).hexdigest(),
            agents_record["candidate_generated_runtime_sha256"],
        )

        snapshot_agents = json.loads(agents)
        role_records = {record["role"]: record for record in agents_record["roles"]}
        self.assertEqual(set(role_records), set(ROLES))
        self.assertEqual(set(snapshot_agents), set(ROLES))
        self.assertTrue(agents_record["frontmatter_byte_identical_for_all_roles"])
        for role, record in role_records.items():
            agent = snapshot_agents[role]
            tool_field = "tools" if "tools" in agent else "disallowedTools"
            payload = (
                "---\n"
                f"name: {role}\n"
                f"description: {agent['description']}\n"
                f"model: {agent['model']}\n"
                f"effort: {agent['effort']}\n"
                f"{tool_field}: {', '.join(agent[tool_field])}\n"
                "---\n\n"
                f"{agent['prompt']}\n"
            ).encode()
            self.assertEqual(len(payload), record["candidate_bytes"])
            self.assertEqual(
                hashlib.sha256(payload).hexdigest(),
                record["candidate_sha256"],
            )
            self.assertNotIn(
                b"Task text has no compressible markdown prose worth touching",
                payload,
            )

        combined = evidence["inputs"]["combined"]
        self.assertEqual(
            policy_record["candidate_bytes"] + agents_record["candidate_bytes"],
            combined["candidate_bytes"],
        )
        self.assertEqual(
            combined["original_bytes"] - combined["candidate_bytes"],
            combined["reduction_bytes"],
        )

        behavior = evidence["behavioral_gates"]
        small_lifecycle = behavior["small_lifecycle"]
        self.assertEqual(small_lifecycle["status"], "passed")
        self.assertEqual(
            small_lifecycle["turn_1_plan"]["agent_calls"][0]["verdict"],
            "READY",
        )
        self.assertEqual(
            small_lifecycle["turn_2_approved_execution"]["agent_calls"][1][
                "verdict"
            ],
            "CONFIRMED",
        )
        self.assertFalse(
            small_lifecycle["turn_2_approved_execution"]["main_source_writes"]
        )
        for prompt_name, record in (
            ("small-lifecycle-plan.txt", small_lifecycle["turn_1_plan"]),
            (
                "small-lifecycle-approve.txt",
                small_lifecycle["turn_2_approved_execution"],
            ),
        ):
            prompt = (gate / "prompts" / prompt_name).read_bytes()
            self.assertEqual(
                hashlib.sha256(prompt).hexdigest(),
                record["prompt_file_sha256"],
            )
            self.assertEqual(
                hashlib.sha256(prompt.rstrip(b"\n")).hexdigest(),
                record["prompt_runtime_sha256"],
            )

        observed_cost = sum(
            (
                evidence["context_census"]["baseline"]["client_reported_cost_usd"],
                evidence["context_census"]["candidate"]["client_reported_cost_usd"],
                behavior["spontaneous_mechanical_candidate"][
                    "client_reported_cost_usd"
                ],
                behavior["spontaneous_mechanical_v1_3_3_control"][
                    "client_reported_cost_usd"
                ],
                behavior["spontaneous_bug_candidate"]["client_reported_cost_usd"],
                behavior["explicit_lifecycle_turn_1"][
                    "client_reported_cost_usd"
                ],
                behavior["explicit_lifecycle_user_continuation"][
                    "client_reported_cost_usd"
                ],
                small_lifecycle["turn_1_plan"]["client_reported_cost_usd"],
                small_lifecycle["turn_2_approved_execution"][
                    "client_reported_cost_usd"
                ],
            ),
            Decimal("0"),
        )
        self.assertEqual(
            observed_cost,
            evidence["paid_campaign"]["client_reported_cost_usd_so_far"],
        )

    def test_installer_requires_tool_enforcing_runtime(self) -> None:
        installer = (ROOT / "install/AGENT-INSTALL.md").read_text(encoding="utf-8")
        self.assertIn("claude --version", installer)
        self.assertIn("Claude Code 2.1.219 or newer", installer)
        self.assertIn("does not guarantee one exact backend", installer)
        self.assertIn("stop before presenting a write plan or changing anything", installer)
        self.assertIn("depend on enforced tool exclusion", installer)

        for readme in ("README.md", "README.zh-TW.md"):
            content = (ROOT / readme).read_text(encoding="utf-8")
            self.assertIn("2.1.219", content)
            self.assertIn("remove the eight pilotfish agent files", content)
            self.assertIn("`mech-executor`", content)
            self.assertIn("`verifier`", content)

    def test_legacy_installer_backup_is_verified_and_fail_closed(self) -> None:
        installer_path = ROOT / "install/AGENT-INSTALL.md"
        blocks = re.findall(
            r"```bash\n(?P<body>.*?)\n```",
            installer_path.read_text(encoding="utf-8"),
            re.DOTALL,
        )
        matches = [block for block in blocks if "SETTINGS_BACKUP_EXISTS=0" in block]
        self.assertEqual(len(matches), 1)
        script = matches[0]
        self.assertNotIn("|| true", script)
        self.assertNotIn("2>/dev/null", script)

        first_stamp = "20260823-020304"
        second_stamp = "20260823-020305"
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)

            def execute(
                name: str,
                *,
                stamp: str = first_stamp,
                sources: bool = True,
                settings: bool = True,
                fail_utility: str | None = None,
                collision: bool = False,
                invalid_retained: str | None = None,
                temp_collision: bool = False,
            ) -> tuple[subprocess.CompletedProcess[bytes], Path, Path, dict[str, bytes], Path]:
                root = base / name
                config = root / "config"
                config.mkdir(parents=True, exist_ok=True)
                original = {}
                if sources:
                    original = {"CLAUDE.md": b"user policy\n"}
                    if settings:
                        original["settings.json"] = b'{"model":"custom"}\n'
                    for relative, content in original.items():
                        (config / relative).write_bytes(content)

                collision_path = config / "backups" / f"CLAUDE.md.pilotfish-{stamp}"
                if collision:
                    collision_path.parent.mkdir(parents=True)
                    collision_path.write_bytes(b"existing\n")

                if invalid_retained is not None:
                    backups = config / "backups"
                    backups.mkdir(parents=True, exist_ok=True)
                    (backups / "settings.json.pilotfish-00000000-000000").write_bytes(
                        b"valid retained backup\n"
                    )
                    invalid = backups / "settings.json.pilotfish-99999999-999999"
                    if invalid_retained == "directory":
                        invalid.mkdir()
                    elif invalid_retained == "dangling-symlink":
                        invalid.symlink_to("missing-retained-backup")
                    else:
                        raise ValueError(invalid_retained)

                if temp_collision:
                    temp = config / "backups" / f".pilotfish-settings-{stamp}.tmp"
                    temp.parent.mkdir(parents=True, exist_ok=True)
                    temp.symlink_to("missing-temporary-backup")

                fake_bin = root / "fake-bin"
                fake_bin.mkdir(exist_ok=True)
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
                return completed, config, sentinel, original, fake_date

            complete, config, sentinel, original, fake_date = execute("complete")
            self.assertEqual(complete.returncode, 0, complete.stderr)
            for relative, content in original.items():
                self.assertEqual((config / relative).read_bytes(), content)
                backup = config / "backups" / f"{relative}.pilotfish-{first_stamp}"
                self.assertEqual(backup.read_bytes(), content)
            self.assertTrue((config / "agents").is_dir())
            self.assertEqual(list((config / "backups").glob(".pilotfish-*.tmp")), [])
            self.assertTrue(sentinel.exists())

            fake_date.write_text(
                "#!/bin/sh\n"
                f"printf '%s\\n' '{second_stamp}'\n",
                encoding="utf-8",
            )
            sentinel.unlink()
            rerun = subprocess.run(
                [
                    "/bin/sh",
                    "-c",
                    script
                    + "\nprintf '%s\\n' mutated > \"$PILOTFISH_MUTATION_SENTINEL\"\n",
                ],
                cwd=config.parent,
                env={
                    "CLAUDE_CONFIG_DIR": str(config),
                    "HOME": str(config.parent / "home"),
                    "PATH": f"{fake_date.parent}:/usr/bin:/bin",
                    "PILOTFISH_MUTATION_SENTINEL": str(sentinel),
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(rerun.returncode, 0, rerun.stderr)
            self.assertEqual(
                len(list((config / "backups").glob("settings.json.pilotfish-*"))),
                1,
            )
            self.assertEqual(
                len(list((config / "backups").glob("CLAUDE.md.pilotfish-*"))),
                2,
            )
            self.assertEqual(
                (
                    config
                    / "backups"
                    / f"settings.json.pilotfish-{first_stamp}"
                ).read_bytes(),
                original["settings.json"],
            )
            self.assertEqual(list((config / "backups").glob(".pilotfish-*.tmp")), [])

            missing, config, sentinel, _, _ = execute("missing", sources=False)
            self.assertEqual(missing.returncode, 0, missing.stderr)
            self.assertTrue((config / "agents").is_dir())
            self.assertTrue(sentinel.exists())

            for utility, source, settings in (
                ("cp", "settings.json", True),
                ("cmp", "settings.json", True),
                ("cp", "CLAUDE.md", False),
                ("cmp", "CLAUDE.md", False),
            ):
                with self.subTest(failure=utility, source=source):
                    failed, config, sentinel, original, _ = execute(
                        f"fail-{utility}-{source}",
                        settings=settings,
                        fail_utility=utility,
                    )
                    self.assertNotEqual(failed.returncode, 0)
                    self.assertFalse(sentinel.exists())
                    self.assertFalse((config / "agents").exists())
                    backups = config / "backups"
                    self.assertEqual(
                        list(backups.glob("settings.json.pilotfish-*")), []
                    )
                    self.assertEqual(
                        list(backups.glob("CLAUDE.md.pilotfish-*")), []
                    )
                    self.assertEqual(list(backups.glob(".pilotfish-*.tmp")), [])
                    for relative, content in original.items():
                        self.assertEqual((config / relative).read_bytes(), content)

            for retained_kind in ("directory", "dangling-symlink"):
                with self.subTest(invalid_retained=retained_kind):
                    failed, config, sentinel, original, _ = execute(
                        f"invalid-retained-{retained_kind}",
                        invalid_retained=retained_kind,
                    )
                    self.assertNotEqual(failed.returncode, 0)
                    self.assertIn(
                        b"retained settings backup must be a readable regular file",
                        failed.stderr,
                    )
                    self.assertFalse(sentinel.exists())
                    self.assertFalse((config / "agents").exists())
                    self.assertEqual(
                        (
                            config
                            / "backups"
                            / "settings.json.pilotfish-00000000-000000"
                        ).read_bytes(),
                        b"valid retained backup\n",
                    )
                    for relative, content in original.items():
                        self.assertEqual((config / relative).read_bytes(), content)

            collided, config, sentinel, original, _ = execute(
                "temp-collision", temp_collision=True
            )
            self.assertNotEqual(collided.returncode, 0)
            self.assertIn(b"backup temporary path already exists", collided.stderr)
            self.assertFalse(sentinel.exists())
            self.assertFalse((config / "agents").exists())
            self.assertEqual(
                list((config / "backups").glob("settings.json.pilotfish-*")), []
            )
            for relative, content in original.items():
                self.assertEqual((config / relative).read_bytes(), content)

            collided, config, sentinel, original, _ = execute(
                "collision", collision=True
            )
            self.assertNotEqual(collided.returncode, 0)
            self.assertIn(b"backup destination already exists", collided.stderr)
            self.assertFalse(sentinel.exists())
            self.assertFalse((config / "agents").exists())
            collision_path = (
                config / "backups" / f"CLAUDE.md.pilotfish-{first_stamp}"
            )
            self.assertEqual(collision_path.read_bytes(), b"existing\n")
            for relative, content in original.items():
                self.assertEqual((config / relative).read_bytes(), content)

    def test_fresh_install_defaults_to_opus_with_sonnet_fallback(self) -> None:
        settings = json.loads(
            (ROOT / "templates/settings.snippet.json").read_text(encoding="utf-8")
        )
        self.assertEqual(settings["model"], "opus")
        self.assertEqual(settings["fallbackModel"], ["sonnet"])

        installer = (ROOT / "install/AGENT-INSTALL.md").read_text(encoding="utf-8")
        self.assertIn('If absent → set `"opus"`', installer)
        self.assertIn('If absent → add `["sonnet"]`', installer)
        self.assertIn("Never replace an existing", installer)
        self.assertIn("Claude Code 2.1.219", installer)
        self.assertIn("provider, account, and settings", installer)
        self.assertIn(
            'ensure it contains `"opus"`, `"fable"`, `"sonnet"`, `"haiku"`',
            installer,
        )

    def test_mechanical_replay_fetches_pinned_snapshot(self) -> None:
        pinned = "863b117b9da42179c5bb77a05158920fbc092ee2"
        for readme in (
            "benchmarks/dispatch-brake/positive-controls/README.md",
            "benchmarks/dispatch-brake/positive-controls/README.zh-TW.md",
        ):
            content = (ROOT / readme).read_text(encoding="utf-8")
            fetch = f'fetch --depth 1 origin "$PINNED"'
            worktree = 'worktree add --detach "$SNAPSHOT" "$PINNED"'
            self.assertNotIn(f"PINNED={pinned}", content)
            self.assertNotIn(fetch, content)
            self.assertNotIn(worktree, content)
            self.assertIn('pilotfish-dispatch-static.XXXXXX', content)
            self.assertIn('SENTINEL=', content)
            self.assertIn('npm --prefix "$ROOT/fixture" test', content)

    def test_reproduction_sections_are_bilingual_safe_and_claim_bounded(self) -> None:
        documents = (
            ROOT / "benchmarks/baton-dispatch-effect/README.md",
            ROOT / "benchmarks/baton-dispatch-effect/README.zh-TW.md",
            ROOT / "benchmarks/dispatch-brake/README.md",
            ROOT / "benchmarks/dispatch-brake/README.zh-TW.md",
            ROOT / "benchmarks/dispatch-brake/positive-controls/README.md",
            ROOT / "benchmarks/dispatch-brake/positive-controls/README.zh-TW.md",
        )
        sections = {}
        for path in documents:
            text = path.read_text(encoding="utf-8")
            heading = "## Reproduction" if path.name == "README.md" else "## 重現"
            self.assertEqual(text.count(heading), 1, path)
            slug = heading[3:].lower().replace(" ", "-")
            self.assertIn(f"](#{slug})", text)
            body = text.split(heading, 1)[1].split("\n## ", 1)[0]
            sections[path] = body
            for forbidden in (
                r"claude\s+-p",
                r"remora\s+-p",
                r"dangerously-skip-permissions",
                r"git\s+fetch[^\n]*[0-9a-f]{40}",
                r"rm\s+-rf",
                r"\beval\b|sh\s+-c",
                r"(?:print|export)[^\n]*(?:token|secret)|token dump",
            ):
                code = "\n".join(re.findall(r"```(?:bash|sh)?\n(.*?)```", body, re.S))
                self.assertIsNone(re.search(forbidden, code, re.I), (path, forbidden))

        baton_en = sections[documents[0]]
        baton_zh = sections[documents[1]]
        for value in (
            "https://github.com/Nanako0129/pilotfish.git",
            "refs/heads/benchmark/v1.3.1-baton-large-fixture",
            "34ebabe2a26dd53de1a019607992f1ac10af245f",
            "3773149bae5c514abe6d141d6fc5216e86d02574",
            "45",
            "3,032",
            "mktemp -d",
            "0600",
            "normalized",
        ):
            for body in (baton_en, baton_zh):
                self.assertIn(value, body)
        for value in ("Static", "historical", "non-turnkey"):
            self.assertIn(value, baton_en)
        for value in ("靜態", "歷史", "非 turnkey"):
            self.assertIn(value, baton_zh)
        self.assertIn("does not replay", baton_en)
        self.assertIn("不會重播", baton_zh)
        for body in (baton_en, baton_zh):
            self.assertIn("EXPECTED_COMMIT", body)
            self.assertIn("EXPECTED_TREE", body)
            self.assertIn("set -eu", body)
            self.assertIn("ls-remote", body)
            self.assertIn("FETCH_HEAD", body)
            self.assertIn("git -C", body)
            self.assertIn("hashlib", body)
            self.assertNotIn("sha256sum", body)
            self.assertNotIn("worktree add", body)
            self.assertIn("e901e16abdca03ea5f55e3d86f8726fcfa984488305e304c7a382426cd6b7c61", body)
            self.assertIn("0b42c137…9723c", body)

        for body in (sections[documents[2]], sections[documents[3]]):
            self.assertIn("positive-controls", body)
            self.assertRegex(body.lower(), r"(?:full lifecycle|完整 lifecycle)")
            self.assertRegex(body.lower(), r"(?:separate spend|另行批准的 spend)")
            self.assertIn("normalized", body.lower())
        for body in (sections[documents[4]], sections[documents[5]]):
            self.assertIn("863b117", body)
            self.assertIn("mktemp -d", body)
            self.assertIn("sentinel", body)
            self.assertIn("SENTINEL=", body)
            self.assertIn("npm", body)
            self.assertIn("set -eu", body)
            self.assertIn("set +e", body)
            self.assertIn('NPM_STATUS=$?', body)
            self.assertIn('test "$NPM_STATUS" -eq 1', body)
            self.assertIn("grep -Fx '# pass 0'", body)
            self.assertIn("grep -Fx '# fail 12'", body)
            self.assertIn("-print0 | xargs -0 -n 1 node --check", body)
            self.assertNotIn("-exec node --check {} +", body)
            self.assertNotIn("|| test", body)
            self.assertRegex(body.lower(), r"(?:non-turnkey|非 turnkey)")
        self.assertIn("沒有已證明可遠端取得", sections[documents[5]])

    def test_every_named_role_owns_its_model(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Omit invocation `model`", policy)
        self.assertIn("override would replace role routing", policy)
        self.assertIn("truly ad-hoc agent", policy)

        for role in ROLES:
            agent = (ROOT / "templates" / "agents" / f"{role}.md").read_text(
                encoding="utf-8"
            )
            frontmatter = agent.split("---", 2)[1]
            self.assertRegex(frontmatter, rf"(?m)^name:\s*{re.escape(role)}\s*$")
            self.assertRegex(frontmatter, r"(?m)^model:\s*\S+\s*$")
            self.assertIn(f"`{role}`", policy)

    def test_default_implementation_tier_stays_below_opus_main_loop(self) -> None:
        # Regression for #18: the main session defaults to Opus. The default
        # delegated implementation role must stay below that tier. Review and
        # security roles deliberately remain on Opus for their separate
        # capability and trust-boundary requirements.
        expected_models = {
            "scout": "haiku",
            "Explore": "haiku",
            "plan-verifier": "opus",
            "security-reviewer": "opus",
            "mech-executor": "sonnet",
            "executor": "sonnet",
            "verifier": "opus",
            "security-executor": "opus",
        }
        for role, expected_model in expected_models.items():
            frontmatter = (
                (ROOT / "templates" / "agents" / f"{role}.md")
                .read_text(encoding="utf-8")
                .split("---", 2)[1]
            )
            self.assertRegex(
                frontmatter,
                rf"(?m)^model:\s*{re.escape(expected_model)}\s*$",
                f"{role} should default to {expected_model}",
            )
        # executor now shares mech-executor's Sonnet tier: it is the default
        # delegated implementation path, and must not sit at the same tier as
        # the Opus main loop. verifier deliberately retains its separate
        # Opus binding for the acceptance-boundary role.
        self.assertEqual(expected_models["executor"], expected_models["mech-executor"])
        self.assertNotEqual(expected_models["executor"], expected_models["verifier"])

    def test_policy_uses_phase_specific_dispatch_brakes(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("phase-aware lifecycle", policy)
        self.assertIn("Discovery needs stable research contract", policy)
        self.assertIn("never pre-decided outcome", policy)
        self.assertIn("No source edit or implementation brief before required approval", policy)
        self.assertIn("Broad initial request is not approval", policy)
        self.assertIn("main synthesizes one Plan", policy)
        self.assertIn("Block fan-out when evidence evolves", policy)

    def test_policy_selects_interaction_shape_before_routing(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        routing = next(
            line
            for line in policy.splitlines()
            if line.startswith("- Interaction shape precedes Baton")
        )
        for mapping in (
            "`co_discover` when outcome/acceptance is unclear",
            "`explore_then_plan` when otherwise-clear direction is broad/high-impact",
            "`execute` for an otherwise-clear bounded outcome",
        ):
            self.assertIn(mapping, routing)
        self.assertLess(routing.index("`co_discover`"), routing.index("`explore_then_plan`"))
        self.assertLess(routing.index("`explore_then_plan`"), routing.index("`execute`"))
        self.assertIn(
            "`co_discover` asks only direction-changing questions or uses the smallest reversible probe",
            routing,
        )
        self.assertLess(
            policy.index("Interaction shape precedes Baton"),
            policy.index("After shape selection, inspect available skills"),
        )
        self.assertIn("Choose first match", policy)
        boundary = next(
            line
            for line in policy.splitlines()
            if line.startswith("  **`explore_then_plan` boundary:**")
        )
        for contract in (
            "first turn is `discovery_read_only`",
            "despite imperative implementation wording",
            "Write/Edit/NotebookEdit and mutating Bash are forbidden",
            "one reversible slice",
            "label `next_gate: user_approval` only after every applicable readiness gate is `READY`",
            "otherwise label the blocking or paused gate",
            "then end the turn",
            "Execution is unreachable until later explicit approval",
        ):
            self.assertIn(contract, boundary)
        self.assertIn("Routing controls interaction; approval controls authority", policy)
        self.assertIn("Stop discovery when more evidence cannot change next gate", policy)

    def test_policy_brakes_tightly_coupled_execution(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("root-cause discovery", policy)
        self.assertIn("trace-driven debugging", policy)
        self.assertIn("coupled state propagation", policy)
        self.assertIn("Single unknown bug", policy)
        self.assertIn("sequential `scout`→`executor` pipeline", policy)
        self.assertIn("neither owns nor blocks diagnosis", policy)
        self.assertIn("without rediscovery", policy)
        self.assertIn("non-positive net benefit", policy)

    def test_policy_uses_rebuttable_mechanical_default(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Stable same-shape multi-file mechanical repetition", policy)
        self.assertIn("complete one-shot brief", policy)
        self.assertIn("exclusive ownership", policy)
        self.assertIn("per-item acceptance", policy)
        self.assertIn("defaults to one `mech-executor`", policy)
        self.assertIn("Foreground unless possible long command requires background", policy)
        self.assertIn("Collect mechanical result before main edits", policy)
        self.assertIn("worker files remain worker-only until completion", policy)
        self.assertIn("never redo worker changes", policy)
        self.assertIn("requires prior concrete blocker", policy)
        for blocker in (
            "evolving/coupled evidence",
            "ownership/integration conflict",
            "worker unavailable",
            "non-positive net benefit",
        ):
            self.assertIn(blocker, policy)
        self.assertIn(
            "Main retains per-item triage, exceptions, integration, acceptance",
            policy,
        )
        self.assertLess(
            policy.index("defaults to one `mech-executor`"),
            policy.index("requires prior concrete blocker"),
        )
        self.assertNotIn("eligible rather than mandatory", policy)
        self.assertNotIn("direct execution being slightly faster is not a veto", policy)

    def test_policy_preserves_single_bug_and_task_local_read_guards(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Single unknown bug", policy)
        self.assertIn("root-cause discovery", policy)
        self.assertIn("first minimal fix", policy)
        self.assertIn("Bounded task-local search stays main-session work by default", policy)
        self.assertIn("neither owns nor blocks diagnosis", policy)

    def test_policy_prevents_duplicate_recon_after_dispatch(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Active agent scope is temporarily exclusive", policy)
        self.assertIn("main must not read/analyze same scope", policy)
        self.assertIn("cancellation, or redirection", policy)
        self.assertIn("declare main-owned versus agent-owned read scopes", policy)
        self.assertIn("later Read/Glob/Grep/Bash must reject mixed commands", policy)
        self.assertIn("touching any active-agent path", policy)
        self.assertIn("Collect all discovery results before cross-surface comparison", policy)
        self.assertIn("Post-result sanity checks", policy)
        self.assertIn("launch all back-to-back", policy)
        self.assertIn("before remaining main work", policy)
        self.assertIn("allow no interleaved duplicate reconnaissance", policy)
        self.assertIn("requires Git", policy)
        self.assertIn("without Git, never fan out", policy)
        self.assertIn("use one shared-checkout writer or work direct", policy)

    def test_policy_preserves_positive_delegation_paths(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("delegate only when", policy)
        self.assertIn("outweigh reconstruction", policy)
        self.assertIn("lower cost/quota", policy)
        self.assertIn("preserved context", policy)
        self.assertIn("bounded read-only `scout`/`Explore`", policy)
        self.assertIn("stays main-session work by default", policy)
        self.assertIn("genuinely independent substantial surfaces", policy)
        self.assertIn("overlapping latency", policy)
        self.assertIn("independently gathered evidence/perspectives", policy)
        self.assertIn("Stable same-shape multi-file mechanical repetition", policy)

    def test_policy_uses_backend_neutral_recurrence_conditions(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "one-shot brief",
            "independent and same shape",
            "done criteria",
            "exclusive ownership",
            "per-item acceptance",
            "defaults to one `mech-executor`",
            "main session",
            "diagnosis",
            "integration",
            "known remedy",
            "Execution work",
        ):
            self.assertIn(phrase, policy)

        for phrase in (
            "about three times",
            "feature or PR closure",
            "two REVISE rounds per Plan",
            "plan documents",
        ):
            self.assertNotIn(phrase, policy)

    def test_policy_verifies_at_coherent_boundary(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "smallest coherent integration boundary",
            "explicit user request for independent review",
            "Any independent-review trigger makes that unit risky",
            "pre-approval `plan-verifier` and post-implementation `verifier` are mandatory Agent calls",
            "with no extra opt-in",
            "pause before edits, never direct fallback or waiver",
            "unblock only by lifting the prohibition or narrowing away every trigger",
            "Bounded fail-soft exception applies only without listed risk",
            "After readiness, present Plan and end turn",
            "implementation begins only after explicit approval in a later turn",
            "Plan readiness judges proposed acceptance check",
            "Run primary user-visible acceptance first",
            "avoid micro-verifier calls",
            "Tests/builds/static checks are intermediate evidence",
            "security",
            "cross-language/FFI",
            "serialization/pre-aggregation",
            "irreversible",
            "integration-blocking boundaries",
        ):
            self.assertIn(phrase, policy)
        self.assertNotIn("tests are sufficient evidence", policy)
        self.assertNotIn("tests are sufficient", policy)
        self.assertIn(
            "never change a `CONFIRMED` candidate for them", policy
        )
        self.assertIn(
            "Any required post-verdict change invalidates final-byte coverage",
            policy,
        )

    def test_plan_review_requires_future_slice_identity_not_optional_detail(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        prompt = (ROOT / "templates/agents/plan-verifier.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("stable ID, outcome, scope, non-goals, owners, prerequisites", policy)
        self.assertIn("unrelated downstream slices do not block", policy)
        self.assertIn("optional downstream implementation detail", prompt)
        self.assertIn(
            "Missing required future-slice metadata (stable ID, outcome, or prerequisites) remains blocking",
            prompt,
        )

    def test_policy_adjudicates_findings_and_bounds_long_runs(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "Role verdicts are evidence, never implementation/scope authority",
            "before `FIX`/`DEFER`/`REJECT`",
            "Documented deferral or evidence-backed rejection addresses a finding",
            "path overlap alone is irrelevant",
            "stated missing evidence, contract, prerequisite, or environment",
            "otherwise pause affected slice",
            "explicit acceptance, approved scope, bounded change",
            "AUTO/ASK mode selection applies only to likely-long autonomous work",
            "offer `AUTO` or `ASK` and wait",
            "explicit “continue while I am away” selects AUTO and must be announced",
            "emergency recovery, not quota",
            "Headless likely-long run without selected mode",
            "otherwise end with `PAUSED_NEEDS_USER`",
            "Default recovery: one targeted recheck",
            "High-risk claim-critical P1/P2 recovery allows at most five meaningful",
            "never adjacent-hardening audit",
            "stop earlier when next pass only searches adjacent risk",
            "batch-dispositions every current-head finding",
            "external evidence/prerequisites",
            "a verdict/output alone is not change",
            "tracked/staged diff",
            "untracked input paths/content",
            "input submodule HEAD plus recursive working-tree content",
            "only as sole deliverable",
            "Never reverify identical state",
            "After five still-blocking passes",
            "continue unrelated approved slices",
            "Questions belong to main session, never child",
            "unattainable original scope",
        ):
            self.assertIn(phrase, policy)

    def test_verifier_uses_calibrated_three_way_verdicts(self) -> None:
        verifier = (ROOT / "templates/agents/verifier.md").read_text(
            encoding="utf-8"
        )
        self.assertTrue(
            all(f"**{verdict}**" in verifier for verdict in (
                "CONFIRMED",
                "REFUTED",
                "INCONCLUSIVE",
            ))
        )
        self.assertIn(
            "at least one reproducible P0-P2 finding blocks the exact claim",
            verifier,
        )
        self.assertIn(
            "regressions caused by the reviewed implementation are claim-relevant",
            verifier,
        )
        self.assertIn(
            "For every finding or advisory under any verdict",
            verifier,
        )
        self.assertIn(
            "any reproducible high-impact user/system failure",
            verifier,
        )
        self.assertIn(
            "sufficient for every required acceptance condition",
            verifier,
        )
        self.assertIn(
            "List each condition checked and its evidence/result",
            verifier,
        )
        self.assertIn(
            "REFUTED takes precedence when a reproducible P0-P2 blocker coexists",
            verifier,
        )
        self.assertIn(
            "even when the primary flow is blocked or unavailable",
            verifier,
        )
        self.assertIn(
            "without suppressing an independently reproducible blocker",
            verifier,
        )
        self.assertNotIn("Only after it is evidenced", verifier)
        self.assertIn(
            "any unevaluated required acceptance condition makes the verdict INCONCLUSIVE",
            verifier,
        )
        self.assertIn(
            "P3/P4 are non-blocking advisories and cannot by themselves produce REFUTED",
            verifier,
        )
        self.assertIn(
            "Confidence high/medium/low, Evidence, Expected, Actual, and Recheck",
            verifier,
        )
        self.assertIn("reason, missing evidence, and retry condition", verifier)
        self.assertTrue(all(phrase in verifier for phrase in (
            "real user/system impact, not claim centrality",
            "P0 =",
            "P1 = any reproducible high-impact user/system failure that does not meet P0",
            "P2 = material bounded/recoverable issue",
            "P3 =",
            "P4 =",
            "failed acceptance condition is P2 when bounded/recoverable",
        )))
        lowered = verifier.lower()
        self.assertIsNone(re.search(
            r"assume it is broken|do not trust|don't trust|try to refute it|"
            r"maximi[sz]e findings|as many findings as possible",
            lowered,
        ))

    def test_policy_requires_plan_convergence_or_escalation(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "program envelope",
            "next executable slice",
            "scope, non-goals",
            "acceptance proving outcome",
            "Two automatic `REVISE` verdicts",
            "main dispositions every blocker as `FIX`, `DEFER`, or `REJECT`",
            "Ask user only for unresolved P0/P1",
            "not merely permission for another review round",
            "new readiness epoch",
            "evidence-backed disposition changing readiness claim",
            "exactly one closing fresh review",
            "closing review cannot restart loop",
            "Another `REVISE` pauses or escalates",
            "substantially unchanged Plan",
            "simplifies",
            "narrow",
            "split",
        ):
            self.assertIn(phrase, policy)
        plan_verifier = (
            ROOT / "templates/agents/plan-verifier.md"
        ).read_text(encoding="utf-8")
        for phrase in ("Blocker:", "Evidence:", "Minimum revision:", "Acceptance check:"):
            self.assertIn(phrase, plan_verifier)
        self.assertNotIn("main session decides the residual disagreements", policy)

    def test_planning_skills_compose_with_role_routing(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "After shape selection, inspect available skills",
            policy,
        )
        self.assertIn("before dispatch brake", policy)
        self.assertIn("direct-vs-delegated choice", policy)
        self.assertIn("listed `baton-dispatch` → invoke", policy)
        self.assertIn("never pre-screen it away", policy)
        self.assertIn("Baton may still choose direct work", policy)
        self.assertIn("may shape questions, topology, worker count, ownership, stops", policy)
        self.assertIn("If absent, apply this policy without searching/installing", policy)
        self.assertIn("pilotfish and Baton compose", policy)
        self.assertIn("neither bypasses the other's", policy)
        self.assertIn(
            "named-role, model-routing, leaf, approval, or verification boundaries",
            policy,
        )
        self.assertIn("final judgment", policy)
        self.assertLess(
            policy.index("After shape selection, inspect available skills"),
            policy.index("small/local/stable work"),
        )

    def test_plan_and_outcome_verification_have_separate_capabilities(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        plan_verifier = (
            ROOT / "templates/agents/plan-verifier.md"
        ).read_text(encoding="utf-8")
        verifier = (ROOT / "templates/agents/verifier.md").read_text(encoding="utf-8")
        self.assertIn("`plan-verifier` reviews one stable envelope/slice", policy)
        self.assertIn("Outcome `verifier` receives exact claim/acceptance", policy)
        self.assertIn("Never swap roles", policy)
        self.assertIn("tools: Read, Glob, Grep", plan_verifier)
        self.assertIn("excludes Bash, Write, Edit", plan_verifier)
        self.assertIn("READY", plan_verifier)
        self.assertIn("REVISE", plan_verifier)
        self.assertIn("explicit outcome, scope and non-goals", plan_verifier)
        self.assertIn("acceptance proving slice outcome", plan_verifier)
        self.assertIn("slice-local budget", plan_verifier)
        self.assertIn("explicit stop conditions", plan_verifier)
        self.assertIn("every currently known blocker in the same pass", plan_verifier)
        self.assertIn("Do not use `REVISE` for P3/P4 advice", plan_verifier)
        self.assertIn("P2 = material bounded or recoverable", plan_verifier)
        self.assertNotIn("CONFIRMED", plan_verifier)
        self.assertNotIn("INCONCLUSIVE", plan_verifier)
        self.assertIn("CONFIRMED", verifier)
        self.assertIn("REFUTED", verifier)
        self.assertIn("INCONCLUSIVE", verifier)
        self.assertIn("Attempt the primary acceptance flow first", verifier)
        self.assertIn("do not reopen adjacent hardening", verifier)
        self.assertNotIn("READY", verifier)
        self.assertNotIn("REVISE", verifier)
        self.assertIn("Never plan, edit, or fix anything", verifier)

    def test_baton_harness_builds_exact_agent_definitions(self) -> None:
        builder = ROOT / "benchmarks" / "baton-compatibility" / "build-agents-json.py"
        completed = subprocess.run(
            [sys.executable, str(builder), str(ROOT / "templates" / "agents")],
            check=True,
            capture_output=True,
            text=True,
        )
        agents = json.loads(completed.stdout)
        self.assertEqual(set(agents), set(ROLES))

        for role in ROLES:
            template = (ROOT / "templates" / "agents" / f"{role}.md").read_text(
                encoding="utf-8"
            )
            _, frontmatter, prompt = template.split("---", 2)
            fields = dict(
                line.split(":", 1) for line in frontmatter.strip().splitlines()
            )
            self.assertEqual(agents[role]["model"], fields["model"].strip())
            self.assertEqual(agents[role]["effort"], fields["effort"].strip())
            self.assertEqual(agents[role]["prompt"], prompt.strip())

    def test_subagents_never_detach_long_running_processes(self) -> None:
        for role in ("executor", "mech-executor", "verifier", "security-executor"):
            agent = (ROOT / "templates" / "agents" / f"{role}.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("Long work: foreground", agent)
            self.assertIn("Never detach", agent)
            self.assertIn("absolute working directory", agent)
            self.assertIn("required env vars/input paths", agent)
            self.assertIn("orchestrator runs it exact context", agent)
            self.assertNotIn("launch it detached", agent)

        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Long-running processes belong to main session", policy)
        self.assertIn("Agent with possible long command runs `run_in_background: true`", policy)
        self.assertIn("Bash-capable leaf roles never detach", policy)
        self.assertIn("absolute working/worktree directory", policy)
        self.assertIn("in that context", policy)
        self.assertIn("Bash(run_in_background: true)", policy)

    def test_result_collection_and_agent_continuation_are_distinct(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("read completed output directly", policy)
        self.assertIn(
            "resume only for genuinely new/redirected work", policy
        )
        self.assertIn("never collection/restatement", policy)
        self.assertNotIn("resuming one merely makes it re-run", policy)

        for role in ("scout", "Explore"):
            agent = (ROOT / "templates" / "agents" / f"{role}.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("Final message per run", agent)
            self.assertIn("genuinely new follow-up work", agent)
            self.assertIn("another self-contained final message", agent)
            self.assertNotIn("answer a follow-up", agent)

    def test_security_role_preserves_the_approval_boundary(self) -> None:
        policy = (ROOT / "templates/claude-md.orchestration.md").read_text(
            encoding="utf-8"
        )
        reviewer = (ROOT / "templates/agents/security-reviewer.md").read_text(
            encoding="utf-8"
        )
        executor = (ROOT / "templates/agents/security-executor.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Before required approval", policy)
        self.assertIn("tool-enforced read-only `security-reviewer`", policy)
        self.assertIn("send pre-approval work to write-capable security executor", policy)
        self.assertIn("tools: Read, Glob, Grep, WebSearch, WebFetch", reviewer)
        self.assertIn("excludes Bash, Write, Edit", reviewer)
        self.assertIn("approved, stable execution contract", executor)
        self.assertIn("pre-approval analysis belongs to `security-reviewer`", executor)

    def test_bilingual_docs_and_field_report_claim_boundaries(self) -> None:
        report = ROOT / "docs/field-report-tokscale-2026-07.zh-TW.md"
        self.assertTrue(report.is_file())
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("./docs/field-report-tokscale-2026-07.zh-TW.md", changelog)

        report_text = report.read_text(encoding="utf-8")
        self.assertIn("remora", report_text)
        self.assertIn("GPT-5.6", report_text)
        self.assertIn("backend-neutral", report_text)
        self.assertIn("native-Claude efficiency A/B", report_text)
        self.assertNotIn("native Claude 的最佳", report_text)

        english = (ROOT / "benchmarks/baton-compatibility/README.md").read_text(
            encoding="utf-8"
        )
        chinese = (
            ROOT / "benchmarks/baton-compatibility/README.zh-TW.md"
        ).read_text(encoding="utf-8")
        rejected_hash = (
            "64376ea52a4e67192df29d8595c180dd"
            "c5017638029759a8ac13aff87d5cca81"
        )
        for content in (english, chinese):
            self.assertIn("results.json", content)
            self.assertEqual(content.count("--max-budget-usd 6"), 2)
            self.assertNotIn("--max-budget-usd 3", content)
            self.assertIn(rejected_hash, content)
        self.assertIn("compatibility/provenance", english)
        self.assertIn("remora", english)
        self.assertIn("GPT-5.6", english)
        self.assertIn("CONFIRMED", english)
        self.assertIn("compatibility／provenance", chinese)
        self.assertIn("remora／GPT-5.6", chinese)
        self.assertIn("CONFIRMED", chinese)
        self.assertNotIn("prove native-Claude efficiency", english)
        self.assertNotIn("原生 Claude 效率提升", chinese)

        snapshot = (
            ROOT / "benchmarks/baton-compatibility/final-gate-snapshot/README.md"
        ).read_text(encoding="utf-8")
        for phrase in (
            "v1.3.1",
            "Claude Code 2.1.217",
            "--model opus",
            "runtime-tested",
            "CONFIRMED",
        ):
            self.assertIn(phrase, snapshot)
        self.assertIn("previous_final_gate", english)
        self.assertIn("previous_final_gate", chinese)
        self.assertIn("v1.3.0", english)
        self.assertIn("v1.3.0", chinese)

    def test_baton_evidence_record_granularity_and_totals(self) -> None:
        results = json.loads(
            (
                ROOT / "benchmarks/baton-compatibility/results.json"
            ).read_text(encoding="utf-8"),
            parse_float=Decimal,
        )
        self.assertEqual(results["schema_version"], 4)
        self.assertEqual(results["final_gate_status"], "complete")
        final = results["final_gate"]
        self.assertEqual(final["status"], "passed")
        self.assertEqual(final["granularity"], "invocation")
        self.assertEqual(len(final["turns"]), final["total_cli_invocations"])
        self.assertEqual(final["source_base_head"], "4d65cc94b59acec2debec37983ad0a021440d643")
        self.assertEqual(final["release_candidate_version"], "1.3.1")
        self.assertEqual(final["requested_main_model"], "opus")
        self.assertEqual(final["observed_main_model"], "claude-opus-4-8")
        self.assertEqual(final["transcript_sha256"], "6563b1c5f3d15f2640688a8509fa093364c5534f9246e0ee700e67c3469ac0b5")
        self.assertEqual(final["total_cli_invocations"], 2)
        final_metric_keys = {
            "duration_ms",
            "duration_api_ms",
            "num_turns",
            "client_reported_cost_usd",
            "models",
            "disposition",
        }
        for expected, turn in enumerate(final["turns"], 1):
            self.assertEqual(turn["cli_invocation"], expected)
            self.assertIn("prompt_turn", turn)
            self.assertEqual(turn["max_budget_usd"], 6)
            self.assertTrue(final_metric_keys <= turn.keys())
        for field, total_field in (
            ("duration_ms", "total_duration_ms"),
            ("duration_api_ms", "total_duration_api_ms"),
            ("num_turns", "total_num_turns"),
        ):
            self.assertEqual(
                sum((turn[field] for turn in final["turns"]), 0),
                final[total_field],
            )
        self.assertEqual(final["total_duration_ms"], 443281)
        self.assertEqual(final["total_duration_api_ms"], 440965)
        self.assertEqual(final["total_num_turns"], 13)
        self.assertEqual(
            sum(
                (turn["client_reported_cost_usd"] for turn in final["turns"]),
                Decimal("0"),
            ),
            final["total_client_reported_cost_usd"],
        )
        self.assertEqual(final["total_client_reported_cost_usd"], Decimal("2.8822337"))
        self.assertFalse(final["result_collection_runtime_exercised"])
        self.assertFalse(final["security_reviewer_runtime_exercised"])
        self.assertIn(
            "result_collection_background_recon_triggered",
            results["unexercised_controls"],
        )
        self.assertIn("result_collection_evidence", results["unexercised_controls"])
        self.assertTrue(final["passed"])
        self.assertEqual(
            [call["role"] for call in final["agent_calls"]],
            ["plan-verifier", "mech-executor", "verifier"],
        )
        executor_evidence = results["unexercised_controls"][
            "executor_role_evidence"
        ]
        for role in ("plan-verifier", "mech-executor", "verifier"):
            self.assertIn(role, executor_evidence)
        self.assertNotIn("scout, scout", executor_evidence)
        self.assertIn("executor and scout roles were not dispatched", executor_evidence)
        post_gate_note = results["post_gate_role_frontmatter_change"]["note"]
        self.assertIn("changed executor itself was not live-exercised", post_gate_note)
        self.assertIn("distinct mech-executor or scout roles", post_gate_note)
        self.assertTrue(all(call["invocation_model"] is None for call in final["agent_calls"]))
        self.assertTrue(all(not call["background"] for call in final["agent_calls"]))
        self.assertEqual(final["agent_calls"][0]["observed_tools"], ["Read", "Grep"])
        self.assertEqual(final["agent_calls"][1]["observed_model"], "claude-sonnet-5")
        self.assertEqual(final["agent_calls"][1]["observed_tools"], ["Bash", "Write"])
        self.assertTrue(final["agent_calls"][1]["direct_write_blocked_by_hook"])
        self.assertEqual(final["turns"][1]["integration_write_owner"], "main_session")
        self.assertEqual(final["agent_calls"][-1]["verdicts"], ["CONFIRMED"])

        release = results["v1_3_2_release_gate"]
        self.assertEqual(release["status"], "passed")
        self.assertEqual(release["granularity"], "invocation")
        self.assertEqual(release["release_candidate_version"], "1.3.2")
        self.assertEqual(len(release["turns"]), release["total_cli_invocations"])
        self.assertEqual(release["total_cli_invocations"], 2)
        self.assertEqual(release["total_duration_ms"], 445010)
        self.assertEqual(release["total_duration_api_ms"], 443416)
        self.assertEqual(release["total_num_turns"], 19)
        self.assertEqual(
            sum(
                (turn["client_reported_cost_usd"] for turn in release["turns"]),
                Decimal("0"),
            ),
            release["total_client_reported_cost_usd"],
        )
        self.assertEqual(
            release["total_client_reported_cost_usd"], Decimal("2.77709775")
        )
        self.assertEqual(
            [
                unit["id"]
                for unit in release["turns"][0]["readiness_units"]
            ],
            ["ENV-report-audit", "S1-report"],
        )
        self.assertTrue(
            all(
                unit["verdict"] == "READY"
                and unit["invocation_model"] is None
                and not unit["background"]
                for unit in release["turns"][0]["readiness_units"]
            )
        )
        self.assertEqual(
            release["turns"][1]["verifier"]["verdict"], "CONFIRMED"
        )
        self.assertTrue(release["turns"][1]["independent_final_byte_test_passed"])
        self.assertFalse(release["turns"][1]["deferred_unit_executed"])
        self.assertTrue(release["passed"])
        opus5 = results["v1_3_2_opus5_release_gate"]
        self.assertEqual(opus5["status"], "passed_with_corrective_verification")
        self.assertEqual(opus5["observed_main_model"], "claude-opus-5")
        self.assertEqual(opus5["claude_code"], "2.1.219")
        self.assertEqual(opus5["gate_policy_version"], "1.3.2")
        self.assertEqual(opus5["proposed_install_version"], "1.3.3")
        self.assertNotIn("source_base_head", opus5)
        self.assertEqual(
            opus5["post_gate_v1_3_3_policy_sha256"],
            "90e3d06409e8769b71c8807cce67876bebd9eaea65ec11ec6f947f597b44229b",
        )
        self.assertIn(
            "version stamp only",
            opus5["post_gate_v1_3_3_policy_delta"],
        )
        source_manifest = opus5["source_input_manifest"]
        self.assertEqual(
            source_manifest["policy"]["sha256"],
            opus5["orchestration_sha256"],
        )
        self.assertEqual(
            source_manifest["agents_file"]["sha256"],
            opus5["agents_json_file_sha256"],
        )
        self.assertEqual(
            source_manifest["agents_runtime"]["sha256"],
            opus5["agents_json_runtime_sha256"],
        )
        self.assertEqual(
            source_manifest["settings"]["sha256"],
            opus5["settings_sha256"],
        )
        baton_source = opus5["baton_skill_source"]
        self.assertEqual(
            baton_source["commit"],
            "77f12e600406065a6e62a22a66347355e278a9d7",
        )
        self.assertEqual(
            baton_source["files"]["SKILL.md"],
            opus5["baton_skill_sha256"],
        )
        self.assertEqual(
            set(baton_source["files"]),
            {
                "SKILL.md",
                "references/dispatch-planning.md",
                "references/context-and-briefs.md",
                "references/execution-and-verification.md",
                "references/examples.md",
                "references/claude-code-ultracode.md",
                "references/codegraph.md",
            },
        )
        opus5_snapshot_readme = (
            ROOT
            / "benchmarks"
            / "baton-compatibility"
            / "v1.3.2-opus5-gate-snapshot"
            / "README.md"
        ).read_text(encoding="utf-8")
        for pinned_value in (
            baton_source["commit"],
            baton_source["tree"],
            *baton_source["files"].values(),
        ):
            self.assertIn(pinned_value, opus5_snapshot_readme)
        self.assertEqual(len(opus5["turns"]), opus5["total_cli_invocations"])
        self.assertEqual(opus5["total_cli_invocations"], 3)
        self.assertEqual(opus5["total_duration_ms"], 453853)
        self.assertEqual(opus5["total_duration_api_ms"], 969791)
        self.assertEqual(opus5["total_num_turns"], 12)
        self.assertEqual(
            sum(
                (turn["client_reported_cost_usd"] for turn in opus5["turns"]),
                Decimal("0"),
            ),
            opus5["total_client_reported_cost_usd"],
        )
        self.assertEqual(
            opus5["total_client_reported_cost_usd"], Decimal("5.54877495")
        )
        self.assertEqual(
            [
                unit["verdicts"]
                for unit in opus5["turns"][0]["readiness_units"]
            ],
            [["REVISE", "READY"], ["REVISE", "READY"]],
        )
        self.assertTrue(
            all(
                unit["invocation_model"] is None
                and unit["observed_model"] == "claude-opus-5"
                for unit in opus5["turns"][0]["readiness_units"]
            )
        )
        self.assertTrue(opus5["turns"][1]["post_verdict_edit"])
        self.assertFalse(opus5["turns"][1]["initial_verdict_covers_final_bytes"])
        self.assertFalse(opus5["turns"][1]["accepted_as_final"])
        self.assertEqual(opus5["turns"][2]["verifier"]["verdict"], "CONFIRMED")
        self.assertTrue(opus5["turns"][2]["independent_final_byte_test_passed"])
        self.assertFalse(opus5["exact_two_cli_invocation_contract_passed"])
        self.assertTrue(opus5["corrective_verification_closed_final_bytes"])
        self.assertTrue(opus5["result_collection_runtime_exercised"])
        self.assertFalse(opus5["fallback_model_runtime_exercised"])
        self.assertTrue(opus5["passed"])

        rejected_opus5 = results["v1_3_2_opus5_rejected_user_source_attempt"]
        self.assertEqual(rejected_opus5["status"], "rejected")
        self.assertEqual(rejected_opus5["observed_main_model"], "claude-opus-4-8")
        self.assertFalse(rejected_opus5["turn_1"]["turn_2_started"])
        self.assertEqual(
            rejected_opus5["total_client_reported_cost_usd"],
            Decimal("1.7603425"),
        )
        recorded_campaign_cost = (
            opus5["total_client_reported_cost_usd"]
            + rejected_opus5["total_client_reported_cost_usd"]
        )
        self.assertEqual(recorded_campaign_cost, Decimal("7.30911745"))
        for evidence_doc in (
            ROOT / "CHANGELOG.md",
            ROOT / "benchmarks" / "baton-compatibility" / "README.md",
            ROOT / "benchmarks" / "baton-compatibility" / "README.zh-TW.md",
        ):
            content = evidence_doc.read_text(encoding="utf-8")
            self.assertIn("$7.30911745", content)
            self.assertNotIn("OPUS5_DEFAULT_GATE_OK", content)
            self.assertNotIn("$7.34386145", content)
        self.assertFalse(rejected_opus5["passed"])
        post_gate = results["v1_3_2_post_gate_role_change"]
        self.assertEqual(post_gate["role"], "plan-verifier")
        self.assertTrue(post_gate["recorded_gate_role_exercised"])
        self.assertFalse(post_gate["live_gate_rerun"])
        self.assertIn("slice-local budget", post_gate["change"])
        self.assertIn("explicit stop conditions", post_gate["change"])
        self.assertIn("static contract coverage only", post_gate["note"])

        previous_final = results["previous_final_gate"]
        self.assertEqual(previous_final["granularity"], "invocation")
        self.assertEqual(previous_final["status"], "passed")
        self.assertEqual(previous_final["release_candidate_version"], "1.3.0")
        self.assertEqual(previous_final["total_cli_invocations"], 2)
        self.assertEqual(
            previous_final["transcript_sha256"],
            "98724de501d714dcb58b315b2260147f9cdd43975f16e52297a84ed258a83ac4",
        )

        failed = results["failed_candidate_gate"]
        self.assertEqual(failed["granularity"], "invocation")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(len(failed["turns"]), failed["total_cli_invocations"])
        self.assertEqual(failed["total_cli_invocations"], 1)
        self.assertEqual(failed["total_duration_ms"], 218040)
        self.assertEqual(failed["total_duration_api_ms"], 186738)
        self.assertEqual(failed["total_num_turns"], 13)
        self.assertEqual(failed["total_client_reported_cost_usd"], Decimal("4.12912975"))
        self.assertEqual(failed["turns"][0]["disposition"], "budget_exhausted")
        self.assertEqual(failed["turns"][0]["terminal_status"], "budget_exhausted")
        self.assertEqual(failed["turns"][0]["max_budget_usd"], 3)
        self.assertTrue(failed["prompt_fix_applied_to_release_candidate"])
        self.assertTrue(failed["failure_led_to_prompt_fix"])
        self.assertEqual(
            failed["prompt_turn_1_file_sha256"],
            "edce6a591e5879769b89b0fff0f4aa8c64e038f79b93e6a804161e4f9914624f",
        )
        self.assertEqual(
            failed["prompt_turn_1_runtime_input_sha256"],
            "8aa4459acbb2f96df4617dcbf2b147c91222252a48c8fac754f344bc2d32d2fb",
        )
        self.assertEqual(
            failed["transcript_sha256"],
            "250b8cd8b53e758299b233d16c2753890a46c6284a99a8d21ba5d5e907bf7ebc",
        )

        candidate = results["superseded_candidate_gate"]
        self.assertEqual(candidate["granularity"], "invocation")
        self.assertEqual(len(candidate["turns"]), candidate["total_cli_invocations"])
        self.assertEqual(candidate["source_commit"], "40f38151581b890c7aec64218a95758045dfec57")
        metric_keys = {
            "duration_ms",
            "duration_api_ms",
            "num_turns",
            "client_reported_cost_usd",
            "models",
            "disposition",
        }
        for expected, turn in enumerate(candidate["turns"], 1):
            self.assertEqual(turn["cli_invocation"], expected)
            self.assertIn("prompt_turn", turn)
            self.assertTrue(metric_keys <= turn.keys())

        for field, total_field in (
            ("duration_ms", "total_duration_ms"),
            ("duration_api_ms", "total_duration_api_ms"),
            ("num_turns", "total_num_turns"),
        ):
            self.assertEqual(
                sum((turn[field] for turn in candidate["turns"]), 0),
                candidate[total_field],
            )
        self.assertEqual(
            sum(
                (turn["client_reported_cost_usd"] for turn in candidate["turns"]),
                Decimal("0"),
            ),
            candidate["total_client_reported_cost_usd"],
        )
        self.assertEqual(candidate["total_client_reported_cost_usd"], Decimal("4.60368875"))

        summary_keys = (
            "previous_release_gate",
            "historical_release_gate",
            "superseded_gate",
            "rejected_harness_run",
            "unexercised_controls",
        )
        for key in summary_keys:
            self.assertEqual(results[key]["granularity"], "summary")
            self.assertNotIn("turns", results[key])
        self.assertEqual(
            results["rejected_harness_run"]["transcript_sha256"],
            "64376ea52a4e67192df29d8595c180ddc5017638029759a8ac13aff87d5cca81",
        )
        self.assertEqual(results["previous_release_gate"]["release_candidate_version"], "1.2.1")
        historical = results["historical_release_gate"]
        self.assertEqual(historical["release_candidate_version"], "1.2.0")
        self.assertEqual(historical["source_commit"], "125146508587d69eab1265b00210a59d1e5b375f")
        self.assertEqual(historical["total_duration_ms"], 448148)
        self.assertEqual(historical["total_num_turns"], 22)
        self.assertEqual(historical["total_client_reported_cost_usd"], Decimal("3.7890481"))

        metric_names = {
            "duration_ms",
            "duration_api_ms",
            "num_turns",
            "client_reported_cost_usd",
        }

        def find_nested_metric_invocation(value: object, top_level_turn: bool = False) -> bool:
            if isinstance(value, dict):
                if not top_level_turn and (
                    "interrupted_invocation" in value
                    or "invocation" in value
                    or ("cli_invocation" in value and metric_names & value.keys())
                ):
                    return True
                return any(
                    find_nested_metric_invocation(child, False)
                    for child in value.values()
                )
            if isinstance(value, list):
                return any(find_nested_metric_invocation(child, False) for child in value)
            return False

        for record in (final, previous_final, failed, candidate):
            self.assertFalse(
                any(
                    find_nested_metric_invocation(turn, True)
                    for turn in record["turns"]
                )
            )
        self.assertNotIn("interrupted_invocation", json.dumps(results, default=str))

    def test_attempt_accounting_ledger_is_complete_and_tamper_evident(self) -> None:
        ledger_path = ROOT / "benchmarks" / "attempt-accounting.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        _attempt_accounting_validate(ledger)

        self.assertEqual(len(ledger["sources"]), 11)
        self.assertEqual(
            sum(len(cell["claim_pointers"]) for cell in ledger["cells"]), 193
        )
        self.assertEqual(
            sum(len(cell["attempt_pointers"]) for cell in ledger["cells"]), 137
        )
        self.assertEqual(
            sum(
                cell["failed"]
                for cell in ledger["cells"]
                if cell["count_status"] == "known"
            ),
            37,
        )

        verifier_failed = next(
            cell
            for cell in ledger["cells"]
            if cell["id"]
            == "cell:benchmarks/verifier-boundary/results.json#failed"
        )
        self.assertEqual(
            (verifier_failed["attempted"], verifier_failed["passed"], verifier_failed["failed"]),
            (6, 0, 6),
        )
        verifier_failures = [
            entry
            for entry in ledger["failed_attempts"]
            if entry["attempt_pointer"]["source"]
            == "benchmarks/verifier-boundary/results.json"
        ]
        self.assertEqual(len(verifier_failures), 6)
        self.assertEqual(
            sorted(
                entry["attempt_pointer"].get("occurrence", 0)
                for entry in verifier_failures
                if entry["attempt_pointer"]["json_pointer"] == "/failed_attempts/2"
            ),
            [0, 1],
        )
        self.assertEqual(
            sorted(
                entry["attempt_pointer"].get("occurrence", 0)
                for entry in verifier_failures
                if entry["attempt_pointer"]["json_pointer"] == "/failed_attempts/3"
            ),
            [0, 1],
        )

        hash_identity = deepcopy(ledger)
        hash_entry = next(
            entry
            for entry in hash_identity["failed_attempts"]
            if entry["attempt_pointer"]["source"]
            == "benchmarks/verifier-boundary/results.json"
            and entry["attempt_pointer"]["json_pointer"] == "/failed_attempts/2"
            and entry["attempt_pointer"].get("occurrence", 0) == 0
        )
        hash_entry["candidate_identity"] = {
            "limitation": "identity intentionally removed"
        }
        with self.assertRaises(AssertionError):
            _attempt_accounting_validate(hash_identity)

        config_identity = deepcopy(ledger)
        config_entry = next(
            entry
            for entry in config_identity["failed_attempts"]
            if entry["attempt_pointer"]["source"]
            == "benchmarks/spontaneous-dispatch/issue-29-topology.json"
        )
        config_entry["candidate_identity"] = {
            "limitation": "identity intentionally removed"
        }
        with self.assertRaises(AssertionError):
            _attempt_accounting_validate(config_identity)

        control_entry = next(
            entry
            for entry in ledger["failed_attempts"]
            if entry["attempt_pointer"]["source"]
            == "benchmarks/prompt-compression/results.json"
            and entry["attempt_pointer"]["json_pointer"]
            == "/behavioral_gates/spontaneous_mechanical_v1_3_3_control"
        )
        self.assertEqual(control_entry["candidate_identity"], {"version": "1.3.3"})

        root_identity = deepcopy(ledger)
        root_entry = next(
            entry
            for entry in root_identity["failed_attempts"]
            if entry["id"] == control_entry["id"]
        )
        root_entry["candidate_identity"] = {"version": "1.3.4"}
        with self.assertRaises(AssertionError):
            _attempt_accounting_validate(root_identity)

        control_limitation = deepcopy(ledger)
        limitation_entry = next(
            entry
            for entry in control_limitation["failed_attempts"]
            if entry["id"] == control_entry["id"]
        )
        limitation_entry["candidate_identity"] = {
            "limitation": "identity intentionally removed"
        }
        with self.assertRaises(AssertionError):
            _attempt_accounting_validate(control_limitation)

        cue_free_failures = [
            entry
            for entry in ledger["failed_attempts"]
            if entry["attempt_pointer"]["source"]
            == "benchmarks/spontaneous-dispatch/cue-free-tui.json"
        ]
        self.assertEqual(len(cue_free_failures), 4)
        self.assertTrue(
            all(
                entry["candidate_identity"]
                == {
                    "hash": "5ecbbe9a797ba1269a20ac9a1aa3ba5182bf7d9da887ea889263ef9ee64c0564"
                }
                for entry in cue_free_failures
            )
        )
        cue_free_identity = deepcopy(ledger)
        cue_free_entry = next(
            entry
            for entry in cue_free_identity["failed_attempts"]
            if entry["attempt_pointer"]["source"]
            == "benchmarks/spontaneous-dispatch/cue-free-tui.json"
        )
        cue_free_entry["candidate_identity"] = {
            "limitation": "identity intentionally removed"
        }
        with self.assertRaises(AssertionError):
            _attempt_accounting_validate(cue_free_identity)

        tui_entry = next(
            entry
            for entry in cue_free_failures
            if entry["attempt_pointer"]["json_pointer"] == "/campaign/cells/3"
        )
        self.assertEqual(
            [item["json_pointer"] for item in tui_entry["evidence"]],
            ["", "/tui_observation", "/campaign/cells/3"],
        )
        wrong_tui_owner = deepcopy(ledger)
        wrong_tui_failures = [
            entry
            for entry in wrong_tui_owner["failed_attempts"]
            if entry["attempt_pointer"]["source"]
            == "benchmarks/spontaneous-dispatch/cue-free-tui.json"
        ]
        wrong_cell_zero = next(
            entry
            for entry in wrong_tui_failures
            if entry["attempt_pointer"]["json_pointer"] == "/campaign/cells/0"
        )
        wrong_cell_three = next(
            entry
            for entry in wrong_tui_failures
            if entry["attempt_pointer"]["json_pointer"] == "/campaign/cells/3"
        )
        wrong_cell_zero["evidence"].append(wrong_cell_three["evidence"].pop(1))
        with self.assertRaises(AssertionError):
            _attempt_accounting_validate(wrong_tui_owner)

        missing_cell_mapping = deepcopy(ledger)
        cell = next(
            cell
            for cell in missing_cell_mapping["cells"]
            if len(cell["claim_pointers"]) > 1
        )
        cell["claim_pointers"].pop()
        with self.assertRaises(AssertionError):
            _attempt_accounting_validate(missing_cell_mapping)

        missing_attempt_mapping = deepcopy(ledger)
        attempt_cell = next(
            cell
            for cell in missing_attempt_mapping["cells"]
            if cell["attempt_pointers"]
        )
        attempt_cell["attempt_pointers"].pop()
        with self.assertRaises(AssertionError):
            _attempt_accounting_validate(missing_attempt_mapping)

        missing_failure_mapping = deepcopy(ledger)
        missing_failure_mapping["failed_attempts"].pop()
        with self.assertRaises(AssertionError):
            _attempt_accounting_validate(missing_failure_mapping)


if __name__ == "__main__":
    unittest.main()
