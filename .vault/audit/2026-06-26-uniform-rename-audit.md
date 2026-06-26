---
tags:
  - '#audit'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
  - "[[2026-06-26-uniform-rename-adr]]"
---

# `uniform-rename` audit: `uniform feature rename verb implementation review`

## Scope

Reviewed the completed implementation of the uniform feature rename verb across the
feature branch: the shared-module extraction (`rename_ops.py`), the `rename_feature`
backend with reverse-journal rollback (`query.py`), the CLI command (`vault_cmd.py`),
the 25 real-filesystem tests, and the firmware conformance. Two independent
`vaultspec-code-reviewer` passes were run with distinct lenses - backend/rollback
correctness, and CLI/test-integrity/firmware. The CI unit gate was green before the
review (1402). Resolutions applied in this review round are recorded inline.

## Findings

### archive-snapshot-rollback-gap | high | rename mutated archived docs that the rollback never snapshotted

The shared `related:` cascade `rewrite_incoming_refs` skipped only `data`/`logs`/dot
directories, not `.vault/_archive/`, so a rename rewrote archived documents'
back-reference wiki-links and bumped their `modified:` stamps; but `_snapshot_docs`
excludes `_archive`, so a failure after the cascade would leave those mutations
un-rolled-back (drift), and on success it violated the ADR's "archived docs are not
touched" boundary. RESOLVED: added an `exclude_dirs` parameter to
`rewrite_incoming_refs` (default empty, preserving the structure check's whole-vault
behaviour) and the rename backend now passes `{"_archive"}`, so archived documents are
never mutated by a rename. Covered by a new regression test asserting an archived
back-reference is byte-identical after a rename.

### firmware-atomicity-overstated | medium | user-facing copy implied crash-durable atomicity

