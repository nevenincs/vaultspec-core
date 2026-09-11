---
tags:
  - '#research'
  - '#binary-release-bundles'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:01c0dec07ab9b64b693c18bbe65c316515852974b7e4a94e8419179f57349118'
related:
  - "[[2026-09-06-offline-binaries-prepared-distribution-adr]]"
  - "[[2026-09-06-offline-binaries-prepared-distribution-research]]"
  - "[[2026-08-28-binary-portability-adr]]"
---

`binary-release-bundles` needs a stable public artifact contract because the current release edge exposes target-qualified executables while stable command names exist only after package-manager installation. The evidence favors evaluating a target archive as the public boundary, with stable executable names inside and generated metadata beside them; the ADR must settle the exact archive, layout, manifest, and publication contract.

## Findings

### The release currently publishes raw target-qualified executables

`dev/binaries/build_pyapp.py:608-610` derives an asset name from the binary name plus Rust target, adding `.exe` only for Windows. `dev/binaries/build_pyapp.py:737-745` copies the built file into the release output and writes a checksum; `.github/workflows/binaries.yml:1175-1180` uploads that directory directly. The `v0.2.0` release therefore exposes per-target executable assets rather than a platform archive: https://github.com/nevenincs/vaultspec-core/releases/tag/vaultspec-core-v0.2.0. Keeping raw assets is the lowest-change option, but it leaves direct downloads with target-specific executable names and no colocated descriptive metadata.

### Package-manager naming does not establish a direct-download contract

`dev/packaging/products.py:88-96` repeats the builder's target-qualified naming rule, while `dev/packaging/scoop.py:34-72` maps each raw asset to its stable installed command. `dev/packaging/homebrew.py` applies the corresponding channel-specific installation names. This makes package-manager installs stable, but it leaves the release page and manual downloads on a separate naming surface. A bundle boundary could unify both consumers; retaining independent naming inference would preserve the current drift risk.

### The existing archive operation is an internal build input, not a release bundle

`dev/binaries/build_pyapp.py:358-384` creates the prepared distribution that PyApp embeds. That archive is an implementation input and is not emitted as a user-facing release asset. The publish path at `dev/binaries/build_pyapp.py:737-745` has no archive or manifest stage. A release bundle therefore needs a distinct post-build operation after the executable has been finalized.

### The current manifest is integrity-only

`.github/workflows/binaries.yml:1094-1116` combines per-asset sidecars into `SHA256SUMS` and verifies the listed bytes. This establishes hashes but does not describe product version, target, archive contents, executable roles, runtime/toolchain, or platform compatibility. A small generated JSON manifest would serve those descriptive facts, while `SHA256SUMS` could remain the simple digest surface. The manifest must be generated after final files exist; placing an archive digest inside its own archive member would create a circular value.

### Windows branding is partially present, while authored PE metadata remains absent

`dev/binaries/build_pyapp.py:741` calls `stamp_icon` for Windows and `dev/binaries/windows_icon.py:190-263` verifies the embedded ICO. The checked `v0.2.0` Windows core executable matched the repository icon, so icon stamping should be preserved. The same checked executable exposed no authored PE version fields; adding those fields is a separate binary-metadata implementation concern within the packaging contract. Unix executable metadata was not investigated because the requested public contract is the release bundle.

### Release publication is not currently an atomic platform-bundle gate

The `v0.2.1` release is marked latest while its release API has no assets: https://github.com/nevenincs/vaultspec-core/releases/tag/vaultspec-core-v0.2.1. Its binary workflow run has a failed runner preflight and failed or queued offline legs: https://github.com/nevenincs/vaultspec-core/actions/runs/34561648858. The existing workflow intends to validate matrix legs before upload, but release status can still get ahead of binary availability. A bundle design must define the exact expected target set and make stable publication contingent on the complete validated set.

### The alternatives differ mainly in where platform identity lives

Keeping raw files as the public contract minimizes workflow change but preserves naked downloads and duplicated naming. Letting package managers continue to rename raw files improves only managed installs. One universal archive hides the target distinction that the build matrix and platform floors require. Per-target archives put product, version, and target identity in the outer filename and stable command names in the extracted contents; this is the option the evidence favors for ADR consideration. The archive layout, naming, manifest fields, and compatibility treatment of any legacy raw assets remain uninvestigated decisions for the ADR.

## Sources

`dev/binaries/build_pyapp.py:358-384`
`dev/binaries/build_pyapp.py:608-610`
`dev/binaries/build_pyapp.py:737-745`
`dev/binaries/windows_icon.py:190-263`
`dev/packaging/products.py:88-96`
`dev/packaging/scoop.py:34-72`
`.github/workflows/binaries.yml:1094-1116`
`.github/workflows/binaries.yml:1175-1180`
https://github.com/nevenincs/vaultspec-core/releases/tag/vaultspec-core-v0.2.0
https://github.com/nevenincs/vaultspec-core/releases/tag/vaultspec-core-v0.2.1
https://github.com/nevenincs/vaultspec-core/actions/runs/34561648858
