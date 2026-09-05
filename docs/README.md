# Documentation

User documentation for vaultspec-core. For what vaultspec-core is and how to install it,
start with the [project README](../README.md).

## Start here

These guides assume vaultspec-core is already installed in your project. If you read
only one, read the framework manual.

| Guide                            | What it covers                                                                                                       |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| [Framework manual](framework.md) | How to run the workflow day to day: the stages you move through, and which files the tool writes for you.            |
| [Document syntax](syntax.md)     | Which parts of a document the tool writes and which parts you write. Editing the tool's half is what breaks a check. |

## Look these up when you need them

| Guide                                             | What it covers                                                                                |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| [Verifying a workspace](verification.md)          | Running the health checks, reading what they report, and repairing a document that fails one. |
| [Review a feature implementation](correctness.md) | Record review findings, address them, and verify test evidence.                               |
| [CLI reference](CLI.md)                           | Every command, argument, flag, and exit code.                                                 |
| [MCP server](MCP.md)                              | The Model Context Protocol server: its tools, setup, and configuration.                       |

Not covered here: installation lives in the [project README](../README.md), and bugs and
questions go to the [issue tracker](https://github.com/nevenincs/vaultspec-core/issues).

## For maintainers

Use conventional commit messages such as `feat:`, `fix:`, and `feat!:`. release-please
maintains a release pull request with the next version and changelog. Merging it creates
a GitHub release and starts publication: the workflow builds and smoke-tests the wheel
and sdist, then publishes to PyPI using OIDC trusted publishing.

The terminal renders and the demo GIF in `assets/` are produced by the renderers in
`_render/`, which run `vaultspec-core` against a throwaway vault. Edit the renderer
rather than the SVG, then run `just docs` to regenerate. That covers `demo.gif` and the
`term-*.svg` files; the logo and the Obsidian screenshot are not generated.

### Update package-manager manifests

From the Core repository, run this command with the tag and aggregated `SHA256SUMS` from
the same release:

```sh
just channels <tag> <path-to-homebrew-tap-checkout> <path-to-SHA256SUMS>
```

The command generates and validates `bucket/vaultspec-core.json` and
`Formula/vaultspec-core.rb` in your `nevenincs/homebrew-tap` checkout. These manifests
install pre-built binaries. Review both files, then commit and push the changes.

Validation runs offline. It checks digest syntax, matching versions, and buildable asset
names. It doesn't download or verify assets or confirm URLs exist.

To change the generated output, edit [package metadata](../dev/packaging/products.py) or
the [Scoop](../dev/packaging/scoop.py) and [Homebrew](../dev/packaging/homebrew.py)
generators. The next release overwrites generated files.
