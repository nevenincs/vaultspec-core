---
tags:
  - '#reference'
  - '#cli-simplification-ux'
date: '2026-05-18'
modified: '2026-05-18'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
  - '[[2026-05-17-cli-simplification-ux-adr]]'
---

# `cli-simplification-ux` reference: `Audit-driven decomposition: from findings to rules`

Reusable blueprint for the audit-driven decomposition pattern that
this pull request exemplifies. Captures the pattern's shape, the
artifact graph, the agent roles, the validation loop, and the
lessons learned about the pattern itself. Future audits should
follow this blueprint; the framework's own use of it is the
worked example.

## Summary

The pattern walks a body of work from raw observation to durable
project policy through five sequential artifact types, with a
self-correcting agent-driven validation loop layered on top. The
artifacts compose; the loop iterates.

## The artifact graph

The pattern produces six classes of vault artifact, each authored
through the canonical CLI verb listed:

- **Audit** (`vault add audit`) — the rolling observation log. One
  per audit pass, possibly updated across multiple rounds. Captures
  fresh-eyes findings with verbatim CLI output. Findings carry
  stable identifiers (B1, B2, S1, S2, ...) used by every
  downstream artifact.
- **Research synthesis** (`vault add research`) — one per finding
  cluster. Distils the audit's evidence on the cluster's axis and
  identifies the architectural shape the sibling ADR proposes.
- **Sibling cluster ADR** (`vault add adr`) — one per cluster.
  Records the architectural decision the cluster's evidence
  motivates. Each ADR has its own feature tag, its own research
  predecessor, and its own `related:` chain back to the audit.
- **Umbrella decomposition ADR** (`vault add adr`) — one per
  audit. Records the meta-decision to decompose the body of work
  into sibling cluster ADRs rather than a single monolithic
  refactor doc. Lives under the umbrella feature tag.
- **Umbrella plan** (`vault add plan`) — the L4 epic. One per
  audit. Binds every cluster ADR through `related:` and sequences
  the implementation work into Waves, Phases, and Steps. Phases
  map one-to-one onto clusters; Steps decompose each cluster's
  work into the smallest tractable units.
- **Reference** (`vault add reference`) — this document.
  Captures the pattern itself as a reusable blueprint.

Plus the framework's language-track artifacts that propagate the
audit's findings into durable policy:

- **Discipline builtin rules** (`spec rules add`) — one per
  cluster whose findings produce a cross-session constraint that
  should bind future agents. Authored via the codify pipeline
  phase. Each rule references its source finding by ID and its
  authorising ADR by stem in backticks.
- **Codifier persona and skill** — the agent and entry contract
  that enact the discipline. Shipped once across the framework,
  reused for every audit.

## The decomposition rule

Each audit finding cluster maps to one sibling ADR under its own
kebab-case feature tag. Cluster boundaries are drawn so each ADR
captures one architectural decision the framework needs to make.
The criteria for a valid cluster:

- Findings in the cluster share a common architectural lever
  (one verb, one frontmatter field, one renderer, one discipline).
- The cluster's ADR can stand alone; a reader who picks it up
  without context understands the decision from the ADR alone.
- The cluster maps onto exactly one phase in the umbrella plan,
  with three to five Steps per phase.

Clusters that fail any criterion subdivide further; clusters that
trivially overlap (sharing both lever and rationale) merge.

## The agent roles

The pattern is built for parallel, persona-driven execution:

- **Auditor agents** — fresh-eyes personas operating in disposable
  sandboxes with no source-code access. They drive the audit by
  exercising the framework end to end and capturing friction. Two
  parallel auditors with complementary briefs (e.g., one task-list
  style, one natural-language chat brief) produce convergent
  evidence; convergence across independent agents on the same
  finding is decisive.
- **Decomposer agent** (the main session) — reads the audit,
  proposes clusters, scaffolds the artifact graph, fills the
  cluster ADRs, authors the umbrella plan, ships the
  language-track artifacts. This agent does NOT enter the
  sandbox; it stays on the source side.
- **Codifier agent** — promotes durable lessons surfaced by the
  audit or by the cluster ADRs into project rules. Operates
  through the `vaultspec-codify` skill and `vaultspec-codifier`
  persona.

## The validation loop

The pattern includes a self-correcting validation step:

