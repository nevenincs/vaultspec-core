---
tags:
  - '#exec'
  - '#cli-reference-automation'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S05
related:
  - '[[2026-06-10-cli-reference-automation-plan]]'
---

# GATED on the ADR deciding build, implement the generator and wire it into the pre-commit and CI surface beside the drift guard, regenerating the bundled reference from the live Typer tree with covering tests (D6 deferral)

## Scope

- `src/vaultspec_core`

## Description

- Add the generator module `src/vaultspec_core/cli/reference_gen.py`: it walks the
  live Typer command tree in registration order (mirroring the drift guard's
  `registered_commands`/`registered_groups` recursion, skipping hidden entries),
  resolves each leaf through the Click command tree, and renders the
  command-inventory signature block via Click's own `make_metavar`.
- Define a managed-region scheme keyed by stable HTML-comment markers
  (`vaultspec:generated:begin <region-id>` ... `:end <region-id>`). The
  `MANAGED_REGIONS` registry currently owns one region, `command-inventory`; the
  renderer rewrites only content between the markers and carries all prose outside
  them through verbatim.
- Provide `generate(check=...)`: write mode rewrites the bundled reference in place
  when the managed regions have drifted; check mode renders in memory, diffs against
  the committed file, and reports whether the two match without writing.
- Wire the verb `vaultspec-core spec reference generate` (with `--check` and `--json`)
  as a hidden `reference` sub-group on `spec_app` in `src/vaultspec_core/cli/spec_cmd.py`.
  The group is mounted with `add_typer(..., hidden=True)` so the drift guards and the
  generated inventory both skip it; the verb therefore does not document itself.
- Introduce the managed markers into the bundled reference and reconcile its
  command-inventory zone to the live surface by running the generator in write mode,
  then format with `mdformat --wrap 88` so the committed artifact is byte-identical to
  fresh output.
- Add the pre-commit hook `cli-reference-check` running the generator in `--check`
  mode, scoped to `src/vaultspec_core/cli/*.py` and the bundled `cli.md`, so drift
  fails the hook (and, through the tests job that runs the new
  `test_committed_reference_is_in_sync_with_live_surface` and `--check` cases, CI).
- Add covering tests in `src/vaultspec_core/tests/cli/test_cli_reference_generated.py`:
  the committed reference is in sync with the live surface; the CLI `--check` verb exits
  0 in sync; a hand-corrupted managed region is detected with a non-zero result and a
  diff; an unmanaged prose sentinel survives a regenerate byte-for-byte; rendering is
  idempotent; a missing marker raises; and write mode reconciles then no-ops.

## Outcome

The generator builds the derivable command-inventory region from the live Typer surface
and preserves every hand-written prose zone. Reconciling the managed zone surfaced and
corrected stale drift the hand-authored inventory carried: the committed inventory had
omitted `doctor`, `vault graph`, `vault rule promote`, `spec rules/skills/agents status`,
`spec hooks show/edit/rename/status`, and `config get/list`, and ordered the `config`
group at the top. The regenerated inventory now lists all live leaves in registration
order. No command, flag, enumeration, or exit-code content was lost; only the curated
prose tables and narrative were untouched. `vaultspec-core spec reference generate --check` exits 0. The drift guard `test_cli_reference_drift.py` and the hydration suite
stay green; the new generator suite passes (12 tests).

Validation before commit: ruff and ty clean on the new and modified Python; the new
generator tests plus the drift guard plus the hydration suite pass (35 tests); the
`--check` verb exits 0.

## Notes

The byte-identity completion criterion required reconciling the bundled `cli.md`'s
managed zone to the generator output format. The reconciliation was additive (missing
commands added, ordering aligned to registration order) plus the introduction of the
marker pair and a one-line "generator-owned" prose note around the block; no prose zone
was removed or garbled. The reformatting is the expected one-time migration the ADR's
honest-cost note anticipated. The per-command option tables remain hand-written prose
(the ADR classifies their curated Default/Description columns as not mechanically
derivable), so this step manages the command-inventory block and leaves the option
tables to the retained drift guard; extending coverage to option tables is a future
region addition the `MANAGED_REGIONS` registry already accommodates.
