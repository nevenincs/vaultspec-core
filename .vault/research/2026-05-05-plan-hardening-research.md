---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/research/ location)
# Feature tag (replace plan-hardening with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#research'
  - '#plan-hardening'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-05'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-plan]]")
related: []
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `plan-hardening` research: umbrella research

This is the umbrella research artefact for the `plan-hardening` feature. The
feature is a multi-wave hardening of the vaultspec plan surface. Subsequent
waves (template engine work, validators, CLI checks, etc.) reuse this
research; each wave gets its own ADR section and plan-document section but
shares this research baseline.

Wave 1 in scope: rewrite the natural-language contract that governs plan
production - the skill files, agent personas, plan template, and any
auxiliary markdown under the `.vaultspec/` tree that still mentions plan
structure, task granularity, phases, steps, waves, or review gates. No code
changes; pure language and contract work.

The driving observation is that current vaultspec plan documents drift into
generic prose. They list "phases" and "steps" but each step is summarised at
the level of an intent rather than a single mechanically-checkable action.
Self-similar rollouts across many files collapse into one or two terse
bullets, which destroys traceability between the plan, the commits, and the
review gates.

The desired contract: every task is a single row, every row is one
prompt-run + one commit, every row sits between two user-review gates, and
rows group into phases, steps, or waves expressing parent-child
relationships. Repetitive output is desirable, not a smell.

## Findings

### Audit: current `.vaultspec/` plan-writing surface

The plan-writing contract is currently spread across nine markdown files, with
some of the binding language only stated indirectly. The two
authoritative-feeling files are
`.vaultspec/rules/templates/plan.md` and
`.vaultspec/rules/agents/vaultspec-writer.md`. The skill, system rules,
public docs, and execute skill add reinforcements that often contradict each
other on granularity and structure.

#### `.vaultspec/rules/templates/plan.md`

This is the literal scaffold the writer fills in. The current "Tasks"
section has three problems for `plan-hardening`:

- It explicitly offers a "simpler" mode where tasks are flat bullets without
  phases, steps, or check-state. That escape hatch is the main source of
  prose-drift in practice.

- The phase example uses bare nested bullets with no checkbox, no stable
  ID, no parallelism marker, no traceability footer, and no "one row = one
  commit" rule.

- The header comment says "must be updated between execution runs to track
  progress" but supplies no progress mechanism (no `- [ ]` checkboxes, no
  state column, no row-level outcome field).

There is also no reference to "wave" anywhere in the template, even though
the user request explicitly treats waves as a first-class container above
phases for rolling, multi-batch features.

#### `.vaultspec/rules/agents/vaultspec-writer.md`

This persona file holds the most mechanical rules currently in the surface,
but they are weaker than they need to be:

- The "Step Template" specifies `Name`, `Step summary`, `Executing agent`,
  `References`. It is paragraph-shaped, not row-shaped. There is no
  checkbox, no stable ID, no commit gate, no review-gate marker.

- The "Phasing" rule triggers a phase only "if a task involves more than 3
  distinct logical contexts or exceeds ~200 lines of potential code change".
  This produces one giant phase for self-similar wide-rollout work
  (touching N files identically), which is the exact case the user wants to
  expand into N rows, not one summary.

- "Autonomously assign the most appropriate agent persona for each step"
  competes with the user's contract that each row is one prompt-run between
  review gates - "step" and "task" are used interchangeably here.

- Nothing in this file requires repetition. The persona's training
  pressure is to compress, so without an explicit repetition mandate it
  collapses N self-similar rows into "for each file, do X".

#### `.vaultspec/rules/skills/vaultspec-write/SKILL.md`

The skill explicitly states: "Do **NOT** include granular code details. The
plan should outline the PHASES, STEPS but not the code. Focus on **what**
and **where**." This rule, written for an earlier conception of plans as
high-level outlines, is now in direct tension with the desired contract,
which mandates exhaustive per-row enumeration of every concrete action.

The skill also uses "phases, steps" (no waves, no tasks-as-rows) as the
canonical structure vocabulary, propagating the gap.

#### `.vaultspec/rules/skills/vaultspec-execute/SKILL.md`

