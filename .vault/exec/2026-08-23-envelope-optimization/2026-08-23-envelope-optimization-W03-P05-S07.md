---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:9d503940b10d9c382415e2864044eca8634dd36d08d3e6dfb05b90110d28311e'
step_id: 'S07'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Replace full pair materialisation with a bounded per-node selection and a weight floor

## Scope

- `src/vaultspec_core/graph/derived.py`

## Description

- Replace the all-pairs candidate enumeration with a generator that emits only pairs able to carry a signal.
- Add a per-node fan-out cap over the resulting ranking.

## Outcome

The generator enumerated every unordered pair in the vault, scored them all, and discarded those with no signal: 772,003 pairs to emit 23,499 at 1,243 nodes, and 54.9 million pairs at 10,476, where the command did not return within twenty minutes.

Every signal is sparse. Reciprocity and co-citation arrive as pair-keyed maps; the link-prediction scores are zero unless two nodes share a neighbour, so those candidates come from each node's neighbourhood; shared feature and shared tag are pairs within a group. The union is exactly the set the previous code kept.

Verified byte-identical rather than merely similar: 23,535 edges before and after, same order, same weights and signals, in 0.63 seconds against 13.44. At 10,476 documents the export fell from twenty minutes sixteen seconds to forty-two seconds.

## Notes

The fan-out cap is a cap on edges per node, not a budget on the total: an edge survives while either endpoint has room, so a node's only link is never dropped and the periphery is not stranded. The first test written for it asserted a harder guarantee than the code gives; the code was right and the description was corrected to say what it actually does.
