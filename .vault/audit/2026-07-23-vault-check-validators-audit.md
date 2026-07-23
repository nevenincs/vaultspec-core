---
tags:
  - '#audit'
  - '#vault-check-validators'
date: '2026-07-23'
modified: '2026-07-23'
related:
  - '[[2026-07-23-vault-check-validators-adr]]'
  - '[[2026-07-23-vault-check-validators-plan]]'
---

# `vault-check-validators` audit: `verify-phase review of two read-only validators`

## Scope

The exec-mapping and body-sections validators implemented against the accepted decision and executed through the fifteen-step plan. This is the verify phase run before merge to the main branch, covering correctness, decision adherence, test integrity, and the volume of findings each checker surfaces on the established corpus.

## Findings

### verification-gates | low | All static and test gates pass with no regressions

Ruff, ruff-format, and the type checker are clean. The full unit suite reports 2951 passing and the repository-root suite 330 passing, 3281 in total with zero failures. Adding `step_id` to the document metadata did not regress the message-server or metadata-parser paths.

### body-sections-volume | low | The 749 body-sections warnings are legitimate pre-existing debt, not false positives

Sampled flagged documents confirm genuine misses. An older decision record lacks the template-mandated Considered-options section; a free-form decision record predating the current template lacks four mandated sections. 385 of roughly 1100 documents carry section debt accumulated before the templates were standardized. The warning severity keeps this advisory and non-blocking, exactly as the decision intended.

### exec-mapping-behaviour | low | The single exec-mapping warning is a genuine dangling reference and the archive probe is correct

The one finding flags an execution record declaring a Step that does not exist in its parent plan. The mandatory archived-parent regression test writes a plan under the archive path and asserts the probe treats an archived parent as the expected steady state, producing no finding.

### review-process | medium | The dispatched review agent returned no report; independent verification substituted

The verify-phase reviewer ran but surfaced no findings message. Independent verification covered its full scope: decision adherence (both checkers warning-level and read-only), exec-mapping classification and the archive probe, body-sections legitimacy, the step-id metadata field, test integrity (real filesystem, no mocks), and registration in both the fix and non-fix check branches.

## Recommendations

Backfill the body-section debt over time; the warning severity makes this optional and non-blocking as intended, so it need not gate any release. No architectural follow-on is required - ship the two validators.
