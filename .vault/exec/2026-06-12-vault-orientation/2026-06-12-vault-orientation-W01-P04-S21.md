---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-13'
step_id: S21
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# register the modified-stamp checker in the check registry

## Scope

- `src/vaultspec_core/vaultcore/checks/__init__.py`

## Description

- Import `check_modified_stamp` in `src/vaultspec_core/vaultcore/checks/__init__.py` and add it to `__all__`, mirroring the sibling registrations.
- Wire the checker into `run_all_checks` after `frontmatter` in both the read-only and the fix paths; the fix-path entry uses `append_and_refresh` so a stamp rewrite refreshes the shared graph.
- Update the `run_all_checks` docstring to name the `modified-stamp` step in the ordered list.
- Add the `vault check modified-stamp` Typer subcommand in `src/vaultspec_core/cli/vault_cmd.py`, mirroring `cmd_check_frontmatter`, with the `vault.check.modified-stamp` command id.
- Carry the `modified` stamp through the graph: add a `modified` field to `DocNode`, populate it from parsed metadata during the build pass, round-trip it through `to_nx_attrs` / node reconstruction, and emit it from `to_snapshot`. Without this the snapshot the checker consumes always read `modified` as `None`, so the fix never converged.
- Bump the graph cache schema to `v3` so stale `v2` caches lacking the field are treated as a miss rather than misread.
- Extend the graph envelope contract's expected node-field set with `modified` to match the additive wire-schema change.
- Regenerate the managed CLI reference region so the parity hook recognizes the new `vault check modified-stamp` command.

## Outcome

`uv run --no-sync vaultspec-core vault check modified-stamp` runs live; after the graph-snapshot fix the read-only pass over the live vault reports zero findings (the working tree carries stamps), and the checker appears in `vault check all`. Graph suite passes 137 tests including the updated envelope contract; ruff and `ty` are clean.

## Notes

The graph-snapshot defect was load-bearing: `to_snapshot` reconstructed `DocumentMetadata` from node fields and silently dropped `modified`, so every fix pass re-reported the same documents as missing a stamp and never converged. The fix is the minimal faithful extension of the node payload rather than a re-parse from disk. The wholesale backfill of pre-existing documents is deferred to the `S23` migration; the registration change itself does not rewrite vault content.
