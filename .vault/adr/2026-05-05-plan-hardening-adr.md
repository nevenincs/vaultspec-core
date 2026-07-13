---
tags:
  - '#adr'
  - '#plan-hardening'
date: '2026-05-05'
modified: '2026-06-13'
related:
  - '[[2026-05-05-plan-hardening-research]]'
---

# `plan-hardening` adr: plan-hardening natural-language convention | (**status:** `proposed`)

This ADR authorises **Wave 1** of the `#plan-hardening` plan
document: the language-only rewrite of the `.vaultspec/`
firmware. The CLI surface is authorised separately by
`2026-05-06-plan-hardening-adr.md` as Wave 2.

## Context

Plan documents currently allow phase-level prose with no row-level
granularity rule, no stable identifiers, and no anti-compression
mandate. Self-similar work across N files collapses into terse
summaries, breaking the one-to-one mapping between rows, prompts,
and commits. This ADR defines the natural-language contract that
governs plan production. Wave 1 is language-only; programmatic
validation is a later Wave.

## Hierarchy and tiers

The plan hierarchy has four levels: `Epic > Wave > Phase > Step`.
`Step` is the canonical leaf-row noun across every `.vaultspec/`
surface this convention governs. The execution-log artefact
(`<Step Record>`) maps one-to-one to a Step.

The plan declares its tier in frontmatter as `tier: L1` (or `L2`,
`L3`, `L4`). The tier determines which containers exist; the Step
row contract is identical at every tier. Selection is by predicate;
the writer never invents a container to qualify a tier.

| Tier | Structure                                 | Selection criteria (any one is sufficient)                                                                                                                                                                     |
| :--- | :---------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `L1` | Steps only                                | Single session; single concern; one cohesive change; one day or less; no cross-module coupling.                                                                                                                |
| `L2` | Phases above Steps                        | All Steps within a single package, subsystem, or configuration domain; 1-3 days; multiple Phases each grouping logically related Steps; no hard interdependencies between Phases.                              |
| `L3` | Waves above Phases above Steps            | Hard interdependencies between Phase groups; 3-10 days; multi-session; codebase reordering or foundational changes; Steps span two or more package, subsystem, or configuration boundaries with hard ordering. |
| `L4` | Epic above Waves above Phases above Steps | Multi-week or multi-month; multi-team or multi-agent; tracking against external project-management artefacts; MVP, business case, or equivalent governance attached.                                           |

`L4` plans MUST declare a project-management association (project
milestone, project board, roadmap entry) in the `## Epic intent`
block prose. A frontmatter field is reserved for a later Wave.

## Frontmatter contract

A plan document's YAML frontmatter carries the following fields
relevant to this convention. The `tier` field is new. The
`related` field exists today but its semantic is tightened
below: it now carries the authorising documents for every Step
in the plan. Other existing fields (`tags`, `date`, etc.) are
unchanged.

| Field     | Required                                              | Allowed values                 | Notes                                                                                                                                                                                                                                                                               |
| :-------- | :---------------------------------------------------- | :----------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tier`    | always required                                       | `L1`, `L2`, `L3`, `L4`         | Unquoted scalar (`tier: L1`). Case-sensitive. Plans authored before this ADR landed are treated as `L2` by `vault plan check`; the missing field is reported as a warning with a migration hint and the writer adds the field on first edit.                                        |
| `related` | required when the plan contains at least one Step row | YAML list of quoted wiki-links | Carries the **authorising documents** for every Step in this plan: the ADR, research, references, and prior plans that authorise the work. Steps inherit this chain; per-row reference footers do not exist. Empty-plan scaffolds may omit `related` until the first Step is added. |

The frontmatter is the only place wiki-links appear. Plan body
remains free of wiki-links and markdown links per the existing
LINK RULES. YAML emission style follows the existing template
convention: single-quoted string scalars, unquoted enum scalars
for `tier`, list form for `related` and `tags`.

## Identifiers and addressing

| Container | Identifier               | Scope             |
| :-------- | :----------------------- | :---------------- |
| Step      | `S01`, `S02`, ..., `S##` | per plan document |
| Phase     | `P01`, `P02`, ..., `P##` | per plan document |
| Wave      | `W01`, `W02`, ..., `W##` | per plan document |
| Epic      | implicit (no `E##`)      | one per `L4` plan |

