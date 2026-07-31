---
tags:
  - '#adr'
  - '#modified-stamp-provenance'
date: '2026-07-30'
modified: '2026-07-30'
body_schema: 'body-v1'
body_hash: 'sha256:03e8442e0c0f9c99d184fd3836e7d650c6ae06a3e73bab7560134885293a2d9a'
related:
  - '[[2026-07-30-modified-stamp-provenance-research]]'
  - '[[2026-06-12-vault-orientation-adr]]'
  - '[[2026-07-27-body-schema-attestation-adr]]'
  - '[[2026-07-23-vault-check-validators-adr]]'
---

# `modified-stamp-provenance` adr: `derive stamp staleness from a content fingerprint, not file mtime` | (**status:** `accepted`)

## Problem Statement

The `modified:` reconciliation checker infers staleness by comparing the stamp to the
file's mtime date. On this corpus that signal is not evidence of content change.
`2026-07-30-modified-stamp-provenance-research` establishes the condition: the open
staleness findings descend from a vault-scoped, content-neutral bulk touch; they sit on the
very values an earlier run of the checker's own fix path wrote; the fix cannot converge in
a single pass; and a second pass would cross the git-signature threshold and suppress the
evidence corpus-wide rather than resolve it. Every branch that reads frontmatter rather
than the filesystem reports zero findings, so the filesystem is the whole of the signal.

The governing record already rejects that evidence source: `2026-06-12-vault-orientation-adr`
D3 ruled mtime out as a recency source because it does not survive git operations, and
described hand-edit reconciliation as firing when a document's content fingerprint is newer
than its stamp. The shipped checker substituted mtime for that fingerprint, making this
implementation drift from an existing decision rather than an unconsidered gap. A decision
is needed on what staleness is actually derived from, and on the disposition of the
currently-wrong stamps.

## Considerations

- The stamp's consumers and contract are settled by `2026-06-12-vault-orientation-adr`
  D3/D3b and are not reopened here: CLI-owned stamping, lenient parsing, canonical
  rewrite. Only the staleness evidence source is at issue.
- The permitted hand-edit surface is body prose only; frontmatter hand-edits are forbidden
  corpus-wide. The only legitimate unstamped change a document can receive is therefore a
  body change, which makes the body the exact scope a fingerprint must cover.
- The project already operates content-hash provenance: the body-schema baseline ledger
  records path and digest evidence, and `2026-07-27-body-schema-attestation-adr` ratified
  that an absent attestation is silence, not a finding - the precedent for how an
  un-fingerprinted document should behave.
- Mtime failure is not exceptional here; it is routine. The research records two
  corpus-scale mtime events in six weeks, on top of every clone, checkout, and
  stash/restore cycle the git-signature guard was built to paper over.
- This repository runs concurrent sessions across shared worktrees; any single hot ledger
  file written by every mutating verb would be a standing merge conflict.
- A migrations framework exists and has shipped corpus-affecting convergence migrations; a
  deterministic one-time seed is inside its normal envelope.
- `vault check all` has no dry-run; the non-fix run is the only preview, so the fix must be
  deterministic for that preview to be truthful.
- The `vault-fix` pre-commit hook runs `vault check all --fix` unattended with
  `pass_filenames: false` on every commit touching any markdown, giving a commit-scoped
  protocol a corpus-wide mutation surface; both bulk stamp-rewrite generations were emitted
  through this channel, and the hook runner's staging protocol reverts the working tree
  around hook execution, so any hook-time tree mutation is additionally hazardous in shared
  worktrees.

## Considered options

- **Keep mtime; repair the fix loop and retune the guard** (rebuild mtimes per iteration,
  post-fix re-verify, adjust ratio). Rejected: repairs convergence, not truth. A
  content-neutral touch still fabricates staleness for the whole corpus; mtime is not
  evidence of content change, and no loop repair makes it so.
- **Git-derived last-content-change.** Rejected: `2026-06-12-vault-orientation-adr` already
  rejected git as a recency source (cannot be assumed present in every deployment); on this
  corpus the git signal is additionally polluted by the bulk stamp-rewrite commits
  themselves, so filtering would need its own heuristics - the failure class being removed.
- **Retire staleness detection entirely; stamp only on CLI mutation.** Rejected, narrowly -
  it is the runner-up and the fallback if fingerprint cost proves unacceptable. It destroys
  the fabrication engine at near-zero cost but abandons the reconciliation half of D3:
  permitted body-prose hand edits would never surface, and the stamp silently under-reports
  forever.
- **Content fingerprint stored in a committed workspace ledger** (the body-schema baseline
  idiom). Rejected: path-keyed (every rename and archive must cascade through the rename
  engine) and a single-file merge hotspot under this project's concurrent-worktree reality.
- **Content fingerprint carried in document frontmatter (chosen).** A machine-maintained
  field holding a hash of the body, written beside `modified:` by every stamping code path.
  Staleness becomes a deterministic comparison: current body hash versus attested hash.
  Travels with the document through clone, archive, and rename for free; diffs localize to
  the document being edited.

## Constraints

- Hash scope is the body only. Frontmatter is CLI-owned and re-attested by the same write
  that changes it, so including it would be self-referential; body-only aligns the
  fingerprint exactly with the permitted hand-edit surface.