The execute skill consumes the plan and writes one Step Record per
"completed phase" (its words). This is a granularity mismatch: if a phase
contains many rows, the execute skill currently expects one record per
phase, not one per row. The plan-hardening contract collapses this by
making row = step = one commit = one record.

#### `.vaultspec/rules/templates/exec-step.md` and `exec-summary.md`

Both templates frame the unit as a `{step}` and ask for a "Brief summary of
work done" plus "Modified / Created" lists. They are usable for row-shaped
execution, but the surrounding language ("Brief summary", "Detailed
description") tilts the writer toward prose rather than diff-grade row
records.

#### `.vaultspec/rules/system/03-vaultspec.md` and `rules/vaultspec.builtin.md`

These pin the workflow vocabulary: "phases" and "steps" only. No mention of
waves; no row-level contract; placeholder taxonomy table lists `{phase}`
and `{step}` without `{wave}` or `{task-row}`.

#### `.vaultspec/README.md`

Public docs describe the plan as "phased, concrete steps" with "acceptance
criteria" - not the row-level contract. This is the user-visible surface
and must change in lockstep so external readers do not get the old mental
model.

#### Other ripples

`vaultspec-team/SKILL.md`, `vaultspec-projectmanager/SKILL.md`,
`vaultspec-curate/SKILL.md`, and the executor personas
(`vaultspec-low/standard/high-executor.md`) all reference "step" or "phase"
in passing. None of them define plan structure, but every one of them needs
its mention reconciled so the vocabulary stays coherent after wave 1.

`vaultspec-projectmanager/SKILL.md` is the most divergent because it talks
about milestones, sprints, and roadmaps at a different granularity. That
file should *not* adopt the row contract; it operates above the plan
surface. The audit needs to call this out so wave 1 does not over-reach.

#### Wave 1 rewrite surface (compiled list)

These files contain language that governs plan production or describes plan
structure to readers; all are in scope for wave 1 rewriting:

- `.vaultspec/rules/templates/plan.md` (primary - the scaffold itself)
- `.vaultspec/rules/agents/vaultspec-writer.md` (primary - persona contract)
- `.vaultspec/rules/skills/vaultspec-write/SKILL.md` (primary - skill rules)
- `.vaultspec/rules/skills/vaultspec-execute/SKILL.md` (consumer-side reconciliation)
- `.vaultspec/rules/templates/exec-step.md` (row-shaped step record)
- `.vaultspec/rules/templates/exec-summary.md` (phase summary - row roll-up)
- `.vaultspec/rules/system/03-vaultspec.md` (workflow vocabulary)
- `.vaultspec/rules/rules/vaultspec.builtin.md` (built-in rule, placeholder taxonomy)
- `.vaultspec/README.md` (public-facing description)
- `.vaultspec/rules/agents/vaultspec-low-executor.md` (consumer)
- `.vaultspec/rules/agents/vaultspec-standard-executor.md` (consumer)
- `.vaultspec/rules/agents/vaultspec-high-executor.md` (consumer)
- `.vaultspec/rules/skills/vaultspec-team/SKILL.md` (vocabulary touch-up only)
- `.vaultspec/rules/skills/vaultspec-curate/SKILL.md` (vocabulary touch-up only)

Out of scope for wave 1 (vocabulary may overlap but governance differs):

- `.vaultspec/rules/skills/vaultspec-projectmanager/SKILL.md`
- `.vaultspec/rules/agents/vaultspec-project-coordinator.md`

### Survey: external prior art on mechanical task contracts

#### GitHub `spec-kit`

The `spec-kit` tasks template is the closest prior art. Each task is a
single bulleted row of the form `[ID] [P?] [Story] Description`, where
`ID` is a stable sequential identifier (`T001`, `T002`, ...), `[P]` marks
parallelisable rows ("different files, no dependencies"), and `[US1]`
threads each row back to the user-story it serves. Phases are flat
section headers (Setup, Foundational, User Stories, Polish) - not nested
containers. The template states explicitly: "Commit after each task or
logical group." Independent delivery and parallel execution are first-class
properties of the row contract.

What `spec-kit` gives us:

- A working precedent for stable per-row IDs.
- A working precedent for inline traceability brackets back to higher-level
  containers (`[US1]`).
- A working precedent for an explicit parallelism marker.
- An explicit "commit after each task" rule baked into the template.

What `spec-kit` does *not* give us, and `plan-hardening` needs:

- No checkbox state. `spec-kit` is one-shot; the row does not track
  progress. We need `- [ ]` because our plan is updated between waves.

- No wave concept. `spec-kit` phases are linear. We need a phase / step /
  wave hierarchy because our rolling rollouts cross multiple plan revisions.

- No explicit "one prompt-run between review gates" rule. `spec-kit` is
  silent on the agent loop; we are not.

#### AWS Kiro `tasks.md`

Kiro `tasks.md` uses checkbox rows: `- [ ] N. description`, with sub-bullets
for implementation steps and a trailing `_Requirements: 1.1, 1.5_`
traceability footer linking each row to entries in `requirements.md`. Tasks
are "discrete, trackable" and are run individually or in batch via the IDE.

What Kiro gives us:

- A working precedent for checkbox state in the row.
- A working precedent for sub-bullet implementation steps under a parent
  row, while keeping the parent row itself as the trackable unit.
- A working precedent for trailing requirements traceability.

What Kiro does *not* give us, and `plan-hardening` needs:

- Kiro decouples requirements (`requirements.md`) from tasks; we trace to
  ADRs, research, and references via wiki-links instead. Footer format
  must therefore use `[[wiki-links]]` rather than dotted requirement IDs.

- Kiro is silent on parent-child phase / wave grouping in the published
  docs; we need it explicit.

#### BMAD-METHOD

BMAD's distinctive contribution is the *story* as the atomic unit of work,
with a hard create-implement-review cycle around each story. Each story
is created by a Scrum Master agent, implemented by a Dev agent, and
reviewed by Dev before retrospective. Crucially, BMAD has known issues
where the create-story template "doesn't enforce the required elements
that the validation checklist expects" - a direct cautionary tale for
`plan-hardening`: the template and the validator must agree, or rows will
drift into prose.

What BMAD gives us:

- The strongest analogue to our review-gate semantics: each unit of work is
  bracketed by an explicit human-mediated gate (create gate, implement gate,
  review gate). Maps directly to the user's "between user review gates"
  contract.

- A warning: the language contract is only as strong as the validator. We
  cannot ship the row contract without a validator, but wave 1 is
  language-only - so the ADR must explicitly schedule the validator as a
  later wave and the wave-1 plan must state which row properties are
  unenforced until then.

### Gap analysis: current output vs. desired contract

The gap is structural, not stylistic. The current surface allows valid
plans that violate every property the user wants:

| Desired property                               | Current surface state                                                                                                                |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Each task is a single row                      | Template explicitly permits flat bullets or nested phases without row-level granularity.                                             |
| Each row = one prompt-run + one commit         | No rule anywhere ties a row to a single commit; execute skill expects one record per "completed phase".                              |
| Each row sits between two review gates         | Skill's "Approval Loop" applies once at plan creation; no per-row gate semantics.                                                    |
| Phases / steps / waves express parent-child    | Only "phases" and "steps" exist in the vocabulary; no waves; no rule that a step sits inside a phase or that a wave contains phases. |
| Self-similar rollouts must enumerate every row | Writer persona's phasing rule actively collapses self-similar rollouts into one phase.                                               |
| Repetition is desirable                        | No rule encourages repetition; LLM training pressure compresses.                                                                     |
| Stable per-row IDs                             | None.                                                                                                                                |
| Checkbox state                                 | None.                                                                                                                                |
| Inline traceability per row                    | "References" lives at step-template level, not row level.                                                                            |
| Parallelism marker                             | None.                                                                                                                                |
| Validator parity                               | None - the template makes claims that nothing checks.                                                                                |

### Industry alignment check

Before committing to the hierarchy, the proposal was sanitised against
established frameworks. Findings:

- **Agile / SAFe / Jira** converge on `Epic > (Feature) > Story > Task` as
  the canonical issue hierarchy. "Story" is customer-facing and does not
  fit pure-engineering rollouts; "Feature" collides with the existing
  `#feature-tag` usage in vaultspec; "Task" is universally the leaf.

- **PMBOK** uses `Project > Phase > Activity > Task` in the Work Breakdown
  Structure. The boundary between phases is called a **stage gate / phase
  gate / kill point**. This is the same concept as the user's "review
  gate" and inherits decades of project-management precedent for free.

- **Rolling-wave planning** (PMBOK) and **rollout waves** (release
  management) use `Wave` as a horizontal slicing concept: an iterative
  planning batch (current wave detailed, future waves sketched) or a
  shippable rollout batch. Waves are explicitly orthogonal to phases in
  the literature, not nested inside them.

- **"Step"** does not appear as a structural level in any standard
  framework. PMBOK has `Activity` between `Phase` and `Task`; modern
  agile frameworks have collapsed it into Task.

### Industry alignment check (deeper survey: identifier stability and complexity tiers)

A second survey examined how production-grade tools assign and maintain
identifiers, and how they grade work-item complexity. The findings
overturn an earlier proposal in this research that emitted full
`W01.P01.T01` compound IDs even at trivial complexity.

**Jira and Linear: flat stable identifiers, hierarchy as relationship.**
Both tools use `TEAM-123` style identifiers: a flat per-project sequential
number assigned at creation and immutable for the lifetime of the issue.
Hierarchy (parent epic, sub-issue, parent task) is a relationship
attached to the issue, never encoded in the identifier itself. Promoting
an issue type does not change its key. Re-parenting a sub-issue does not
change its key. The identifier is a permanent address; the hierarchy is
metadata. This is the dominant convention in tracker software.

**PMBOK / WBS: hierarchical numbering exists but with an explicit
warning.** Work Breakdown Structures conventionally use `1.1.1` style
codes that show the hierarchy in the identifier. The literature is
explicit about the trade-off: if the order or level of an element is
altered, the element receives a new number. The Sparx Enterprise
Architect documentation states this directly: hierarchical numbering
"makes this mechanism unsuitable if immutable numbers are needed".
Industry consensus on requirement traceability is that renumbering
breaks historical references, training links, and audit trails;
renumbering is treated as a last resort.

**T-shirt sizing as the de-facto complexity vocabulary.** Asana,
ClickUp, SAFe, and adjacent agile tooling converge on the
`XS / S / M / L / XL` vocabulary for sizing work items. Each size
combines effort, complexity, and risk into a single ordinal. Concrete
tier examples published across these tools: XS = 1-2 days, S = 2-3
days, M = 5-7 days, L = 8-10 days, XL = 2+ weeks. Best-practice
guidance is consistent: define the sizes by complexity criteria, not by
arbitrary cardinality rules ("must have at least N phases").

**SAFe Epic predicates.** SAFe defines an Epic by portfolio properties,
not by raw size. Epic-grade work satisfies a set of predicates: cannot
be delivered within a single Program Increment; crosses Agile Release
Train boundaries; requires portfolio-level funding decisions; needs
MVP definition; requires Lean Portfolio Management approval. Smaller
work that lacks these predicates is a Feature, not an Epic. This
matches the user's framing for the vaultspec convention: Epics are
project-managed and tracked against external milestones; lower
complexity tiers are "naked coding tasks".

### Synthesis: industry-aligned identifier and tier model

Combining the above findings produces a model that resolves the
identifier-stability tension and the complexity-grading question
simultaneously:

- Identifiers at every level are flat, append-only, and immutable.
  Tasks have stable IDs `T01`, `T02`, `T03` per plan document;
  Phases have stable IDs `P01`, `P02`; Waves have stable IDs `W01`,
  `W02`. Promotion adds containers but never renumbers.

- The compound `W01.P02.T15` form is a display path computed from the
  Task's current grouping. It is not the identifier. The identifier is
  the leaf segment (`T15`).

- Complexity tiers map to t-shirt sizes and gate which structural
  containers a plan emits:

  - L1 (XS-S) = Tasks only. Single session, single concern, ≤1 day.
  - L2 (M) = Phases above Tasks. Multi-concern, cohesive module
    work, 1-3 days.
  - L3 (L) = Waves above Phases above Tasks. Hard interdependencies
    between batches, 3-10 days, multi-session.
  - L4 (XL) = Epic above Waves above Phases above Tasks. Multi-week
    or multi-month, multi-team or multi-agent, MUST declare project
    -management association (milestone, project board, roadmap goal).

- Tier selection is by complexity criteria, not by counting containers.
  A plan with one Phase and many Tasks is L2 if the work is cohesive at
  the module level; it does not need to invent a second Phase to
  qualify.

- The Epic level is reserved for project-managed work and inherits the
  SAFe Epic predicates (portfolio scope, MVP, business case). The
  vaultspec adaptation is: Epic plans MUST declare a project-management
  association in frontmatter. The mechanism (frontmatter field name,
  validation, integration with the project-coordinator agent) is
  deferred to a later Wave of `#plan-hardening`.

### Implications for the ADR (industry-aligned)

The ADR for `plan-hardening` commits to a four-level hierarchy with `Step`
preserved only as a synonym for `Task` to keep the existing
`<Step Record>` artefact name viable, and adopts complexity tiers (L1
through L4) to gate which containers a given plan instantiates:

- **Hierarchy**: `Epic > Wave > Phase > Task`, with `Step` as an explicit
  synonym for `Task` so that the execution-side `<Step Record>` artefact
  name continues to make sense without renaming. Each level maps to a
  named industry precedent: `Epic` (SAFe / Jira), `Wave` (PMBOK
  rolling-wave / release-management rollout wave), `Phase` (PMBOK), `Task`
  (universal).

- **Complexity tiers gate the structure.** A plan instantiates only the
  containers its tier requires: L1 emits Tasks only; L2 emits Phases
  above Tasks; L3 emits Waves above Phases above Tasks; L4 emits Epic
  above Waves above Phases above Tasks. The tier is declared in the plan
  frontmatter and selected by complexity criteria drawn from t-shirt
  sizing and SAFe Epic predicates.

- **Phase gate as the named review-gate concept**: the boundary between
  Phases is a phase gate. The boundary between Waves is a merge gate.
  Each Task is bracketed by a pre-task gate (approve intent) and a
  post-task gate (review commit). This vocabulary inherits PMBOK
  semantics directly.

- **Row contract**: every Task is exactly one bulleted checkbox row,
  anchored by a flat append-only stable canonical ID (`T01`, `T02`),
  rendered with a display path `W##.P##.T##` that reflects the Task's
  current grouping (the path is computed, not stored). The row carries
  a mandatory imperative-mood action verb, a mandatory file or area
  scope in inline backticks, and a trailing `_Refs: <wiki-link>_`
  italic traceability footer pointing at the ADR, research, or
  reference docs that authorise the row.

- **Identifier stability**: identifiers at every level are flat,
  append-only, and immutable. Promotion (L1 to L2, L2 to L3, L3 to L4)
  adds containers but does not renumber existing items. Demotion is
  symmetric. This matches the Jira / Linear convention and avoids the
  WBS-renumbering trap flagged by the PMBOK literature.

- **Tier-driven structure (no container collapsing)**: the plan's
  declared complexity tier determines which containers exist. L1 emits
  Tasks only with no Phase or Wave headings. L2 emits Phase headings
  above Tasks. L3 emits Wave headings above Phase headings above
  Tasks. L4 adds the Epic frame and a project-management association
  declaration. There is no "always emit full prefix" rule and no
  "simpler-features escape hatch": the tier picks the structure
  exactly.

- **No compression rule**: when N self-similar actions touch N files,
  the writer MUST emit N rows. Repetition is correctness. The ADR states
  this explicitly to overcome LLM compression bias.

- **Vocabulary reconciliation**: the workflow vocabulary in
  `system/03-vaultspec.md` and `rules/vaultspec.builtin.md` must add
  `{wave}` and `{task}` placeholders alongside `{phase}` and `{step}`,
  and the placeholder table must declare `{task}` and `{step}` as
  synonyms.

- **Forbidden vocabulary**: `subtask`, `feature` as a structural noun
  (only allowed as the kebab-case tag), `story`, `sprint`,
  `iteration` standalone, and `milestone` standalone (use `phase gate`
  instead).

- **Scoped wave-1 deliverable**: language-only changes to the surface
  listed above. Validator, CLI checks, plan-management Python module,
  and template-engine work are explicit later-wave items in the same
  plan document.

### Settled questions

- The hierarchy is `Epic > Wave > Phase > Task`. `Step` is a synonym for
  `Task`. The `<Step Record>` artefact name in `.vault/exec/` is
  retained.

- Plans declare a complexity tier (L1, L2, L3, L4) that gates which
  containers exist. Tier selection is by complexity criteria (t-shirt
  sizing analogues), not by counting containers.

- IDs are flat, per-level, append-only, and immutable. `T01`, `T02`,
  `T03` for Tasks; `P01`, `P02` for Phases; `W01`, `W02` for Waves.
  An identifier never changes for the lifetime of the plan document.

- Compound `W01.P02.T15` notation is a display path computed from the
  Task's current grouping. The canonical identifier is the leaf segment
  (`T15`).

- Promotion adds containers, never renumbers. Existing Tasks keep their
  `T##` IDs when a plan is promoted from L1 to L2; existing Phases
  keep their `P##` IDs when a plan is promoted from L2 to L3.

- Epic level (L4) requires an explicit project-management association
  declared in plan frontmatter. The mechanism is deferred to a later
  Wave of `#plan-hardening`; this ADR only mandates the requirement.

- Checkbox state is two-state: `- [ ]` (open) and `- [x]` (closed,
  merged after the post-task gate). No interim `[~]` state.

- Optional `_Commit: <sha>_` footer, filled in by the writer after the
  Step is closed, deferred from wave 1 to keep wave-1 scope to
  language only.

### Reconciliation note: final ADR decisions

This research surveyed several conventions the ADR ultimately
narrowed or rejected. The final ADR
(`2026-05-05-plan-hardening-adr.md`) supersedes any contrary
guidance in earlier sections of this research. The reconciliation:

- **Leaf-row noun**: the canon is `Step` everywhere across
  `.vaultspec/`. Earlier paragraphs in this research that used
  the universal leaf-row noun interchangeably are superseded; the
  ADR mandates `Step` as the single name across plan documents,
  the writer agent, the write-skill, the executor agents, and
  every adjacent surface. The execution-log artefact retains the
  name `<Step Record>`.

- **T-shirt sizing**: the survey found t-shirt sizing
  (XS / S / M / L / XL) as a de-facto agile complexity ordinal.
  The ADR rejects it. The four-level hierarchy (`Epic > Wave > Phase > Step`) itself encodes the complexity gradient; an
  orthogonal sizing vocabulary is superfluous and is not adopted
  by current agentic platforms.

- **Gate vocabulary**: the survey found PMBOK's `phase gate / stage gate / kill point` as established review-gate
  terminology. The ADR rejects the formal gate vocabulary entirely
  (no `phase gate`, no `merge gate`, no `pre-task gate`, no
  `post-task gate`, no `epic-completion gate`). Review semantics
  are inferred from checkbox state and Step / Phase / Wave
  completion, not from named gate tokens.

- **Forbidden-vocabulary table**: the survey produced a
  forbidden-vocabulary list. The ADR drops the forbidden table in
  favour of a positive-canon framing: the Approved structural
  vocabulary section names the four authorised structural nouns
  (`Epic`, `Wave`, `Phase`, `Step`), and any term not in that
  list is by definition unauthorised.

- **Identifier scheme**: the canon uses `S##`, `P##`, `W##` flat
  per-document append-only identifiers, with compound dot-notation
  as a display path only. This part of the survey is preserved
  unchanged.

- **Complexity tiers**: the canon uses `L1`, `L2`, `L3`, `L4`
  declared in plan frontmatter, with selection by predicate-based
  criteria. This part of the survey is preserved unchanged. The
  t-shirt-sizing column in earlier drafts of the criteria table
  is dropped.

- **Epic project-management association**: the canon requires
  `L4` plans to declare an external PM artefact in the
  `## Epic intent` block prose. The frontmatter mechanism is
  reserved for a later Wave.
