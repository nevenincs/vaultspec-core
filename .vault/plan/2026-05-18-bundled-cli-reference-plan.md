---
tags:
  - '#plan'
  - '#bundled-cli-reference'
date: '2026-05-18'
tier: L1
related:
  - '[[2026-05-18-bundled-cli-reference-adr]]'
  - '[[2026-05-18-bundled-cli-reference-research]]'
---

# `bundled-cli-reference` plan: `bundle a machine-facing CLI reference and guard it against drift`

Author a hand-authored machine-facing CLI reference under
`src/vaultspec_core/builtins/reference/`, guard it with a drift test against
the live CLI surface, and point the existing bundled CLI rule at its local
seeded path.

## Description

The work is authorised by the bundled-cli-reference ADR. The ADR decides a
hand-authored reference at `src/vaultspec_core/builtins/reference/cli.md`
(plain markdown, no rule frontmatter, inert to the rule pipeline and the
sync passes), a drift test mirroring `test_cli_handbook_drift.py`, and a
local-path pointer added to `vaultspec-cli.builtin.md`. The first iteration
covers the CLI surface only; MCP and framework references are out of scope
per the ADR.

The plan is tier L1: three Steps, no Phases. The Steps are ordered so the
reference exists before the test that guards it and before the rule that
points at it.

## Steps

- [ ] `S01` - author the machine-facing CLI reference as plain markdown covering the full command and subcommand inventory, per-command options with short forms, argument enumerations, exit-code semantics, and the environment-variable table, extracted from the machine-actionable surface of `docs/CLI.md`; `src/vaultspec_core/builtins/reference/cli.md`.
- [ ] `S02` - add a drift test that walks the live Typer command tree and asserts every command name and every non-global option appears in the bundled reference, mirroring the existing handbook drift test; `src/vaultspec_core/tests/cli/test_cli_reference_drift.py`.
- [ ] `S03` - add a line to the references section pointing at the local seeded path `.vaultspec/rules/reference/cli.md` so an agent in a consumer project finds the reference without a network round-trip; `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`.

## Parallelization

The three Steps are ordered. `S01` must land first because both `S02` (the
drift test reads the reference) and `S03` (the rule points at the
reference) depend on the reference file existing. `S02` and `S03` are
independent of each other once `S01` has landed and may be applied in
either order. The whole plan is small enough to land in a single commit.

## Verification

The plan is complete when every Step is closed and the following criteria
all hold.

- `uv run --no-sync pytest src/vaultspec_core/tests/cli/test_cli_reference_drift.py -v` passes: every live command and option appears in the bundled
  reference.
- `uv run --no-sync pytest -m "not integration and not e2e"` passes the
  full unit suite with no regressions.
- `uv run --no-sync pytest -m "integration and not gemini and not claude"`
  passes the integration tier with no regressions.
- `uv run --no-sync ruff check src tests`,
  `uv run --no-sync ruff format --check src tests`, and
  `uv run --no-sync ty check src/vaultspec_core` are clean.
- `uv run --no-sync prek run --all-files` passes every hook, including the
  wrapped-markdown check on the new `builtins/reference/cli.md` file.
- `uv run --no-sync vaultspec-core install` against a workspace seeds
  `.vaultspec/rules/reference/cli.md` and `uv run --no-sync vaultspec-core sync --force` followed by `spec doctor` and `vault check all` all report
  clean: the new `reference/` subtree is inert to the sync passes and the
  diagnostics.
- The assembled provider configurations (the consumer's `CLAUDE.md`,
  `AGENTS.md`, and equivalents) do NOT contain the reference content:
  `reference/cli.md` is not discovered as a rule.
- `uv build` produces a wheel that ships
  `vaultspec_core/builtins/reference/cli.md` via standard package
  discovery.
