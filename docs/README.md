# Documentation

User documentation for vaultspec-core. For what vaultspec-core is and how to install it,
start with the [project README](../README.md).

## Start here

These three assume vaultspec-core is already installed in your project. If you read only
one, read the framework manual.

| Guide                               | What it covers                                                                                                       |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| [Framework manual](framework.md)    | How to run the workflow day to day: the stages you move through, and which files the tool writes for you.            |
| [A feature end to end](examples.md) | One feature from the first command to the final check, with the terminal output as it was produced, not retyped.     |
| [Document syntax](syntax.md)        | Which parts of a document the tool writes and which parts you write. Editing the tool's half is what breaks a check. |

## Look these up when you need them

| Guide                                      | What it covers                                                                                            |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| [Verifying a workspace](verification.md)   | Running the health checks, reading what they report, and repairing a document that fails one.             |
| [The correctness workflow](correctness.md) | What the framework makes an agent prove before work counts as done, and which judgments it leaves to you. |
| [CLI reference](CLI.md)                    | Every command, argument, flag, and exit code.                                                             |
| [MCP server](MCP.md)                       | The Model Context Protocol server: its tools, setup, and configuration.                                   |

Not covered here: installation lives in the [project README](../README.md), and bugs and
questions go to the
[issue tracker](https://github.com/nevenincs/vaultspec-core/issues).

## For maintainers

[Distribution channels](channels.md) covers how the Scoop and Homebrew builds are
published and which platforms they cover.

The terminal renders and the demo GIF in `assets/` are produced by the renderers in
`_render/`, which run `vaultspec-core` against a throwaway vault. Edit the renderer
rather than the SVG, then run `just docs` to regenerate. That covers `demo.gif` and the
`term-*.svg` files; the logo and the Obsidian screenshot are not generated.
