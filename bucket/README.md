# Scoop bucket

This directory makes the repository its own Scoop bucket. Scoop resolves app
manifests from a `bucket/` subdirectory when one is present, so no separate bucket
repository exists or needs to be created.

```powershell
scoop bucket add vaultspec-core https://github.com/nevenincs/vaultspec-core
scoop install vaultspec-core
```

That installs `vaultspec-core` and `vaultspec-mcp` as standalone Windows binaries,
with no Python toolchain required. The first launch of either bootstraps its pinned
runtime and needs network once.

`vaultspec-core.json` is **generated, never hand-authored**. The release job in
`.github/workflows/binaries.yml` runs `dev/packaging/generate.py` against the
release's own `SHA256SUMS` and commits the result, and the same command reproduces
it locally (`just channels <tag> <checksums>`). Structural changes belong in
`dev/packaging/scoop.py`, which is what generates the file; editing the JSON
directly is overwritten by the next release.

The manifest's `checkver` and `autoupdate` stanzas serve maintainer tooling only.
`scoop install` reads the committed `version`, `url`, and `hash`, so those must be
correct on their own - an autoupdate stanza does not rescue a manifest whose pinned
hash is wrong. Release `vaultspec-core-v0.1.60` shipped exactly that: correct URLs
beside empty hashes, from a green run. See `dev/packaging/checksums.py` for the
cause and the guards that now refuse it.

The Homebrew half of the same release lives in `../Formula/`, generated from the
same aggregate in the same step so the two channels cannot disagree about which
release is current.
