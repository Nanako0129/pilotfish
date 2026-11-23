# pilotfish for the Antigravity CLI (preview)

This directory is a port of pilotfish to `agy`, the Antigravity CLI. It gives the main agent the pilotfish orchestration policy and seven leaf subagents, with prompts written for Gemini 4.

It is a preview. It was built and observed on agy 1.5.15 on macOS with a consumer plan on 2026-11-23, and it is versioned separately from the Claude Code plugin (`plugin.json` says `0.1.1`). It is not on a marketplace.

The policy is a hand rewrite of the Claude Code policy. [`docs/agy-parity.md`](../docs/agy-parity.md) maps every rule of the original to the clause that carries it here and lists what was not ported.

## What it installs

| Component | File | What it does |
|---|---|---|
| Policy | `rules/AGENTS.md` | Always-on rules for the main agent: shape the work, ask for approval on risky work, delegate with brakes, verify. |
| Seven roles | `agents/pilotfish-*.md` | Leaf subagents the main agent launches with `invoke_subagent`. |
| Model-floor hook | `hooks.json`, `hooks/model-floor.sh` | Warns at session start when the conversation runs on a Hydrogen or Flash tier. |

| Role | Model tier | Tools | Use |
|---|---|---|---|
| `pilotfish-scout` | `flash` | read, sandboxed shell | Bounded read-only lookup |
| `pilotfish-mech-executor` | `flash` | read, edit, write, shell | Fully specified repetition |
| `pilotfish-executor` | `flash` | read, edit, write, shell | Implementation that needs judgment |
| `pilotfish-plan-verifier` | `inherit` | read, sandboxed shell | Plan review before approval |
| `pilotfish-verifier` | `inherit` | read, sandboxed shell | Outcome review after implementation |
| `pilotfish-security-reviewer` | `inherit` | read, sandboxed shell, web search | Security analysis before approval |
| `pilotfish-security-executor` | `inherit` | read, edit, write, shell | Approved security implementation |

On agy 1.5.15, `flash` resolved to Gemini 4 Hydrogen (High) and `inherit` to the main agent's model. A subagent reaches a frontier model only through `inherit`, so run the main conversation on one (the observations here used `gemini-4-neon-high`).

## Install

Requires `agy` and a checkout of this repository. No build step.

For every workspace:

```bash
git clone https://github.com/Nanako0129/pilotfish.git
agy plugin install "$PWD/pilotfish/plugin-agy"
```

For one repository only, copy the directory into that repository:

```bash
mkdir -p .agents/plugins
cp -R /path/to/pilotfish/plugin-agy .agents/plugins/pilotfish
```

Check and remove:

```bash
agy plugin list
agy plugin uninstall pilotfish
```

Start a new session after installing. The hook is a POSIX `sh` script and needs no runtime.

## What was observed

- All seven roles start, each on the tier in the table above.
- `agy plugin install` reports 7 agents, 1 rule and 1 hook, and `agy plugin validate --strict` passes.
- The hook's warning reached a main agent on `gemini-4-hydrogen-medium` and was absent on `gemini-4-neon-high`.
- With the 0.1.1 policy, one headless run each on `gemini-4-neon-high` (2026-11-24): asked for a schema migration, the main agent edited nothing, wrote a Plan envelope that opened with intent, outcome and non-goals, and sent it to `pilotfish-plan-verifier`; asked for the same `var` to `const` change in eight files, it launched one `pilotfish-mech-executor` without asking for approval and all eight files changed.
- Delegation behavior with and without the plugin on two tasks, measured on the 0.1.0 policy: [`benchmarks/agy-preview`](../benchmarks/agy-preview/README.md).

## Known limits

- **Read-only roles are read-only by instruction.** agy gave a role with only `read_file` no way to list or search, so the discovery and review roles have a shell under `commandExecutionPolicy: sandbox`. The sandbox blocked writes outside the workspace and allowed them inside it; it did not block network access.
- **MCP tools reach every subagent.** agy grants `call_mcp_tool` to a subagent whatever its `tools` list says.
- **The policy and the hook reach every subagent.** agy injects plugin rules into subagents and fires `SessionStart` for each of them. The policy opens by telling a subagent to ignore it, and the hook's message does the same.
- **The model floor is a warning, not a gate.** The hook knows two weak tiers by name (`hydrogen`, `flash`). Any other model, and `auto`, passes without a check.
- **No enforcement hooks.** Nothing blocks a tool call; every rule except the tool lists and the sandbox is text.
- **Not observed:** Linux, Windows, the Antigravity desktop app and IDE, an interactive session, `flash_lite` in a role file, and any agy version other than 1.5.15.