Each segment is zero-padded to a minimum of two digits; padding
widens with the counter (`S117`); existing identifiers are never
re-padded. Identifiers are append-only and immutable; gaps from
deletions are never reused. `S01` in plan A is unrelated to `S01`
in plan B.

Canonical identifier order and document order are independent.
The canonical identifier reflects creation order. The document
order is the order rows appear in the file and is writer-
controlled (or CLI-controlled). The two diverge whenever a Step,
Phase, or Wave is inserted between existing items or moved. A
plan reading top-to-bottom may show identifiers out of sequence
(`S02, S08, S03`); this is correct and reflects the immutability
guarantee. The display path is computed from the current
ancestor chain, never from document position.

The display path concatenates ancestor identifiers with `.` and
ends in the Step identifier:

Display paths exist for Step rows AND for Phase / Wave headings.
Each container renders its own ancestor-aware path:

| Tier | Step path     | Phase heading | Wave heading |
| :--- | :------------ | :------------ | :----------- |
| `L1` | `S03`         | n/a           | n/a          |
| `L2` | `P02.S03`     | `P02`         | n/a          |
| `L3` | `W01.P02.S03` | `W01.P02`     | `W01`        |
| `L4` | `W01.P02.S03` | `W01.P02`     | `W01`        |

Display paths are recomputed at render time; the canonical
identifier is the leaf segment. Cross-document references use the
leaf identifier and the plan stem when disambiguation is needed
(e.g., `S03 in 2026-05-05-plan-hardening-plan`).

Re-parenting (moving a Step between Phases, or a Phase between
Waves) preserves the canonical identifier; only the display path
recomputes. The donor container retains a gap.

### Promotion is non-renumbering and transitive

Promotion (`L1` to `L2`, or any non-adjacent jump such as `L1` to
`L4`) adds outer containers without renumbering. Transitive
promotion is one revision: existing Steps land under a fresh
`P01`; the existing `P01` lands under a fresh `W01`; the new Epic
frame is authored fresh.

Worked example. An `L1` plan with `S01..S05` is promoted to `L3`:

```
L1:  S01, S02, S03, S04, S05
L2:  P01.S01, P01.S02, P01.S03, P01.S04, P01.S05
     P02.S06, P02.S07
L3:  W01.P01.S01, ..., W01.P01.S05
     W01.P02.S06, W01.P02.S07
     W02.P01.S08
```

Every `S##` and `P##` keeps its number. Display paths grow.

Document-order example. The writer adds a Step between `S02` and
`S03` after the plan already contains `S07`. The new Step gets
the next-available canonical identifier `S08`. Document order
reads `S01, S02, S08, S03, S04, S05, S06, S07`. Canonical IDs
remain unchanged. The same logic applies to Phases (a new Phase
inserted before `P01` gets `P##` next-available, displayed
first) and Waves.

L4 promotion example. An `L3` plan with `W01..W02` and `P01..P05`
is promoted to `L4`. The Epic frame instantiates: a level-one
plan title becomes the Epic title, and a `## Epic intent` block
is authored fresh at the top of the body containing the
project-management association. Existing `W##`, `P##`, `S##`
identifiers are preserved.

Demotion example. An `L3` plan is demoted to `L2`. Demotion
collapses the outermost container; existing Phase and Step
identifiers are preserved, but the Wave wrapper `W01` is
retired. Demotion is permitted only when collapsing the Wave
layer would not lose information (a single non-retired Wave
exists). When multiple non-retired Waves exist, demotion is
refused; the writer must consolidate or delete Waves first.

## Step row contract

A Step is exactly one Markdown bulleted checkbox row:

```markdown
- [ ] `<display-path>` - imperative-verb action; `path/to/file.ext`.
```

Components, in order:

- `- [ ]` open or `- [x]` closed. Two-state only. At `L3`/`L4`,
  `- [x]` means commit accepted; merge happens when the Wave is
  complete.
- `` `<display-path>` `` in inline backticks; tier-conditional
  shape from the table above.
- `-` separator (single ASCII space, ASCII hyphen-minus, single
  ASCII space).
- imperative-verb action statement; describes one prompt-run plus
  one commit; names what changes, not why.
