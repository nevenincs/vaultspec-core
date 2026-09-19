---
tags:
  - '#plan'
  - '#vault-index-folder'
date: '2026-09-19'
tier: L1
related:
  - '[[2026-04-30-vault-index-folder-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:241b4c1f4039676893f272a208234d6e753f3539d8d143020c97f182ff554951'
---

# `vault-index-folder` plan

Move generated feature indexes from the vault root into a configurable `index/` subfolder, with a migration path for existing vaults.

## Description

Reconstructed 2026-09-19 from this feature's three historical execution
records (`2026-04-30-vault-index-folder-phase1-2-3-exec`,
`2026-04-30-vault-index-folder-phase4-9-exec`,
`2026-04-30-vault-index-folder-phase10-11-exec`) and its summary
(`2026-04-30-vault-index-folder-summary-exec`), which recorded completed work
but had no surviving plan to attribute it to. The Steps below restate what
those records report as done; they are closed on that evidence, not
re-executed. Authorization is historical: the work shipped under issue #91.

Decision coverage: `[[2026-04-30-vault-index-folder-adr]]` governs the
`index_dir` knob, the `#index` directory tag, and the
`vault check structure --fix` migration path this plan sequences.

## Steps

- [x] `S01` - add the index_dir config knob and classify and generate into the new subfolder; `src/vaultspec_core/vaultcore/index.py`.
- [x] `S02` - add the legacy-index migration helper to the structure checker and index-safety checks; `src/vaultspec_core/vaultcore/checks/structure.py`.
- [x] `S03` - update docs and migrate this repo's own vault into the new index subfolder; `README.md`.

## Parallelization

None. The Steps are recorded sequentially as the historical records report
them (phases 1-3, then 4-9, then 10-11), and the work is complete, so no
container is available for concurrent assignment.

## Verification

Verified historically by the three execution records this plan reconstructs:
`pytest`, `ruff check`/`format`, and `ty check` all reported clean at each
phase group, and the final phase ran `vault check all` clean against this
repo's own migrated `.vault/` tree.
