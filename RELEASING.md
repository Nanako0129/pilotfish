# Releasing

Maintainer checklist — the three version stamps must move together:

1. Bump `VERSION`.
2. Update the version comment in `templates/claude-md.orchestration.md` (`<!-- pilotfish vX.Y.Z -->`), and mirror the block into your own `~/.claude/CLAUDE.md`.
3. Add the `CHANGELOG.md` entry (what changed, why — users see this during update).
4. Run the dependency-free policy regression suite and inspect the diff:

```bash
python3 -m unittest discover -s tests -v
git diff --check
```

5. Commit, then tag and publish:

```bash
git tag vX.Y.Z
git push && git push --tags
gh release create vX.Y.Z --title "vX.Y.Z" --notes-from-tag  # or paste the changelog entry
```

> **注意 / Note:** If `templates/agents/*.md` changed, keep them byte-identical with `~/.claude/agents/` before committing — the e2e assumption is that templates are the single source of truth.