- After language-track artifacts ship, the auditor personas run a
  convergence-test round against the new artifacts. The auditors
  test whether the language-track outputs are discoverable, whether
  they match the actual CLI's behaviour, and whether the bridge
  from pipeline to durable rule closes when an agent reaches the
  end of a feature.
- Findings from the convergence test feed back into the audit
  document as a new Round section. New blockers or sharp findings
  may produce additional cluster ADRs or extend existing ones.
  Bugs in the just-shipped language artifacts (rules naming
  unshipped CLI surfaces, path mismatches, missing entries) are
  caught and fixed within the same round.

The loop's invariant: every artifact must reflect today's CLI
honestly. Planned-but-unshipped surfaces are marked-as-planned
asides, not normative instructions. This invariant is itself
codified as the `vaultspec-codify` rule's standing constraint.

## Lessons learned from this PR

The framework was used on itself for this audit. The exercise
surfaced lessons about the pattern that future applications should
inherit:

- **Same-feature filename collisions force date fakery.** The
  framework's filename schema is `YYYY-MM-DD-{feature}-{type}.md`.
  Multiple ADRs for the same feature on the same day collide.
  This PR uses one feature tag per cluster to side-step the
  collision; future applications should adopt the same rule. The
  finding (round-2 B4) is also captured as an audit blocker.
- **Language-track outruns code-track.** This PR shipped the
  codify pipeline phase, the codifier persona, the codify skill,
  the audit template's Codification candidates section, and three
  discipline rules — all before the CLI verb (`vault rule promote`) that the language refers to existed. The validation
  loop caught two violations of the framework's own discipline
  ("rules must reflect today's CLI") and corrected them mid-round.
  Future applications should expect this same loop and budget for
  the corrections.
- **Convergence across independent agents is decisive evidence.**
  Findings reproduced by two agents in two sandboxes are real
  bugs, not session-specific artifacts. Findings reproduced by
  one agent should be confirmed before being promoted to
  blocker-grade.
- **Empty Codification candidates is the positive signal.** Most
  audits produce zero codification candidates. The template
  explicitly states this so authors do not invent candidates to
  fill the section.
- **The plan's Step count is a signal of audit scale.** This PR's
  L4 plan has 52 Steps across 14 phases in 5 waves; the audit's
  evidence justified that scope. Smaller audits should produce
  smaller plans. An audit whose plan exceeds 100 Steps probably
  needs to be decomposed into multiple audits.

## How to apply the blueprint

For a future audit, the sequence:

1. Spawn auditor personas. Brief them with hard no-source-access
   constraints and a friction-log format. Run multiple rounds
   across days of audit work. Append findings to one rolling
   audit document.
1. Identify clusters. Group findings by shared architectural
   lever. Validate cluster boundaries against the three criteria.
1. Author one research synthesis per cluster. Distil the audit
   evidence on the cluster's axis.
1. Author one sibling ADR per cluster. Reference the audit and
   the research synthesis. State the architectural decision.
1. Author the umbrella decomposition ADR. Record the choice to
   decompose into siblings rather than monolith.
1. Author the umbrella plan. Bind the cluster ADRs through
   `related:`. Sequence Waves and Phases by dependency order.
   Add Steps via the CLI verbs, then prose last (per the
   `vaultspec-plan-editing-discipline` rule).
1. Ship the language-track artifacts. For each cluster whose
   findings produce a durable cross-session constraint, author a
   builtin discipline rule under `.vaultspec/rules/rules/`. Add
   pipeline-phase or skill entries if the cluster introduces a
   new lifecycle operation.
1. Run the validation loop. Re-deploy the auditor personas
   against the just-shipped artifacts. Fix violations mid-round.
   Confirm convergence on the closing meta-finding.

## Boundary conditions

The pattern is right-sized for audits whose findings span more
than one architectural lever. Smaller audits (one bug, one
decision) should produce one ADR without the umbrella
infrastructure. Larger audits (multiple distinct subsystems with
their own internal architecture) should produce one umbrella ADR
per subsystem and use this pattern recursively.

The pattern assumes the framework supports the artifact types
this PR exercised. Frameworks without typed frontmatter
relationship fields, without an audit doc type, without a codify
pipeline phase, will need to develop those primitives before the
pattern composes.
