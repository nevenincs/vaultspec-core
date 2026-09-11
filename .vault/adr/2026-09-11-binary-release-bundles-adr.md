---
tags:
  - '#adr'
  - '#binary-release-bundles'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:f7d7470d5d61bc07d0de00048075ae1169f67e4f5444da378b7cc7bf3b59eaaa'
related:
  - "[[2026-09-11-binary-release-bundles-bundle-contract-research]]"
  - "[[2026-09-11-binary-release-bundles-current-pipeline-reference]]"
  - "[[2026-09-06-offline-binaries-prepared-distribution-adr]]"
---

# `binary-release-bundles` adr: `publish target archives with stable inner executables` | (**status:** `accepted`)

## Problem Statement

The standalone binary release needs one public artifact contract. Today the release edge exposes target-qualified executable files, while stable command names and product grouping are supplied only by individual package channels. The release must instead describe and publish a complete platform artifact whose identity is unambiguous outside the build workspace. The evidence and current code boundary are recorded in `2026-09-11-binary-release-bundles-bundle-contract-research` and `2026-09-11-binary-release-bundles-current-pipeline-reference`.

## Considerations

- The outer filename must identify product, version, and target without making the extracted command name target-specific (`2026-09-11-binary-release-bundles-bundle-contract-research`).
- The existing prepared-distribution and offline verification behavior remains the binary construction constraint (`2026-09-06-offline-binaries-prepared-distribution-adr`).
- Package channels and direct downloads must consume the same product and target model (`2026-09-11-binary-release-bundles-current-pipeline-reference`).
- Descriptive metadata must be generated from finalized files so its hashes and contents describe what is actually shipped (`2026-09-11-binary-release-bundles-bundle-contract-research`).
- Existing Windows icon stamping and verification remain part of executable finalization (`2026-09-11-binary-release-bundles-current-pipeline-reference`).

## Considered options

- **Keep raw target-qualified executables as the public contract.** Rejected: it preserves the direct-download naming and metadata gap.
- **Publish one universal archive.** Rejected: it hides the target identity and conflicts with the target-specific build and compatibility matrix.
- **Add archives but keep raw executables as the canonical public surface.** Rejected: it creates two release contracts and two validation paths.
- **Publish one versioned archive per target with stable inner executable names.** Chosen: it makes platform identity explicit at the boundary and gives direct downloads the same stable commands that managed channels install.

## Constraints

- Target triples and the supported matrix remain the source of platform identity; the bundle layer does not broaden platform coverage.
- `vaultspec-core` and `vaultspec-mcp` remain the executable set for the product unless the product model changes separately.
- Windows uses ZIP and Unix targets use TAR.GZ; each archive contains stable executable names, a generated `manifest.json`, and the required license and usage material.
- `manifest.json` describes the release version, target, executable roles, sizes, hashes, source revision, runtime/build versions, and platform floor. It does not contain the enclosing archive hash.
- `SHA256SUMS` continues to hash completed top-level release artifacts.
- A release cannot become stable/latest until the expected target archive set has passed validation.

## Implementation

Add a release-bundle layer under `dev/packaging` backed by the existing product model. It consumes finalized target outputs, assigns stable inner names, writes the archive-local manifest, and emits one target-qualified archive. The release workflow changes its public handoff from raw staging files to validated archives, then generates checksums and channel pointers from those final artifacts. Windows PE version metadata is authored from the same product/version model while the existing icon path is retained. Tests and direct-download documentation describe and enforce the bundle contract.

## Rationale

Per-target archives are the smallest boundary that simultaneously preserves platform identity, stable executable names, and a single immutable artifact for direct downloads and package channels. They also give validation one object to inspect after executable finalization. The choice follows the release evidence in `2026-09-11-binary-release-bundles-bundle-contract-research` and the implementation seams in `2026-09-11-binary-release-bundles-current-pipeline-reference`.

## Consequences

Direct downloads become self-describing and extract to stable command names. The release surface gains a durable archive and manifest contract, and package-channel generation moves from raw files to those archives. The build retains target-qualified staging names, but those names stop being public compatibility commitments. The workflow and test suite become responsible for archive contents, metadata, and complete target coverage before publication. Consumers of existing raw release URLs will need the documented archive surface.
