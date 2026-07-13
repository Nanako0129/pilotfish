#!/usr/bin/env python3
"""pilotfish PreToolUse guard — enforces what the policy can only ask for.

Two enforcement legs, of deliberately different strength:

1. `run_in_background` is a STRUCTURAL block. It is a typed tool parameter, so denying
   it in a subagent removes the capability outright — there is no spelling around it.

2. Shell-level detaching (`nohup`, `setsid`, `disown`, a backgrounding `&`) is caught by
   BEST-EFFORT lexical matching. A hook sees the command only as a string, so this leg
   cannot be airtight: a subshell (`bash -c '…'`), an `eval`, or an exotic launcher
   (`screen`, `systemd-run`, `at`) can route around it. It is defense against the
   *accidental* pattern — a subagent reaching for the `nohup … &` habit — not a sandbox.
   The structural leg above is what actually holds.

Why this matters (verified empirically, 2026-07-13): a foreground Bash command that
exceeds its `timeout` is not killed — the harness promotes it to a background task and
promises a completion notification. In a subagent spawned with run_in_background=true the
promoted process survives and the notification fires; in one spawned in the FOREGROUND it
is SIGTERMed seconds after the agent returns, destroying the work. `nohup`/`setsid` dodge
that SIGTERM but escape the harness's task tracking entirely, so the result is orphaned
instead — no task id, no captured output, no notification. Either way, a subagent must
not own a long process; it hands the command back to the orchestrator.

Main-session calls are never restricted. The orchestrator's backgrounding is the path
that works, and it must keep working. The discriminator is `agent_type`: absent for the
main session, present for a subagent (verified against real captured payloads).

The guard also blocks the built-in `Explore` agent, which since Claude Code v2.1.198
inherits the main-session model and so bills every search at frontier rates. A plugin
cannot shadow a built-in (plugin agents are namespaced), so it is blocked and recon is
routed to `pilotfish:scout`, pinned to Haiku.

The guard FAILS OPEN: any unexpected input allows the call. It cannot lock you out.
"""

import json
import re
import sys

# `nohup`/`setsid`/`disown` in COMMAND position: at the start, or right after a shell
# control operator (`; & | (` backtick newline), with an optional path prefix so
# `/usr/bin/nohup` is caught but `grep nohup logs` (nohup as an argument) is not.
DETACH = re.compile(
    r"""(?:^|[;&|(`\n])        # start of a command
        \s*
        (?:[^\s;&|()]*/)?      # optional path prefix: /usr/bin/
        (?:nohup|setsid|disown)\b
     """,
    re.VERBOSE,
)
# A backgrounding `&`: not part of `&&`, not an fd redirect (`>&`, `&>`, `2>&1`).
BACKGROUND_AMP = re.compile(r"(?<![&>])&(?![&>])")

EXPLORE_REASON = (
    "pilotfish: use `pilotfish:scout` instead of the built-in `Explore`. Since Claude "
    "Code v2.1.198 the built-in Explore inherits your main-session model, so every search "
    "it runs bills at frontier rates — which is precisely the cost this setup exists to "
    "avoid. `pilotfish:scout` is the same read-only recon role, pinned to Haiku. Re-issue "
    'this call with subagent_type: "pilotfish:scout".'
)

DETACH_REASON = (
    "pilotfish: subagents may not detach a process (`nohup`, `setsid`, `disown`, a "
    "backgrounding `&`). Detaching escapes the harness's task tracking entirely — no task "
    "id, no captured output, no completion notification — so the result is orphaned and "
    "nobody ever collects it. Run it in the foreground with an explicit `timeout` (max "
    "600000ms). If it cannot finish in 10 minutes, do not run it: report that the task "
    "needs a long-running process, name the exact command, and stop. The orchestrator "
    "runs it and re-tasks you with the output."
)

BACKGROUND_REASON = (
    "pilotfish: subagents may not background a command. A backgrounded process is not "
    "reliably collected, and if this agent was spawned in the foreground it is SIGTERMed "
    "the moment the agent returns — the work is destroyed and its output truncated. Run "
    "it in the foreground with an explicit `timeout` (max 600000ms). If it cannot finish "
    "in 10 minutes, do not run it: report that the task needs a long-running process, "
    "name the exact command, and stop."
)


def allow() -> None:
    sys.exit(0)


def deny(reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.exit(0)


def strip_quotes(command: str) -> str:
    """Blank out single- and double-quoted spans so a token inside a string literal
    (`git commit -m 'drop nohup'`, `grep 'a && b'`) is never mistaken for a command."""
    command = re.sub(r"'[^']*'", " ", command)
    command = re.sub(r'"[^"]*"', " ", command)
    return command


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            allow()
    except Exception:
        allow()  # never break a session on a malformed payload

    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        allow()

    if tool == "Agent":
        # Only the bare built-in is a problem. `pilotfish:*` roles are ours and pinned.
        if (tool_input.get("subagent_type") or "").strip() == "Explore":
            deny(EXPLORE_REASON)
        allow()

    # Bash restrictions apply to subagents only — the main session carries no agent_type
    # and must keep backgrounding, which is the mechanism that actually works.
    if tool == "Bash" and payload.get("agent_type"):
        if tool_input.get("run_in_background") is True:
            deny(BACKGROUND_REASON)
        command = tool_input.get("command")
        if isinstance(command, str):
            scrubbed = strip_quotes(command)
            if DETACH.search(scrubbed) or BACKGROUND_AMP.search(scrubbed):
                deny(DETACH_REASON)

    allow()


if __name__ == "__main__":
    main()
