---
tags:
  - '#audit'
  - '#curator-reframe'
date: '2026-06-28'
modified: '2026-06-28'
related:
  - "[[2026-06-28-curator-reframe-plan]]"
---

# `curator-reframe` audit: `curator reframe code review`

## Scope

Verify phase for the curator reframe feature. A code review covered the Python surface of
the change: the `AdrStatus` enum in `core/enums.py`, the `adr_supersede` reconciliation in
`core/adr.py`, the new `adr_status.py` checker and its registration, the
`vault check adr-status` CLI command, and the enum and checker tests. The skill and agent
prose were out of scope (intentional rewrite). The review was followed by remediation and
a full re-run of the unit gate.

## Findings

### review-divergence-deadcode | high | snapshot dropped superseded_by, making the divergence check dead in production

`VaultGraph.to_snapshot()` built `DocumentMetadata` without `superseded_by`, so the
frontmatter-versus-body supersession divergence branch in `check_adr_status` could never
fire on the real call path. The hand-built-snapshot unit tests passed because they set
`superseded_by` directly, masking the defect. Resolved: `to_snapshot()` now threads
`superseded_by` from the node frontmatter, and a graph-path integration test
(`TestGraphPath`) exercises the divergence through `VaultGraph.to_snapshot()` so the gap
cannot regress.

### review-backup-toctou | medium | backup re-read the file, risking a stale rollback

`_normalize_h1_quote` read the file once to process it and again to write the `.bak`
backup, opening a window where a concurrent external edit would back up different bytes
than were processed. Resolved: the raw bytes are now captured once and reused for both the
decode and the backup.

### review-h1-anchor | low | scanner returned the first status-bearing H1, not the first H1

`_find_h1_status` scanned every level-one heading line and returned the first with a status
token, so a title without a status marker could defer to a later heading. Resolved: the
scanner now anchors to the document's first H1 and treats a missing marker there as no
parseable status, matching the documented contract.

### review-modified-stamp | low | --fix left the modified stamp stale, needing a second pass

`_normalize_h1_quote` rewrote the H1 without refreshing the `modified:` stamp, so a
`--fix` pass left the stamp stale until a later run. Resolved: the quoting rewrite now
refreshes the stamp in the same pass, mirroring `adr_supersede`.

## Recommendations

All review findings were remediated in this feature; no deferred items. The unit gate
passes at 1583 tests after remediation. Follow-on curation work, separate from this
feature, remains available for the curator to run: 10 historical ADRs still carry legacy
`## Status` sections or table-form status that the `adr-status` check surfaces as warnings
but cannot auto-fix, and which need manual normalization through the CLI mutators.
