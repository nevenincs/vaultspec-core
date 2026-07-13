---
tags:
  - '#plan'
  - '#commit-linkage'
date: '2026-06-13'
modified: '2026-07-13'
tier: L1
related:
  - '[[2026-06-13-commit-linkage-adr]]'
  - '[[2026-06-13-commit-linkage-research]]'
---

# `commit-linkage` plan

- [x] `S01` - add the trailer module with keys, value regexes, and pure parse, format, and validate helpers; `src/vaultspec_core/plan/trailer.py`.
- [x] `S02` - add vault plan trailer emit and validate verbs that always exit zero; `src/vaultspec_core/cli/plan_cmd.py`.
- [x] `S03` - document the opt-in commit-msg pre-commit hook and update the bundled reference and docs; `docs/CLI.md`.
- [x] `S04` - cover the trailer module and both verbs with tests including malformed-trailer exit-zero; `src/vaultspec_core/tests/plan/test_trailer.py`.

## Description

Deliver the opt-in commit-linkage trailer per the accepted ADR: a single trailer module
owning the keys (`Vaultspec-Step`, `Vaultspec-Feature`), the value regexes, and pure
parse, format, and validate helpers; `vault plan trailer emit` and `validate` verbs, the
latter always exiting zero so it is safe as an advisory hook; and a documented opt-in
`commit-msg` pre-commit entry. The convention is enrichment only: absence or
malformation never blocks a commit or fails a core command.

## Parallelization

`S01` (trailer module) is the foundation. `S02` (CLI verbs) and `S04` (tests) depend on
it; `S03` (docs and bundled reference) depends on the verb surface from `S02`. The module
and its tests can be authored together, with the verbs and docs following.

## Verification

`vault plan trailer emit` produces a well-formed `Vaultspec-Step:` or `Vaultspec-Feature:`
line; `vault plan trailer validate` on a message with a malformed trailer reports it and
still exits zero, and on a clean or trailer-free message also exits zero; the trailer
regexes accept every valid L1..L4 display path and reject malformed ids; `ruff`, `ty`, and
the new tests are green.
