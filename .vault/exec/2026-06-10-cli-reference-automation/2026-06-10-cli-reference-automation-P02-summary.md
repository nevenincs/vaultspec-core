---
tags:
  - '#exec'
  - '#cli-reference-automation'
date: '2026-06-10'
related:
  - '[[2026-06-10-cli-reference-automation-plan]]'
---

# `cli-reference-automation` `P02` summary

Phase `P02` resolved the design-gated CLI-reference generator follow-up the
firmware-wording-review campaign deferred as decision D6. `S04` produced the decision ADR
and concluded build; `S05` implemented the Typer-surface generator, reconciled the
bundled reference, and wired the `--check` gate into pre-commit and CI; `S06` documented
the generator as the canonical reference-update path in the CLI rule. The decision-gate
condition in the plan's Parallelization and Verification sections is satisfied: the ADR
concluded build, so both downstream Steps executed as code and documentation rather than
closing as decided-not-to-build.

- Created: `src/vaultspec_core/cli/reference_gen.py`
- Created: `src/vaultspec_core/tests/cli/test_cli_reference_generated.py`
- Modified: `src/vaultspec_core/cli/spec_cmd.py`
- Modified: `src/vaultspec_core/builtins/reference/cli.md`
- Modified: `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`
- Modified: `docs/CLI.md`
- Modified: `.pre-commit-config.yaml`

## Description

`S04` (decision ADR, committed separately at `8120f35`) weighed a Typer-surface
auto-generator against the existing hand-authored-plus-drift-guard approach. It concluded
build: the generator removes the manual two-surface update burden the prior
`bundled-cli-reference` decision accepted, and its `--check` mode converts the detect-only
drift guard into an auto-fix-plus-gate. The ADR specified the generator as a `spec`-group
verb, a Typer tree walk reusing the drift guard's introspection, a managed/unmanaged
region scheme, retention of the existing drift guard as an independent backstop, and a
one-time byte-faithful reconciliation of the committed reference.

`S05` implemented that design. A new generator module walks the live Typer command tree
in registration order (mirroring the drift guard's `registered_commands` and
`registered_groups` recursion), resolves each leaf through the Click command tree, and
renders the command-inventory signature block through Click's own metavar rendering. The
derivable zone is delimited by stable `vaultspec:generated` HTML-comment markers; the
renderer rewrites only content between the markers and carries all surrounding prose
through verbatim. The verb `vaultspec-core spec reference generate` exposes a write mode
and a `--check` mode from one rendering path. Reconciling the committed `cli.md` corrected
stale drift the hand-authored inventory carried: it had omitted `doctor`, `vault graph`,
`vault rule promote`, the per-resource `spec ... status` verbs, several `spec hooks`
verbs, and `config get` / `config list`. No command, flag, enumeration, or exit-code
content was lost; only the curated prose tables were left untouched. A `--check`
pre-commit hook was added beside the existing markdown and vault hooks, and covering tests
assert the committed reference is in sync, the CLI `--check` exits 0 in sync, a corrupted
managed region is detected with a diff, an unmanaged prose sentinel survives a regenerate
byte-for-byte, rendering is idempotent, and a missing marker raises.

A correction within `S05` (committed at `9e8d53a`) made the `spec reference` group visible
rather than hidden. The project's CLI language-contract guard requires every command named
in documentation to exist in the visible Typer tree, so a hidden group could not be named
in the bundled reference or the CLI rule. With the group visible, the generated inventory
and `docs/CLI.md` both document the `generate` leaf, and the self-documentation test
asserts the verb is present.

`S06` added a "Maintaining the bundled CLI reference" section to the bundled CLI rule
source naming `vaultspec-core spec reference generate` as the canonical reference-update
path, recording that the managed zones between the markers are generator-owned and must
never be hand-edited, and that `--check` is wired into pre-commit and gates CI.

Verification: the full test suite passes at 2052 passed across the Phase's final state;
`prek run --all-files` passes every hook including the new `cli-reference-check`; ruff and
ty are clean on the new and modified Python; and `vaultspec-core spec reference generate --check` exits 0. `vault check all` is green on the documents this Phase introduces, with
the only residual being the plan's no-research-document advisory. The retained drift guard
`test_cli_reference_drift.py` continues to pass as the independent coverage backstop
alongside the generator's byte-fidelity check.
