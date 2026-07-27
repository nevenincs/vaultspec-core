---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
step_id: 'S20'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# verify the shipped libyaml CSafeLoader seam engages on the frontmatter hot path and record the measured parse gain

## Scope

- `src/vaultspec_core/vaultcore/parser.py`

## Description

- Confirm the libyaml CSafeLoader-with-fallback seam is already in
  committed history on the frontmatter parse hot path and that
  libyaml is active in this environment.
- Measure engagement on the real corpus: the full parse pass runs
  at the C-loader's speed, proving the seam is live.

## Outcome

Measured on the 1,180-document corpus: the C loader parses the
frontmatter set 7.3x faster than the pure-Python loader (0.055s vs
0.403s), and the shipped parse path matches the C-loader timing
exactly. No code change was needed for this Step.

## Notes

Remaining pure-Python YAML load sites parse a handful of workspace
resource files, not the corpus; converting them buys nothing
measurable and was left alone.
