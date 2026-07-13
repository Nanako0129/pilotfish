# Policy sources used by the dispatch-brake experiment

| Run family | Exact policy source |
|---|---|
| pilotfish baseline | Tag `v1.1.5`, commit `e5b45dd2330b1ba781d9da0f80211dd657d854cf`, `templates/claude-md.orchestration.md` |
| remora baseline | Tag `v0.1.6`, commit `d2ad6e553c48de2b9a6feda199fc6f595882b5dc`, `agents/orchestration.md` |
| pilotfish candidate | [`pilotfish-candidate.md`](./pilotfish-candidate.md) |
| remora candidate | [`remora-candidate.md`](./remora-candidate.md) |
| pilotfish postpatch | Repository `templates/claude-md.orchestration.md` in the commit that publishes this benchmark |
| remora postpatch | remora repository `agents/orchestration.md` in the corresponding dispatch-brake release commit |

The baseline and final policies use their canonical repository files rather than duplicated snapshots. The development candidates are stored here because they were never canonical product policies.
