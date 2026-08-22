# Plugin beta lineage

This Plugin beta uses dromsak's PR #11 only as a design and provenance reference. Current policy and role semantics derive from repository v1.3.10 at `7a7f71b327f079fecbf29fa91e444b9a6180c31c`; historical Plugin wording is not a policy source.

| Provenance reference | Contribution lineage carried into the new artifact |
|---|---|
| `f636e298590f0f71b21c8ff084930da224a1c872` | PR #11 Plugin packaging, marketplace layout, Session Skill, and namespaced-agent design |
| `647fd5b430804d77c6e43eeec5e733b450af8735` | PR #11 explicit agent routing metadata |
| `5067870b1fd5db5bf9e6a3cd0021ec5a22084257` | PR #11 portability finding that an interpreted guard should not be shipped |
| `71d92bc5afdd60c34557764304d058bf41535128` | PR #11 rebase work preserving phase, security, and verification gates |

pilotfish Plugin beta is supported on macOS and tested with Claude Code 2.1.239. Its SessionStart hook supplies the bounded policy only when no legacy global pilotfish policy is detected. It does not claim stable ambient reliability, cross-platform support, cross-version compatibility, runtime namespace-collision proof, equivalence to the legacy global install, or authority beyond the existing pilotfish gates.
