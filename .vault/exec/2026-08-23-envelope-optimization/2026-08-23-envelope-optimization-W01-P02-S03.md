---
tags:
  - '#exec'
  - '#envelope-optimization'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:bfe58088f48d553d324584e9fe9275fce9861d992728079bbc323673b73f1ea3'
step_id: 'S03'
related:
  - "[[2026-08-23-envelope-optimization-plan]]"
---

# Route every CLI envelope through one emitter using compact separators, with pretty output opt-in

## Scope

- `src/vaultspec_core/cli/rendering_shapes.py`

## Description

- Add a formatting-policy module for the CLI JSON channel, owning the choice of separators
  and indentation in one place.
- Route all 53 emission sites across 23 command modules through it, replacing the per-site
  indentation argument.
- Default to compact separators; restore indentation only when an environment variable opts
  in, for a human reading a payload by hand.
- Leave file-writing serialisation untouched. The manifest, MCP definition and workspace
  modules write files where indentation is correct and is not a wire cost.

## Outcome

Measured against the 10,476-document benchmark corpus.

| command            | before    | after     | cut   |
| ------------------ | --------- | --------- | ----- |
| document listing   | 5,934,666 | 4,719,452 | 20.5% |
| health check, all  | 653,418   | 490,743   | 24.9% |
| orientation rollup | 259,451   | 168,377   | 35.1% |
| feature listing    | 199,579   | 111,383   | 44.2% |
| vault statistics   | 384       | 261       | 32.0% |

The share rises with nesting depth, so the payloads least able to afford the surcharge were
paying the most of it. Every command now sits at its theoretical compact floor plus the
trailing newline.

Verification: the full repository suite passes at 3,715 tests, lint and format are clean, the
type checker is clean across the command package, emitted JSON parses, and the indentation
escape hatch still produces indented output.

## Notes

The first implementation was wrong in a way that looked right, and this is the important part
of the record. The policy was exposed as a mapping subclass resolving lazily through
overridden lookup methods. Keyword unpacking of a mapping subclass reads the underlying
storage directly and bypasses those overrides, so it expanded to nothing and the compact
separators never applied. The payload still shrank, because the indentation argument was gone,
so a before-and-after comparison showed a plausible 29.6% improvement.

It was caught only by comparing against the theoretical floor: 182,649 bytes actual against
168,375 expected, with 14,287 spaces still present against a single newline. A before-and-after
delta cannot distinguish a fix from a half-fix. Every subsequent Step states the floor and the
distance to it.

A second defect: the import-insertion pass matched a prose line beginning with `from` inside a
module docstring, corrupting the docstring and leaving the helper undefined. The linter caught
it. Every command module was then audited by parsing its syntax tree to confirm no import had
landed inside a docstring and no module used the helper without importing it.

Two tests in the host-recognition suite fail. Both were verified against a clean tree with this
work set aside and fail identically there, so both are pre-existing and unrelated. The earlier
run stopped at the first failure and so did not reveal the second.
