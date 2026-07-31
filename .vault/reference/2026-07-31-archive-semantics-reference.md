---
tags:
  - '#reference'
  - '#archive-semantics'
date: '2026-07-31'
modified: '2026-07-31'
body_schema: 'body-v1'
body_hash: 'sha256:518c13bac58bea6dd0f4d24327b5ab2a10abd75418ac08c6ade31506167d6c0c'
related:
  - "[[2026-06-27-rename-convergence-adr]]"
---

# `archive-semantics` reference: `archive engines and dry-run preflight`

Code-grounded survey of the two archive surfaces - the tag-scoped feature archive and
the manifest-scoped document archive - answering whether per-document archiving of
plans is genuinely supported and what the dry run actually guarantees. Sources: the
two engine modules, the checks that consume archived state, the scanner, and the CLI
wiring, all read in full on 2026-07-31.

## Summary

### Two engines, and the document engine is the hardened one

`archive_documents` in `src/vaultspec_core/vaultcore/batch_archive.py` is the
manifest path. It is document-type-agnostic by construction: nothing in the module
inspects `doc_type`, tags, or templates. Each input must be a project-relative path
under the configured vault dir, live (outside `_archive`), `.md`-suffixed, a regular
readable file, with no symlink components; the destination is
`.vault/_archive/<vault-relative-path>` and must not already exist
(`batch_archive.py:355-381`, `batch_archive.py:278-303`). The apply runs inside a
`RenameTransaction` under the docs-domain lock with a snapshot and rollback on
failure, and re-runs the entire preflight while holding the lock so nothing can
change between validation and the first rename (`batch_archive.py:153-174`).

`archive_feature` in `src/vaultspec_core/vaultcore/query_archive.py` is the
tag-scoped path. It selects documents via `list_documents(root_dir, feature=...)`
and moves each with `shutil.move` after `dest.parent.mkdir(parents=True,
exist_ok=True)` (`query_archive.py:110-118`): no lock, no transaction, no rollback,
and no destination-exists preflight. Contrary to the working hypothesis that only
features can "genuinely" be archived, the feature path is the weaker engine; the
per-document path is the one built on the transactional rename machinery ratified by
`2026-06-27-rename-convergence-adr`.

### Downstream consumers were built for archived plans

An archived plan is an anticipated steady state, not an unsupported one. The
exec-mapping check explicitly probes `.vault/_archive/plan/` when an exec record's
parent plan is missing from `.vault/plan/`, and classifies an archived parent as
"the expected, benign steady state" producing no finding, versus a truly-absent
parent which is a WARNING (`src/vaultspec_core/vaultcore/checks/exec_mapping.py:16`,
`exec_mapping.py:97`, `exec_mapping.py:165-208`). The vault scanner excludes
`_archive` wholesale (`src/vaultspec_core/vaultcore/scanner.py:79`), so `status`,
listings, graph, and regenerated feature indexes drop archived documents uniformly.

### What the dry run does and does not evaluate

For `archive_documents`, `dry_run=True` executes the identical `_preflight` the
apply uses - path confinement, liveness, suffix, regular-file readability, duplicate
sources, destination collisions, destination-exists, safe destination parents - plus
the cross-link scan, and returns the resolved destination paths
(`batch_archive.py:136-140`). Two gaps exist between a green dry run and a
guaranteed apply:

- The runtime-directory precondition (`.vault/data` must not be a symlink and must
  be creatable as a directory) is checked only on the apply path
  (`batch_archive.py:142-151`); a pathological runtime dir passes the dry run and
  fails the apply.
- Dry-run validity is point-in-time. The apply re-preflights under the docs lock, so
  any interleaved change fails the batch closed rather than misbehaving - a safety
  property, but it means dry-run success is a preview, not a reservation.

The feature path's dry run shares neither property set: it previews the same
`shutil.move` list the apply would attempt, with no destination-exists or symlink
preflight on either side.

### CLI wiring

`src/vaultspec_core/cli/archive_cmd.py` owns manifest decoding and presentation
only: manifest lines are read as UTF-8 and passed verbatim to the engine
(`archive_cmd.py:28-35`); validation lives entirely in `batch_archive.py`. Restore
is the exact inverse (`restore_documents`), with an opt-in byte-identical
deduplication branch for already-restored duplicates
(`batch_archive.py:438-456`).

### Not investigated

Behavior of `unarchive_feature` beyond signature level, and Windows-specific
`shutil.move` overwrite semantics in the feature path (moot if the feature path
converges on the batch engine).
