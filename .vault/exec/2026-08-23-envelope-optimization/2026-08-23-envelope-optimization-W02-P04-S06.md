---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:4e30e60f75a61ede5bf6adf1ef1ab2e16206955281791d67b4737f80136111f9'
step_id: 'S06'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Replace the uncapped-machine-contract docstrings with the bounded contract

## Scope

- `src/vaultspec_core/vaultcore/checks/_base.py`

## Description

- Rewrite the render-cap constant's documentation so it describes a cap that governs both surfaces rather than only the human one.
- Correct the render function's description, which told a reader the machine surface carried the full set.
- Change the human truncation notice so it no longer points at the machine surface for everything it withheld.
- Rewrite the tree render cap's documentation in the graph package for the same reason.

## Outcome

Three passages specified the machine surface as deliberately uncapped, on the premise that its consumer was a script. The consumer is a context window, so the cap was being given to the reader who can scroll and withheld from the one who cannot. That reading is what allowed a graph export to reach 416 MB.

The wording now matches the behaviour: both surfaces cut at the same constant and both carry the full totals, so neither can mislead about what was withheld.

## Notes

Retiring the wording was deliberately sequenced after the behaviour changed. Doing it first would have replaced a docstring that was honest about an unbounded payload with one that claimed a cap that did not yet exist.
