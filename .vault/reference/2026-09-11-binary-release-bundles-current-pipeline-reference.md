---
tags:
  - '#reference'
  - '#binary-release-bundles'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:95145add38ee3355a0c4f0697042750680735d34ad8b74306fa4f23c9ea64c5c'
related:
  - "[[2026-09-06-offline-binaries-prepared-distribution-adr]]"
---

`binary-release-bundles` is implemented as a post-build packaging boundary. The current code produces target-qualified executable files, then the release workflow validates and uploads those files directly. The existing package-channel layer has product data and target naming, but no shared release-bundle or binary-metadata model.

## Summary

### Build and staging

`dev/binaries/build_pyapp.py:233-236` declares the two executable outputs, `vaultspec-core` and `vaultspec-mcp`. `dev/binaries/build_pyapp.py:478-507` constructs PyApp environment metadata including project name, project version, Python version, distribution path, skip-install, and full-isolation settings. These values configure the embedded runtime; they do not create a user-facing release manifest or Windows PE version resource.

`dev/binaries/build_pyapp.py:608-610` is the builder's public asset-name function. It places the executable name before the Rust target and adds `.exe` for Windows. `dev/binaries/build_pyapp.py:613-632` emits one checksum sidecar per file. `dev/binaries/build_pyapp.py:737-745` copies each raw output, stamps the Windows icon, applies Unix execute permissions, checks the target floor, and writes the sidecar. `dev/binaries/build_pyapp.py:748-814` writes those target-qualified files into the output directory.

`dev/binaries/windows_icon.py:190-263` owns Windows icon resource replacement and verification. The existing `dev/binaries/tests/test_windows_icon.py:57-67` exercises real PE stamping, so a bundle change should reuse this path rather than introduce a second branding implementation.

### Product and channel model

`dev/packaging/products.py:24-30` declares the target matrix and `dev/packaging/products.py:44-96` declares product executables plus the repeated target-qualified asset naming rule. `dev/packaging/scoop.py:34-72` converts raw release assets into stable installed command names. `dev/packaging/homebrew.py:179-209` performs the equivalent platform/resource mapping for Homebrew. `dev/packaging/generate.py` consumes `SHA256SUMS` to render channel pointers. These modules are the natural home for one authoritative bundle filename and inner-layout model.

`dev/packaging/tests/test_generators.py:61-74` currently protects equality between the builder and channel naming rules. That test should become a contract test for the centralized packaging model when the duplicate naming functions are removed or redirected.

### Release workflow

`.github/workflows/binaries.yml:226-280` defines the target build matrix. The build job invokes `just release-binaries` at line 409 and stages unverified outputs. The offline matrix begins at line 458 and publishes only verified binary artifacts around lines 776-790. The attestation job is separate, and the release job aggregates sidecar hashes at lines 1094-1116 before uploading every file in `dist-bin` at line 1180.

The workflow therefore already has a build -> offline verification -> release sequence. The bundle builder belongs after the target-specific executable has passed its existing finalization and before the verified artifact is handed to publication. The release job should consume a clean directory whose expected contents are archives and the generated release manifest, not raw staging files.

`justfile:549-552` exposes the local `release-binaries` recipe. A bundle recipe can be added beside it or called by the workflow, but the source of target and executable identity should remain the shared `dev/packaging` model.

### Current verification coverage and missing contract

`dev/binaries/tests/test_build_pyapp.py:86-178` covers tag parsing, raw asset names, uniqueness, and checksum formatting. `dev/packaging/tests/test_validate.py:69-218` and `dev/packaging/tests/test_generators.py:76-226` cover channel pointers, release digests, target availability, and malformed hashes. `dev/guards/test_release_matrix_coverage.py:82-97` protects build/offline/acquisition matrix parity.

No current test asserts a platform archive exists, that extracted executable names are stable, that archive contents are exact, that a generated JSON manifest matches extracted bytes, that PE version fields are present, or that stable publication is refused when the complete expected archive set is absent. Those are the missing contract checks.

### Translation boundary

Keep target-qualified compiled files as private staging names because they disambiguate matrix outputs. Build one target archive from the finalized files, with stable inner names such as `vaultspec-core.exe` and `vaultspec-mcp.exe`. Put product, version, and target in the outer archive filename. Generate the manifest and aggregate checksums from the completed archives and publish only that clean set. Package-manager pointers should consume the same final artifact model rather than re-deriving names independently.

The implementation should stay limited to release bundle construction, descriptive metadata, naming convergence, validation, documentation, and release gating. Installer redesign, runtime changes, and unrelated channel policy are outside this reference.
