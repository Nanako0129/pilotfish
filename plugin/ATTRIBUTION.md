# Experimental Plugin lineage

This brand-new G0 Plugin artifact uses the historical `codex/v2-ambient-spike` branch and dromsak's PR #11 only as design and provenance references. Current policy and role semantics derive from repository v1.3.10 at `7a7f71b327f079fecbf29fa91e444b9a6180c31c`; historical Plugin wording is not a policy source.

| Provenance reference | Contribution lineage carried into the new artifact |
|---|---|
| `f636e298590f0f71b21c8ff084930da224a1c872` | PR #11 Plugin packaging, marketplace layout, Session Skill, and namespaced-agent design |
| `647fd5b430804d77c6e43eeec5e733b450af8735` | PR #11 explicit agent routing metadata |
| `5067870b1fd5db5bf9e6a3cd0021ec5a22084257` | PR #11 portability finding that an interpreted guard should not be shipped |
| `71d92bc5afdd60c34557764304d058bf41535128` | PR #11 rebase work preserving phase, security, and verification gates |

G0 is a macOS-only spike and never installs or loads this Plugin. A disabled hook is not a security guarantee. Plugin-only behavior, coexistence with a global v1 installation, and compact-event source/hash/count evidence are deferred to G1. This artifact makes no ambient reliability, authority, v1-equivalence, or product-readiness claim.
