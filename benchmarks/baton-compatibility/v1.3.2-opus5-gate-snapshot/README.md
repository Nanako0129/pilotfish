# v1.3.2 Opus 5 Baton Gate snapshot

> Evidence only. Do not install these files as the current pilotfish policy.

This directory preserves the changed runtime inputs used by the Opus 5
approval-lifecycle Gate on Claude Code 2.1.219. The orchestration policy was
byte-identical to
[`../v1.3.2-gate-snapshot/CLAUDE.md`](../v1.3.2-gate-snapshot/CLAUDE.md),
so this snapshot reuses that immutable file instead of duplicating it.

| Input | SHA-256 |
|---|---|
| Reused `CLAUDE.md` file bytes | `b42bd2f0d6c4be23472020cc107d6ceb4ab0eb34553ccfcac5fe6e65c9164b4b` |
| `agents.json` file bytes | `61bb008bcc491e0b90c7ed131c090ec196fef22593ae90725baadb87b5a28541` |
| Shell-stripped `agents.json` runtime bytes | `f272948d82cd4320f24ca849f884f5e1b74c04c23d28271753281bfdd9ffcaba` |
| `settings.snippet.json` file bytes | `108da7014d44b2078581f9f98008b6f9d6c7ed08e5c9c7e93a7dd2f083f1a5d9` |

The project-local Baton copy came from
[`Nanako0129/baton@77f12e6`](https://github.com/Nanako0129/baton/tree/77f12e600406065a6e62a22a66347355e278a9d7)
(tree `75a30fb6f54f852aa46b3ab5bbf33d7cbd3513c9`). The installed copy matched
these pinned inputs:

| Baton input | SHA-256 |
|---|---|
| `SKILL.md` | `48b1e573a9e3de85fdb68c433bd47d69add9ec8491613ca304cfcef2326e3d67` |
| `references/dispatch-planning.md` | `91d84a81230a95249e212ee9227d348c8946cde21c4153d8f1c0719d15ae2286` |
| `references/context-and-briefs.md` | `021ecc301ac53c390c513d27ad2bf2b3f390dadb62a3e8d0bc42cfa7ab170a6a` |
| `references/execution-and-verification.md` | `daafef501df071b5846173024f01da01c4ccd52913f1560740844d8e364ed6e7` |
| `references/examples.md` | `b9e7ad77c2e882601338e504d1e2116b51e8cd2c165b60304a06ac8435b6dc73` |
| `references/claude-code-ultracode.md` | `80c9734863fdd42fbdcdc5c0085bc8647d12673c4cfc07d57f90a03ff4a120e1` |
| `references/codegraph.md` | `30d70ea9ac9d739af240a3f9e16e8ba600833cdfa7d9a84dcbfd1319d060485b` |

The exact prompts, invocation metrics, rejected user-source attempt,
post-verdict verification correction, and limitations are recorded additively
under `v1_3_2_opus5_release_gate`.
