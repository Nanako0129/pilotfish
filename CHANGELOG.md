# Changelog

All notable changes to pilotfish. The installed version is stamped inside the policy block in `~/.claude/CLAUDE.md` (`<!-- pilotfish vX.Y.Z -->`); installs older than v1.1.0 carry no stamp.

## Unreleased

Fix the main-loop/executor tier collapse reported in [#18](https://github.com/Nanako0129/pilotfish/issues/18). The shipped roles assumed a Fable-5 coordinator with Opus as an execution tier beneath it; on any plan where `best` falls back to Opus (no Fable 5 access, or usage-credit billing), the default `executor` was also pinned to Opus, so every delegated implementation task became Opus talking to Opus, paying subagent coordination and context-reconstruction overhead for zero capability gain. `executor` now defaults to Sonnet. `verifier`, `plan-verifier`, `security-reviewer`, and `security-executor` stay on Opus: they are the last automated check before a claim, a Plan, or security-sensitive work is accepted, so keeping them a tier above `executor` buys a genuine cross-tier review instead of a model checking its own output. No role agent should default to the same tier as the main session; that principle, and the reasons the four Opus roles are exempt, are documented in the README role table, the fallback story, a new FAQ entry, and `docs/design.md`. An installer profile or main-loop autodetection was considered and rejected: `best` is dynamic at runtime, and Claude Code does not expose the billing information needed to reliably tell Fable-5 and usage-credit sessions apart.

Changing `executor`'s frontmatter changes the generated `--agents` payload used by the Baton exact-byte compatibility gate. `benchmarks/baton-compatibility/final-gate-snapshot/agents.json` is regenerated to stay byte-identical with current templates, and `results.json`'s `release_candidate_agents_json_sha256` / `final_gate_agents_json_sha256` / `final_gate_candidate_agents_json_sha256` are updated to match. The already-recorded `final_gate` transcript, turns, costs, and verdicts are unaffected: that fixture's `agent_calls` never dispatched `executor` (only `scout`, `plan-verifier`, `mech-executor`, and `verifier` ran), so nothing in the observed run used the changed role. The prior hash is preserved as `final_gate_agents_json_sha256_pre_issue_18` and the change is disclosed under `post_gate_role_frontmatter_change`; a fresh live Gate exercising the new Sonnet `executor` specifically has not been separately run.

A new policy contract test, `test_no_role_collapses_onto_the_main_loop_tier`, locks the eight roles' expected model tiers so this cannot regress silently.

## v1.3.0 — 2026-07-20

Close the recurrence blind spot in execution dispatch. Per-decision brakes miss same-shape small tasks that arrive one at a time because each instance can individually pass the direct-work test. A field attribution of two long remora sessions routed to GPT-5.6 ([報告](./docs/field-report-tokscale-2026-07.zh-TW.md), proposed in [#15](https://github.com/Nanako0129/pilotfish/issues/15)) measured the aggregate observation: 1,267 direct main-session edits alongside 12 delegations in one 26-hour session, with the frontier tier consuming 92% of all output tokens while milestone worktree fan-out was working correctly. Those exact observations motivate backend-neutral guardrails, not native-Claude numeric thresholds or efficiency claims. The policy now permits batching only when the remaining items are independent and the same shape and one stable one-shot brief fully specifies goal, constraints, done criteria, ownership, and per-item acceptance; delegation remains conditional, while main retains diagnosis, exceptions, integration, and acceptance. An already-diagnosed review finding with a known remedy is Execution work rather than unknown-bug discovery, but it is still delegated only when the stable-brief and net-benefit conditions hold.

Place fresh outcome verification at the smallest coherent integration boundary where the complete claim can be independently refuted. The same field data showed 201 outcome-verifier passes averaging under six minutes — an effective gate (42% REFUTED) applied at the wrong granularity — and 24 plan-verifier readiness passes for 2 Plans at a 71% REVISE rate. Tests, builds, and static checks are intermediate evidence during an iteration, not a universal replacement for fresh verification; security, cross-language or FFI, serialization or pre-aggregation, irreversible, and integration-blocking changes are verified earlier. A substantially unchanged Plan is not resubmitted; if convergence still fails, the main session simplifies the Plan, surfaces the blocker to the user, or defers blocked scope rather than silently overriding it. Policy tests lock these guardrails.

Complete the Baton compatibility gate evidence for the amended policy. The successful native first-party Claude run used Claude Code 2.1.215 with Fast mode off and base HEAD `a38dd2dde000441b24881fa49495e545ff21b9e6`. Baton loaded, two background scouts ran without pre-approval writes, the read-only Opus `plan-verifier` returned `READY`, the foreground Sonnet `mech-executor` wrote only `REPORT.md`, `npm test` passed, and the foreground Opus outcome `verifier` returned `CONFIRMED`. The run took 323.978 seconds wall time across 458.056 seconds of API time, 6 API turns, 2 CLI invocations, and reported $3.5088455 in the client cost field; background result collection was exercised. The final transcript and both prompt hashes, policy/snapshot hash, and shell-stripped agents hash are recorded in `results.json`. A non-blocking verifier note records that `architecture.md:63` is blank while `:62` fully supports the claim; no fixture change followed `CONFIRMED`.

The Gate is compatibility/provenance only and makes no native-Claude efficiency, latency, cost, or A/B claim. A prior attempt against the same policy bytes is retained as `failed_candidate_gate`: its old Turn 1 prompt omitted the mandatory closing outcome-verifier requirement and the run ended `budget_exhausted` at 218.040 seconds, 13 API turns, and $4.12912975. The 2026-07-20 candidate at commit `40f3815` remains `superseded_candidate_gate`; the v1.2.1 gate remains `previous_release_gate`, and v1.2.0 remains summary-only `historical_release_gate`.

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
