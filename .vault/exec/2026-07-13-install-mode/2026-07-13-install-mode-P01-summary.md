---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# `install-mode` `P01` summary

Phase P01 built the mode model and its two persistence surfaces: the committed
declaration that is the shared source of truth, and the gitignored manifest echo used
for local bookkeeping. All five Steps (S01-S05) closed with no incidents.

- Created: `src/vaultspec_core/core/workspace_mode.py`
- Modified: `src/vaultspec_core/core/enums.py`
- Modified: `src/vaultspec_core/core/manifest.py`
- Created: `src/vaultspec_core/tests/cli/test_workspace_mode.py`
- Modified: `src/vaultspec_core/tests/cli/test_manifest_v2.py`

## Description

`InstallMode` (S01) landed in `core/enums.py` as a StrEnum with `TOOL` and `DEPENDENCY`
members and a lenient `from_token` parser that returns `None` on a missing or malformed
token rather than silently defaulting, so callers own the typed-error decision.

`WorkspaceDeclaration` and its `read_workspace_declaration` /
`write_workspace_declaration` functions (S02) landed in the new `core/workspace_mode.py`
module, owning the committed `.vaultspec/workspace.json` surface distinct from the
gitignored per-machine `providers.json`. Reads are lenient on a missing file (`None`)
and strict on a broken one (corrupt JSON, non-object payload, or an out-of-vocabulary
mode raise a typed `VaultSpecError`). Writes use canonical deterministic serialization
(sorted keys, two-space indent, trailing newline) under the shared advisory lock, and
omit the optional `minimum_vaultspec_version` floor field when unset.

`ManifestData` (S03) gained additive `resolved_mode` and `resolved_floor_version` echo
fields, both defaulting to `None` so a legacy manifest written before mode-awareness
still parses; `read_manifest_data` and `write_manifest_data` round-trip both fields,
with the mode parsed leniently through `InstallMode.from_token`.

Ten WorkspaceFactory-based tests (S04) pin the committed-declaration contract: round
trips for both modes, the floor key omitted when unset, canonical output shape, the
missing-file lenient path, and the strict-refusal paths (corrupt JSON, non-object
payload, malformed mode, missing `install_mode` key). Six new tests (S05) extend the
manifest suite with the echo-field round trip, legacy-manifest backward compatibility,
and survival through an `add_providers` read-modify-write cycle; all seventeen
pre-existing manifest tests continued to pass.

## Verification

`ruff check` and `ty check` were clean on every touched module. The workspace-mode test
module holds 10 tests; the manifest test module holds 23 (6 new, 17 pre-existing, all
passing). No review revisions were required for this phase.
