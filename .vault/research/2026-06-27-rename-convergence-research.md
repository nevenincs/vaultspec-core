---
tags:
  - '#research'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
related:
  - "[[2026-06-27-rename-convergence-reference]]"
  - "[[2026-06-26-uniform-rename-adr]]"
  - "[[2026-05-17-cli-rename-integrity-adr]]"
---

# `rename-convergence` research: `converging CLI rename CRUDs onto one engine with lock and drift check`

This researches how to converge every CLI rename/move CRUD onto the one hardened engine
`vault feature rename` already uses, add a vault-wide advisory lock, and add a
feature-rename-integrity check - so all rename surfaces are atomic, concurrency-safe,
drift-detected, and verified. It is the deliberate follow-on the uniform-rename ADR named
("eventual unification of the spec-resource rename verbs onto the same shared engine").
The companion reference holds the divergence map and exact locators.

## Findings

### The problem

Four divergent rename paths exist (`resource_rename`, `_execute_rename`/`vault rename`,
`rename_feature`, `hooks_rename`); only `rename_feature` has containment, reverse-journal
rollback, symlink-safety, case-only-rename safety, and the shared link cascade. `vault rename` is the worst: it rewrites incoming links before renaming with no rollback (a
crash leaves dangling links) and uses a duplicate link-rewriter, bypassing the
`rename_ops` hardening. None take a cross-process lock. No feature-scoped drift check
exists.

### Recommended design

1. **Scoped `RenameTransaction` engine.** Extract the reverse-journal + symlink-safe
   restore + root-parameterized containment into a shared `vaultcore` module exposing a
   transaction: `snapshot(paths)` (a CALLER-SUPPLIED set, not a whole-tree rglob - so a
   single-file resource rename does not snapshot all of `.vaultspec/`), `rename(src, dst)`
   (containment-checked, case-safe via `rename_document_path`, journaled),
   `record_write/created/dir`, and context-manager rollback-on-exception. `rename_feature`
   keeps its plan computation but drives the transaction with its non-archive snapshot
   set; `vault rename` snapshots `{old_doc} + incoming-ref docs` and switches to the
   shared `rewrite_incoming_refs` (retiring its duplicate); `resource_rename` snapshots
   `{file}` or the skill dir. This is the literal "converge onto the shared engine"
   mandate, not just primitive sharing.
1. **Root-generalized containment.** Generalize `_assert_within_docs(docs_dir, path)` to
   `_assert_within(managed_root, path)` with the resolution body byte-identical; each
   caller passes its own root - `.vault/` for docs/features, the per-scan-group `base_dir`
   for resources (so provider-mirror fixes still work; the root is NOT a single workspace
   dir). Skill renames check the directory endpoints, not just `SKILL.md`.
1. **Domain advisory locks.** A docs-domain lock at `.vault/data/.vault.lock` (parent
   already gitignored and usually present) and a resource-domain lock at
   `.vaultspec/.lock`. Every rename verb acquires its domain lock; the structure-rename
   cascade (`vault check --fix`) acquires the docs lock too, since it renames. The lock
   only serializes callers sharing the target, so the decision must commit the rename
   surfaces (and the cascade) to the shared targets. Dry-run takes the lock to read a
   consistent snapshot (read-only, short).
1. **`feature-rename-integrity` check.** Read-only by default. Owns only drift classes
   nothing else covers: filename feature-segment vs `#feature` tag mismatch; exec folder
   name vs the feature its records are tagged with; orphaned old-feature artifacts (a doc
   still tagged `#old` after a rename). DEFERS index existence/staleness to
   `check_features` and filename grammar to `check_structure` (no duplication). Reports
   observed-vs-expected and the suggested `vault feature rename` remediation; wired into
   `run_all_checks` after `check_features`. A filename-wins `--fix` is a separate
   follow-on, not bundled.

### Migration risk and regression gate

Output contracts that must not drift: the `spec.{rules,skills,agents}.rename` JSON
envelopes; the `vault.rename` envelope keys (note `incoming_rewritten` may move from
per-doc to per-link counting when switching to the shared cascade - an observable change
to decide and test). The reverse-journal generalization must keep all `rename_feature`
adversarial suites byte-identical-green, and the shared-primitive extraction must keep
`test_structure_case_rename.py` green. Gate: the union of the rename/structure/lock test
suites plus the full unit gate.

### Scope / tiering

One L3 plan, four waves in dependency order: W1 engine extraction + root-generalized
containment (no behavior change, regression-gated); W2 the domain locks + adoption across
rename verbs and the structure cascade; W3 converge resource + document (+ hooks) renames
onto the engine (the observable wave: case-only renames, rollback, shared link engine) -
resource and document as separate phases (different roots, different suites); W4 the
read-only feature-rename-integrity check (independent, could ship first).

### Recommended approach

Build a scoped `RenameTransaction` engine + `_assert_within(managed_root, path)` in a
shared `vaultcore` module; drive `rename_feature`, `vault rename`, `resource_rename`, and
`hooks_rename` through it; add `.vault/data/.vault.lock` and `.vaultspec/.lock` domain
locks adopted by every rename surface and the structure cascade; add a read-only
`feature-rename-integrity` check. Deliver as one L3 plan, four waves, gated by the
existing rename/structure/lock suites and the full unit gate.

### Open questions for the ADR

1. Engine depth: full scoped `RenameTransaction` (the mandate) vs primitive-level sharing
   only (lower risk). The "converge onto the shared engine" wording argues for the engine.
1. `vault rename` `incoming_rewritten` counting: keep per-doc or move to the shared
   engine's per-link+dedup count (observable envelope change either way).
1. Lock breadth: commit `vault check --fix` (the structure cascade) to the docs lock now
   (required for the lock to be meaningful for renames); defer `vault add`.
1. Lock placement: `.vault/data/.vault.lock` (already gitignored) vs `.vault/.lock` (needs
   a new anchored gitignore entry); confirm dry-run acquire-to-read is acceptable.
1. `feature-rename-integrity` `--fix`: read-only first (recommended) vs filename-wins
   reconcile; confirm it defers index/staleness to `check_features`.
1. `hooks_rename` (`core/hooks.py:239`): include in the convergence (the goal says EVERY
   rename CRUD) or explicitly defer? Recommended: include - it is the same one-file shape
   as `resource_rename`.
1. Provider-mirror containment: confirm the root is the per-scan-group `base_dir`, not a
   single workspace root.
