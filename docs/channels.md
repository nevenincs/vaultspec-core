# Distribution channels

`vaultspec-core` ships through Scoop and Homebrew from **one channel root per account**,
not one per product: `nevenincs/homebrew-tap`. Both package managers resolve a tap or
bucket to a *repository*, and a user who adds two of them to install two vaultspec
products has to add a third for the next one. The account root is added once and carries
every product.

The name says Homebrew and serves both because the two managers read different
directories of the same repository: Scoop takes JSON manifests from `bucket/`, Homebrew
takes Ruby formulae from `Formula/`, and the release job writes each product into both.
A reader who assumes one repository cannot be a bucket and a tap at once is reading the
name rather than the layout.

```sh
# Windows, via Scoop
scoop bucket add nevenincs https://github.com/nevenincs/homebrew-tap
scoop install vaultspec-core

# macOS and Linux, via Homebrew
brew tap nevenincs/tap https://github.com/nevenincs/homebrew-tap
brew install vaultspec-core
```

That installs `vaultspec-core` and `vaultspec-mcp` as standalone binaries with no Python
toolchain required. The first launch of either bootstraps its pinned runtime and needs
network once.

## Coverage

| Platform       | Channel  | Status                |
| -------------- | -------- | --------------------- |
| Windows x86-64 | Scoop    | served                |
| macOS arm64    | Homebrew | served                |
| macOS x86-64   | Homebrew | not built - see below |
| Linux x86-64   | Homebrew | served                |
| Linux arm64    | Homebrew | served                |

One gap, declared rather than silent. The generator omits a target the release did not
attach and prints a `::warning::` naming it, so a missing platform is visible in the
release log instead of becoming a formula whose download 404s.

**macOS x86-64** was dropped because the binary we built did not run: its `cryptography`
wheel resolved to a build the PyApp bootstrapper cannot load on that target, so the
artifact launched and exited 1. Pinning `cryptography` back would have held its CVE
fixes across every other platform to serve one shrinking one.

**Linux arm64** was the second gap and is one no longer. It had no host that could build
it to the target's glibc floor: the ARM64 runner is itself a colima container with no
reachable docker daemon, so it cannot start the pinned `manylinux_2_28` image, and a
native build there inherits the guest's much newer glibc. The release now attaches an
`aarch64-unknown-linux-gnu` binary and the generated formula carries it, which is the
same evidence the table is read from.

## Verifying what you downloaded

Two checks, answering two different questions.

`SHA256SUMS` is attached to every release and says the bytes you hold are the bytes that
release published:

```sh
sha256sum -c SHA256SUMS
```

It covers more than the binaries. `publish.yml` merges the wheel and sdist digests into
that same file, so one manifest speaks for every asset on the release.

Provenance is the second question, and a checksum cannot answer it: a manifest published
beside a tampered download matches it perfectly. Every release asset also carries a
build attestation binding its digest to this repository and the workflow run that
produced it:

```sh
gh attestation verify <asset> --repo nevenincs/vaultspec-core
```

`<asset>` is the file as you downloaded it, named as the release names it - for example
`vaultspec-core-x86_64-pc-windows-msvc.exe`. `--repo` is not decoration: with no
expectation to hold the bundle's signer identity against, there is nothing for the
verification to fail.

**This is not a code signature and does not stand in for one.** The attestation is
signed through Sigstore, which is not in the Microsoft Trusted Root Program and is not
going to be, so it moves nothing in SmartScreen, Gatekeeper, or a WDAC policy. Those
want a publisher identity this project does not hold, and that gap is tracked in
[#405](https://github.com/nevenincs/vaultspec-core/issues/405) rather than left unsaid.
What the attestation gives you is a way to check where an asset came from without
trusting the page you downloaded it from.

The release attaches nothing it could not attest, and re-checks every attached asset
against the API before the run is allowed to go green.

On Windows, the exposure that remains is narrower than "the binaries are unsigned"
suggests. Scoop clears the Mark-of-the-Web from what it installs, so the `scoop install`
path above reaches you unmarked and raises nothing. What is exposed is fetching the
`.exe` from the releases page in a browser and launching it from Explorer, where an
unsigned binary raises SmartScreen's "Windows protected your PC", and managed fleets
running WDAC or AppLocker, which commonly refuse unsigned executables outright.

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
