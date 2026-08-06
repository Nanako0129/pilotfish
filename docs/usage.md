# Using pilotfish

This guide collects day-to-day model, delegation, compatibility, and opt-out
questions. Installation and file mutation rules remain in the
[install runbook](../install/AGENT-INSTALL.md); exact orchestration behavior
remains in the [policy template](../templates/claude-md.orchestration.md).

[繁體中文](./usage.zh-TW.md)

## Contents

- [Model routing](#model-routing)
- [Delegation behavior](#delegation-behavior)
- [Configuration and compatibility](#configuration-and-compatibility)
- [Tuning](#tuning)
- [Long runs and verification](#long-runs-and-verification)
- [Disable, update, or uninstall](#disable-update-or-uninstall)

## Model routing

| Need | Setting or action | Effect |
|---|---|---|
| Default main session | `model: "opus"` | Uses the provider-resolved Opus family alias; the installer preserves an existing choice unless you approve a change |
| Explicit Fable session | `/model fable` | Opts into Fable without changing role-agent bindings |
| Lower main-session quota use | `/model opusplan` | Uses Opus for planning turns and Sonnet for the main session's execution turns |
| Explicit 1M context request | `model: "opus[1m]"` | Requests the documented 1M Opus alias where the provider supports it |
| Primary model unavailable | `fallbackModel: ["sonnet"]` | Falls back on overload or unavailability; it does not catch authentication, billing, or rate-limit failures |

Each role's model and effort live in its agent frontmatter. Do not set
`CLAUDE_CODE_SUBAGENT_MODEL` unless you intentionally want to override every
role, including the Opus review and security roles.

## Delegation behavior

Higher-priority Claude Code instructions can suppress Agent dispatch. When the
pilotfish lifecycle matters, make the request explicit:

```text
Use pilotfish. Follow its dispatch brake: keep direct work in the main session
and call the named agents only when the policy selects delegation.
```

The optional [activation guide](../install/ACTIVATION-INSTALL.md) offers a
user-invocable `/pilotfish` skill and a one-line CLI wrapper, with an
approval-gated AI install contract. Both remain explicit opt-ins, not cue-free
dispatch; the wrapper can optionally mention an already installed Baton skill.

| Work shape | Expected owner |
|---|---|
| Small, local, stable work or one tightly coupled unknown bug | Main session |
| Stable multi-file mechanical repetition with a complete one-shot brief | `mech-executor` |
| Approved implementation requiring local judgment | `executor` |
| Security-sensitive implementation after approval | `security-executor` |
| Risk-triggered Plan or outcome challenge | `plan-verifier`, `security-reviewer`, or `verifier` |

The [cue-free evidence](../benchmarks/spontaneous-dispatch/README.md) records
where automatic dispatch did and did not occur. Those observations are bounded
examples, not a dispatch rate or proof of the active system-prompt bytes.

## Configuration and compatibility

| Situation | What to check |
|---|---|
| Custom configuration root | Every `~/.claude/` path moves under `CLAUDE_CONFIG_DIR`; the installer resolves it before writing |
| Project-level `CLAUDE.md` | Claude Code stacks project and user memory; pilotfish never writes into the project |
| Custom `Explore` role | Pins reconnaissance to Haiku, but unlike the built-in role it loads user memory; the policy self-disables inside subagent roles to limit that overhead |
| `availableModels` allowlist | Include `opus`, `fable`, `sonnet`, `haiku`, and the selected main-model value or role aliases may silently inherit the main model |
| Managed or enterprise settings | Managed models, allowlists, and same-name agents outrank the user-level install; pilotfish does not bypass them |
| `claude-router` | Keep `forceRoute` off because it overrides agent frontmatter; `restoreDelegation` strips the separately tracked delegation injection |
| Delegation-planning skills | Tools such as [Baton](https://github.com/cablate/baton) may shape work topology; pilotfish still owns named roles, model routing, approval, and verifier contracts |

## Tuning

| Goal | Adjustment |
|---|---|
| Reduce quota use | Use `/model opusplan`; keep reconnaissance and mechanical roles at their shipped low effort |
| Increase main-session judgment | Start at `high` effort and lower it only when quota or latency matters more |
| Change one role's tier | Edit only that agent file's `model:` frontmatter; the policy names roles, not models |
| Keep more work inline | Ask the main session to work inline; this disables optional execution delegation, not mandatory risk review |
| Understand spawn overhead | Every agent starts a fresh context and pays reconstruction plus integration cost; dispatch only when the combined benefit is positive |

Model economics, official mechanisms, and measured limitations are documented
in [research](./research.md), the [design rationale](./design.md), and the
[behavioral benchmarks](../benchmarks/dispatch-brake/README.md).

## Long runs and verification

| State | Meaning |
|---|---|
| `AUTO` | Continues reversible work inside approved scope; it grants no new commit, publish, install, destructive, external-action, or spending authority |
| `ASK` | Pauses for decisions through native input or `PAUSED_NEEDS_USER` |
| P0 | Freezes the affected slice and its dependants |
| P1 or introduced P2 | Must be fixed within approved scope or paused; P3/P4 are advisory |
| `verifier` result | Evidence for main-session judgment, never automatic scope or implementation authority |

Normal verification is one complete pass plus one targeted recheck after a
reproduced blocker is fixed. Long-running commands stay owned by the main
session; leaf agents return the exact command and working context instead of
detaching a process.

## Disable, update, or uninstall

| Action | Method |
|---|---|
| Update | Re-run the pinned install prompt and follow the runbook's **Updating an existing install** section |
| Disable optional execution delegation | Ask the main session to work inline |
| Disable pilotfish for one repository | Launch that repository with a separate `CLAUDE_CONFIG_DIR` that has no pilotfish policy block |
| Disable the policy globally | Remove or comment the `pilotfish:begin/end` block, then start a new session |
| Uninstall | Follow the runbook's **Uninstall** section so agent files and settings backups are handled safely |
