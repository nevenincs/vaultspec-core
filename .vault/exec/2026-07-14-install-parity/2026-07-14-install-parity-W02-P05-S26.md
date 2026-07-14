---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S26'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Verify the released vaultspec-core version on PyPI carries the DEV member and schema v2 API - this step blocks the remainder of the wave

## Scope

- `pyproject.toml`

## Description

- Verify the released `vaultspec-core` 0.1.38 artifact from PyPI carries the parity API surface, independent of the rag working tree, by resolving it into an ephemeral environment.
- Confirm `InstallMode.DEV` resolves to the `dev` value and that `resolve_install_mode_with_provenance`, `read_package_declaration`, `write_package_declaration`, `CORE_DISTRIBUTION_NAME`, and `render_launch_for_mode` all import from the released build.
- Exercise the schema v2 declaration on disk: write both a `vaultspec-core` entry and a companion `vaultspec-rag` entry into a single workspace declaration and read each back.
- Exercise the legacy v1 single-key declaration read-fold against the released build.

## Outcome

The release gate is open. The released 0.1.38 build exposes every symbol the rag adoption wave depends on. `InstallMode.DEV` prints `dev`. The workspace declaration writes at `schema_version` 2.0 as a per-package map, and the two package entries round-trip independently (one declared `dependency`, the other `dev`), confirming the mixed-configuration shape the ADR requires. A legacy v1 single-key file folds to the current package on read without error. With the released API confirmed, the remainder of the wave is unblocked.

## Notes

Verification ran against the released artifact resolved into a throwaway environment rather than the rag project environment, so the gate does not depend on the floor bump landing first; the floor bump and in-environment re-verification belong to the sibling floor-bump step. The released helper signatures differ from the values named in the dispatch brief: `PackageDeclaration` carries `install_mode` and `minimum_version` fields, and `write_package_declaration` takes a `PackageDeclaration` rather than keyword floor arguments; the verification was adjusted to the real released signatures.
