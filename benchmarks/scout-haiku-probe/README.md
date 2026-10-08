# Scout Haiku probe

[繁體中文](./README.zh-TW.md)

This probe decided whether `scout` should return from Sonnet to Haiku. On 2026-09-26 `scout` moved to Sonnet because of secondhand reports that Haiku hallucinated too often. Nobody recorded a failing case. Haiku 5.5 shipped on 2026-10-07, and this probe measures the failure that was reported: wrong answers and fabricated `file:line` citations in reconnaissance.

## Method

| Item | Value |
|---|---|
| Date | 2026-10-08 |
| Client | Claude Code 2.1.287 for the probe runs. Models were requested by full ID, because that client still resolved the `haiku` alias to Haiku 4.5 |
| System prompt | The body of `templates/agents/scout.md` at `aa595da`. It was the Sonnet-era prompt, and only the model line differs from the shipped one |
| Tools | `--tools Read,Glob,Grep` (scout's allowlist) |
| Isolation | `--setting-sources project --strict-mcp-config`, run in a `git archive aa595da` snapshot, so no user hooks, plugins, MCP servers or untracked files |
| Questions | Two rounds of 10: [round 1](./task-round1.txt) (lookups) and [round 2](./task-round2.txt) (12-item enumeration, a cross-function trace, an exact count, facts from a zh-TW document). Six questions are traps that ask about something that does not exist, and several have a near-miss decoy |
| Configurations | Haiku 5.5 at `low`, `medium`, `high`, `xhigh` and `max`; Sonnet 5.5 at `low` (the scout of that time); Haiku 4.5 at `low` (the model replaced on 2026-09-26). Each ran twice per round, for 40 answers per configuration |
| Grading | Every main answer against the answer keys ([round 1](./answer-key-round1.md), [round 2](./answer-key-round2.md)). Every auxiliary `file:line` citation in every answer was opened and compared with the snapshot |

## Results

Per-run grades, token counts and defects are in [`results.json`](./results.json). Every final answer is in [`answers/`](./answers/).

| Configuration | Wrong or incomplete answers (of 40) | Fabricated citations | Other defects | Mean duration | Mean input / output tokens |
|---|---|---|---|---|---|
| Sonnet 5.5 `low` | 1 | 0 | 0 | 34 s | 79k / 4.9k |
| Haiku 5.5 `low` | 0 | 0 | 0 | 29 s | 113k / 6.9k |
| Haiku 5.5 `medium` | 0 | 0 | 1 | 37 s | 223k / 7.7k |
| Haiku 5.5 `high` | 0 | 0 | 0 | 59 s | 406k / 11.5k |
| Haiku 5.5 `xhigh` | 0 | 0 | 1 | 87 s | 447k / 19.1k |
| Haiku 5.5 `max` | 0 | 0 | 0 | 189 s | 459k / 45.2k |
| Haiku 4.5 `low` | 2 | 0 | 2 | 110 s | 938k / 9.5k |

Input tokens include cache reads. "Other defects" are an incoherent sentence, a misquoted hash abbreviation and off-target citations. In each case the main answer was right.

Effort above `low` bought Haiku 5.5 no measured main-answer accuracy. It cost time and tokens, and the two configurations with an other defect, `medium` and `xhigh`, are both above `low`. That is why the shipped role keeps `effort: low`.

## Limits

- **Weak discriminator.** Haiku 4.5 nearly passed as well, so this probe did not reproduce the reported failure on any model. It shows no measured accuracy gap on bounded reconnaissance. It does not show that Haiku never hallucinates.
- Anthropic's [Haiku 5.5 system card](https://www.anthropic.com/document/claude-haiku-5-5-system-card) (2026-10-07) says Haiku 5.5 hallucinates about as much as Haiku 4.5, and that Sonnet 5.5 is strictly better on input hallucination (misrepresenting files or tool output). Those are general measurements, not scout's workload, but they are the reason to keep orchestrator-side checks on single-fact decisions.
- One repository, 20 questions, two repetitions per configuration.

## Shipped-role check

Run on Claude Code 2.1.294 with the branch's `plugin/` loaded via `--plugin-dir`, and `--output-format stream-json --verbose`. The main session issued an `Agent` `tool_use` `toolu_017ZLSiKQWjARhKAKtYfaKka` with `subagent_type` `pilotfish:scout`. The child assistant message with that `parent_tool_use_id` reported `message.model` `claude-haiku-5-5`. Session-wide `modelUsage` was not used as evidence, because Claude Code's own auxiliary calls also use the Haiku tier.

## Reproduce

```bash
bash benchmarks/scout-haiku-probe/run.sh benchmarks/scout-haiku-probe/task-round1.txt /tmp/scout-probe/round1
bash benchmarks/scout-haiku-probe/run.sh benchmarks/scout-haiku-probe/task-round2.txt /tmp/scout-probe/round2
```

Each call is paid: 14 per round. The script exits non-zero if any call failed. Each committed file in `answers/` is the `result` field of one output JSON. The answer keys hold only at ref `aa595da`, the default third argument.
