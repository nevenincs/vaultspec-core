# Homebrew tap

This directory makes the repository its own Homebrew tap, mirroring what
`../bucket/` does for Scoop. Homebrew reads formulae from `Formula/` in any
repository when the tap is added with an explicit URL, so the product ships through
Homebrew without a second repository to keep in sync.

```sh
brew tap nevenincs/vaultspec-core https://github.com/nevenincs/vaultspec-core
brew install vaultspec-core
```

That installs `vaultspec-core` and `vaultspec-mcp` on macOS (Apple Silicon and
Intel) and on Linux x86-64. The first launch of either bootstraps its pinned Python
runtime and needs network once.

## Why this is a binary formula

`vaultspec-core.rb` installs the pre-built PyApp binaries attached to the GitHub
Release. That is a deliberate divergence from cadrumo, whose formula builds a
Python virtualenv from a locked sdist cohort: cadrumo has no binary channel, so its
formula has to be the thing that assembles the product. vaultspec already publishes
standalone binaries for every platform Homebrew serves, and rebuilding the same
product a second way would double the surface that can break while pinning two
different sets of bytes as "the release".

The idiom shared across the family is the generation discipline - one pointer per
channel, generated from the release's own `SHA256SUMS`, guarded against a backward
bump - not the formula's internal strategy.

## Coverage

| Platform     | Status                                                       |
| ------------ | ------------------------------------------------------------ |
| macOS arm64  | served                                                       |
| macOS x86-64 | served                                                       |
| Linux x86-64 | served                                                       |
| Linux arm64  | **gap** - no build; see the matrix comment in `binaries.yml` |

Homebrew supports Linux arm64, so the missing `aarch64-unknown-linux-gnu` build is
a platform the formula cannot offer an install on at all. The generator omits it
rather than pinning an asset that was never published, and prints a `::warning::`
naming the gap on every release.

## Maintenance

The formula is **generated, never hand-authored** - the release job runs
`dev/packaging/generate.py` and commits the result alongside the Scoop manifest.
Structural changes belong in `dev/packaging/homebrew.py`. Editing the Ruby directly
is overwritten by the next release.