- New-field surface cost: the frontmatter schema section of the framework rule, the shipped
  templates' machine-filled fields, the curator's allowed-keys, document metadata parsing
  (precedent: the `step_id` first-classing in `2026-07-23-vault-check-validators-adr`), and
  the template-annotations guard's allowed-keys set. The last is governed by the sibling
  `guard-subject-integrity` decision; the two land independently.
- The seeding migration writes facts, not inferences: the hash of each document's current
  committed body. It must not touch `modified:` values (see amnesty, below). Deterministic
  and idempotent by construction.
- No new dependencies; hashing is stdlib. The lenient-date machinery, the stamp writer's
  guarded atomic rewrite, and the missing, non-canonical, unparseable, and predates-date
  branches are unchanged.

## Implementation

A machine-maintained frontmatter field (working name `body_hash`, canonical form a
prefixed lowercase hex digest; exact name and form are the plan's to fix) is written by
every code path that writes `modified:`: scaffold, every mutating verb, and the checker's
own fix path.

The staleness branch of the modified-stamp checker is rebuilt on the fingerprint: attested
hash present and equal to the current body hash means clean; present and unequal means
stale (WARNING, fixable). The fix refreshes `modified:` to today - the observation date,
the only honest value since the true edit date of a hand edit is unrecorded - and
re-attests the hash in the same write, so the run converges: an immediate second run
compares equal and reports clean. A document with no attested hash yields no staleness
inference (silence, per the `2026-07-27-body-schema-attestation-adr` precedent); under fix
it is seeded (hash written, stamp untouched, INFO diagnostic). All mtime consultation is
deleted: the staleness-by-mtime branch, the future-mtime clamp, and the git-signature
heuristic and its document tally are removed wholesale - once mtime is not evidence, a
heuristic to excuse mtime has no subject. The module docstring is rewritten to the new
semantics.

The `vault-fix` pre-commit hook stops running `--fix` unattended: its entry becomes the
non-mutating `vault check all`, a pure gate. Unattended corpus-mutating repair from inside
a commit is retired as a discipline, not just detuned: `pass_filenames: false` gives the
hook the whole corpus as blast radius regardless of what the commit touches, a hook-time
fix writes dates nobody reviewed into commits that are not about them, and the hook
runner's revert-based staging protocol makes hook-time tree mutation unsafe in shared
worktrees. The fingerprint design makes this costless - the non-fix check is an exact,
deterministic preview, so a failing gate names precisely what a deliberate operator-run
`--fix` will do - and the fix remains one command away, run on purpose, reviewed like any
other change.

A one-time migration seeds the field corpus-wide from current body content. Existing
`modified:` values receive amnesty: they are known to carry two generations of mtime-derived
fiction, but every candidate recomputation source is worse - mtime is the defect, and git
history is polluted by the stamp-rewrite commits themselves - so the stamps stand as-is and
correctness restarts at seed time. The 790 open findings dissolve without any stamp being
rewritten, because the evidence that produced them is no longer consulted.

## Rationale

The knockout criterion is that staleness evidence must be a property of the content,
because content is the thing the stamp attests. Mtime is a property of the filesystem event
log, which this project's own history shows is rewritten wholesale by git operations, by
bulk touches, and by the fix path itself - the checker was measuring its own exhaust. Every
mtime-preserving option fails this criterion; the git option fails D3's portability
constraint a second time. Between the two fingerprint carriers, frontmatter wins on the
concurrency reality of this repository (no shared hot file) and on rename-transparency; the
ledger idiom remains right for the body-schema case, where attestation is a deliberate
human act rather than a side effect of every mutation.

The chosen design also repairs the operational defects without bespoke machinery:
convergence holds because the fix writes the comparison's own right-hand side; the missing
dry-run stops mattering for this class because the non-fix run becomes an exact preview of
a deterministic fix; and the self-sealing failure mode is structurally impossible because
there is no suppression heuristic left to trip. Amnesty is chosen over recomputation
because a third bulk write of inferred dates - the exact shape of `cc1c1353` - is the
pattern this record exists to end; the seed migration is categorically different in that it
writes verifiable facts derived from the content itself.

## Consequences

- The open findings close without any stamp rewrite; a third generation of fabricated dates
  never happens. Hand body edits are detected deterministically from seed time onward,
  including across clones and checkouts, which mtime never survived.
- The corpus gains one machine field on every document: a one-time seeding diff across the
  whole corpus, then per-document churn only alongside real mutations (the hash changes in
  the same diff as the body it fingerprints, which is self-documenting).
- Historical inaccuracy is accepted: pre-seed `modified:` values remain distorted by the two
  mtime generations until each document's next real mutation, so orientation recency
  ordering stays imperfect for dormant legacy documents. Recorded openly as the price of
  amnesty.
- A stale finding's fix writes today's date, an upper bound on the edit date, not the edit
  date itself; the stamp's meaning for hand-edited documents is "reconciled on", one day
  coarser in truth than for CLI-mutated ones.
- Third-party or downstream vaults created before the field existed behave exactly like this
  corpus: silent until seeded by migration or touched by a mutating verb - no false findings
  on old corpora, by the silence rule.
- The checker sheds its only heuristic and its only environment-dependent input, simplifying
  both the implementation and its test surface (no more mtime manipulation in tests).
- Commits with outstanding fixable findings now fail the gate instead of being silently
  repaired in flight; authors run the fix deliberately and commit its effects visibly. The
  hook loses its self-healing convenience, which is exactly the property that let two
  corpus-scale corruptions ship unreviewed.