- `;` followed by a single space.
- `` `path/to/file.ext` `` file or area scope in inline backticks.
  One file or one cohesive area per Step. "The codebase" is not
  acceptable; pick the file or the cohesive area the Step changes.
- `.` ending the row sentence.

Per-row reference footers are NOT used; wiki-links and markdown
links are forbidden in plan body per the existing vaultspec link
rules. Authorising documents (the ADR, research, references,
prior plans) are listed once at the top of the plan document in
the `related:` frontmatter field. Each Step inherits the plan
document's `related:` chain.

Step rows within a Phase are contiguous (no blank lines between
rows). One blank line separates the Phase intent paragraph from
the first row. Rows appear in document order, which reflects
writer intent and is independent of canonical identifier order.

Examples:

```markdown
# L1 shape
- [ ] `S03` - remove the unused import; `vaultspec_core/audit/__init__.py`.

# L3 shape
- [ ] `W01.P02.S03` - rewrite the Steps section to enforce the row contract; `.vaultspec/rules/templates/plan.md`.
```

## Block formats

### Phase block (`L2`, `L3`, `L4`)

```markdown
# L2 shape
### Phase `P02` - rewrite the writer-agent contract

One sentence stating what this Phase delivers.

- [ ] `P02.S01` - ...
- [ ] `P02.S02` - ...
```

