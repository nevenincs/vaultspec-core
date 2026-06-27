---
tags:
  - '#adr'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
related:
  - "[[2026-06-27-rename-convergence-research]]"
  - "[[2026-06-27-rename-convergence-reference]]"
  - "[[2026-06-26-uniform-rename-adr]]"
  - "[[2026-05-17-cli-rename-integrity-adr]]"
---

# `rename-convergence` adr: `converge all rename CRUDs onto one transactional engine with domain locks and drift checks` | (**status:** `accepted`)

## Problem Statement

The CLI has four divergent rename/move paths and only one is hardened. `rename_feature`
(the uniform-rename verb) has a containment guard, a reverse-journal for byte-for-byte
rollback, symlink-safety, case-only-rename safety, line-ending fidelity, and the shared
`related:` link cascade. The other three do not: `resource_rename` (spec
rules/skills/agents) has only an ad-hoc move-back; `_execute_rename` (`vault rename`) has
no rollback at all AND rewrites incoming links before renaming, so a crash leaves
dangling links into a now-missing stem; `hooks_rename` is a bare `shutil.move`. None of
the four take a cross-process lock, so concurrent mutators can interleave and lose
updates (the open follow-up from the uniform-rename audit). `vault rename` also carries a
second, parallel link-rewrite implementation, reintroducing the very duplication the
uniform-rename ADR's shared-module extraction set out to eliminate. Finally, there is no
check that detects post-rename feature drift in `.vault/`. This ADR records the decision
to converge every rename surface onto one transactional engine, make them
concurrency-safe with domain locks, and add drift detection - the deliberate follow-on
the uniform-rename ADR named.

## Considerations

- Single source of safety: the hardened mechanics (containment, reverse-journal,
  symlink-safety, case-safe rename, line-ending fidelity) should exist once and protect
  every rename, not be re-derived per verb.
- Two managed roots: docs/feature renames operate under `.vault/`; resource and hook
  renames operate under `.vaultspec/` (and resource fixes can target provider mirror
  dirs outside both). The containment guard and lock must be parameterized by root, not
  hardcoded to the docs dir.
- Scoped snapshots: `rename_feature`'s journal snapshots the whole docs tree because a
  feature rename touches the whole tree. A single-file resource or document rename must
  snapshot only its participating files, so the shared engine must take a caller-supplied
  snapshot set rather than always rglob the root.
- Lock reality: an advisory lock only serializes callers that share the same target, so
  the decision must commit every rename surface in a domain (and the structure-rename
  cascade) to one well-known per-domain target.
- Observable contracts: the `spec.*.rename` and `vault.rename` JSON envelopes are public;
  convergence must preserve their keys (with one deliberate, tested exception noted under
  Constraints).
- Drift detection must not duplicate existing checks: `check_features` already owns index
  existence/staleness, `check_structure` owns filename grammar.

## Considered options

Engine depth:

- Scoped `RenameTransaction` engine (chosen) - extract the journal + symlink-safe restore
  - root-parameterized containment into a shared module taking a caller-supplied snapshot
    set; all four callers drive it. Directly satisfies "converge onto the shared engine"
    and kills the duplicate link-rewriter.
- Primitive-level sharing only (rejected) - share `rename_document_path` + a generalized
  containment + the lock, but leave each path's own (or absent) rollback. Lower effort
  but leaves two journal implementations and falls short of the mandate.
- Leave non-feature paths as-is, add only lock + containment (rejected) - least churn,
  but `vault rename` keeps its no-rollback dangling-link defect and its duplicate engine.

Advisory lock:

- Per-domain whole-vault locks (chosen) - one docs lock and one resource lock, each
  acquired by every rename surface in that domain plus the structure cascade. Actually
  serializes the cascade and journal against other mutators in the same domain.
- Per-feature lock (rejected) - unsound: a feature rename's `related:` cascade touches the
  whole docs tree, so two "disjoint" feature renames still race on shared third-party docs.
- No lock / keep deferring (rejected) - contradicts the concurrency-safety mandate.

feature-rename-integrity check:

- Read-only, owns only uncovered drift classes (chosen) - segment-vs-tag, exec-folder-vs-tag,
  orphaned old-feature artifacts; defers index/staleness to `check_features` and filename
  grammar to `check_structure`.
- Bundle a filename-wins `--fix` (rejected for now) - reconciliation is ambiguous (which
  side is canonical) and dangerous unattended across many files; a separate later decision.

## Constraints

- The reverse-journal extraction must keep every `rename_feature` adversarial suite
  byte-identical-green (`test_rename_feature{,_security,_encoding}.py`,
  `test_feature_rename_cli.py`), and the shared-primitive reuse must keep
  `test_structure_case_rename.py` green - these are the regression gates.
