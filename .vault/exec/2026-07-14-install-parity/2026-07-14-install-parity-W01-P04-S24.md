---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S24'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Run the full unit gate and perform an ADR-conformance review confirming the schema v2 migration, DEV mode, and per-package renderers match the install-parity ADR before the wave is released

## Scope

- `src/vaultspec_core`

## Description

- Run the full vaultspec-core unit gate
  (`pytest src/vaultspec_core -m "unit and not gemini and not claude" -q`): 1737 passed,
  1052 deselected, 0 failed.
- Verify D1 through D4's W01 obligations against the shipped symbols by targeted read
  and grep.
- Confirm the D3 provenance-advisory refinement and the D4 substitution-seam key
  contract.
- Confirm this repository's own committed workspace declaration folds to v2, the doctor
  reads it cleanly per package, and a plain sync raises no dependency-leak advisory.
- Rebuild the feature index and confirm the feature-scoped `vault check all` is clean.

## Outcome

The full unit gate is green (1737 passed, 0 failed) and every W01 obligation of the
install-parity ADR is present in the shipped surface. Wave W01 is conformant and
shippable; the only remaining open Steps in the plan are Wave W02, whose scope is the
vaultspec-rag repository and whose first Phase is the release gate.

### D1 - third mode (DEV)

Conformant. `InstallMode.DEV = "dev"` is a member alongside `TOOL` and `DEPENDENCY` in
`core/enums.py`. The single rendering comparator `render_mode(mode)` maps `DEV` onto
`DEPENDENCY` and passes `TOOL`/`DEPENDENCY` through unchanged, so no renderer grows a
third branch. The `--mode` flag accepts `dev` (the Typer option is typed on
`InstallMode`, whose member value is `dev`), and its help text describes all three modes
including the "renders like dependency but does not ship in built distributions" nuance.
Every renderer routes through `render_mode` before choosing a launch shape, so `DEV`
renders byte-identically to `DEPENDENCY` while remaining a distinct value for doctor
labeling and declared bookkeeping, exactly as D1 chose over the rejected non-persisted
"leak detail" flag.

### D2 - schema shape (per-package v2)

Conformant. `WORKSPACE_SCHEMA_VERSION = "2.0"`; `PackageDeclaration` carries
`install_mode` and the renamed per-package floor field `minimum_version` (the v1 field
name `minimum_vaultspec_version` is folded on read). `read_workspace_declaration` parses
the v2 `packages` map and folds a legacy v1 single-key file into a package entry keyed
to the current package, writing the migrated shape back;
`read_package_declaration`/`write_package_declaration` read-modify-write a single
package's entry without clobbering siblings. This was exercised for real: running
`install --upgrade` in S23 migrated this repository's own committed `workspace.json`
from v1 (`install_mode`/`minimum_vaultspec_version`/`schema_version 1.0`) to v2
(`packages.{vaultspec-core}`/`schema_version 2.0`) with the mode value unchanged. The
chosen per-package map, not the rejected overrides key or per-package files, is what
shipped.

### D3 - runtime-dependency placement enforcement (warn-only, moment-of-choice)

Conformant, and faithful to the P02 review refinement. The dependency-leak advisory is
warn-only and never refuses a placement. The refinement moved it from `resolve()` (which
only ever sees persisted state and would nag every install/sync/upgrade forever) to the
install/upgrade command path, gated on `newly_establishes_dependency(resolved)`, which
is true only when the current run elects dependency mode by explicit `--mode dependency`
(`ModeProvenance.EXPLICIT`), by detection (`DETECTED`), or by upgrade inference
(`INFERRED`), and false for a `PERSISTED` read-back. `_resolve_dependency_leak_advisory`
is entirely absent from `resolver.py` (grep count 0). Verified behaviorally: a plain
`sync --dry-run` against this dependency-mode repository prints no leak advisory,
satisfying the "guidance at the moment of choice, never a standing nag, never silent,
never a refusal" reading of D3.

### D4 - rag's adoption surface (core-side prerequisites)

Conformant for the core-side prerequisites W01 owns; rag's own adoption is Wave W02 and
is correctly out of W01 scope, not a deviation.
`render_launch_for_mode(mode, package, module)` is the single
package-and-module-parameterized launch comparator, collapsing `DEV` onto `DEPENDENCY`
via `render_mode` before choosing the `uv run` (dependency) or `uvx --from <package>`
(tool) shape; core's own launch table is re-derived from it so the table and renderer
cannot drift. The per-definition substitution seam is the two optional metadata keys
`_vaultspec_mode_package`/`_vaultspec_mode_module`, consumed and stripped during
substitution and defaulting to core's own package/module so core's token-only builtin
renders byte-identically. The seam-key contract is documented in the module docstrings
where W02's rag work will find it: `render_launch_for_mode`'s docstring names it as "the
seam a companion package (for example vaultspec-rag) substitutes through," and the key
constants carry a comment describing the companion-package use. The doctor's
`collect_mode_mismatch_state` and `collect_version_floor_state` both take a `package`
parameter, and `diagnosis.py` threads each declared package through them, producing a
per-package `install mode (<package>)` row - confirmed live: `doctor` reports
`install mode (vaultspec-core) ok declared dependency; artifacts match`, reading the
migrated v2 map entry.

### Housekeeping

Feature index rebuilt (`vault feature index -f install-parity`);
`vault check all --feature install-parity` is clean across all seventeen checks. With
this Step closed, every Wave W01 Step is closed; the plan's remaining open Steps are all
Wave W02.

## Notes

No deviations to record. The two schema warnings and the codebase-drift-sweep
missing-ADR warning that surface in a full-vault `doctor` run belong to unrelated
pre-existing plans, not this feature; the feature-scoped
`vault check all --feature install-parity` is fully clean. Wave W02's rag-side work (the
`--mode` flag on rag's CLI, the tokenized rag builtin, rag's doctor rows) is deferred to
that wave by design and is not a W01 gap.
