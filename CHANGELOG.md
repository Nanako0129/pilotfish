# Changelog

All notable changes to pilotfish. The installed version is stamped inside the policy block in `~/.claude/CLAUDE.md` (`<!-- pilotfish vX.Y.Z -->`); installs older than v1.1.0 carry no stamp.

## v1.2.1 — 2026-07-16

Fix the recon-agent results handoff. The orchestration policy now states that a subagent's final message *is* its deliverable and that the orchestrator **pulls** it from the finished task — the harness captures it on completion, the agent never pushes it. The read-only recon and review roles (`scout`, `Explore`, `plan-verifier`, `security-reviewer`) hold positive read-only tool allowlists that exclude outbound messaging, so the orchestrator must never ask one to send, relay, or report back findings already present in completed output, and must never resume or re-dispatch a finished recon agent merely to make those results "return directly." The results already returned, and re-running pays the discovery cost and latency twice. The liveness rule now separates collection from continuation: inspect tracked task state and output first; use the message channel only for liveness, redirection, or genuinely new work. Resuming a custom agent retains its context and creates another run with another final message, so follow-ups remain valid without turning the channel into a result-collection mechanism. `scout` and `Explore` each carry the same per-run, self-contained-deliverable contract. Prompted by an observed session that fanned out three background scouts, asked them to "relay their reports," concluded the findings were unretrievable when the read-only agents could not push, and re-ran all three synchronously — the exact waste the split exists to prevent.

The v1.2.1 release candidate was rerun through the two-turn Baton compatibility Gate with the exact release policy and eight-role payload under Claude Code 2.1.211. Discovery stayed in the main session with a clean tree. The Opus `plan-verifier` returned `REVISE` after finding six incorrect citation ranges; the main session corrected them before explicit approval. Baton then kept the already-contextualized one-file write in the main session, `npm test` passed, `REPORT.md` was the only fixture change, and a fresh Opus outcome `verifier` returned `CONFIRMED`. The run took 368.395 seconds across 17 API turns and reported $3.7104345 in the client cost field. The exact snapshot and hashes are published under `benchmarks/baton-compatibility/`. This fixture did not trigger background recon result collection, so runtime coverage is not claimed for that path; the new deterministic policy test instead locks the collection-versus-continuation contract. The change touches no role model routing, tool allowlist, phase brake, approval gate, or verifier vocabulary.

## v1.2.0 — 2026-07-14

Add phase-aware orchestration informed by [Baton](https://github.com/cablate/baton). Small stable work remains direct. Large, ambiguous, architectural, risky, or cross-surface work can use bounded read-only discovery before its implementation outcome is known; the main session then synthesizes one Plan, may request a fresh readiness review, and waits for explicit approval before writing when the task requires a Plan gate. Execution keeps the strict brake: stable scope, exclusive ownership, constraints, done criteria, integration, and verification.

Single unknown bugs still keep root-cause discovery, trace-driven debugging, the first minimal fix, and live verification in one orchestrator reasoning chain instead of becoming a sequential scout-to-executor pipeline. Large cross-surface investigations may use bounded read-only discovery, but must return to main-session Plan synthesis before any executor starts. Task-local scans stay inline by default; substantial independent surfaces, overlapable latency, or evidence needed to reduce Plan uncertainty retain explicit discovery paths. Stable multi-file repetition retains an explicit path to `mech-executor`.

Fresh verification is split by capability instead of relying on mode text. The new `plan-verifier` has a positive read-only tool allowlist and returns `READY` / `REVISE` before approval; the existing `verifier` remains read-and-run after implementation and returns `CONFIRMED` / `REFUTED`. Security follows the same boundary: the new read-only `security-reviewer` gathers pre-approval evidence, while the write-capable `security-executor` accepts only an approved stable implementation contract. Plan synthesis and final judgment stay in the main session, and named-role model ownership remains unchanged.

Fix the long-running-process handoff based on four direct harness trials reported by [@dromsak](https://github.com/dromsak) in PR #10. Every Bash-capable leaf role (`mech-executor`, `executor`, `verifier`, `security-executor`) now rejects `nohup`, `setsid`, trailing `&`, and subagent-side background commands: detaching escapes task tracking and orphans the result. A subagent that cannot finish a foreground command within 10 minutes reports the exact command, absolute worktree or working directory, required environment, and input paths; the main orchestrator owns tracked background execution in that same context rather than the parent checkout. Agents likely to run a long command must themselves be spawned in the background, because a timeout-promoted command in a foreground-spawned agent is terminated shortly after that agent returns.

This release publishes the complete bilingual experiment behind the dispatch decision: negative and positive-control fixtures, neutral prompts, rejected policy iterations, exact Agent tool inputs, normalized traces, model usage, timing, client-reported cost fields, raw-stream hashes, commands, correctness results, and limitations. A hard direct-speed veto suppressed useful delegation; the balanced policy still routed a stable 12-file mechanical edit to the cheaper worker. In the execution-only segment, before the release policy's required outcome-verifier pass, the delegated run reported 36.01% less cost with a 7.92% wall-time trade-off. This proves the cheaper route remains reachable, not full-lifecycle savings.

The dispatch report now scopes the earlier small-research result correctly. Two scouts were slower and more expensive than direct work on that single task-local fixture, while the early Baton-assisted probes stopped immediately after discovery dispatch and therefore established neither conflict nor end-to-end compatibility. The separate [pilotfish + Baton compatibility gate](./benchmarks/baton-compatibility/README.md) now closes that lifecycle gap under native Claude routing.

Policy contract tests lock the phase boundary, approval gate, planning-skill composition, capability-separated Plan and outcome verification, read-only pre-approval security review, verdict vocabulary, named-role model ownership, background scheduling, worktree isolation, long-process ownership, and fresh-context verification. The final fresh-session two-turn Gate completed zero-write Discovery and main-session Plan synthesis, an Opus `plan-verifier` returning `READY`, explicit approval, a Sonnet `mech-executor` selected by Baton, and a separate Opus outcome `verifier` returning `CONFIRMED`. All three named-role calls omitted invocation-level `model`; `npm test` passed and `REPORT.md` was the only change. The exact tested project policy and eight-role agents JSON are committed under `benchmarks/baton-compatibility/final-gate-snapshot/`, with their recorded hashes locked against current templates except for the inert version-stamp comment: the tested candidate said v1.1.6 and was reclassified as v1.2.0 before release because this is a feature-level orchestration change. The run took 448.148 seconds and reported $3.7890481 in the client cost field; these are single-run observations, not population estimates or an invoice. Rejected or superseded harness runs remain disclosed rather than presented as release evidence.

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
