---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S49
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# run the code-binding check for the ref-audit.md template filename across Python loaders, provider sync mappings, and tests (D7)

## Scope

- `src/vaultspec_core`

## Description

- Grep the whole repository (case-insensitive, `ref.audit|ref_audit`) for bindings of
  the `ref-audit.md` template filename across Python loaders, provider sync mappings,
  and tests
- Inspect the template-resolution path (`vaultcore/hydration.py` `get_template_path`),
  the provider seeding code (`builtins/__init__.py`), the templates-directory plumbing
  in `core/types.py`, `core/commands.py`, `core/skills.py`, packaging config
  (`pyproject.toml`), and every test tree (`tests/`, `src/vaultspec_core/tests/`,
  `src/vaultspec_core/vaultcore/tests/`)

## Outcome

**Verdict: TRIVIALLY-REMAPPABLE.** Exactly one mapping constant binds the filename;
no test literal and no sync mapping names it. Binding sites, exhaustively:

- `src/vaultspec_core/vaultcore/hydration.py` line 439: `DocType.REFERENCE: "ref-audit.md"` inside the `get_template_path` doc-type-to-template mapping. This is
  the single Python binding and the one constant S50 must update.
- Provider sync is name-blind: `src/vaultspec_core/builtins/__init__.py`
  (`seed_builtins`, `list_builtins`, `check_outdated`) walks the builtins tree with
  `rglob("*")`; no per-filename mapping exists, so a rename propagates transparently
  on the next sync or upgrade.
- Tests are name-blind: `tests/test_template_annotations.py` discovers templates via
  `glob("*.md")` over the deployed templates directory; a case-insensitive grep for
  `ref.audit|ref_audit` across `tests/`, `src/vaultspec_core/tests/`, and
  `src/vaultspec_core/vaultcore/tests/` returns zero matches. `DocType.REFERENCE`
  appears in `metrics/tests/test_metrics.py` and `vaultcore/tests/test_scanner.py`
  only as a doc-type value, never coupled to the template filename.
- Packaging is name-blind: `pyproject.toml` names neither the file nor the templates
  directory.
- No firmware markdown under `src/vaultspec_core/builtins/` references `ref-audit.md`
  (consistent with the research's orphaned-member finding).
- Non-binding residue: the deployed mirror copy `.vaultspec/rules/templates/ ref-audit.md` becomes a stale orphan after the rename because `seed_builtins` never
  removes files; mirror reconciliation is owned by `P09.S121`/`P09.S122`.

The rename to `reference.md` in S50 is therefore unblocked: one constant plus the
`git mv`, no test edits, no sync-mapping edits.

## Notes

Check-only gate Step: no firmware edit; this record plus the plan-state change is the
commit. Until `P09.S121` propagates, the workspace mirror still serves the old
filename, so S50's resolution check must run against a scratch install rather than
this workspace.
