---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
step_id: S19
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# add a sync output-vocabulary section matching the verified description in the CLI rule (D6)

## Scope

- `src/vaultspec_core/builtins/reference/cli.md`

## Description

- Add a "Sync output vocabulary" section after the `vaultspec-core sync` section,
  stating that sync-shaped results (`install`, `sync`, `spec <resource> sync`,
  `migrations run`) share one vocabulary: `created`, `updated`, `unchanged`,
  `removed`, `restored`, `skipped`, `failed` (D6)
- Carry over the three semantic notes verbatim from the verified CLI rule wording:
  `unchanged` is a successful no-op, not a failure; `skipped` always carries a reason
  worth reading; only `failed` stops the pipeline
- Document the `--json` aggregate: the payload declares schema `vaultspec.sync.v1` and
  the top-level `status` is the run's aggregate outcome (`mixed` when items disagree)
- Run mdformat --wrap 88 on the edited file

## Outcome

The bundled CLI reference now documents the sync output vocabulary that
`src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md` describes, closing the
last of the five `reference/cli.md` lag items from the research. The wording mirrors
the rule's description, which the research's CLI cross-check verified accurate against
live `--json` output (`sync --dry-run --json` emits schema `vaultspec.sync.v1` with
exactly these outcome keys and the aggregate `status` field).

## Notes

The evidence for this Step is the prior verification recorded in the research's CLI
cross-check rather than a fresh mutating run; no sync command was executed during this
Step. The `vaultspec.sync.v1` schema identifier is included beyond the rule's prose
because this is the machine-facing reference and the identifier appears in the
verified `--json` payload.
