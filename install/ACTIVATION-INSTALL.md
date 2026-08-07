# Install optional pilotfish activation shortcuts

These optional shortcuts remove repeated typing without changing pilotfish's
role agents or orchestration policy. Install pilotfish with
[AGENT-INSTALL.md](./AGENT-INSTALL.md) first.

> **Claim boundary:** Both shortcuts are deliberate user opt-ins, not cue-free
> dispatch. The reference sentence has bounded behavioral evidence. The skill
> and CLI-wrapper delivery paths have not been separately qualified for
> dispatch reliability or frequency.

## Choose an activation path

| Method | Input source | Status |
|---|---|---|
| Paste the opt-in sentence | User prompt | Tested reference path; no extra install |
| Invoke `/pilotfish <task>` | [User-invocable skill](https://code.claude.com/docs/en/slash-commands#control-who-invokes-a-skill) with the task in `$ARGUMENTS` | Recommended shortcut; closest to the tested user-prompt path |
| Start `claude-pilotfish` | [`--append-system-prompt`](https://code.claude.com/docs/en/cli-usage#system-prompt-flags) adds one session instruction | Optional CLI wrapper; explicit launch, different prompt surface |
| Model-selected `pilotfish-auto` | Model invokes an always-visible skill | Not shipped; experiment tracked in [#53](https://github.com/Nanako0129/pilotfish/issues/53) |
| `UserPromptSubmit` hook | [Hook context](https://code.claude.com/docs/en/hooks#userpromptsubmit) wrapped as a system reminder | Not offered; it is not equivalent to a user request and may trigger prompt-injection defenses |

The `/pilotfish` skill uses `disable-model-invocation: true`, so Claude cannot
activate it for the user. The wrapper is also explicit because the user chooses
to start that launcher, but its instruction reaches Claude as an appended system
prompt rather than a user message.

## Install with AI

Clone a reviewed release, start Claude Code from that checkout, and paste:

```text
Read the local file install/ACTIVATION-INSTALL.md in the current checkout and
follow its AI install contract. Ask me to choose the /pilotfish skill, the CLI
wrapper, or both; for the wrapper, ask whether to include the optional Baton
hint. Show me the complete plan and get my approval before writing anything.
```

### Shared AI install contract

Resolve the configuration root exactly as Step 0 of
[AGENT-INSTALL.md](./AGENT-INSTALL.md) specifies. Use the resolved root as
`$CFG`; do not assume `~/.claude` when `CLAUDE_CONFIG_DIR` is set. Verify that
the pilotfish marker block and eight role agents are already installed.

Ask which shortcut to install. For a wrapper, ask whether to use the plain or
Baton-aware prompt. The Baton-aware choice requires an already installed
[Baton](https://github.com/cablate/baton) skill; this runbook never installs or
updates Baton.

Inspect every selected target before writing. Show its existing state, proposed
content, update behavior, verification, and rollback, then wait for approval.
Never overwrite an existing target that lacks the matching
`pilotfish-activation` ownership marker. Stop and ask the user to keep it,
or remove it themselves.

Before updating a marked Pilotfish-owned target, copy its exact bytes to a new
timestamped file under `$CFG/backups/pilotfish-activation/history/`, read it
back, compare it with the current target, and record its path. For a wrapper,
also record its executable state. If creating or verifying the history backup
fails, stop without modifying the target. Never reuse or overwrite an earlier
backup. History backups support an explicit update rollback; they are never
restored by uninstall.

### `/pilotfish` skill payload

Inspect `$CFG/skills/pilotfish/SKILL.md` and the legacy
`$CFG/commands/pilotfish.md` for a name collision. Do not modify a legacy
command; stop until the user resolves that collision. After approval, create
only `$CFG/skills/pilotfish/SKILL.md` with these exact contents:

```markdown
---
name: pilotfish
description: Explicitly activate the installed pilotfish orchestration policy for one task.
argument-hint: "<task>"
disable-model-invocation: true
---

<!-- pilotfish-activation-skill -->

Use pilotfish. Follow its dispatch brake: keep direct work in the main session
and call the named agents only when the policy selects delegation.

Complete this task:

$ARGUMENTS

If no task was supplied, ask the user for it before starting work.
```

### CLI wrapper payload

Use the plain session instruction by default:

```text
The user explicitly authorizes Agent delegation for this session. Follow the installed pilotfish policy and its dispatch brake.
```

Use this variant only when the user selected Baton and the skill is already
installed:

```text
The user explicitly authorizes Agent delegation for this session. Follow the installed pilotfish policy and its dispatch brake. If Baton is installed, use it as the delegation-planning layer when its planning benefit exceeds coordination cost.
```

Choose an existing user-owned directory already present in `PATH`. Do not edit a
shell profile or change `PATH`; if no suitable directory exists, stop and show
the direct command from [Use and verify](#use-and-verify) instead.

On macOS, Linux, or WSL, install `claude-pilotfish` with the selected instruction
substituted for `<SESSION_INSTRUCTION>`, then make the file executable:

```sh
#!/bin/sh
# pilotfish-activation-wrapper
exec claude --append-system-prompt '<SESSION_INSTRUCTION>' "$@"
```

On native Windows, install `claude-pilotfish.cmd` in an existing user-owned
`PATH` directory:

```bat
@echo off
REM pilotfish-activation-wrapper
claude --append-system-prompt "<SESSION_INSTRUCTION>" %*
```

Read every installed target back and compare its complete contents with the
selected payload. Run `claude-pilotfish --version` to confirm wrapper lookup,
argument forwarding, and executable state without starting a paid Claude
session. Report every backup path. Do not modify `settings.json`, the eight role
agents, the pilotfish policy block, Baton, shell profiles, or `PATH`.

## Use and verify

Claude Code supports [live skill change detection](https://code.claude.com/docs/en/slash-commands#live-change-detection).
Open `/skills` and confirm that `pilotfish` is visible, or start a new session
if the current one does not pick it up. Invoke it at the start of a task:

```text
/pilotfish migrate the cache schema without changing the public API
```

Start a wrapper-installed session with:

```sh
claude-pilotfish
```

Without installing a wrapper, the plain one-off command is:

```sh
claude --append-system-prompt "The user explicitly authorizes Agent delegation for this session. Follow the installed pilotfish policy and its dispatch brake."
```

Both methods authorize pilotfish to apply its dispatch brake; neither requires
delegation. Small or tightly coupled work may remain in the main session, and
higher-priority managed policy can still block Agent use.

## Update or remove

Re-run the AI install prompt to compare selected targets with this reviewed
file. For an explicit update rollback, restore the selected history backup and
verify its bytes and wrapper executable state. For uninstall, remove only a
target that carries the matching ownership marker and still matches a reviewed
Pilotfish payload. Never restore a history backup during uninstall. Stop and
show a diff if current content has changed. Because this runbook never replaces
unowned content, uninstall has no pre-Pilotfish file to restore. The core
pilotfish and optional Baton installations remain unchanged.