The reverse journal is in-memory, so it rolls back on an exception raised during apply
but not across a hard process kill; the CLI docstring ("byte-identical after any
mid-apply failure"), the firmware rule ("applies atomically with rollback"), and the
ADR ("True cross-file all-or-nothing") overstated this. RESOLVED: reworded the CLI
docstring and the firmware rule to "rolls back on failure during apply", and appended
an explicit crash-window limitation to the ADR's "Honest limits".

### firmware-reference-detail-missing | medium | the CLI reference carried only the one-line synopsis for rename

The hand-authored per-command detail sections in the locally-resident CLI reference
covered archive/unarchive but not rename. RESOLVED for the firmware reference: added a
`vault feature rename` detail section documenting every option and the `--force` merge,
matching the sibling style, and re-seeded it into the installed workspace. The public
`docs/CLI.md` richer per-command block is deferred to the separate user-docs effort.

### dry-run-writes-graph-cache | low | a dry-run persisted the derived graph cache

The cross-feature link analysis built a cached `VaultGraph`, which persisted a graph
cache file on a cache miss even under `--dry-run`. RESOLVED: the analysis now builds the
graph with `use_cache=False`, so a dry-run writes nothing and a real run still
invalidates the cache from the CLI afterwards.

### human-output-cross-feature-label | low | applied-run summary mislabelled intra-feature rewrites

The applied-run summary printed the cascade count as "cross-feature related-link
rewrite(s)", but the count includes intra-feature `related:` rewrites. RESOLVED:
relabelled to "related-link rewrite(s)"; the dry-run line was already neutral and the
JSON key `related_rewrites` is unambiguous.

### backend-cache-invalidation-layering | low | graph-cache invalidation lives only in the CLI

The ADR's layering attributes graph-cache invalidation to the apply path, but only the
CLI command invalidates after a successful rename. ACCEPTED as-is: the cache manifest is
a total fingerprint match and a rename changes the file set, forcing a rebuild on next
load, so a direct backend caller self-heals; noted as a latent design deviation, not a
correctness defect.

### extraction-and-core-logic-verified | low | the extraction, transform, tag rewriter, validation, and tests are sound

Verified-correct, no action: the P01 extraction is behaviour-identical with correct
re-exports and lazy cycle-avoidance; the anchored date-keyed filename transform is
prefix-collision-safe (the `-{old}-` boundary plus `re.escape`) and preserves audit
topic-infixes; the tag rewriter touches only the feature tag in the `tags:` block (never
the directory tag, `related:`, or body) with flow-to-block normalization; validation and
per-file collision detection are complete; the CLI mirrors the archive conventions and
the shared JSON envelope; and the 25 tests are genuine real-filesystem assertions with
no mocks, stubs, skips, or tautologies (the rollback test induces a real
directory-at-destination failure and asserts true byte-identity).

### sec-rollback-symlink-write-through | high | rollback could write through a `.md` symlink to an out-of-bounds target

A dedicated defensive security pass (filesystem-mutation threat model) demonstrated that
`_snapshot_docs` captured bytes through a `.md` file-symlink (via `is_file()`) and
`_rollback_rename` restored with raw `write_bytes`, which follows a surviving symlink and
clobbers the external target. RESOLVED: the snapshot, the cascade, and the dry-run
predictor now skip `is_symlink()` documents, and rollback restores via `_safe_restore_bytes`
(unlinks a symlink first, never writes through it). Proven by real-symlink tests.

### sec-dir-symlink-write-escape | high | index/exec writes could escape `.vault/` via a directory symlink

Demonstrated: with `.vault/index` symlinked to an external directory, the raw
`mkdir(exist_ok=True)` plus `atomic_write` wrote the regenerated index outside the vault.
RESOLVED: a containment guard `_assert_within_docs` resolves symlinks and `..` and refuses
any source/destination that escapes the docs tree; it runs before every exec-folder mkdir,
every file rename (both endpoints), and the index regen. Proven by a real directory-symlink
escape test that asserts refusal plus byte-identical rollback.

### sec-symlink-unbounded-read | medium | symlink-target reads were unbounded and pulled external bytes into the vault

`_snapshot_docs`/`_predict_rewrites` read every `.md` including symlink targets, an OOM/DoS
and information-exposure channel. RESOLVED by the same `is_symlink()` skips above. The
adversarial re-verification surfaced one further read-only residual - the dry-run
tag-rewrite count loop still read a symlinked source's target - which was closed by an
`is_symlink()` skip there too, so dry-run and apply are symmetric and no out-of-bounds
read remains on the rename path.

### sec-arg-injection-and-collision | low | source unvalidated; case-insensitive collisions under-reported; Windows device names accepted

RESOLVED: `_validate_feature_rename` now shape-gates `old` with the kebab grammar and rejects
Windows reserved device names for `new`; collision detection keys on `os.path.normcase`; and
`_rewrite_feature_tag_block` refuses to persist a rewrite of a document whose frontmatter
never closes. Covered by 48 adversarial real-filesystem tests (argument injection with
`../`, separators, NUL, newline, regex metacharacters, unicode homoglyphs; reserved names;
malformed and non-UTF8 content; collision data-loss).

### sec-no-cross-process-lock | medium | concurrent mutators are not serialized (accepted, documented)

`rename_feature` takes no vault-wide advisory lock, so a concurrent mutating command could
interleave with the snapshot/apply/rollback and cause a lost update. ACCEPTED as a documented
limitation: there is no established vault-wide lock target and a partial lock would be
inconsistent with the single-file `advisory_lock` convention. Recommended follow-up: a shared
vault-level advisory lock adopted by all mutating vault commands.

### sec-crlf-stamp-fidelity | medium | the shared modified-stamp helper corrupted CRLF line endings

Surfaced by the CRLF security/fidelity tests: `refresh_modified_stamp` rewrote a CRLF
`modified:` line to LF because `[^\n]*$` consumed the trailing `\r`. RESOLVED at root cause in
`models.py` (the regex now stops at `[^\r\n]*` and captures `(?P<cr>\r?)` to re-append it).
This is a shared helper used beyond rename; the 122-test modified-stamp regression set and the
full gate stay green.

## Recommendations

The first-round high and medium findings are resolved. A subsequent defensive security
pass against a filesystem-mutation threat model found two further HIGH out-of-bounds
write vectors (symlink-based) plus medium/low issues; all are resolved and proven by 48
adversarial real-filesystem tests (real OS symlinks, argument injection, malformed input,
collision data-loss), and the fixes were adversarially re-verified. The full unit gate is
green at 1451. Two items are accepted as documented follow-ups rather than blockers: a
vault-wide advisory lock for concurrent mutators (`sec-no-cross-process-lock`) and the
backend-vs-CLI cache-invalidation layering note. A future `feature-rename-integrity`
check and the public `docs/CLI.md` detail block (folded into the separate user-docs
rework) remain reasonable follow-ons. No residual out-of-bounds, symlink, or data-loss
vector remains.
