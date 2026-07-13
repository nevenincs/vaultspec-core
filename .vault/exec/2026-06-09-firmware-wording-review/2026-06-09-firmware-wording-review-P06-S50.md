---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S50
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# rename the template file to reference.md if the code-binding check shows the name unbound or trivially remappable, otherwise keep the filename and unify prose only (D7)

## Scope

- `src/vaultspec_core/builtins/templates/ref-audit.md`

## Description

- Rename `src/vaultspec_core/builtins/templates/ref-audit.md` to
  `src/vaultspec_core/builtins/templates/reference.md` via git mv, preserving content
  byte-for-byte (no formatting pass needed; rename only)
- Update the single binding the S49 check surfaced: the `get_template_path` mapping
  constant in `src/vaultspec_core/vaultcore/hydration.py` now reads
  `DocType.REFERENCE: "reference.md"`
- Run the full test suite via `uv run --no-sync pytest -x -q`
- Verify resolution scratch-safe: fresh `vaultspec-core install` into a temp
  directory, confirm `reference.md` is seeded into the scratch templates directory,
  then run `vaultspec-core vault add reference --feature scratch-test --dry-run`
  against the scratch target; delete the scratch directory afterwards

## Outcome

**Renamed.** The S49 verdict (TRIVIALLY-REMAPPABLE) held exactly: one constant edit
plus the git mv, zero test edits, zero sync-mapping edits. Evidence:

- Full suite green: 2035 passed in 285.55s, no failures, no skips added.
- Scratch check green: the fresh install seeds `reference.md` (and no
  `ref-audit.md`), and the dry-run reports it would create
  `.vault/reference/2026-06-10-scratch-test-reference.md` - the doc-type resolves
  through the renamed template end to end.
- The template-name decision D7 is now consistent with the doc type, the directory
  tag, and the `vault add reference` verb; the prose unification follows in S51, and
  the template mandate pointing at the new path lands in S52.

## Notes

- The dry-run printed a pre-existing `{topic}` unhydrated-placeholder warning; it
  comes from the template's title line and is unrelated to the rename (same warning
  fires for other doc types scaffolded without `--title`).
- The workspace mirror `.vaultspec/rules/templates/ref-audit.md` is now a stale
  orphan until `P09.S121`/`P09.S122` propagate; `vault add reference` against this
  workspace keeps resolving the old mirror name until then, which is why the
  verification ran against a scratch install. No deferral to P09.S126 is needed for
  Python work; the mirror cleanup is already P09's mandate.
