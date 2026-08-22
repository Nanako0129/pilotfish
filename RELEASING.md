# Releasing

`VERSION` is the single release-version source. The renderer writes that exact value to both `plugin/.claude-plugin/plugin.json` and the Plugin entry in `.claude-plugin/marketplace.json`; never edit either generated version by hand.

1. Set `VERSION`, update the matching version comment in `templates/claude-md.orchestration.md`, and add the release entry to `CHANGELOG.md`.
2. Regenerate Plugin artifacts, then prove they are current:

   ```bash
   python3 tools/render_plugin_spike.py --write
   python3 tools/render_plugin_spike.py --check
   ```

3. Run strict manifest validation and the full dependency-free test suite:

   ```bash
   claude plugin validate --strict .claude-plugin/marketplace.json
   claude plugin validate --strict plugin
   python3 -m unittest discover -s tests -v
   git diff --check
   ```

4. Review the complete diff, commit the release candidate, require a clean worktree, and dry-run the matching Plugin tag:

   ```bash
   claude plugin tag --dry-run plugin
   ```

   The dry-run must report `pilotfish--vX.Y.Z`, where `X.Y.Z` equals `VERSION`. An existing tag or version mismatch is a stop condition; never use `--force` to bypass it.

5. After review and separate release authorization, push the release commit to the repository's default branch and verify the remote branch before creating either tag:

   ```bash
   (
   set -eu
   RELEASE_VERSION=$(tr -d '\n' < VERSION)
   RELEASE_BRANCH=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD)
   RELEASE_BRANCH=${RELEASE_BRANCH#origin/}
   test -n "$RELEASE_BRANCH"
   test "$(git branch --show-current)" = "$RELEASE_BRANCH"
   git push origin "HEAD:refs/heads/$RELEASE_BRANCH"
   git fetch origin "$RELEASE_BRANCH"
   test "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$RELEASE_BRANCH")"
   git tag -a "v$RELEASE_VERSION" -m "pilotfish v$RELEASE_VERSION"
   claude plugin tag plugin -m "pilotfish Plugin v%s"
   git push origin "v$RELEASE_VERSION" "pilotfish--v$RELEASE_VERSION"
   gh release create "v$RELEASE_VERSION" --title "v$RELEASE_VERSION" --notes-from-tag
   )
   ```

   Any branch-name, push, fetch, or SHA check failure is a stop condition. Do not create or publish tags from a release commit that is absent from the remote default branch.

Keep the project name lowercase (`pilotfish`) in repository and release prose. After publishing or editing a GitHub Release, read its body back and confirm that prose is not manually column-wrapped and every linked path exists on the tagged version.

> If `templates/agents/*.md` changed, keep the legacy global install templates and generated Plugin agents consistent through their renderer checks. Do not mutate a maintainer's real Claude configuration as part of release preparation.
