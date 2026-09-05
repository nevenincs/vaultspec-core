# Distribution channels

Install Core with Scoop on Windows or Homebrew on macOS and Linux. Both channels install
`vaultspec-core` and `vaultspec-mcp`.

You don't need a separate Python installation. First launch needs network access to
install the pinned Vaultspec package and its dependencies from PyPI.

## Coverage

| Platform | Architecture          | Availability |
| -------- | --------------------- | ------------ |
| Windows  | x86-64                | Scoop        |
| macOS    | arm64 (Apple Silicon) | Homebrew     |
| macOS    | x86-64 (Intel)        | Unavailable  |
| Linux    | x86-64                | Homebrew     |
| Linux    | arm64                 | Homebrew     |

Windows with Scoop:

```powershell
scoop bucket add nevenincs https://github.com/nevenincs/homebrew-tap
scoop install vaultspec-core
```

macOS and Linux with Homebrew:

```sh
brew tap nevenincs/tap https://github.com/nevenincs/homebrew-tap
brew install vaultspec-core
```

## Verifying what you downloaded

Download `SHA256SUMS` from the same release as your asset. Compare the asset's SHA-256
hash with its entry in that file. If you downloaded all listed assets, check them
together from their download directory with:

```sh
sha256sum -c SHA256SUMS
```

A matching checksum confirms agreement with the release manifest. To verify an asset's
build provenance, use [GitHub CLI](https://cli.github.com/manual/gh_attestation_verify):

```sh
gh attestation verify <asset> --repo nevenincs/vaultspec-core
```

Replace `<asset>` with the downloaded file's path. Older releases may have no build
attestation; a checksum match alone does not verify provenance. If verification fails,
check the command's error before running the asset.

To require a particular signing workflow, add `--signer-workflow`. For standalone
binaries:

```sh
gh attestation verify <asset> --repo nevenincs/vaultspec-core --signer-workflow nevenincs/vaultspec-core/.github/workflows/binaries.yml
```

For a wheel or source distribution, use
`nevenincs/vaultspec-core/.github/workflows/publish.yml` instead. `SHA256SUMS` itself
has no attestation because both release workflows update it; verify the individual
assets.

Build attestations do not grant permission to run an executable under your operating
system's security policy. Publisher signing is tracked in
[#405](https://github.com/nevenincs/vaultspec-core/issues/405).

## Why binary formulae

The Homebrew formula installs the pre-built PyApp binaries attached to the GitHub
Release, rather than building the product from source the way a formula usually does.
vaultspec already publishes standalone binaries for every platform Homebrew serves, so
assembling the same product a second way would double the surface that can break while
pinning two different sets of bytes as "the release".

That is a deliberate divergence from the other product this release-channel machinery
generates. `cadrumo` is a separate tool in its own repository, sharing this machinery
and so shipping the same channel shapes; nothing here depends on knowing it, and it is
named because the two formulae differ on purpose rather than by drift. Its formula does
build a virtualenv from a locked sdist cohort, because it publishes no binary channel
and the formula has to be the thing that assembles the product.

The idiom shared across the family is the generation discipline - one pointer per
channel, generated from the release's own `SHA256SUMS`, guarded against a backward bump
\- not the formula's internal strategy.

## Generation, and why nothing is hand-authored

Both pointers are **generated, never hand-authored**. The release job in
`.github/workflows/binaries.yml` runs `dev.packaging.generate` against the release's own
`SHA256SUMS` and commits the result into the tap checkout. Structural changes belong in
`dev/packaging/scoop.py` and `dev/packaging/homebrew.py`; editing a manifest or formula
directly is overwritten by the next release.

Reproduce locally against a tap checkout:

```sh
just channels <tag> <checksums> <path-to-homebrew-tap-checkout>
```

The root argument is required rather than defaulted. It used to default to this
repository, which quietly wrote the pointers into a `bucket/` and `Formula/` that no
longer exist - the local command and the release job disagreeing about where a channel
lives is exactly how the two roots drifted four releases apart.

### The 0.1.60 failure, and the guard that now refuses it

Scoop's `checkver` and `autoupdate` stanzas serve maintainer tooling only.
`scoop install` reads the committed `version`, `url`, and `hash`, so those must be
correct on their own - an autoupdate stanza does not rescue a manifest whose pinned hash
is wrong.

Release `vaultspec-core-v0.1.60` shipped exactly that: correct version, correct URLs,
and `"hash": ["", ""]`, out of a run that was green from end to end.

`dev/packaging/validate.py` now runs between generating the pointers and committing
them, and refuses blank or truncated digests, a version the two channels disagree about,
and a URL naming an asset no build produces. It runs at the only point where a bad
pointer can still be stopped rather than reported afterwards.
