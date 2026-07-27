---
tags:
  - '#adr'
  - '#markdown-feature-scope'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-27-markdown-feature-scope-research]]"
---

# `markdown-feature-scope` adr: `feature-scoped markdown repair bypasses lazy migrations` | (**status:** `proposed`)

## Problem Statement

Feature-scoped markdown repair promises to limit mutation to the selected feature,
but its discovery path can cause unrelated vault records to change before the
scope filter applies. The command needs a bounded migration policy that restores
that safety contract without redesigning migration ownership. Grounding:
`2026-07-27-markdown-feature-scope-research` and
`2026-07-27-markdown-feature-scope-reference`.

## Considerations

- The feature filter is correct at the markdown writer; the pre-filter scanner
  side effect is the decision locus (`2026-07-27-markdown-feature-scope-reference`).
- Existing creation and index paths depend on default lazy convergence, so the
  correction must preserve that default (`2026-07-27-markdown-feature-scope-research`).
- Markdown hygiene is deliberately limited to safe whitespace normalization;
  operating on pending-migration records is acceptable only for the explicitly
  selected feature (`2026-07-27-markdown-feature-scope-research`).

## Considered options

- **Optional migration-free scan for feature-scoped markdown repair (proposed).**
  Add an opt-out scanner parameter that preserves migration triggering by default;
  `check_markdown` uses it only when a feature is supplied.
- **Make every scanner consumer migration-free.** Rejected for this issue: it is a
  broader migration-ownership redesign with unknown compatibility impact on mature
  mutating commands.
- **Retain unconditional lazy migration.** Rejected: it cannot satisfy the selected
  feature's byte-preservation contract.

## Constraints

- No dependency or schema migration changes are required.
- `scan_vault` is a mature shared seam; its migration-triggering default must remain
  stable for callers that do not explicitly request a non-mutating scan.
- The regression must exercise the actual CLI with an installed stale workspace;
  direct checker tests do not observe registry side effects.
- The separately reported plan-section and UTF-8 corruption is not decided here:
  current markdown and known migration behavior do not account for it.

## Implementation

`scan_vault` gains an optional migration-control parameter whose default retains
today's lazy migration behavior. A `check_markdown` call with `--feature` requests
the non-migrating mode before it reads or repairs documents; unscoped markdown
checks and every other caller keep the default. A real CLI regression provisions
a stale workspace with dirty selected and unselected documents and proves the
unselected document remains byte-identical.

## Rationale

The proposed boundary is the smallest change that makes the explicit scope
guarantee true. It separates this repair command from global schema convergence
without changing the established default relied on elsewhere. The evidence and
alternative analysis are in `2026-07-27-markdown-feature-scope-research`; the
source-level mutation trace is in `2026-07-27-markdown-feature-scope-reference`.

## Consequences

Feature-scoped markdown repair becomes safe to run in a shared stale workspace:
only matching documents may be normalized, and pending migrations remain visible
for explicit operator action. The trade-off is that selected documents may be
checked before workspace schema convergence; that is intentionally limited to the
existing pure hygiene transform. A future decision may address migration-free
reads globally, but it must audit all scanner callers and is not implied here.