At `L3` and `L4` the Phase heading uses the ancestor-aware path
(`### Phase \`W01.P02\` - ...\`). The intent sentence is mandatory.
See the Identifiers and addressing display-path table for the
full conditional rendering rule.

### Wave block (`L3`, `L4`)

```markdown
## Wave `W01` - language-only convention rollout

One paragraph stating what this Wave delivers, which downstream
Wave depends on it, and which authorising documents back it.

### Phase `W01.P01` - ...
### Phase `W01.P02` - ...
```

The Wave intent paragraph is mandatory.

### Epic block (`L4` only)

The plan title (`# ...` heading) is the Epic title. No separate
Epic heading. The body opens with a `## Epic intent` block:

```markdown
## Epic intent

One paragraph stating the strategic goal, the external
project-management association, the timeline horizon, and the
teams or agents involved.

## Wave `W01` - ...
## Wave `W02` - ...
```

The `## Epic intent` block is mandatory at `L4` and absent at
`L1`, `L2`, `L3`.

## No-compression rule

When N actions are self-similar across N files, N concerns, or N
locations, emit N rows. Never collapse into "for each file, do X"
or "across all callers, do Y" or "in every module, replace Z". A
five-Step plan that enumerates each action is correct; a one-Step
plan that says "do all five" is a defect. The rule applies at
every tier including `L1`.

## Separator convention

ASCII spaced hyphens everywhere (single space, ASCII U+002D,
single space). Em-dash (U+2014) and en-dash (U+2013) are
forbidden in body, headings, frontmatter, and markdown-comment
hints.

## Markdown comment hints

The following blocks are embedded verbatim in the plan template
(`rules/templates/plan.md`) only. The writer-agent persona, the
write-skill, and other surfaces reference the plan template
rather than duplicating the hints. The ADR is the canonical
authoritative source; the plan template is the canonical
embedded-deployment surface; any future revision edits this ADR
first and the plan template re-syncs.

```markdown
<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artefact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->
```

```markdown
<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorising documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->
```

```markdown
<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

```

## Wave-1 contract anchors

The following rules are stated here so the Surface mapping below
has a body anchor for every per-file action.

- **`<Step Record>` mapping**: each Step in a plan produces
  exactly one `<Step Record>` artefact in `.vault/exec/`. The
  executing agent reads the originating Step row from the plan
  and writes the `<Step Record>` against that Step's canonical
  identifier (`S##`). The originating Step identifier is
  recorded in the `<Step Record>`'s frontmatter as a dedicated
  field (`step_id: S##`) so the linkage is machine-readable. The
  body of the `<Step Record>` may also restate the display path
  in a heading hint, but the frontmatter field is the canonical
  linkage slot.
- **`L4` execute behaviour**: the execute skill respects the
  project-management association declared in the `## Epic intent` block of an `L4` plan.
- **Phase Summary mapping**: a Phase Summary rolls up every
  `<Step Record>` belonging to its Phase.
- **Existing rules superseded**: the writer agent's "phasing only
  past 200 lines / 3 contexts" rule and the write skill's
  "do not include granular code details" rule are obsolete; the
  Hierarchy + Tier + Step row contract supersedes both. The
  research artefact is the canonical record of the previous
  rules' wording.
- **Vocabulary reconciliation in supporting skills**: any
  reference to Phase, Wave, or Step in supporting skills (such
  as the team-coordination skill and the curate skill) is
  reconciled against the canonical hierarchy stated in this ADR.
  No semantic change to those skills' workflows; only term
  alignment.

## Implementation-specifics delegation

This ADR specifies the architecture: the hierarchy, the tier
model, the row contract, the identifier and ordering rules,
and the surfaces that must change. The ADR does NOT specify the
exact prose to insert into each surface during the wave-1
rewrite; that authorial work belongs in the wave-1 plan
document, where the writer agent (gated by the
`vaultspec-docs-curator` and `vaultspec-writer` review per the
rule-extension mandate in `2026-05-06-plan-hardening-adr.md`)
authors the per-surface language. The wave-1 plan's authored
text becomes the binding wording on plan approval; this ADR
remains the architectural authority that the plan must conform
to.

## Surface mapping

The convention lands across the following `.vaultspec/` files in
wave 1. Every file must use `Step` consistently as the leaf-row
noun; no further per-file vocabulary cleanup is called out below.

- `rules/templates/plan.md` (canonical embedded surface) - rewrite
  the body around the hierarchy and tier rules; embed the three
  hint blocks verbatim from this ADR; add the `tier:` frontmatter
  field with the values and legacy-default rule from the
  Frontmatter contract section above; update the existing
  `<!-- LINK RULES: -->` comment to clarify that the `related:`
  field carries authorising documents (ADR, research, references,
  prior plans) and the body remains free of wiki-links and
  markdown links.
- `rules/agents/vaultspec-writer.md` - replace the existing Step
  Template section with this ADR's row contract; reference the
  plan template's three hint blocks rather than duplicating them;
  state the tier-selection criteria and the no-compression rule;
  extend the existing Frontmatter & Tagging Mandate section to
  spell out the new `tier:` field and the new authorising-document
  semantic of `related:`; remove the obsolete phasing rule per the
  Wave-1 contract anchors above.
- `rules/skills/vaultspec-write/SKILL.md` - point to this ADR as
  the authoritative spec; state the hierarchy and the four tiers
  in one paragraph; remove the obsolete "no granular code details"
  rule per the Wave-1 contract anchors above.
- `rules/skills/vaultspec-execute/SKILL.md` - state the
  `<Step Record>` mapping and the `L4` execute behaviour from the
  Wave-1 contract anchors above.
- `rules/templates/exec-step.md` - state that the file represents
  one Step identified by its canonical `S##` and ancestor display
  path; add the `step_id:` frontmatter field per the
  `<Step Record>` mapping rule in the Wave-1 contract anchors
  above.
- `rules/templates/exec-summary.md` - state the Phase Summary
  mapping from the Wave-1 contract anchors above.
- `rules/system/03-vaultspec.md` - extend the pipeline-description
  prose with the Wave concept and the four-tier model; point to
  this ADR for the canon.
- `rules/rules/vaultspec.builtin.md` - add `{wave}` and `{tier}`
  to the placeholder taxonomy with their YAML formats; remove any
  legacy leaf-row placeholders so `{step}` is the sole authorised
  leaf-row placeholder.
- `README.md` - rewrite the Planning subsection around the
  four-tier hierarchy with worked examples for `L2` and `L3`.
- `rules/agents/vaultspec-low-executor.md`,
  `vaultspec-standard-executor.md`,
  `vaultspec-high-executor.md` - state the executor side of the
  `<Step Record>` mapping from the Wave-1 contract anchors above.
- `rules/skills/vaultspec-team/SKILL.md`,
  `vaultspec-curate/SKILL.md` - reconcile any Phase, Wave, or
  Step references to match the canonical hierarchy in this ADR;
  no semantic change.

The plan template is the primary social-enforcement surface
during wave 1: every authored plan ships with the embedded hint
blocks in-band, so the convention is visible to writer agents,
executor agents, code reviewers, and human readers without any
of them having to load the writer-agent persona.
