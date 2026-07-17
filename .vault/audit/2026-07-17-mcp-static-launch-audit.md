---
tags:
  - '#audit'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-17-mcp-static-launch-plan]]"
  - "[[2026-07-17-mcp-static-launch-adr]]"
---

# `mcp-static-launch` audit: `static launch render review` | PASS after revision

## Scope

Phase P02 implementation of the static-execution launch amendment: the
no-sync guard in the launch comparator (`src/vaultspec_core/core/mcps.py`),
the legacy-shape recognition in the observed-shape matcher
(`src/vaultspec_core/core/diagnosis/collectors.py`), and the migrated
launch-shape test suites. Reviewed by an independent reviewer persona
against the governing decision's A1/A3 sub-decisions, comparator
discipline, matcher boundedness, consumer consistency, test integrity, and
platform neutrality, with the four target suites re-run by the reviewer.

## Findings

### code-boundary-stems | high | dev-record identifiers embedded in delivered source

The legacy-shape helper's comment and the matcher docstring cited a
decision-record stem verbatim, violating the one-way vault reference
boundary (code never cites the vault). RESOLVED: reworded to functional
descriptions with no dated stems; boundary re-verified by grep across
non-test sources.

### review-verified-properties | low | all audited properties hold

Single-comparator discipline holds (`render_launch_for_mode` is the sole
no-sync source; the convenience table and the legacy helper both derive
from it). The legacy recognition requires exact list equality plus module
validation and cannot loosen: an arbitrary un-guarded shape still returns
none, covered by a dedicated test. Mode-flip, per-package sync, and
provider-file suites derive expected shapes through the comparator; literal
expected bytes are pinned once as the anti-tautology anchor. No mocks,
stubs, or skips; 120 tests passed across the four target suites; ruff and
ty clean on every changed file. Windows/POSIX neutral.

### dogfood-verification | low | deployed configs verified over the wire

After a forced sync, both managed provider entries render the guarded
shape, and both servers complete a real stdio initialize handshake with the
exact deployed commands; the workspace doctor reports ok with declared and
observed modes matching.

## Recommendations

- None open on core. The sibling package's half of the launch-hygiene
  contract (tool-spec extra, seed-refresh verification, installer placement
  leak) is tracked externally as rag issue 231 and needs no core follow-on
  decision.
