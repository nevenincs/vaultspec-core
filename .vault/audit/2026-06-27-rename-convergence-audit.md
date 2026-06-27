---
tags:
  - '#audit'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
  - "[[2026-06-27-rename-convergence-adr]]"
---

# `rename-convergence` audit: `converged rename engine, domain locks, and drift check review`

## Scope

Closeout review of the rename-convergence implementation (the L3 plan's four waves): the
shared `RenameTransaction` engine (`vaultcore/rename_engine.py`), the four converged
callers (`rename_feature`, `vault rename`, `resource_rename`, `hooks_rename`), the
structure-cascade lock, and the new read-only `feature-rename-integrity` check. Two
independent `vaultspec-code-reviewer` passes ran with distinct lenses (engine/callers and
check/tests/cross-cutting); their findings and resolutions are logged below. The full unit
gate was green throughout (1543 -> 1545 after the remediation).

## Findings

### vault-rename-archive-rollback-gap | high | document rename re-opened the closed archive boundary/rollback gap

`vault rename`'s convergence (W03) called the shared `related:` cascade without the
`_archive` exclusion, so it rewrote and re-stamped archived docs - which its graph-derived
rollback snapshot did not cover - re-opening the exact gap the uniform-rename audit closed
and diverging from `rename_feature`. RESOLVED: a shared `iter_snapshot_docs(managed_root)`
was factored into the engine; both `rename_feature` and `vault rename` snapshot the same
non-archive tree (a guaranteed superset of the cascade's mutation set), and `vault rename`'s
cascade now excludes `_archive`. A regression test asserts an archived back-reference is
byte-identical (link and stamp) after a document rename.

### snapshot-not-superset-of-mutation | medium | the rollback snapshot basis differed from the mutation basis

Beyond the archive instance, `vault rename` derived its snapshot from a (cacheable) graph
while mutating via a live filesystem cascade, so a stale cache could leave a rewritten doc
un-snapshotted and un-rolled-back. RESOLVED by the same shared-iterator fix: snapshot and
cascade now share the non-archive filesystem basis, restoring the engine's load-bearing
`snapshot superset of mutated` invariant.

### check-scope-plan-adr-drift | high | the shipped check delivered one of three originally-listed drift classes

The ADR/plan listed three drift classes (segment-vs-tag, exec-folder-vs-tag, orphaned
old-feature); only exec-folder-vs-tag shipped. RESOLVED by reconciliation, not by forcing
the others: authored filename-segment-vs-tag was DROPPED because vault authored filenames
legitimately use narrative segments distinct from the `#feature` tag (about a third of this
repo's features, all clean under `vault check`), so it false-positives on a clean vault;
orphaned-old-feature collapses into exec-folder-vs-tag. The ADR's considered-options entry
and the plan steps S13/S16 + the Verification acceptance were amended to the delivered
scope, and negative-guard tests lock the deferral in.

### check-remediation-not-executable | high | the check suggested a command that errors on the drift it detects

The check's `fix_description` emitted `vault feature rename {folder_feature} {tag}`, which
errors in both directions on the canonical drift. RESOLVED: it now gives descriptive,
non-command reconciliation guidance.

### narrative-filename-rename-refusal | high | vault feature rename refuses for features with narrative-named docs (fails safe; pre-existing)

`vault feature rename` refuses the whole rename (raises before any mutation - no
corruption) when a feature's authored doc filename does not encode the feature tag
(`_swap_authored_filename` returns None -> `_compute_rename_plan` raises). About a third of
this repo's features carry such narrative-named docs. This is a pre-existing limitation of
the already-shipped uniform-rename verb, surfaced (not introduced) by this work. PARTIALLY
ADDRESSED: the refusal message now names the document and explains the real cause and
limitation instead of framing it as a malformed filename. The deeper change - having the
verb rewrite the tag/`related:`/index for narrative-named docs while preserving their
filenames - is a real contract change recorded in the ADR Honest-limits and Pathways as an
explicit follow-on decision (it warrants its own ADR; not undertaken here).

### case-safe-rename-claim-unrealized | medium | the engine's case-only-rename safety is not reached by single-file callers

`vault rename`/`resource_rename`/`hooks_rename` route through the case-safe
`rename_document_path`, but their `new_path.exists()` collision pre-check rejects a
case-only rename on case-insensitive filesystems before the two-hop runs (unchanged from
prior behavior). RESOLVED by honesty: the ADR's "case-safe" gain claim was softened to note
this, with delivering it listed as a follow-on; `rename_feature` is unaffected (normcase
collision detection).

### concurrency-docstring-overclaim | medium | the concurrency suite claimed a rename_feature proof it lacked

RESOLVED: added a deterministic (Event-based) test that `rename_feature` blocks on a held
`docs_lock_target` and completes after release, matching the docstring's claim.

### dry-run-skips-lock | low | dry-run paths do not acquire the docs lock the ADR mentioned

RESOLVED by reconciling the ADR text to the read-only-takes-no-lock convention (dry-run is
read-only; consistent-snapshot reads are best-effort).

### verified-correct | low | engine core, lock targeting, test integrity, and the check are sound

No action. The reviewers verified: `_assert_within`/rollback ordering are byte-identical to
the pre-convergence `rename_feature`; the docs and resource lock targets are identical
across their domain callers (so they genuinely serialize); the lock releases on every path;
the `spec.*.rename` and `vault.rename` envelopes are preserved (only `incoming_rewritten`
moved to per-link, as the ADR sanctioned); and every new test is real-filesystem with no
mocks/stubs/skips/tautologies (the concurrency proof is a real Event-ordered serialization,
the rollback tests force real post-rename failures, the check's deferral is locked by
negative guards). `feature-rename-integrity` is read-only, owns only the uncovered
exec-folder drift class, and is clean on the repo's real 95-feature vault.

## Recommendations

All HIGH and MEDIUM findings are resolved or honestly reconciled; the full unit gate is
green at 1545 and `vault check all` is clean (`feature-rename-integrity: clean`). The one
item warranting a product decision rather than a code fix is `narrative-filename-rename-refusal`:
`vault feature rename` cannot rename features whose documents use narrative filenames, which
is a meaningful fraction of real features. It fails safe and now reports the limitation
clearly, but whether the verb should be taught to rename narrative-named documents (tag and
links only, preserving filenames) is a contract change deserving its own ADR. The other
follow-ons (case-only-rename delivery for single-file callers; bringing `vault add` under
the docs lock; a filename-wins `--fix` for the integrity check) are reasonable but
non-blocking.
