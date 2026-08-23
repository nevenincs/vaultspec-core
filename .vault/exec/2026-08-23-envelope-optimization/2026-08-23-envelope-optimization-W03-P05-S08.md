---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:14cc65484b6a6d11fff8766ee30defb2ccfd50eb6a9516ac3bfe49e2fa4d03a3'
step_id: 'S08'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Invert the derived-edge CLI default and require an explicit scope for a full graph export

## Scope

- `src/vaultspec_core/cli/vault_cmd.py`

## Description

- Make the derived edge set opt-in rather than default.
- Evaluate the projection flag before the format flag so a narrowing request narrows the payload on every surface.
- Emit the derived set's total and truncation state beside the rows.
- Add a window over the derived set so the cap can be paged past.

## Outcome

Measured at 10,476 documents. The default export fell from 416,754,257 bytes and twenty minutes to 15,437,557 bytes and three seconds.

The summary flag had no effect at all on the machine surface: the format branch returned before the projection branch was reached, so a request for metrics returned the whole graph. It cost 11,175,730 bytes where the human form of the same flag returned 4,794 - a penalty of more than two thousand times for asking the narrower question, with nothing telling the caller their flag had been discarded. That path now returns 25,134 bytes, inside the ceiling for a single response.

## Notes

The derived set is a computed similarity ranking rather than vault state, and it was 94% of the payload. Making it opt-in is a behaviour change for any caller that relied on the default, which is why the export states its total and truncation alongside.

A full unscoped export is still not a context-sized payload; the node array dominates what remains. The decision record is explicit that such an export should require scoping.
