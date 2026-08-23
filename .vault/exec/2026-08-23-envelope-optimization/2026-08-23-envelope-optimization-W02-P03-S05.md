---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:511ec2dc7025c86b212fa394eb9f8d3c724c3c6437ad33c5973d9df49c889285'
step_id: 'S05'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---
# Apply elision to the payload ahead of the format branch and derive the human summary line from it

## Scope

- `src/vaultspec_core/cli/_repair_render.py`

## Description

- Bound every repair payload section that grows with the repair, using the same limits the
  human rendering already applied, so one constant governs both surfaces.
- Bound the collections nested *inside* those sections: the diagnostics grouped under each root
  cause, and the findings carried by each per-checker summary.
- Drop the second copy of the diagnostics carried by the dry-run postcheck phase, which
  re-reports the same results object the check phase already carried, keeping the counts and
  stating why the findings are absent.
- Bump the payload contract to its second version, since the shape of those sections changed.

## Outcome

The human surface capped these sections while the machine payload returned them whole, so the
payload was largest exactly when the vault was most broken — the state the command exists to
diagnose.

Measured on a 10,476-document vault with five percent of documents damaged:

| stage | payload |
| --- | --- |
| before | 2,550,136 bytes |
| after bounding the sections | 166,140 bytes |
| after bounding the nested collections and removing the duplicate phase | 115,167 bytes |

A cumulative reduction of 95.5%. On the smaller 1,229-document fixture, 149,214 to 57,645 bytes.

The intermediate figure is the interesting one. Bounding the top-level sections left 99% of the
payload in two places whose outer lists were already within their caps: one reported four rows
of four, with nothing elided, while a single row embedded 2,428 diagnostics. **A row cap is not
a byte cap wherever a row may contain a collection.** That is the same defect the campaign
exists to remove, reproduced by an incomplete application of its own remedy.

The duplicate phase was verified from the code rather than inferred from the data: the dry-run
postcheck is handed the identical results object the check phase received, and a dry run writes
nothing, so re-running the checkers cannot change what they find. Measured, the two phases held
byte-identical sets of 170 findings.

A hypothesis that did not survive measurement is worth recording too: the root-cause grouping
looked like a superset of the per-phase findings, which would have allowed dropping the latter
entirely. It is not — it carries 78 distinct findings against 170, because it is itself
windowed. Acting on the appearance would have lost data.

## Notes

Two tests now pin the contract rather than merely tolerating it: every growing section is a
window whose returned count matches its rows and does not exceed its total, and the nested
collections carry their own windows. The second is the regression guard for the row-cap
distinction above; without it the nested bounding could be removed and every other test would
still pass.

Updating the six existing assertions to read the new shape would have left exactly that gap.
Accepting a shape is not pinning it.

The contract test then caught the phase-deduplication change, failing because the postcheck
entry no longer carried a findings key. It was tightened rather than relaxed: findings must be
either present and bounded, or absent and marked, with counts either way. An unmarked omission
is indistinguishable from a checker that found nothing.

The payload remains 115,167 bytes against a 14 kilobyte budget for this tier, roughly eight
times over. The dominant remaining term is the phase list at 63,774 bytes.
