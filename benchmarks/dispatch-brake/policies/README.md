# Policy sources used by the dispatch-brake experiment

| Run family | Exact policy source |
|---|---|
| pilotfish baseline | Tag `v1.1.5`, commit `e5b45dd2330b1ba781d9da0f80211dd657d854cf`, `templates/claude-md.orchestration.md` |
| remora baseline | Tag `v0.1.6`, commit `d2ad6e553c48de2b9a6feda199fc6f595882b5dc`, `agents/orchestration.md` |
| pilotfish candidate | [`pilotfish-candidate.md`](./pilotfish-candidate.md) |
| remora candidate | [`remora-candidate.md`](./remora-candidate.md) |
| pilotfish first postpatch | Commit `633336b`, `templates/claude-md.orchestration.md` |
| remora first postpatch | Commit `17b9b90`, `agents/orchestration.md` |
| pilotfish balanced task-local gate | Commit `863b117`, `templates/claude-md.orchestration.md` |
| remora balanced task-local gate | remora commit `e502d91`, `agents/orchestration.md` |
| pilotfish v1.3.1 phase-aware release policy | Current repository `templates/claude-md.orchestration.md`; contract-tested and runtime-gated under [`../../baton-dispatch-effect/`](../../baton-dispatch-effect/). The earlier two-turn approval lifecycle is preserved separately as historical exact-byte evidence under [`../../baton-compatibility/`](../../baton-compatibility/) |

The baseline and balanced task-local policies are pinned to canonical repository commits rather than mutable current files. The development candidates are stored here because they were never canonical product policies. Later positive-control iterations, including the rejected direct-speed veto, broad net-benefit rule, subjective size wording, and unshipped skill-precedence probe, are documented with their observable behavior in [`../positive-controls/`](../positive-controls/). The recorded two-turn lifecycle, exact prompts, content hashes, rejected harness run, and limits belong to the historical policy bytes published in the compatibility Gate; the current phase-aware release policy's activation, dispatch, ownership, collection, and output-shape evidence is published in the dispatch-effect Gate. Raw stream hashes preserve each experiment's identity, and no rejected wording is presented as a shipped product policy.
