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

The project-local Baton copy used the installed `SKILL.md` bytes recorded in
`results.json`; its reference files were available but are not duplicated
here. The exact prompts, invocation metrics, rejected user-source attempt,
post-verdict verification correction, and limitations are recorded additively
under `v1_3_2_opus5_release_gate`.
