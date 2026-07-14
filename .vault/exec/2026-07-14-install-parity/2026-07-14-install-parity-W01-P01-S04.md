---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S04'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Rewrite read_workspace_declaration to parse the v2 packages map and fold a legacy v1 single-key file into packages keyed to the current package on read

## Scope

- `src/vaultspec_core/core/workspace_mode.py`

## Description

- Add `_read_packages_map`, the single lock-free parse point behind the whole read surface: it returns a mapping of canonicalized distribution name to `PackageDeclaration`, `None` on a missing file, and raises on a broken one.
- Recognize both on-disk shapes: parse the schema 2.0 `packages` map entry by entry (via a new `_parse_package_entry` helper), and fold the legacy schema 1.0 single-key shape into a one-entry map keyed to the core distribution, renaming the top-level `minimum_vaultspec_version` floor to the package-relative `minimum_version`.
- Reduce `read_workspace_declaration` to a backward-compatible facade that projects the `vaultspec-core` entry onto the single-package `WorkspaceDeclaration` shape existing callers consume, returning `None` when the file is absent or carries no core entry.
- Preserve the strict/lenient contract exactly: corrupt JSON, non-object payloads, non-object package entries, and out-of-vocabulary `install_mode` values all raise typed `VaultSpecError`s with the same message prefixes existing tests assert; the `dev` token is now named in the hints.

## Outcome

The read surface parses schema 2.0 natively and folds legacy v1 files transparently, so every existing caller of `read_workspace_declaration` keeps its single-package view. Verified with a probe: a hand-written v1 file folds to a `vaultspec-core` entry with its floor renamed to `minimum_version`, and a mixed v2 file (core dependency-mode with a floor, rag tool-mode) parses both entries while the facade returns only core's view. The workspace-mode, collectors, and migration-trigger unit suites pass (111 passed). Ruff and scoped ty clean.

## Notes

Typed `_parse_package_entry`'s `entry` parameter as `Any` (matching the `json.loads` origin type) rather than `object`, because `object.get(...)` widens the token to `object` and trips ty's `invalid-argument-type` against `InstallMode.from_token(str | None)`. Writes still emit the legacy single-key body until S05 rewrites the write path; the fold reads that body back correctly, so the round-trip stays green across the S04-S05 boundary.
