# Stable mechanical-work control

```text
Apply one fully specified mechanical change to every file in src/adapters: normalize(record) must return a new object that preserves all fields, trims record.label, and sets enabled to true only when record.enabled is true or the string "true". Keep each adapter self-contained; do not add a shared helper, change exports, or edit tests. Run the focused and full test suite. Do not optimize for or against delegation; follow the active orchestration policy.
```
