---
tags:
  - '#research'
  - '#modified-stamp-provenance'
date: '2026-07-30'
modified: '2026-07-30'
body_schema: 'body-v1'
body_hash: 'sha256:efaa69501aa50d2fbc7d5117bbf16733e03b8c1f85c1d2bbd9edcc228d307128'
related: []
---

# `modified-stamp-provenance` research: `mtime as a staleness signal on a bulk-touched corpus`

## Findings

The modified-stamp checker decides a `modified:` frontmatter stamp is stale by comparing it
against the file's mtime date. This investigation, run 2026-07-30, measured what that
signal actually reports on this corpus.

**The current finding population is entirely mtime-derived.** A read-only check run reports
790 stale findings, every one of them targeting the same value, `2026-07-23`. Every branch
of the checker that reads frontmatter rather than the filesystem reports zero: missing,
non-canonical, unparseable, and predates-date are all empty. The staleness signal is
therefore the only branch firing, and it is firing on one date.

**That date corresponds to no content change for most of the affected documents.** 782
vault documents share a single mtime instant, `2026-07-23T02:28:59Z`. Zero non-vault
tracked files share it, across all tracked files in the repository - so it was not a clone,
a checkout, or any whole-tree git operation. Of the 790 documents now reported stale, 743
last had their content changed on 2026-07-13. The 2026-07-23 instant was a vault-scoped,
content-neutral bulk touch: a date on which nothing changed in the documents it stamped.

**The condition is second-generation, and the first generation is on the record.** Commit
`cc1c1353` (2026-07-13) is titled as a refresh of stale modified stamps via the check's own
fix path. It rewrote 853 files, 853 insertions and 853 deletions, writing five distinct
mtime-derived values: `2026-06-13` on 709 documents, `2026-07-10` on 73, `2026-06-27` on
40, `2026-06-28` on 16, and `2026-06-25` on 15. Those five values are exactly the prior
stamps carried by the 790 documents reported stale today. The present findings are the
output of the previous fix run.

**The fix cannot converge in a single pass.** The checker builds its per-document mtime
tally once, before the fix loop runs, and the aggregate check routine appends the
modified-stamp result without any post-fix re-verification pass. The fix writes through an
atomic replace, so every rewritten file's mtime becomes the moment of the write. The result
is a stamp of `2026-07-23` on a file whose mtime is now the current day - still stale by
the checker's own rule, immediately after being "fixed".

**The second pass would suppress the evidence rather than resolve it.** The checker carries
a git-operation guard that suppresses all staleness findings when the largest two mtime-date
buckets together account for at least 80 percent of documents, on the theory that such
concentration indicates a git operation rather than real edits. Today that ratio is
933/1210 = 0.771 and the guard is inactive - no suppression diagnostic is emitted. A
simulated post-fix distribution, computed rather than applied, reaches 977/1210 = 0.807,
which crosses the threshold. A second run would therefore report the corpus clean while 790
documents carried fabricated dates. The heuristic is inactive when the corpus is
demonstrably touched, and would activate precisely once the corpus had been made worse.

**No preview exists.** The aggregate check verb exposes only a fix flag, feature filter,
verbosity, JSON output, hint suppression, and target selection. There is no dry-run, so a
790-file rewrite has no safe preview short of reading the fix logic.

**The guard's model does not cover the observed event.** It is built for whole-tree git
instants - a fresh clone collapsing every file onto one timestamp, a stash and restore cycle
adding a second. A vault-scoped bulk touch that leaves every non-vault file untouched is a
third category the two-bucket model does not represent.

**The governing decision already rejected this evidence source.** The vault-orientation
record's D3 ruling excluded mtime as a recency source on the grounds that it does not
survive git operations, and described hand-edit reconciliation as firing when a document's
content fingerprint is newer than its stamp. The shipped implementation substituted mtime
for that fingerprint, so the condition documented here is implementation drift from an
existing decision rather than an unconsidered gap.

**Scope of the corpus.** 1210 documents in the checker's snapshot; 1221 Markdown files on
disk under the vault, of which 11 sit under the archive tree.

## Sources

- Read-only aggregate check runs with JSON output, 2026-07-30; no fix path was ever invoked.
- Direct reading of the modified-stamp checker module and the aggregate check routine for
  tally ordering, guard constants, and fix-write semantics.
- Repository history: commit `cc1c1353` (2026-07-13) and its diff statistics; the five
  commits touching the vault on 2026-07-23, totalling 44 files.
- Filesystem mtime distribution across vault Markdown files, and the same distribution
  across all tracked non-vault files, 2026-07-30.
