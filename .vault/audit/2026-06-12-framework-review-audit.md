---
tags:
  - '#audit'
  - '#framework-review'
date: '2026-06-12'
modified: '2026-06-13'
related: []
---

# `framework-review` audit: `builtin framework review`

## Scope

A full review of the framework firmware shipped under
`src/vaultspec_core/builtins/`: 4 system fragments, 9 rules, 11 skills, 11 agent
personas, 9 templates, and the bundled CLI reference. The review asked four
questions: is the framework usable, does it make sense, are there observations
worth recording, and are the workflows efficient. Every document was read in
full and every CLI verb named in firmware prose was checked against the live
`vaultspec-core` 0.1.28 command surface.

## Findings

### FW-001 | high | codify firmware is stale against the shipped CLI

The codify rule, the codify skill, the codifier persona, and the audit and adr
templates all describe `vaultspec-core vault rule promote`, the `derived_from:`
frontmatter field, and structured ADR supersession as planned future work. All
three shipped: `vaultspec-core vault rule promote --from <audit-stem> --as <rule-name>` exists, promoted rules carry `derived_from:`, and
`vaultspec-core vault adr supersede` writes `superseded_by:`. The firmware
instructs agents to hand-copy audit text and treat the structured paths as
footnotes, which is now the inverse of the truth. This is the same failure mode
the `firmware-reference-parity` rule codified: a surface changed and the prose
surfaces did not.

### FW-002 | high | massive near-verbatim duplication across firmware surfaces

The "Frontmatter & Tagging Mandate" block is restated in nine documents. The
codify discipline (durability criteria, body template, supersession discipline)
exists in three near-identical copies (rule, skill, persona). The three
executor personas are 95 percent identical, and the unshared 5 percent has
drifted in wording (bold-caps headings in two, sentence case in the third). The
CLI usage mandate for plan mutation is restated in seven documents.
Duplication without a synchronization mechanism is how FW-001 happened: each
copy ages independently. Where a copy must exist (a persona is a standalone
prompt), the copies should be word-identical; where the always-on rules are
guaranteed loaded (skills), a pointer to the `vaultspec` rule suffices and
saves context tokens.

### FW-003 | medium | voice and register diverge across personas

Three registers coexist: calm professional prose (`vaultspec-project-coordinator`,
`vaultspec-documentation`), bold-caps command voice (`vaultspec-reference-auditor`,
`vaultspec-codifier`: "**YOU ARE**", "**EXECUTE**", "**LOCATE**"), and mixed
("YOUR PRIMARY GOAL IS" inside otherwise calm executors). Heading case is
likewise mixed ("When to Use" vs "When to use"). The framework's own
operational guideline mandates a concise, direct tone; the shouting register
predates it.

### FW-004 | medium | the firmware violates its own no-numbered-lists mandate

`02-operations.md` mandates "prefer prose or bullet points over numbered
lists", yet the codifier persona, the projectmanager skill, and all three
executor personas use numbered lists.

### FW-005 | medium | `mode:` taxonomy contradicts one persona and one skill

`03-vaultspec.md` defines `mode:` as "declared file-mutation intent via the
harness file tools (Write/Edit)". The `vaultspec-project-coordinator` persona is
`mode: read-write` yet carries no Write or Edit tool (its mutations flow
through `gh` and `git`). The `vaultspec-docs-curator` persona says "you rarely
edit files directly" while the curate skill says the orchestrator persists the
curator's findings, but the persona later instructs the curator to author the
audit body itself. The definitions and the personas need to agree.

### FW-006 | medium | firmware references vaultspec-core's private vault documents

Shipped firmware repeatedly cites development-vault stems
(`2026-05-06-plan-hardening-adr`, sibling ADRs `cli-spec-crud-parity`,
`cli-memory-lifecycle`, `cli-spec-gitignore`) as if a consumer could open them.
A consumer workspace has no such documents; the references dangle on every
install. Provenance citations in the worked-example rules are fine (they are
explicitly historical), but normative instructions ("see the CLI ADR for the
subcommand contract") must be self-contained or point at surfaces a consumer
has: the plan template hint blocks and `--help`.

### FW-007 | low | pipeline table numbers two phases "1"

The `03-vaultspec.md` pipeline table numbers Research and Reference both as
phase 1 without stating that they are parallel optional entry points.

### FW-008 | low | tier vocabulary collision

Agent frontmatter uses `tier: HIGH|STANDARD|LOW` (capability) while plans use
`tier: L1..L4` (complexity). The frontmatter key is stripped at render time so
the collision is prose-only, but persona text saying "High-Tier" next to plan
text saying "tier L3" forces the reader to disambiguate from context.

### FW-009 | low | `vaultspec-projectmanager` breaks the naming convention

Every other skill slug hyphenates word boundaries (`vaultspec-code-review`);
`vaultspec-projectmanager` does not. Renaming it is a consumer-visible
migration (manifest, provider directories, installed workspaces) and was
deliberately deferred; recorded here so the next breaking-change window picks
it up.

### FW-010 | observation | the pipeline is usable but has no declared light path

The framework is coherent and the artifact chain is genuinely auditable:
research grounds the ADR, the ADR authorizes the plan, the plan's Steps map
one-to-one to Step Records, and review closes the loop. The L1..L4 tier system
scales the plan artifact, but nothing scales the pipeline itself: a one-line
fix formally owes research, an ADR, a plan, execution records, and a review.
In practice operators skip phases ad hoc; the firmware would be more honest and
more efficient if it stated when the short path is legitimate (it partially
does: "all significant work"). Defined explicitly, the judgment becomes
teachable instead of tribal.

### FW-011 | observation | workflow efficiency is mostly limited by restated context

The per-skill announce lines, persona loading, and CLI-owned scaffolding are
cheap and pull their weight. The real token cost is the restated schema and
mandate blocks (FW-002): an executor persona burns roughly half its length on
text that is identical across all three tiers and already enforced by the CLI
and `vault check`.

## Recommendations

- Rewrite the codify rule, codify skill, codifier persona, and audit/adr
  template comments around the shipped `vaultspec-core vault rule promote`,
  `derived_from:`, and `vaultspec-core vault adr supersede` surfaces (FW-001).
- Converge all firmware to one register: calm imperative prose, sentence-case
  headings, bold only for defined terms and severity labels, no numbered lists
  (FW-003, FW-004).
- Deduplicate: skills point at the `vaultspec` rule for the frontmatter schema;
  the three executor personas become word-identical except for their
  genuinely distinct mission paragraphs (FW-002, FW-011).
- Redefine `mode:` as declared mutation intent (files or external state) and
  align the project-coordinator and docs-curator personas with it (FW-005).
- Make normative firmware self-contained: replace "see the CLI ADR" with the
  plan template hint blocks and `--help`; keep dev-vault stems only in the
  worked-example rules' Source sections, framed as upstream provenance
  (FW-006).
- Label the pipeline's two entry phases explicitly and state the
  light-path policy for trivial work (FW-007, FW-010).
- Defer the `vaultspec-projectmanager` rename to a breaking-change window
  (FW-009).

## Codification candidates

None beyond what already exists. FW-001 and FW-006 are both instances of the
already-codified `firmware-reference-parity` rule; this audit strengthens that
rule's evidence base rather than motivating a new one. The remaining findings
are one-time convergence work, not durable constraints.
