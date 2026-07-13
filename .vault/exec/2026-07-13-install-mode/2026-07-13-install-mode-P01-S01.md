---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S01'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add the InstallMode enum with TOOL and DEPENDENCY members

## Scope

- `src/vaultspec_core/core/enums.py`

## Description

- Add the `InstallMode` StrEnum to `core/enums.py` with `TOOL = "tool"` and
  `DEPENDENCY = "dependency"` members, `TOOL` documented as the default.
- Add a lenient `from_token` classmethod mirroring the existing
  `AdrStatus.from_token` house pattern: case-insensitive, whitespace-tolerant,
  returning `None` for a missing or out-of-vocabulary token so callers own the
  typed-error decision on invalid input.

## Outcome

`InstallMode` is the canonical mode vocabulary the rest of the plan renders
against. The enum lands clean on `ruff check` and `ty check`. The `from_token`
parser gives the committed-declaration reader (S02) a lenient front door that
distinguishes a missing mode (`None`) from a malformed one, keeping the ADR Q1
mandate that reads never silently fall back on a bad value.

## Notes

No incidents. No tests are attached to this Step; the enum is exercised by the
`workspace.json` round-trip tests in S04 and the manifest echo tests in S05.
