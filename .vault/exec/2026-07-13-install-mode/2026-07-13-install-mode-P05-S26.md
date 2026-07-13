---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S26'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Implement Q6 migration inference in install_run so install --upgrade against a workspace with no persisted mode infers dependency mode from a uv run-shaped canonical hook entry and a pyproject.toml dependency listing, tool mode otherwise, and records the inferred declaration

## Scope

- `src/vaultspec_core/core/commands.py`

## Description

- Add `_infer_upgrade_mode`, the Q6 migration inference: an explicit `--mode` flag wins
  first, then an already-persisted declaration wins (making a repeated upgrade
  idempotent), and only a legacy workspace with neither falls through to inference from
  its deployed state.
- Infer dependency mode only when the deployed canonical hook entries are
  `uv run`-shaped and the target `pyproject.toml` lists `vaultspec-core`; tool mode in
  every other case, per the Q6 detection order.
- Read the deployed hook shape through the existing `_observed_precommit_mode` collector
  rather than a fresh parser, so migration inference and the doctor mode-mismatch check
  share one shape reader and cannot disagree.
- Extract `_write_mode_declaration`, a floor-preserving declaration writer that reuses
  the deterministic canonical write, and route the fresh-install write, the new upgrade
  write, and `_persist_resolved_mode` through it.
- Fold the inferred mode into the upgrade branch and persist the declaration before the
  provider sync and hook scaffold run, so both mode-aware renderers read the inferred
  mode in the same run.
- Pass the inferred mode explicitly to the upgrade `_scaffold_precommit` call.

## Outcome

`install --upgrade` now infers and records a provisioning mode for a legacy workspace
that never declared one, and a second upgrade re-derives the persisted mode and rewrites
the declaration byte-for-byte, so it is idempotent at the content level. The inference
is conservative: it commits to dependency mode only when both the deployed hook shape
and the dependency listing agree, and defaults to tool mode otherwise. Because the
declaration is written before the sync and scaffold renderers, an inferred tool mode now
yields uvx-shaped artifacts in the same run instead of the dependency-shaped artifacts
the legacy-absent render bridge would otherwise have produced against a tool-mode
declaration. The floor constraint on an existing declaration survives the mode rewrite.
The four touched test modules stay green (48 passed) and `ty` reports no new findings.

## Notes

The upgrade inference deliberately mirrors, rather than reuses wholesale,
`resolve_install_mode`: it adds the deployed hook-shape signal that only exists at
upgrade time, and conjoins it with the pyproject listing so a workspace is migrated to
dependency mode only on corroborating evidence. This self-hosted repository lists no
`vaultspec-core` dependency in its own `pyproject.toml` and carries no committed
declaration, so a bare `install --upgrade` here would infer tool mode; its
dependency-mode status is established by an explicit declaration at rollout, not by
inference. That interplay is examined in the S33 conformance review.
