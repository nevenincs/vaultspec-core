---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S03'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Extend ManifestData with resolved_mode and resolved_floor_version echo fields plus their read and write round trip in read_manifest_data and write_manifest_data

## Scope

- `src/vaultspec_core/core/manifest.py`

## Description

- Add `resolved_mode` (`InstallMode | None`) and `resolved_floor_version`
  (`str | None`) echo fields to `ManifestData`, both defaulting to `None` so a
  legacy manifest written before mode-awareness still parses.
- Extend `read_manifest_data` to parse `resolved_mode` leniently through
  `InstallMode.from_token` and to normalize `resolved_floor_version` to a
  string or `None`.
- Extend `write_manifest_data` to serialize the resolved mode as its string
  value (or `null`) and the floor version through the payload.

## Outcome

The gitignored per-machine manifest now carries a bookkeeping echo of the mode
and floor the last install resolved, mirroring the committed
`.vaultspec/workspace.json` declaration without becoming a second source of
truth. Backward compatibility holds: the 17 existing manifest tests pass
unchanged, since the new keys are additive and default to `None` when absent
from an older payload. Clean on `ruff check` and `ty check`.

## Notes

No incidents. The echo fields are purely informational per the ADR Q1 split
(committed declaration is authoritative, manifest echo is local bookkeeping);
the legacy-manifest backward-compatibility and round-trip assertions are added
in S05.
