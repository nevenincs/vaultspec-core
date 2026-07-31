---
tags:
  - '#research'
  - '#guard-subject-integrity'
date: '2026-07-30'
modified: '2026-07-30'
body_schema: 'body-v1'
body_hash: 'sha256:7cb8bacbb3e9016b8d7fdaf9d3b12c1a6e63c714df6c46ad621ecc54b60d7cc9'
related: []
---

# `guard-subject-integrity` research: `which tree each repository guard actually validates`

## Findings

The repository-wide contract guards live in `dev/guards/` and comprise eight test modules
plus a package initialiser. Each was inspected on 2026-07-30 to establish what tree its
assertions actually read.

**Exactly one guard validates a generated artefact.** The template-annotation module
resolves its subject as the installed `.vaultspec/templates/*.md` mirror
(`dev/guards/test_template_annotations.py:22`), never the
`src/vaultspec_core/builtins/templates/` tree that the sync pipeline renders it from. All
three tests in the module inherit that resolver, so all three assert against the mirror.
The mis-targeting is documented rather than accidental: the package docstring names "the
installed `.vaultspec/templates`" among the guards' declared subjects
(`dev/guards/__init__.py:9`).

**The correct pattern already coexists in the same package.** The CLI-language guard walks
the builtins source tree directly, globbing `src/vaultspec_core/builtins` for Markdown
(`dev/guards/test_cli_language_contract.py:35`). It therefore fails on the commit that
introduces a violation, with no dependence on sync freshness.

**The remaining six modules validate committed sources or the live command tree** and need
no change: the automation-contracts, CLI-handbook-drift, CLI-reference-contract-helpers,
package-metadata, test-suite-quality, and typings-fidelity modules. The mirror directories
constructed inside the automation-contracts module are temporary-path fixtures rather than
subjects, and were confirmed as such.

**One adjacent instance sits outside the guard package.** The dev-only statistics package
reads the installed mirror's CLI reference rather than the builtins source
(`dev/statistics/metrics/capability.py:55`). It is a measurement input to transcript
analytics, not a gate. Measuring the catalog agents actually observe is a defensible
subject for that consumer, so it is recorded here as context rather than as a defect.

**The failure mode was observed, not hypothesised.** On 2026-07-30 a `body_schema` field
was added to the builtins templates and committed while the template-annotation guard
remained green, because the installed mirror had not been regenerated and so still lacked
the field. Regenerating the mirror turned the guard red - not because anything broke, but
because the guard finally observed a field the source had carried for some time. The guard
therefore passes at the moment a change is introduced and fails at the moment of unrelated
hygiene, inverting the signal a guard exists to give. The interval between those two
moments is unbounded, because nothing forces regeneration on any schedule.

**Ownership of mirror freshness already rests elsewhere.** The sync surface renders the
mirror and the doctor diagnoses divergence between source and mirror, and the project
forbids hand-editing the mirror at all. A guard asserting on the mirror is therefore
re-testing a derivative whose correctness a different and authoritative surface already
owns.

Quantitatively: eight guard modules surveyed, one offender, one in-package counter-example
demonstrating the correct subject, six correct by inspection, and one non-gating adjacent
consumer noted and excluded.

## Sources

- Direct inspection of all eight modules under `dev/guards/` and the package initialiser,
  2026-07-30.
- The observed green-then-red incident on the template-annotation guard, 2026-07-30,
  triggered by regeneration of the installed mirror.
- `dev/statistics/metrics/capability.py:55` for the adjacent non-gating mirror read.
