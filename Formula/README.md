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

| Platform     | Status                                 |
| ------------ | -------------------------------------- |
| macOS arm64  | served                                 |
| macOS x86-64 | served                                 |
| Linux x86-64 | served                                 |
| Linux arm64  | built from the next release; see below |

Linux arm64 was a gap and is not one any more: the build matrix in `binaries.yml`
now carries an `aarch64-unknown-linux-gnu` leg, served by a colima container on
macbook neo registered as `macbook-neo-linux-arm-core`.

The committed formula still omits that platform, correctly — it pins release
`0.1.60`, which was built before the leg existed, and the generator omits a target
the release did not attach rather than inventing a digest for it. The first release
built after this change picks it up automatically, with no edit here.

One property of this fleet is worth knowing when a release seems slow: **runners
serve only on AC power.** On battery the host's power gate stops every runner once
it is idle, never mid-job, and GitHub queues new jobs until AC returns. An
unplugged laptop makes a release wait, not fail.

## Maintenance

The formula is **generated, never hand-authored** - the release job runs
`dev/packaging/generate.py` and commits the result alongside the Scoop manifest.
Structural changes belong in `dev/packaging/homebrew.py`. Editing the Ruby directly
is overwritten by the next release.
