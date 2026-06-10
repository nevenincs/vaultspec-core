---
tags:
  - '#exec'
  - '#cli-reference-automation'
date: '2026-06-10'
related:
  - '[[2026-06-10-cli-reference-automation-plan]]'
---

# `cli-reference-automation` `P01` summary

Phase `P01` closed all three transitional-fallback and reference-accuracy hardening
Steps that the firmware-wording-review code review left as LOW notes. The work touched
two files and added no new behavior: the hydration changes are a documentation marker
plus a pure refactor, and the reference change is a one-cell accuracy correction.

- Modified: `src/vaultspec_core/vaultcore/hydration.py`
- Modified: `src/vaultspec_core/builtins/reference/cli.md`

## Description

`S01` added a removal-milestone marker to the `ref-audit.md` legacy template-name
fallback. The marker schedules the grace path for removal one release after the renamed
`reference.md` first ships in a published release (the rename has not shipped as of
version 0.1.26), and it lands on both the `_LEGACY_TEMPLATE_NAMES` module constant and
the fallback branch inside `get_template_path` so the two halves are removed together.
No behavior changed.

`S02` lifted the in-function current-name template filename map out of
`get_template_path` into a module-scope `_TEMPLATE_NAMES` constant beside
`_LEGACY_TEMPLATE_NAMES`, giving the resolver a symmetric pair of lookup tables. This is
a pure refactor with identical resolved paths and fallback behavior.

`S03` corrected the `vault add --feature` Default-column annotation in the bundled
`cli.md` from `required` to `None`, matching the live `vault add --help`, which shows no
required marker on `--feature` (only the `doc_type` argument is required). A grep of the
reference for other `required` tokens found one further occurrence: prose describing
`vault plan step add --phase` as required at L2+, which is accurate against `--help` and
was left unchanged.

Verification: the targeted hydration suite stays green at 21 passed across `S01` and
`S02`, with the five fallback tests (current-name preference, legacy fallback with
warning, both-missing `None`, end-to-end legacy scaffolding, actionable error) unchanged;
`ruff` and `ty` report no findings on `hydration.py`. The `cli.md` drift guard
(`test_cli_reference_drift.py`) passes at 4 passed after `S03`. `vault check all` is
green on the documents this Phase introduces, with the only residual being the plan's
no-research-document advisory.
