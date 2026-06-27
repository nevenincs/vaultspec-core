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

### enc-tag-rewriter-eol-normalization | high | the tag rewriter normalized mixed/CR line endings and converted exotic separators

A dedicated encoding/line-ending content-fidelity pass (cross-platform vaults mix LF, CRLF,
classic-Mac CR, and exotic in-line separators) demonstrated that `_rewrite_feature_tag_block`
used `splitlines()` (which breaks on every Unicode line boundary) plus a single detected
newline and `newline.join()`, so on every renamed doc with non-uniform endings it silently
re-terminated every line, converted in-body form feeds / vertical tabs / NEL / LS / PS to
newlines, and dropped a CR-only file's trailing CR. RESOLVED: a new `split_keepends` helper
(splits only on `\r\n`/`\r`/`\n`, models lines as `[content, ending]` pairs) lets the rewriter
edit only the targeted line's content and keep every other line byte-for-byte; reassembly is a
plain concatenation. Output is byte-identical to before on uniform docs.

### enc-cascade-eol-normalization | high | the vault-wide related: cascade normalized endings and dropped trailing newlines

Same root cause in the shared `rewrite_incoming_refs`, with a wider blast radius (it runs over
every doc in the vault) and an extra defect: it dropped the trailing newline whenever the
file's final terminator differed from the detected newline. RESOLVED by the same `split_keepends`
refactor, handling the four interaction sites (duplicate-line drop removes the whole pair; the
frontmatter line budget and indexing iterate logical lines; the closing-fence guard is intact;
flow-to-block tag synthesis assigns each new line the original `tags:` line's ending). The
structure check shares this function; its regression suite stays green. The read-only dry-run
counter `_count_related_refs` was also switched to `split_keepends` for prediction consistency.
Proven by 34 byte-exact tests (LF/CRLF/CR-only/mixed/exotic/no-trailing-newline/frontmatter-only/
BOM), adversarially re-verified.

### enc-bom-subject-not-discovered | medium | a UTF-8-BOM authored doc carrying the old feature was invisible to the scanner

The shared parser's `content.lstrip()` did not strip a leading `﻿`, so a BOM-prefixed
authored doc's frontmatter was not recognized and the doc was silently excluded from a rename
(and from the regenerated index) - a silent partial rename. RESOLVED: both `parse_frontmatter`
and `parse_vault_metadata` now strip a single leading BOM before the `---` check, so BOM-prefixed
UTF-8 docs are discovered everywhere the parser runs (vault scan, feature listing, graph build,
every check). A UTF-8-BOM doc is valid UTF-8, so this one central fix is sufficient; the rename
rewriters already preserve the BOM byte-for-byte on write. Proven end-to-end (a BOM doc is now
discovered, renamed, and keeps its BOM) plus parser unit tests.

### enc-non-utf8-invisible | medium | non-UTF-8 docs were silently skipped by every reader

A UTF-16 / Latin-1 `.md` fails `read_text(encoding="utf-8")` and was silently dropped by
`_scan_all`/`list_features`, so a rename silently omitted it. RESOLVED by surfacing rather than
auto-decoding (decoding an arbitrary encoding and rewriting it would silently convert the file to
UTF-8): a new read-only `check_encoding` walks the docs tree directly (a non-UTF-8 doc is absent
from the snapshot) and reports each non-UTF-8 file as an ERROR to convert by hand; wired into
`run_all_checks` (so `vault check all` surfaces it) and exposed as `vault check encoding`. A
plain UTF-8 and a UTF-8-BOM file both pass. Proven by tests (UTF-16 + Latin-1 flagged; clean vault
green; `_archive`/`.obsidian` skipped).

### enc-cr-only-stamp-noop | low | refresh_modified_stamp did not refresh a classic-Mac CR-only doc's stamp

`refresh_modified_stamp` located the frontmatter and its `modified:`/`date:` lines with
`re.MULTILINE` regexes, which only recognize `\n` as a line boundary, so a CR-only (`\r`)
document matched as a single line and the stamp was silently left stale (and the
date-as-last-line case was a no-op too). RESOLVED: the function now splits the frontmatter
via `split_keepends` (the same `\r\n`/`\r`/`\n` splitter the rewriters use) and rewrites or
inserts the stamp line-by-line, preserving every line's exact ending. The two unused
MULTILINE regexes were removed. Covered by a new `TestRefreshModifiedStamp` suite
(LF/CRLF/CR-only rewrite-and-insert, BOM+CRLF, no-frontmatter), and the 34-test
modified-stamp regression stays green.

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

A third pass audited encoding and line-ending contamination for cross-platform vaults
(mixed LF/CRLF/CR and exotic separators). It found two further HIGH byte-corruption
defects in the content rewriters, both resolved by the `split_keepends` terminator-
preserving refactor and proven by 34 byte-exact tests plus adversarial re-verification;
the structure-check regression stays green.

A fourth pass then closed the two discovery-layer gaps that the third pass had deferred:
the shared parser now strips a leading BOM (so UTF-8-BOM authored docs are discovered and
renamed with their BOM preserved), and a new read-only `check_encoding` surfaces non-UTF-8
docs as errors (wired into `vault check all` and exposed as `vault check encoding`) rather
than letting them be silently excluded. A final touch resolved the last low item: the shared
`refresh_modified_stamp` now refreshes classic-Mac CR-only docs (via `split_keepends`),
closing every encoding/line-ending follow-up surfaced by the hardening passes.
