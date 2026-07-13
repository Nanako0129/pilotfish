# Changelog

All notable changes to pilotfish. The installed version is stamped inside the policy block in `~/.claude/CLAUDE.md` (`<!-- pilotfish vX.Y.Z -->`); installs older than v1.1.0 carry no stamp.

## v1.1.6 — 2026-07-13

Add a [Baton](https://github.com/cablate/baton)-style dispatch brake before role routing. Unstable outcomes, dependence on evolving main-session evidence, overlapping writes, and missing closure ownership are hard blockers. All other eligible work is chosen by net benefit across model cost, scarce context, elapsed time, isolation, and verification rather than requiring delegation to win every axis. Direct execution being slightly faster is not a veto when a bounded cheap worker materially saves frontier-model usage.

Single unknown bugs now keep root-cause discovery, trace-driven debugging, the first minimal fix, and live verification in one orchestrator reasoning chain instead of becoming a sequential scout-to-executor pipeline. Read-only repository fan-out is opt-in: small bounded scans stay inline, while substantial independent scans, overlapable external latency, or deliberately independent perspectives can still fan out. Stable multi-file repetition retains an explicit path to `mech-executor`.

This release publishes the complete bilingual experiment behind the change: negative and positive-control fixtures, neutral task prompts, rejected policy iterations, exact Agent tool inputs, normalized tool traces, model usage, timing, client-reported cost fields, raw-stream hashes, commands, correctness results, and limitations. The controls expose both failure directions: a hard direct-speed veto suppressed useful delegation, while a broad independent-surface rule spawned scouts for a handful of short files. The balanced policy kept tightly coupled debugging and small scans inline but still routed a 12-file stable mechanical edit to the cheaper worker, reducing the reported cost field by 36.01% with a 7.92% wall-time trade-off in one run.

The report also discloses the limits: each completed condition is a single run, further pilotfish repetitions stopped when Claude quota approached exhaustion, and the separately installed [baton-dispatch](https://github.com/cablate/baton) skill could still override remora's product policy when GPT-5.6 Sol auto-loaded it. The ineffective precedence wording was removed rather than released as an unverified fix.

New policy contract tests lock the dispatch boundary while preserving named-role model ownership, background scheduling for eligible work, worktree isolation, and the fresh-context verifier gate.

## v1.1.5 — 2026-07-13

Fix named-role model routing at the Agent invocation boundary. The orchestration policy now requires calls to every existing named role to omit `model`, leaving the role file's frontmatter as the sole model source. This prevents an invocation alias from silently overriding the intended Haiku, Sonnet, or Opus assignment. Only truly ad-hoc agents with no named role definition may set an explicit invocation model.

This release also recommends a pinned local checkout for one-prompt installation and updates. The reviewed runbook and templates are read from the same release checkout, avoiding mutable cross-fetches and preserving Claude Code's WebFetch prompt-injection protection instead of asking users to bypass it.

New dependency-free policy tests lock the version stamp, named-role model ownership contract, ad-hoc exception, role frontmatter, and pinned README install commands together.

## v1.1.4 — 2026-07-13

Fix foreground-only delegation caused by an underspecified parallel-agent policy. The orchestrator now schedules by immediate data dependency: independent work and every independent fan-out call use `run_in_background: true`, while foreground execution is reserved for a result required by the very next main-session action when no other useful work can proceed. Background results still must be collected before dependent work or the final answer.

## v1.1.3 — 2026-07-12

Community-driven patch. Re-run the install prompt to upgrade.

| Change | Credit |
|---|---|
| **The orchestration policy now covers running agents in parallel** — three rules earned in a real four-executor fan-out (long-form rationale in [#7](https://github.com/Nanako0129/pilotfish/pull/7)): every writing agent in a parallel batch gets its own worktree, and the orchestrator harvests each worktree's changes on completion; a yielded agent (detached launch, PID + log path) is a handoff the orchestrator must monitor and resume, not a result; agent liveness is probed with a message, never diagnosed from host signals (no local CPU + a stale transcript is not a stuck agent). | [@dromsak](https://github.com/dromsak) (#7) |

The liveness rule's probe semantics were verified empirically before merging (a busy agent queues the probe; a completed one is resumed by it), which caught that the exact response strings vary across harness versions — the shipped rule describes the behavior instead of quoting strings.

## v1.1.2 — 2026-07-10

Hardening patch. Re-run the install prompt to upgrade.

| Change | Credit |
|---|---|
| **The six roles are now hard leaf agents.** The four executor roles get `disallowedTools: Agent, Workflow`; `verifier` extends its existing read-only exclusions with the same; `scout`/`Explore` were already leaves via their `tools` allowlist. Each also carries an explicit "you are a leaf agent" line so a genuinely mis-routed task is reported back instead of re-delegated. | [@dromsak](https://github.com/dromsak) (#6) |

This replaces v1.1.1's prompt-only guard with capability removal. The prompt guard put the routing table into every subagent's context, so a `mech-executor` could pattern-match its own task and re-delegate — observed cascading four levels deep in a real incident. Verified before merge: with the prompt guard a nested role still spawned (a haiku scout ran real work); with `disallowedTools` the spawn is blocked and the role does the work itself.

## v1.1.1 — 2026-07-10

Community-driven patch. Re-run the install prompt to upgrade.

| Change | Credit |
|---|---|
| Policy block now forbids subagent roles from spawning further subagents — delegation is a main-session-only concern. The recursive-spawn risk was verified empirically (a sonnet role successfully dispatched a haiku role) before merging | [@nicofirst1](https://github.com/nicofirst1) (#3, #5) |
| `executor` / `mech-executor` no longer babysit long-running processes: launch detached (nohup + log), one sanity check, then yield with PID + log path for the orchestrator to monitor | [@nicofirst1](https://github.com/nicofirst1) (#2, #4) |
| Follow-up to the above: a detached launch must be reported as a handoff, not a completed verification, when done-criteria depend on the process outcome | maintainer |
| Installer Step 4 verification updated for Claude Code 2.1.198+ (the `/agents` wizard was removed); verify via `/model` and by asking Claude which subagent types are available | [@zxcj04](https://github.com/zxcj04) (#1) |

## v1.1.0 — 2026-07-09

Security, accuracy, and update-flow release. Re-running the install prompt upgrades in place.

### Security & trust

| Change | Why |
|---|---|
| New **Trust & security** README section, with a tag/SHA-pinned install variant | `main` can change between review and install (TOCTOU); pinning makes what-you-reviewed = what-installs |
| Runbook: templates must be fetched from the same pinned ref as the runbook | Pinning now covers the actual installed bytes, not just the instructions |
| `scout` / `Explore` switched from a `disallowedTools` denylist to a positive `tools: Read, Glob, Grep` allowlist | They previously retained Bash, so "read-only" was prompted, not enforced |
| Runbook detects agent collisions by frontmatter `name:` (not filename) and flags plugin shadowing | Claude Code loads only one definition per name; `executor`/`scout` are common names |

### Behavior & quality

| Change | Why |
|---|---|
| Policy block self-disables for subagent roles | A custom `Explore` loads user memory (the built-in skips it); the policy is main-session-only |
| New policy rule: scout findings are unverified inputs | The verifier gate covers executor output, not reconnaissance |
| `verifier` runs maximum-thoroughness on security-sensitive work | medium-effort verification of high-effort security work was inconsistent |
| Versioning + "Updating an existing install" flow (this release) | Early installs had no way to learn about updates |

### Docs & claim accuracy

| Change | Why |
|---|---|
| Split Anthropic's endorsement (delegation + fresh-context verification) from pilotfish's own cheap-model routing thesis | Attribution honesty |
| 12-worker numbers reframed as an upper-bound, API-dollar experiment, with inline sources | One community experiment ≠ a guarantee; subscription quota ≠ API dollars |
| Explore warning corrected: inherited model is Opus-capped on the Claude API | Precision |
| `best`-alias fallback at the 7/12 boundary restated honestly (documented rule + June outage precedent; boundary UX unpublished; `fallbackModel` never triggers on billing errors) | The boundary hasn't been observed by anyone yet |
| Windows portability note; subscription-vs-API/Bedrock scope note; FAQ rows for spawn overhead, fast off-switch, managed environments, project-CLAUDE.md stacking | Compatibility coverage |

## v1.0.0 — 2026-07-08

Initial public release: three-layer global architecture (settings `best` + `fallbackModel`, six role agents with tiered model/effort bindings, role-based delegation policy), one-prompt agent-guided installer with approval gate and idempotent upgrades, bilingual README, sourced research report and design rationale.