- `_assert_within` must be parameterized by the per-scan-group `base_dir` (including
  provider-mirror dirs), not a single workspace root, or `check_rename_integrity`'s
  frontmatter-wins fix against mirrors breaks. Skill renames must containment-check the
  directory endpoints, not just `SKILL.md`.
- Observable change (accepted, must be tested): switching `vault rename` to the shared
  `rewrite_incoming_refs` moves its `incoming_rewritten` count from per-document to
  per-link (plus dedup drops). The key is retained; its test is updated to the per-link
  contract.
- Lock placement: the docs lock lives at `.vault/data/.vault.lock` (the `data/` dir is
  already gitignored, so no new ignore entry and no committed lock file) and the resource
  lock at `.vaultspec/.lock` (`.vaultspec/*.lock` is already gitignored). `advisory_lock`
  skips when the parent dir is absent; dry-run paths acquire the lock to read a
  consistent snapshot (read-only, short) and must not create the parent themselves.
- Parent-feature stability: this builds only on shipped, test-covered internals
  (`rename_feature`, `rename_ops`, `advisory_lock`, the checks framework). No frontier
  dependency.

## Implementation

High-level layering (not a plan):

1. Shared transactional engine. A new `vaultcore` module exposes a `RenameTransaction`
   bound to a managed root and a domain lock target: `snapshot(paths)` captures the
   caller-supplied file set's bytes, `rename(src, dst)` is containment-checked,
   case-safe (via `rename_document_path`), and journaled, and helpers record content
   writes, created files, and created/removed dirs. Used as a context manager, it rolls
   back byte-for-byte on any exception and acquires the domain advisory lock for its
   lifetime. The root-generalized `_assert_within(managed_root, path)` and the
   symlink-safe restore move here too.

1. Converge the callers. `rename_feature` keeps its plan computation but drives the
   transaction (passing its non-archive docs as the snapshot set). `vault rename`
   snapshots the renamed doc plus its incoming-ref docs, switches to the shared
   `rewrite_incoming_refs`, and gains rollback and case-safe rename. `resource_rename`
   and `hooks_rename` snapshot their single file (or the skill directory) and gain
   containment, case-safe rename, and lock-protected rollback.

1. Domain locks. Acquire the docs lock in `rename_feature`, `vault rename`, and the
   structure-rename cascade (`vault check --fix`); acquire the resource lock in
   `resource_rename` and `hooks_rename`. `vault add` adoption is noted as a follow-on.

1. feature-rename-integrity check. A new read-only checker walks the docs tree and reports
   the drift classes nothing else owns (filename feature-segment vs `#feature` tag;
   exec-folder name vs its records' tag; docs still tagged with a feature whose canonical
   surfaces have moved), each with observed-vs-expected and a `vault feature rename`
   remediation hint. Wired into `run_all_checks` after `check_features` and exposed as
   `vault check feature-rename-integrity`.

## Rationale

The research established that the only thing the four paths genuinely share is transaction
mechanics, and that the safety the uniform-rename work proved (containment + reverse
journal + symlink-safety + line-ending fidelity) is exactly what the other three lack. A
scoped transaction engine is the smallest abstraction that lets all four inherit that
safety without forcing a single-file rename to pay a whole-tree snapshot cost, and it is
the literal reading of the "converge onto the shared rename engine" mandate. Per-domain
locks are the only lock granularity that is actually sound given the whole-tree
`related:` cascade. The read-only check follows the conservative posture of the
cli-rename-integrity ADR (detect, do not auto-reconcile, until a fix policy is argued
separately). Grounding is in the linked research and reference.

## Consequences

Gains: every rename surface becomes atomic with byte-for-byte rollback, concurrency-safe
within its domain, and case/symlink/line-ending safe; `vault rename`'s dangling-link
defect and its duplicate link engine are both eliminated; post-rename drift becomes
detectable; and `resource_rename`/`hooks_rename` gain their first real safety and first
unit tests.

Costs and difficulties: the engine extraction touches the most safety-critical code in
the feature and must keep the adversarial suites byte-identical (the chief risk); the
`vault rename` `incoming_rewritten` semantics change is observable and must be migrated
deliberately; the lock is only meaningful because multiple surfaces adopt the same
target, so partial adoption would give false assurance.

Honest limits: the per-domain lock serializes unrelated concurrent edits in a domain
(coarse but sound); `vault add` is not yet brought under the lock (a noted follow-on);
the integrity check is detection-only at first; and crash-durability is still bounded by
the in-memory journal (a hard kill mid-apply is not covered), inherited from the
uniform-rename decision.

Pathways opened: a single place to harden every future rename, an eventual filename-wins
`--fix` for the integrity check, and bringing the remaining docs mutators (`vault add`)
under the docs lock.
