---
tags:
  - '#reference'
  - '#operator-cli-repair-pipeline'
date: '2026-05-15'
modified: '2026-05-15'
related: []
---

# `operator-cli-repair-pipeline` reference: `operator repair-pipeline feedback`

This reference captures direct operator feedback from using
`vaultspec-core vault check all`, `vaultspec-core vault check all --fix`, and
`vaultspec-core vault feature index` in a real workspace.

The testimonial says the CLI is useful as a validator but too assumption-heavy
as an operator recovery tool. The operator had to infer naming semantics,
repair ordering, feature-index lifecycle, Windows case-only rename behavior,
and the difference between mechanical fixes and authorial traceability gaps.

## Findings

### Failure taxonomy

Visibility failures:

- Human output can look clean while INFO diagnostics are visible only through
  `-v` or JSON.
- Flat output streams symptoms instead of grouping downstream findings by root
  cause.
- The accepted filename shape is stricter than the short message
  `yyyy-mm-dd-<feature>-<type>.md` communicates.

Partial repair failures:

- `vaultspec-core vault check all --fix` sounds broad, but only some checks are
  mutating.
- Operators cannot reliably tell which issues were fixed, skipped, unsafe, or
  intentionally authorial.
- A repair pass can require a second pass because earlier mutations affect
  later graph and link state.

Feature-index lifecycle failures:

- `vaultspec-core vault feature index` is discoverable only if the operator
  already knows that generated indexes participate in graph consistency.
- Stale generated artifacts can preserve or reintroduce bad references after
  filename repair.
- The CLI does not clearly say whether index regeneration is required after
  repair.

Platform failures:

- Windows and common macOS filesystems are case-insensitive but case-preserving
  by default.
- Case-only renames may need a two-hop strategy to materialize final casing
  reliably.
- Dangling links can be downstream symptoms of casing drift rather than
  genuinely missing documents.

Traceability failures:

- Missing ADR, plan, and research coverage is valuable to detect but is not the
  same kind of work as filename normalization.
- Operators need explicit scaffolding or next-best-action guidance when a
  governance gap requires authorial judgment.

### Operator expectation

The testimonial asks for a true repair pipeline: detect platform constraints,
apply safe renames transactionally, rewrite affected links, rebuild impacted
indexes, rerun validation, and emit a final delta report.
