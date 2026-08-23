---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:0cc22b2a04ac3b1607440a274b3e1d3cbf5978abf805ab36321e4553496f280b'
step_id: 'S01'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---
# Serialise the tool definition in the true wire form and add a read-only ceiling

## Scope

- `src/vaultspec_core/mcp_server/tests/test_context_budget.py`

## Description

- Replace the guard's serialiser with the true wire form: dump the tool model excluding
  none-valued fields, by alias, with compact separators, so `output_schema` is counted and
  no whitespace is measured that the protocol never sends.
- Reset the aggregate ceiling from measured truth to 45,000 characters and document it as a
  ratchet to be lowered as the campaign lands, never raised, with the 5,000-token budget
  target recorded inline.
- Add a separate ceiling and guard test for the read-only surface, which had none.
- Add a component breakdown to the failure report so a regression names the description,
  input schema or output schema that grew, and report the token cost alongside characters.

## Outcome

The guard was measuring 21,943 of 43,919 real characters, 50% coverage, and passing against a
26,000 ceiling while roughly 22,000 characters grew unobserved. The read-only surface was
covered at 25% with no ceiling at all. Two independent causes: `output_schema` was omitted
entirely, and indent-2 serialisation inflated the covered half so the uncovered half appeared
proportionally smaller than it was.

After the change the full surface measures 43,919 characters, roughly 12,693 tokens, against a
45,000 ceiling with 1,081 characters of headroom; the read-only surface measures 20,131 against
21,000. The suite runs 100 tests, one more than before, with lint and format clean.

The corrected diagnostic immediately paid for itself: output schemas are 26,785 of 43,919
characters, 61% of the entire static surface, and the `status` tool alone is 85% output schema.
This confirms from an independent measurement path what the research records about docstrings
being lifted into schema descriptions, and it sharpens the last Wave's target - the cost is in
generated schema descriptions, not in the tool descriptions, which total only 7,599 characters.

## Notes

The static surface remains 2.5 times its budget after this Step. Nothing was reduced here; the
Step only restores the ability to see the surface honestly and to hold whatever later Waves
recover. Treating this as progress against the budget would misread it.

No behaviour outside the test module changed, so there is no runtime risk. The ceiling now sits
close to the current measurement by design, which means unrelated work that adds a tool or
enlarges a result model will fail this guard. That friction is intended.
