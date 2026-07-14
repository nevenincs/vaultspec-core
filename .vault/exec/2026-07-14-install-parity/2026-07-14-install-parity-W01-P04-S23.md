---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S23'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Regenerate the locally-resident CLI reference to reflect the dev mode token and updated --mode help text

## Scope

- `.vaultspec/reference/cli.md`

## Description

- Update the `--mode` option description in the generator source's hand-written prose
  zone (`src/vaultspec_core/builtins/reference/cli.md`) from the two-token form to the
  three-token form, naming `tool`, `dependency` (ships in built distributions), and
  `dev` (default dev group, renders like dependency but does not ship).
- Apply the parallel three-token edit to the human-facing handbook option list in
  `docs/CLI.md`.
- Run `spec reference generate` to re-render the generator-owned command-inventory
  region and normalize both managed files, then `spec reference generate --check`, which
  reports both `cli.md` and `CLI.md` in sync.
- Run `install --upgrade` to propagate the refreshed bundled reference into the
  locally-resident `.vaultspec/reference/cli.md`, the plan Step's declared scope.

## Outcome

All three reference surfaces now carry the three-mode `--mode` vocabulary: the bundled
generator source, the locally-resident `.vaultspec/reference/cli.md` agents read as a
CLI fallback, and the human-facing `docs/CLI.md` handbook. The `--mode` row lives in a
hand-written prose zone, not a generator-owned marker block, so the edit is a
curated-prose change plus a re-generate that confirms the command inventory itself is
unchanged; `spec reference generate --check` passes. The help text token vocabulary
matches the live `--mode` help added in S10, so the reference and the CLI cannot
disagree on the accepted tokens.

## Notes

Running `install --upgrade` to seed the reference into `.vaultspec/` also migrated this
repository's own committed `workspace.json` from the legacy v1 single-key shape
(`install_mode`/`minimum_vaultspec_version`/`schema_version 1.0`) to the v2 per-package
map (`packages: {vaultspec-core: {install_mode, minimum_version}}`,
`schema_version 2.0`). This is the intended read-fold-writeback path D2 specifies
exercised against a real v1 file: the mode value is unchanged (still `dependency`, this
repository's deliberate self-hosting choice), only the container shape migrated. The
migrated file is committed here as the honest dogfood state; the S24 conformance review
verifies the fold, a clean doctor, and the absence of any dependency-leak advisory on a
plain sync.
