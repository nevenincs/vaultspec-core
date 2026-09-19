---
tags:
  - '#plan'
  - '#cli-output'
date: '2026-09-19'
tier: L1
related:
  - '[[2026-02-23-cli-output-architecture-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:3a943123c201f1db90f07e66a076cf365cf48323dc0330989a5c8b45154c3d62'
---

# `cli-output` plan

Introduce a dual-channel `Printer` abstraction and fix stdout/stderr inconsistencies across the CLI.

## Description

Reconstructed 2026-09-19 from this feature's historical execution records
(`2026-02-23-cli-output-phase1-steps-exec`, `2026-02-23-cli-output-phase2-steps-exec`,
`2026-02-23-cli-output-phase2-review-exec`, `2026-02-23-cli-output-summary-exec`),
which recorded completed work but had no surviving plan to attribute it to. The Steps
below restate what those records report as done; they are closed on that evidence, not
re-executed. S03's evidence is a code-review record (`PASS` status with only medium and
low findings); it is treated as a verification Step. Authorization is historical: the
work shipped in February 2026 under the CLI output architecture it names.

Decision coverage: `2026-02-23-cli-output-architecture-adr` governs the stdout/stderr
channel split this plan sequences.

## Steps

- [x] `S01` - create the Printer dual-channel abstraction and wire it into setup_logging; `src/vaultspec/printer.py`.
- [x] `S02` - fix inconsistent CLI output call sites, routing program output to args.printer.out() and removing duplicate logging; `src/vaultspec/vault_cli.py`.
- [x] `S03` - review the phase-2 output fixes and confirm a PASS with only medium and low findings; `src/vaultspec/printer.py`.

## Parallelization

None. The Steps are recorded sequentially as the historical records report them, and
the work is complete, so no container is available for concurrent assignment.

## Verification

Verified historically by the execution records this plan reconstructs: 13 Printer unit
tests passed at S01, 288 tests passed across 4 suites at S02, and S03's code review
confirmed a PASS with no critical or high findings. The paths sit under the pre-rename
`src/vaultspec/` tree and are not re-checkable at their original locators.
