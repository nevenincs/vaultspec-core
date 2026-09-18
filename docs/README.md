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

Use conventional commit messages such as `feat:`, `fix:`, and `feat!:`. release-please
maintains a release pull request with the next version and changelog. Merging it creates
the tag and an unpublished draft release, then starts the lane that fills it: the
binaries are built for every supported target, proved to start with no network, and
attached to the draft with their checksums and provenance; only once all of them are
there does the wheel and sdist build, smoke-test, and publish to PyPI using OIDC trusted
publishing.

Publishing the draft is the last step. A release that is visible is therefore a release
that carries everything it claims to, and a failure anywhere in the lane leaves a draft
nobody has been shown rather than a half-finished release to walk back. Fix the cause
and re-dispatch `Core Release` for the same tag; the steps that already succeeded are
skipped or repeated harmlessly.

The terminal renders and the demo GIF in `assets/` are produced by the renderers in
`_render/`, which run `vaultspec-core` against a throwaway vault. Edit the renderer
rather than the SVG, then run `just docs` to regenerate. That covers `demo.gif` and the
`term-*.svg` files; the logo and the Obsidian screenshot are not generated.

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
