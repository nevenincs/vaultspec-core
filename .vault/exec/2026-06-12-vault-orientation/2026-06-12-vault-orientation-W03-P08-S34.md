---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S34
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# regenerate the generator-owned cli reference regions for the new verb

## Scope

- `src/vaultspec_core/builtins/reference/cli.md`

## Description

- Added `vault status` subsection to the hand-authored zone of `src/vaultspec_core/builtins/reference/cli.md`,
  covering rollup mode, targeted mode, the two-mode distinction from auditing, all four
  flags (`--limit`, `--since`, `--json`, `--no-hints`), flag semantics, and the JSON
  schema id `vaultspec.vault.status.v1`.
- Extended the `vault check` subcommand enumeration in `src/vaultspec_core/builtins/reference/cli.md`
  to include `modified-stamp` with its fix-path description.
- Added a mirrored `vault status` section to `docs/CLI.md` with the full options table,
  both mode descriptions, and three usage examples; added `modified-stamp` row to the
  `vault check` subcommands table in `docs/CLI.md`.
- Fixed two bare `` `vault status` `` prose references (one per file) to use the full
  `vaultspec-core vault status` entry-point form required by the language-contract test.
- Ran `uv run --no-sync mdformat --wrap 88` on both files.
- Verified `uv run --no-sync vaultspec-core spec reference generate --check` reports
  managed regions in sync.

## Outcome

All 14 guard tests pass: `test_cli_language_contract`, `test_cli_reference_drift`, and
`test_cli_handbook_drift`. The managed regions between `vaultspec:generated:begin` /
`end` markers are untouched.

## Notes

The `docs/CLI.md` handbook drift test (`test_every_cli_option_is_documented`) drove the
need for a mirrored section in `docs/CLI.md` - the bundled reference alone does not
satisfy that guard.
