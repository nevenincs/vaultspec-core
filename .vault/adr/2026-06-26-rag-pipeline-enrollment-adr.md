---
tags:
  - '#adr'
  - '#rag-pipeline-enrollment'
date: '2026-06-26'
modified: '2026-06-27'
related:
  - "[[2026-06-26-rag-pipeline-enrollment-research]]"
---

# `rag-pipeline-enrollment` adr: `firmware rag-grounding mandate for discovery personas` | (**status:** `proposed`)

## Problem Statement

The firmware mandates "ground in existing intent first" at the system-prompt and skill
layers, both already citing `vaultspec-rag` semantic search. The agent personas that
actually carry out discovery do not. The generic researcher persona is a
methodology-free stub; the adr-researcher persona is almost entirely external-source
oriented (web, package metadata, GitHub); and the reference-auditor, code-reviewer,
writer, and docs-curator personas drive discovery through `rg` and `fd` alone. An agent
dispatched into one of these personas inherits an explicit "use `rg`/`fd`" instruction
that locally overrides the higher-layer grounding mandate, so the project's own
semantically indexed intent - its ADRs, audits, prior research, and matching code - goes
unconsulted exactly when a new research, feature, or audit most needs it. Separately, the
Phase 1 framework-dir flatten left roughly thirty stale `.vaultspec/rules/...` references
in this same firmware prose, pointing agents at files that have since moved.

## Considerations

- rag's distinguishing value is internal semantic discovery over our own code and vault,
  complementary to (not a replacement for) the external web and package research the
  adr-researcher already performs.
- rag is an optional sister package that ships and installs its own builtin rule and MCP;
  core owns no rag rule, and the existing firmware already hedges rag behind a
  `vault list` and grep fallback.
- The system-prompt grounding block is the cleanest existing model; persona prose should
  mirror its vocabulary rather than invent a competing one.
- Reference parity: every artifact named in firmware prose must resolve to a shipped
  artifact of exactly that name. The stale paths break that, and they live in the files
  this change already edits.
- Firmware prose is the operative contract for every agent; changes are deliberate and
  consistent, not ad-hoc edits.

## Considered options

- **Enroll rag into the discovery personas and align skills and system, keeping the
  fallback (chosen).** Add an internal-discovery-first step to each discovery persona,
  mirroring the system block, and retain the grep fallback. Pro: closes the gap where
  discovery actually happens and yields one coherent story. Con: touches roughly fifteen
  to twenty files and requires parity-checking every rag verb cited.
- **Rely on the system and skill layers only, leave personas unchanged.** Pro: minimal
  change. Con: the personas' explicit `rg`/`fd` instructions locally override the
  higher-layer mandate, so the gap persists in practice. Rejected.
- **Add a new core-owned `vaultspec-rag` builtin rule.** Pro: a single canonical rag
  rule. Con: rag already owns and installs its rule; a core copy duplicates ownership and
  breaks parity the moment the two drift. Rejected.
- **Hard-mandate rag with no fallback.** Pro: the strongest push toward use. Con: rag is
  optional and may be absent in CI or air-gapped installs; asserting it as required
  contradicts the hedged-capability discipline. Rejected.

## Constraints

- Depends on the `vaultspec-rag` package's shipped command surface: every rag verb and
  flag cited must resolve against rag's own builtin rule. That surface is stable and
  shipped, not frontier, so the dependency is low-risk but must be cross-checked at
  execution time.
- Documentation-only: no Python behavior changes. Validation is `vault check all`, the
  firmware reference greps, and the unit gate to confirm no test fixture asserts the old
  prose.
- Every enrolled site must preserve the optional-tool fallback so an install without rag
  still has a defined grounding path.

## Implementation

Two ordered concerns, parity before enrollment so every intermediate state stays
consistent.

First, restore reference parity: rewrite the stale `.vaultspec/rules/...` references to
their flattened targets (`.vaultspec/templates/`, `.vaultspec/agents/`,
`.vaultspec/rules/`, `.vaultspec/reference/`, `.vaultspec/hooks/`, `.vaultspec/mcps/`)
across the rules, skills, agents, system, and bundled-reference firmware.

Second, enroll rag: give each discovery persona an "internal grounding first" step that
leads with rag semantic search over the vault then the code, framed as internal discovery
distinct from external research, and carrying the `vault list` and grep fallback. Fill
the researcher stub with that methodology, develop the undeveloped internal-context half
of the adr-researcher, and confirm the three pipeline skills and the system block all
tell the same story. Core authors no rag rule of its own.

## Rationale

The personas are where discovery is actually performed, so the mandate must live there to
have effect; the higher layers alone are demonstrably overridden by a persona's own
explicit tool instruction. Mirroring the system-prompt block keeps one vocabulary instead
of a competing one. The hedged fallback and the no-core-rag-rule boundary follow the
firmware-wording-review posture that shipped names win over prose and optional capability
is hedged rather than asserted. Grounded in the feature research and that precedent.

## Consequences

- Agents entering any discovery persona receive one coherent instruction: search our own
  indexed code and vault first, then reach outward. Reference parity is restored across
  the firmware in the same pass.
- A documentation-only change set across roughly fifteen to twenty firmware files; the
  path edits are mechanical and greppable, lowering review risk.
- Core firmware now names rag verbs, so a future rag CLI rename would require a parity
  update here. The risk is mitigated by the fallback and by citing only the stable
  top-level surface.
- Downstream execute and project-management skills and rag's own rule are untouched; if
  rag later changes its query grammar, the cited examples may need a refresh.
