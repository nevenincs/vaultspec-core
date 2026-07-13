---
tags:
  - '#exec'
  - '#firmware-mcp-primacy'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S20'
related:
  - "[[2026-07-09-firmware-mcp-primacy-plan]]"
---

# Run the full unit gate pytest src/vaultspec_core -m unit and confirm it passes, catching any builtins-guarding test that the reword touched

## Scope

- `src/vaultspec_core/tests`

## Description

- Run the full unit gate `pytest src/vaultspec_core -m unit`; report 1587 passed, 4 failed, 1050 deselected.
- Identify the four failures as `TestAddSubcommand` cases in the vault add CLI suite, unrelated to any prose surface.
- Reproduce the same four failures on the pre-feature base commit to confirm they predate the reword.

## Outcome

The reworded firmware introduced zero regressions. The gate runs 1591 selected unit tests: 1587 pass, and the four failures are `test_add_generates_correct_filename`, `test_add_strips_hash_from_feature`, `test_add_created_doc_passes_validation`, and `test_add_retains_template_annotations_until_explicit_fix`, all in the vault add filename suite. Checking out the pre-feature base commit and running the same class reproduces the identical four failures (four failed, two passed), proving they are pre-existing and independent of this feature. Every builtins-guarding, assembled-prompt, sync, and reference-drift test that the reword could have touched passes.

## Notes

The four pre-existing failures are out of scope for firmware-mcp-primacy and are left for the owning surface to address. They relate to vault add date and synthetic-fixture behavior, not to any file this feature edited.
