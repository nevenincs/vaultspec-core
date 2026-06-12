---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
step_id: S125
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# right-size the deferred cli-reference-regeneration item: fix residual British spellings and extend the drift guard (D16)

## Scope

- `docs/CLI.md`
- `docs/framework.md`
- `src/vaultspec_core/tests/cli/test_cli_reference_drift.py`

## Description

- Grepped `docs/CLI.md` and `docs/framework.md` for `-ise`/`-isation` stragglers and
  fixed all four British forms found: `Synthesised` -> `Synthesized`,
  `serialise` -> `serialize`, `synthesised` -> `synthesized`,
  `customisation` -> `customization`
- Formatted both docs with `mdformat --wrap 88` (the hook that covers `docs/`)
- Assessed the existing drift guard `test_cli_reference_drift.py` and extended it with a
  focused test pinning the specific tokens the P03 reference update added
- Ran the drift guard, the type checker, and the linter

## Outcome

The plan row deferred "automate regeneration of cli.md from the live Typer surface" and
the row's verbatim instruction was to "log a follow-up issue". The user overrode that
wording for this Step, directing in-line remediation; no `gh issue create` was run. The
deferred item was right-sized into the two concrete pieces below.

Part 1 - residual British spellings. The audit's out-of-boundary residual list named
`docs/CLI.md:~1221` and `docs/framework.md:~222`. A grep of both files surfaced two
further stragglers beyond those two (`serialise` in `docs/CLI.md` and `customisation` in
`docs/framework.md`), all four now Americanized. The `.pre-commit-config.yaml`
`mdformat-wrap-docs-check` hook covers `docs/.*\.md` at `--wrap 88`, so both files were
formatted with `--wrap 88` accordingly; the resulting diff is exactly four lines (one per
spelling), with no reflow churn because the docs were already wrap-88 compliant. A grep
for `synthesise`/`serialise`/`customisation` now returns zero. The backticked
`--canonicalise` CLI flag token is intentionally left untouched: it is a literal command
surface, not prose.

Part 2 - drift guard. The drift guard already exists and is comprehensive:
`test_cli_reference_drift.py` walks the live Typer command tree, invokes `--help` on every
visible leaf command, and asserts every command name and every non-global option name
appears in the bundled `src/vaultspec_core/builtins/reference/cli.md`. It already covers
every gap P03 closed by construction. Rather than build a speculative full
code-generator, the proportionate remediation is to keep this guard and make its coverage
of the specific P03-surfaced tokens intentional: a new test `test_p03_surfaced_tokens_are_in_reference`
pins the exact tokens the P03 phase added (`--tier`, `--step`, `--all-steps`,
`--no-hints`, `--dry-run`, `--phase`, `--wave`, `--canonicalise`, `rename-integrity`,
`unarchive`). This is intentionally redundant with the broad sweeps so a future reference
rewrite that drops one of these named items fails with a pointed message. The
tier-promote `--target` flag is a global flag documented once at the top of the reference
(the `_GLOBAL_FLAGS` set), so it is covered by the global-options documentation rather
than a per-command table; its presence is confirmed by the broad option sweep.

The full Typer-surface auto-generator remains a genuine future enhancement but is out of
scope here and non-blocking: a hand-authored reference plus an enforced drift guard
delivers the same guarantee (the reference cannot silently fall behind the CLI) without
the maintenance burden and review risk of a generator. That reasoning is recorded here so
the deferral is a decision, not an omission.

Evidence:

- `uv run --no-sync pytest -q src/vaultspec_core/tests/cli/test_cli_reference_drift.py`
  reports `4 passed` (3 prior + the new `test_p03_surfaced_tokens_are_in_reference`).
- `grep -niE "synthesis(e|ed)|serialise|customisation" docs/CLI.md docs/framework.md`
  returns zero.
- `ty check` and `ruff check` on the modified test file report "All checks passed!".

## Notes

The new test is non-tautological: it reads the real bundled reference from disk and
asserts a fixed, specification-derived token set is present; the broad sweeps it
complements derive their expectations from the live Typer tree, not from the reference
itself. The full CLI-reference auto-generator is the remaining enhancement and is
explicitly non-blocking.
