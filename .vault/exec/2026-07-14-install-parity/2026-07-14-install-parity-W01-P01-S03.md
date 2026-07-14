---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S03'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Add a PackageDeclaration dataclass (mode, minimum_vaultspec_version) and bump WORKSPACE_SCHEMA_VERSION to 2.0 for the per-package packages map shape

## Scope

- `src/vaultspec_core/core/workspace_mode.py`

## Description

- Add a `PackageDeclaration` dataclass carrying one distribution's `install_mode` and optional `minimum_version` floor, the per-package entry shape for the schema 2.0 `packages` map.
- Bump `WORKSPACE_SCHEMA_VERSION` to `2.0` and add a `_LEGACY_SCHEMA_VERSION` constant naming the `1.0` single-key shape that gets folded on read.
- Document the floor-key rename: the legacy top-level `minimum_vaultspec_version` becomes the package-relative `minimum_version` once it lives inside a named package entry.

## Outcome

The module now carries the schema 2.0 vocabulary (the `PackageDeclaration` entry type and the bumped version constant) while the read and write bodies still operate on the legacy single-key shape, which the next two steps rewrite. The interim state is self-consistent: writes stamp `schema_version: 2.0` onto a still-single-key body, and reads parse that body through the unchanged legacy path, so the round-trip and corrupt-declaration tests stay green (19 passed). Ruff check, ruff format, and scoped ty clean.

## Notes

No incidents. Chose `install_mode`/`minimum_version` as the `PackageDeclaration` field names to match the schema 2.0 JSON keys exactly and the existing `WorkspaceDeclaration.install_mode` attribute, per the phase's floor-rename binding; the plan row's parenthetical `(mode, minimum_vaultspec_version)` names the concepts, not the wire keys.
