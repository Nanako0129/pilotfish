# Releasing

`VERSION` is the single release-version source. The renderer writes that exact value to both `plugin/.claude-plugin/plugin.json` and the Plugin entry in `.claude-plugin/marketplace.json`; never edit either generated version by hand.

1. Set `VERSION`, update the matching version comment in `templates/claude-md.orchestration.md`, and add the release entry to `CHANGELOG.md`.
2. Before render/tag work, prompt-bearing template changes require the [Independent semantic-equivalence reading](CONTRIBUTING.md#independent-semantic-equivalence-reading). This applies only to `templates/claude-md.orchestration.md` and `templates/agents/*.md`, not the configuration `templates/settings.snippet.json`. Record the exact base revision, changed template paths, independent reader identity who did not author the change, complete prior/current pair records including exact `prior: absent` and `current: absent` markers, and complete all `FIX`, `DEFER`, or `REJECT` dispositions before release readiness. Require a final candidate/tree/template-hash match: current changed-template SHA-256 values and candidate tree/bytes must match the independent record; if they differ, stop before renderer/tag and rerun/update the reading. A tree-identical squash merge may map the reviewed PR head to a new commit SHA only when recorded tree equality and every changed-template byte hash are identical.
3. Regenerate Plugin artifacts, then prove they are current:

   ```bash
   python3 tools/render_plugin_spike.py --write
   python3 tools/render_plugin_spike.py --check
   ```

4. Run strict manifest validation and the full dependency-free test suite:

   ```bash
   claude plugin validate --strict .claude-plugin/marketplace.json
   claude plugin validate --strict plugin
   python3 -m unittest discover -s tests -v
   git diff --check
   ```

5. Review the complete diff, commit the release candidate, require a clean worktree, and dry-run the matching Plugin tag:

   ```bash
   claude plugin tag --dry-run plugin
   ```

   The dry-run must report `pilotfish--vX.Y.Z`, where `X.Y.Z` equals `VERSION`. An existing tag or version mismatch is a stop condition; never use `--force` to bypass it.

6. After review and separate release authorization, push the release commit to the repository's default branch and verify the remote branch before creating either tag:

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
   git push --atomic origin "v$RELEASE_VERSION" "pilotfish--v$RELEASE_VERSION"
   gh release create "v$RELEASE_VERSION" --title "v$RELEASE_VERSION" --notes-from-tag
   )
   ```

   Any branch-name, push, fetch, or SHA check failure is a stop condition. Do not create or publish tags from a release commit that is absent from the remote default branch.

   If the atomic tag push succeeds but `gh release create` fails, do not rerun the tag-creation block. Resume monotonically by proving that both immutable remote tags identify the same commit, then create only the missing GitHub Release:

   ```bash
   (
   set -eu
   RELEASE_VERSION=$(tr -d '\n' < VERSION)
   RELEASE_BRANCH=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD)
   RELEASE_BRANCH=${RELEASE_BRANCH#origin/}
   test -n "$RELEASE_BRANCH"

   remote_tag_commit() {
     TAG=$1
     DIRECT=$(git ls-remote --refs origin "refs/tags/$TAG" | awk 'NR == 1 { print $1 }')
     PEELED=$(git ls-remote origin "refs/tags/$TAG^{}" | awk 'NR == 1 { print $1 }')
     test -n "$DIRECT"
     printf '%s\n' "${PEELED:-$DIRECT}"
   }

   RELEASE_SHA=$(remote_tag_commit "v$RELEASE_VERSION")
   test "$(remote_tag_commit "pilotfish--v$RELEASE_VERSION")" = "$RELEASE_SHA"
   git fetch origin "$RELEASE_BRANCH"
   git fetch origin "$RELEASE_SHA"
   git merge-base --is-ancestor "$RELEASE_SHA" "origin/$RELEASE_BRANCH"

   if gh release view "v$RELEASE_VERSION" >/dev/null 2>&1; then
     test "$(gh release view "v$RELEASE_VERSION" --json tagName --jq .tagName)" = "v$RELEASE_VERSION"
   else
     gh release create "v$RELEASE_VERSION" --title "v$RELEASE_VERSION" --notes-from-tag
   fi
   )
   ```

   This recovery path may create or repair only the GitHub Release for those exact existing tags. It must never recreate, move, force, or repush either tag. Read the Release back and repair its prose or links with `gh release edit` only after confirming its `tagName`; a tag-identity mismatch requires a later `VERSION` and new tags, not mutation of the Release for those exact existing tags.

Keep the project name lowercase (`pilotfish`) in repository and release prose. After publishing or editing a GitHub Release, read its body back and confirm that prose is not manually column-wrapped and every linked path exists on the tagged version.

> If `templates/agents/*.md` changed, keep the legacy global install templates and generated Plugin agents consistent through their renderer checks. Do not mutate a maintainer's real Claude configuration as part of release preparation.
