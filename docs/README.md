# Documentation

Start with [the framework workflow](../README.md#start-a-feature), then
[install it in your project](../README.md#install).

<p id="start-here"></p>

## Use Core

- [Choose a workflow, plan and resume work, and customize project rules](framework.md).
- [Edit document prose and structure](syntax.md).
- [Check your workspace and repair records](verification.md).
- [Review implementation and test evidence](correctness.md).

<p id="look-these-up-when-you-need-them"></p>

## Reference

- [Look up commands](CLI.md).
- [Set up the MCP server and look up tools](MCP.md).

[Report a problem](https://github.com/nevenincs/vaultspec-core/issues).

## For maintainers

CI runs on self-hosted machines, so a pull request runs its checks there only when you
or a collaborator wrote it. A pull request from anyone else, Dependabot included, runs
nothing and its merge gate stays red until you have read the change and applied the
`ci:full` label, which runs the full checks once on that commit. Pull requests from
forks are refused; re-open an outside change from a branch in this repository.

Use conventional commit messages such as `feat:`, `fix:`, and `feat!:`. release-please
maintains a release pull request with the next version and changelog, rebuilt on every
commit that lands on `main`. The full merge gate runs automatically on the proposal's
final head, then releases the bot PR's held checks without a separate approval click.
Merge the release pull request to start the release automatically: `Core Release Please`
proves the merged commit with the full merge gate, then creates the tag and an
unpublished draft release, then starts the lane that fills it: the binaries are built
for every supported target, proved to start with no network, and attached to the draft
with their checksums and provenance; only once all of them are there does the wheel and
sdist build, smoke-test, and publish to PyPI using OIDC trusted publishing. No extra
dispatch is needed after merging. A failed candidate selection, proposal refresh,
verification gate, or cut fails the workflow; expected skips on the other path do not
count as release success.

The Merge button is the only routine manual action. Dispatch `Core Release Please` only
for recovery of a failed release; the optional dispatch can also prove and merge an open
proposal.

Publishing the draft is the last step, and the Scoop and Homebrew pointers are updated
immediately after it, never before. A release that is visible is therefore a release
that carries everything it claims to, and a failure anywhere in the lane leaves a draft
nobody has been shown rather than a half-finished release to walk back. Fix the cause
and re-dispatch `Core Binaries` for the same tag; the steps that already succeeded are
skipped or repeated harmlessly.

Publication runs `publish.yml` from `main`, with the release tag supplied as `tag`.
Before building, it verifies the exact pushed tag against the merged release proposal
and its version manifest, then checks out that commit by SHA. Keep the `pypi`
environment restricted to the `main` branch: this also prevents older tagged copies of
the publication workflow from obtaining publishing credentials. The GitHub release must
already exist; recreate a missing draft with maintainer credentials before retrying
publication.

A cut can also stop before that lane starts: it fails in
`Create the release for the merged proposal` with
`Resource not accessible by integration`, and its `Name a release this token cannot tag`
step names the tag. The workflow token never holds the `workflows` permission, and
without it GitHub refuses any tag or release that targets a commit whose workflow files
differ from `main`, even once the tag exists. A workflow change that landed between the
release commit's merge and its tag, while the automatic cut waits for its proof,
therefore blocks the release for good: no rerun or later cut can finish it. Finish it
with your own credentials, as the cut would have, relabelling the release pull request
first so the next cut does not pick it up again:

```sh
REPO=nevenincs/vaultspec-core
PR=<release pull request number>
VERSION=<version>
TAG="vaultspec-core-v$VERSION"
SHA=$(gh pr view "$PR" --repo "$REPO" --json mergeCommit --jq .mergeCommit.oid)

gh pr edit "$PR" --repo "$REPO" \
  --remove-label "autorelease: pending" --add-label "autorelease: tagged"
git fetch origin "$SHA"
git push origin "$SHA:refs/tags/$TAG"
git show "$SHA:CHANGELOG.md" \
  | awk -v h="## [$VERSION]" 'index($0, "## [") == 1 { p = index($0, h) == 1 } p' \
  > release-notes.md
gh release create "$TAG" --repo "$REPO" --verify-tag --draft \
  --title "vaultspec-core: v$VERSION" --notes-file release-notes.md
gh workflow run binaries.yml --repo "$REPO" --ref main -f tag="$TAG"
```

The terminal renders and the demo GIF in `assets/` are produced by the renderers in
`_render/`, which run `vaultspec-core` against a throwaway vault. Edit the renderer
rather than the SVG, then run `just docs-all` to regenerate. That covers `demo.gif` and
the `term-*.svg` files; the logo and the Obsidian screenshot are not generated. The GIF
needs [agg](https://github.com/asciinema/agg) on `PATH`, and `term-rag.svg` needs a
running vaultspec-rag service; without one, that render is skipped with a warning.

### Update package-manager manifests

From the Core repository, run this command with the tag and aggregated `SHA256SUMS` from
the same release:

```sh
just release-channels <tag> <path-to-homebrew-tap-checkout> <path-to-SHA256SUMS>
```

The command generates and validates `bucket/vaultspec-core.json` and
`Formula/vaultspec-core.rb` in your `nevenincs/homebrew-tap` checkout. These manifests
install pre-built binaries. Review both files, then commit and push the changes.

Validation runs offline. It checks digest syntax, matching versions, and buildable asset
names. It doesn't download or verify assets or confirm URLs exist.

To change the generated output, edit [package metadata](../dev/packaging/products.py) or
the [Scoop](../dev/packaging/scoop.py) and [Homebrew](../dev/packaging/homebrew.py)
generators. The next release overwrites generated files.
