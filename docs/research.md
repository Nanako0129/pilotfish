# Fable 5 Multi-Model Orchestration — Research Report

> 繁體中文原版：[research.zh-TW.md](./research.zh-TW.md)（this is a faithful English translation）

## Purpose

This document collects a sourced research pass from early July 2026 on "how to maximize the value of Claude Fable 5": Fable 5's real strengths versus Opus 4.8 and the scenarios where it's wasteful, the quota economics of Claude subscriptions, the multi-model orchestration mechanisms Claude Code officially provides, and the community's measured numbers and patterns. pilotfish's three-layer architecture (see [design.md](./design.md)) is the applied conclusion of this research. Method: four parallel research agents (official docs, community patterns, subscription economics, Claude Code mechanisms) plus a verification pass against code.claude.com official documentation; data current as of 2026-07-09.

## Contents

- [Fable 5: positioning and strengths](#fable-5-positioning-and-strengths)
- [When not to use Fable 5](#when-not-to-use-fable-5)
- [Subscription quota economics](#subscription-quota-economics)
- [Official Claude Code mechanisms](#official-claude-code-mechanisms)
- [Community measurements and patterns](#community-measurements-and-patterns)
- [Effort tiering](#effort-tiering)
- [Generational shift in prompting](#generational-shift-in-prompting)
- [Sources](#sources)

## Fable 5: positioning and strengths

| Item | Value |
|---|---|
| Model ID | `claude-fable-5` |
| API pricing | $10 / $50 per MTok (2× Opus 4.8) |
| Context / output | 1M (default is the maximum) / 128K |
| Tokenizer | Same as Opus 4.8 (token counts roughly unchanged) |
| Release | GA 2026-06-09; briefly pulled under export controls, restored 07-01 |
| Data retention | Mandatory 30 days — ZDR orgs get 400 on every request |

The official prompting guide lists seven advantage areas, under one core principle: **"the longer and more complex the task, the larger Fable 5's lead."**

| Advantage area | Notes |
|---|---|
| Long-horizon autonomy | Goal-directed runs sustained over days |
| First-shot correctness | Well-specified complex problems done right the first time |
| Vision | Dense technical diagrams; proactively uses bash/crop tools on blurry or flipped images |
| Enterprise workflows | End-to-end financial analysis, spreadsheets, decks, documents |
| Code review & debugging | Bug-finding recall clearly above Opus 4.8, including repo-history search |
| Ambiguity | Notably better at navigating under-specified asks |
| Delegated collaboration | Dispatching and sustaining parallel subagents is markedly more reliable — a born orchestrator |

Representative benchmarks: SWE-Bench Pro 80.3% (Opus 4.8: 69.2%), Cognition FrontierCode 29.3% (Opus 4.8: 13.4%) — both are Anthropic-self-reported figures (own scaffolding / system card), not independently verified.

## When not to use Fable 5

| Scenario | Why | Use instead |
|---|---|---|
| Routine feature work, focused debugging, test generation, routine PR review | Small gap vs Opus at 2× the price | Opus 4.8 |
| High-volume, latency-sensitive pipelines | High-effort single requests can run minutes | Sonnet / Haiku |
| Security work (defensive included) | Safety classifiers misfire on benign work (<5% of sessions, but enough to break a task mid-run) | Pin to Opus 4.8 |
| ZDR organizations | 30-day retention is a hard requirement | Unavailable |
| Mechanical, token-heavy work | Renames, test runs, formatting don't need frontier reasoning | Haiku / Sonnet |

> **Tip:** The community's consensus escalation rule: "start with the cheapest model that reliably does the job, and escalate to Fable 5 only when Opus 4.8 visibly fails, loses the plan mid-task, or burns more total tokens through retries."

## Subscription quota economics

| Mechanism | Detail |
|---|---|
| Two-layer limits | 5-hour rolling window + weekly cap; the pool is shared across Claude Code / Claude.ai / Cowork |
| Two weekly buckets | A shared "all models" bucket + an **additional Sonnet-only bucket** (since Nov 2025) — Sonnet usage counts against the shared bucket too (current builds reportedly drain both), so it's not a fully separate pool, but it does materially extend what Sonnet work can draw |
| Fable 5 multiplier | Official UI wording: "Uses your limits ~2x faster than Opus"; heavy agentic use burns much steeper in practice (one extreme report: a Max $200 user exhausting the 5-hour window in 13 minutes) |
| Relative unit price (API proxy) | Fable 5 = 2× Opus; Sonnet 5 standard ≈ 0.6× ($3/$15; introductory $2/$10 through 2026-08-31, ≈ 0.4×); Haiku 4.5 ≈ 0.2× |
| Official stance | Absolute token numbers per plan were never published; only the plan multipliers (Max 5x/20x) and the ~2× Fable rate are official |

Fable 5's subscription timeline (as of 2026-07-09):

| Date | Event |
|---|---|
| 2026-06-09 | GA; included free in Pro/Max/Team (weighted ~2× Opus) |
| 2026-06-12 | Export-control suspension |
| 2026-07-01 | Restored, with a "max 50% of weekly limit" cap |
| 2026-07-07 | Official five-day extension of subscription inclusion |
| After 2026-07-12 | Leaves subscription limits: prepaid usage credits at API rates ($10/$50) required; Anthropic states the goal is to restore it as a standard plan feature once capacity allows |

> ⚠️ **Warning:** This is exactly why the fallback design is non-negotiable. Per the documented rule, `best` resolves to the latest Opus once an account loses Fable 5 access; the June 2026 outage behaved consistently with this — a notice banner plus new sessions automatically continuing on Opus, while **users who had pinned the full model ID got hard 404s**. But the exact UI at the 7/12 billing boundary (auto-degrade, error, or a credits prompt) is unpublished — and `fallbackModel` explicitly never triggers on billing-class errors, so it cannot catch this case. Worst case is one manual switch.

## Official Claude Code mechanisms

All verified line-by-line against official docs (code.claude.com — sub-agents, model-config, settings pages):

| Mechanism | Detail |
|---|---|
| Subagent `model` frontmatter | Accepts aliases (`sonnet`/`opus`/`haiku`/`fable`), full model IDs, `inherit` (the default when omitted) |
| Subagent `effort` frontmatter | `low`/`medium`/`high`/`xhigh`/`max`, overrides session effort per agent |
| Global agents directory | `~/.claude/agents/` (user level); project level is `.claude/agents/`; same-name conflicts resolve by scope priority |
| Model resolution order | `CLAUDE_CODE_SUBAGENT_MODEL` env → Agent tool's per-invocation `model` param → frontmatter → main conversation model |
| `best` alias | Fable 5 where the org has access, otherwise latest Opus — the built-in frontier-degradation mechanism |
| `fallbackModel` (settings) / `--fallback-model` | An ordered switch chain; fires on overload/unavailability (never on auth/billing/rate-limit errors), with a notice |
| `opusplan` alias | Opus thinks in plan mode, auto-switches to Sonnet for execution — the built-in "strong model thinks, cheap model acts" |
| `availableModels` (settings) | An allowlist constraining the main session, subagent frontmatter, and Task model params alike; values outside it are silently skipped in favor of inheritance |
| `[1m]` suffix | Enables 1M context; documented for `sonnet`/`opus`/`opusplan` aliases and full model IDs — `best` is not listed (empirically `best[1m]` doesn't error, but plain `best` is recommended; Fable 5 is 1M by default anyway) |
| CLAUDE.md and models | CLAUDE.md **cannot** change the main model (settings / `/model` / `--model` do) — CLAUDE.md governs delegation behavior policy |
| Built-in Explore agent | Since v2.1.198 it inherits the main conversation model (Opus-capped on the Claude API); a same-name user-level `Explore.md` overrides it back to Haiku |
| Version pinning | `ANTHROPIC_DEFAULT_OPUS_MODEL` etc. pin aliases to specific versions (relevant for third-party provider deployments) |

## Community measurements and patterns

| Pattern / measurement | Numbers or approach | Source |
|---|---|---|
| **Official first-party benchmark** (2026-07-08) | Fable 5 orchestrator + Sonnet 5 workers: **96% of all-Fable performance at 46% of the cost** on BrowseComp (86.8% vs 90.8% accuracy, $18.53 vs $40.56/problem); the inverse advisor pattern (Sonnet executor consulting a Fable advisor): ~92% at ~63% on SWE-bench Pro — the orchestrator split wins on both axes | Anthropic (@ClaudeDevs thread; [multi-agent docs](https://platform.claude.com/docs/en/managed-agents/multi-agent)) |
| 12-worker audit cost comparison | All-Fable $14.50; Fable+Sonnet $6.10 (−58%); Fable+Haiku $3.70 (−74%); orchestrator premium only $1.75 | Developers Digest |
| Token-cost-reduction claims | Orchestrator + cheap subagents commonly claimed at 5–10×; individual claims up to −90% | Various community posts |
| Explore telemetry | ~36% of API calls in Sonnet-selected sessions actually ran on Haiku (old built-in Explore behavior) — proof that cheap exploration is a huge volume | mirin.pro |
| Marketplace tiering conventions | Tier 0 Fable (longest horizon) → Tier 1 Opus (architecture/security/critical) → Tier 3 Sonnet (docs/tests) → Tier 4 Haiku (fast ops) | wshobson/agents (199 agents) |
| Handoff pattern | Five-role pipeline (ORCHESTRATOR/SCOUT/GUARD/BUILD/CHECK) exchanging `.handoff/` JSON files — auditable, resumable | clouatre.ca |
| Mechanical discipline | PreToolUse "Spawn Guard" blocks under-specified delegations, Stop hook blocks unfinished wrap-ups — hooks enforce what prompts only suggest | Rylaa/fable5-orchestrator |
| Security workers pinned to Opus | The top HN complaint was Fable 5 security work getting intercepted by classifiers and answered by a fallback; the fix is routing security work to Opus from the start | Hacker News |

## Effort tiering

Effort is the second-biggest quota lever, and Fable 5's guidance **differs** from the Opus 4.7/4.8 generation:

| Target | Recommended effort | Why |
|---|---|---|
| Fable 5 main session | `high` (the default) | Official: high for most tasks; Fable 5 at low effort already often exceeds previous-gen xhigh |
| Fable 5 longest-horizon tasks | `xhigh` | >30-minute, million-token-budget runs; pair with a large `max_tokens` (64K up) |
| `max` | Rarely | Diminishing returns, prone to overthinking |
| Recon / mechanical subagents | `low` | High-volume, low-judgment work; low effort = fewer tool calls and less preamble |
| Judgment executors / verifier | `medium` | The quality-cost balance point |
| Security executor | `high` | Correctness over cost |

## Generational shift in prompting

| Finding | Applied implication |
|---|---|
| Over-prescriptive prompts/skills written for previous models **reduce** Fable 5 output quality | Subtract, don't add: state goals and constraints, delete step-by-step scaffolding |
| A well-specified single first turn performs best | Delegation rule: one-shot specs — goal, constraints, done-criteria, paths |
| "Give the reason, not only the request" measurably helps | Every delegation spec includes the why |
| Fresh-context verifiers beat self-critique (official wording) | The `verifier` role is the core of the quality gate |
| Requiring progress claims to be audited against tool results nearly eliminates fabricated status reports | Written into the executor/verifier system prompts |
| Asking the model to restate internal reasoning triggers the `reasoning_extraction` refusal category | Policy and agent prompts avoid such instructions |

## Sources

| Category | Links |
|---|---|
| Official | [Introducing Claude Fable 5](https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5.md) · [Launch announcement](https://www.anthropic.com/news/claude-fable-5-mythos-5) · [Prompting Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5.md) · [Effort](https://platform.claude.com/docs/en/build-with-claude/effort.md) · [Redeploying Fable 5](https://www.anthropic.com/news/redeploying-fable-5) · [Limits update](https://www.anthropic.com/news/higher-limits-spacex) · [Decoupling the brain from the hands](https://www.anthropic.com/engineering/managed-agents) |
| Claude Code docs | [Subagents](https://code.claude.com/docs/en/sub-agents) · [Model config](https://code.claude.com/docs/en/model-config) · [Settings](https://code.claude.com/docs/en/settings) |
| Subscription & limits | [Models, usage and limits in Claude Code](https://support.claude.com/en/articles/14552983) · [What is the Max plan](https://support.claude.com/en/articles/11049741) · [BleepingComputer: not permanently leaving](https://www.bleepingcomputer.com/news/artificial-intelligence/claude-fable-5-isnt-permanently-leaving-subscriptions-anthropic-says/) · [Forbes: five-day extension](https://www.forbes.com/sites/sandycarter/2026/07/07/claude-fable-5-extends-by-five-more-days-10-moves-to-make-now/) |
| Community measurements | [Developers Digest: orchestrator playbook](https://www.developersdigest.tech/blog/fable-5-orchestrator-model-playbook) · [mirin.pro: Haiku telemetry](https://mirin.pro/blog/claude-code-subagents-haiku-telemetry/) · [Upstash: cost control](https://upstash.com/blog/keep-claude-fable-5-costs-under-control) · [TrueFoundry: limits measured](https://www.truefoundry.com/blog/claude-code-limits-explained) |
| Community patterns | [Rylaa/fable5-orchestrator](https://github.com/Rylaa/fable5-orchestrator) · [wshobson/agents](https://github.com/wshobson/agents) · [clouatre.ca: subagent architecture](https://clouatre.ca/posts/orchestrating-ai-agents-subagent-architecture/) · [MindStudio: orchestrator policy](https://www.mindstudio.ai/blog/smart-orchestrator-cheaper-sub-agent-models-claude-code) · [HN discussion](https://news.ycombinator.com/item?id=48752030) |
