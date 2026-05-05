---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/plan/ location)
# Feature tag (replace plan-hardening with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#plan'
  - '#plan-hardening'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-05'
tier: L3
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-adr]]")
related:
  - '[[2026-05-05-plan-hardening-adr]]'
  - '[[2026-05-06-plan-hardening-adr]]'
  - '[[2026-05-05-plan-hardening-research]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `plan-hardening` plan

Two-wave rollout of the `#plan-hardening` feature. Wave 1 lands
the natural-language firmware across the `.vaultspec/` rule
surface; Wave 2 lands the `vault plan` CLI and the rule-extension
prose that mandates CLI use. The convention authority is
`2026-05-05-plan-hardening-adr.md`; the CLI authority is
`2026-05-06-plan-hardening-adr.md`. Wave 1 is sequenced before
Wave 2: the CLI is meaningless without the firmware it
manipulates.

This plan is `L3` because Wave 2 has a hard dependency on Wave
1 landing first (CLI cannot enforce a contract that does not
yet exist in the firmware), Steps span two or more package and
rule-file boundaries with hard ordering between them, and the
total effort exceeds three days of agent work across multiple
sessions.

## Wave `W01` - language firmware rollout

This Wave delivers the convention ADR's surface mapping: a
coordinated rewrite of the `.vaultspec/` rule files that lands
the natural-language convention socially. No Python, no
validators. Authorised by `2026-05-05-plan-hardening-adr.md`.
Wave 2 depends on this Wave landing first. The Phases below are
ordered: the canonical embedded surface (`plan.md` template)
lands first because every other surface either embeds it or
points to it; the writer-agent persona lands second because the
agent is the primary social-enforcement surface; downstream
surfaces follow.

### Phase `W01.P01` - rewrite the plan template

The plan template is the canonical embedded surface for the
hint blocks and the row contract. Every authored plan begins as
a copy of this template. The Phase ends when the template
matches the convention ADR's specified shape and embeds the
three hint blocks verbatim.

- [x] `W01.P01.S01` - replace the existing Tasks section with the hierarchy and tier-driven structure scaffold; `.vaultspec/rules/templates/plan.md`.
- [x] `W01.P01.S02` - embed the HIERARCHY AND TIERS markdown comment hint block verbatim from the convention ADR; `.vaultspec/rules/templates/plan.md`.
- [x] `W01.P01.S03` - embed the IDENTIFIERS AND ROW CONTRACT markdown comment hint block verbatim from the convention ADR; `.vaultspec/rules/templates/plan.md`.
- [ ] `W01.P01.S04` - embed the NO COMPRESSION markdown comment hint block verbatim from the convention ADR; `.vaultspec/rules/templates/plan.md`.
- [ ] `W01.P01.S05` - add the `tier:` frontmatter field with the values and legacy-default rule from the Frontmatter contract section of the convention ADR; `.vaultspec/rules/templates/plan.md`.
- [ ] `W01.P01.S06` - update the LINK RULES comment block to clarify that `related:` carries authorising documents and the body remains free of wiki-links and markdown links; `.vaultspec/rules/templates/plan.md`.
- [ ] `W01.P01.S07` - add the Phase block format example as a commented template; `.vaultspec/rules/templates/plan.md`.
- [ ] `W01.P01.S08` - add the Wave block format example as a commented template; `.vaultspec/rules/templates/plan.md`.
- [ ] `W01.P01.S09` - add the Epic intent block format example as a commented template; `.vaultspec/rules/templates/plan.md`.
- [ ] `W01.P01.S10` - remove the existing flat-bullet escape hatch that previously permitted simpler features to bypass the Step row contract; `.vaultspec/rules/templates/plan.md`.
- [ ] `W01.P01.S11` - rewrite the Parallelization and Verification sections so they reflect the tier-driven structure rather than free-form prose; `.vaultspec/rules/templates/plan.md`.

### Phase `W01.P02` - rewrite the writer-agent persona

The writer-agent persona is the primary social-enforcement
surface: the agent reads its own persona file every time it
authors a plan. The Phase ends when the persona binds the agent
to the convention without duplicating the embedded hint blocks
that live in the plan template.

- [ ] `W01.P02.S12` - replace the existing Step Template section with the Step row contract from the convention ADR; `.vaultspec/rules/agents/vaultspec-writer.md`.
- [ ] `W01.P02.S13` - replace the obsolete phasing rule (the more-than-3-contexts or 200-lines threshold) with the hierarchy and tier model and the no-compression mandate; `.vaultspec/rules/agents/vaultspec-writer.md`.
- [ ] `W01.P02.S14` - add the approved structural vocabulary table and the tier-selection criteria as binding guidance the writer applies at plan-creation time; `.vaultspec/rules/agents/vaultspec-writer.md`.
- [ ] `W01.P02.S15` - add a paragraph stating the writer references the plan template's three hint blocks rather than duplicating them; `.vaultspec/rules/agents/vaultspec-writer.md`.
- [ ] `W01.P02.S16` - extend the existing Frontmatter and Tagging Mandate section to spell out the new `tier:` field and the new authorising-document semantic of `related:`; `.vaultspec/rules/agents/vaultspec-writer.md`.

### Phase `W01.P03` - rewrite the write skill

The write skill is the lightweight skill file that points to
the writer-agent persona. The Phase ends when the skill states
the hierarchy, the tier model, and points to the convention ADR
as the authoritative spec.

- [ ] `W01.P03.S17` - remove the obsolete "do not include granular code details" rule; `.vaultspec/rules/skills/vaultspec-write/SKILL.md`.
- [ ] `W01.P03.S18` - add the hierarchy and tier-model paragraph stating Epic > Wave > Phase > Step and the four tiers L1/L2/L3/L4; `.vaultspec/rules/skills/vaultspec-write/SKILL.md`.
- [ ] `W01.P03.S19` - update the workflow section to point readers to the convention ADR for the row contract, the embedded hint blocks (in the plan template), and the approved-vocabulary list; `.vaultspec/rules/skills/vaultspec-write/SKILL.md`.

### Phase `W01.P04` - rewrite the execute skill

The execute skill consumes plans and produces Step Records. The
Phase ends when the skill maps to one Step Record per Step (not
per Phase) and respects the L4 PM-association rule.

- [ ] `W01.P04.S20` - reconcile the existing "Step Record per completed phase" wording to "one Step Record per completed Step"; `.vaultspec/rules/skills/vaultspec-execute/SKILL.md`.
- [ ] `W01.P04.S21` - add a paragraph stating that at L4 the execute skill respects the project-management association declared in the Epic intent block; `.vaultspec/rules/skills/vaultspec-execute/SKILL.md`.

### Phase `W01.P05` - rewrite the exec-step and exec-summary templates

The exec-step and exec-summary templates govern Step Record and
Phase Summary scaffolding. The Phase ends when both templates
state their relationship to the originating plan via the
canonical Step identifier.

- [ ] `W01.P05.S22` - add a heading hint that the file represents one Step from the plan, identified by its canonical `S##` and ancestor display path; `.vaultspec/rules/templates/exec-step.md`.
- [ ] `W01.P05.S23` - add the `step_id` frontmatter field per the Wave-1 contract anchor of the convention ADR; `.vaultspec/rules/templates/exec-step.md`.
- [ ] `W01.P05.S24` - add wording that the summary rolls up every Step Record for one Phase; `.vaultspec/rules/templates/exec-summary.md`.

### Phase `W01.P06` - extend the system rules

The system rules describe the vaultspec pipeline at the highest
level. The Phase ends when the pipeline description names Wave,
the four tiers, and points to the convention ADR.

- [ ] `W01.P06.S25` - extend the pipeline-description prose with the Wave concept and the four-tier model; `.vaultspec/rules/system/03-vaultspec.md`.

### Phase `W01.P07` - extend the built-in rules and placeholder taxonomy

The built-in rules file holds the placeholder taxonomy used
across templates. The Phase ends when `{wave}` and `{tier}` are
present and `{step}` is the sole authorised leaf-row
placeholder.

- [ ] `W01.P07.S26` - add `{wave}` to the Document Body Placeholders table with its YAML format; `.vaultspec/rules/rules/vaultspec.builtin.md`.
- [ ] `W01.P07.S27` - add `{tier}` to the Document Body Placeholders table with its allowed values; `.vaultspec/rules/rules/vaultspec.builtin.md`.
- [ ] `W01.P07.S28` - remove any legacy leaf-row placeholders so `{step}` is the sole authorised leaf-row placeholder; `.vaultspec/rules/rules/vaultspec.builtin.md`.

### Phase `W01.P08` - extend the executor agent personas

Each executor persona writes Step Records. The Phase ends when
all three personas state the executor side of the Step Record
mapping.

- [ ] `W01.P08.S29` - state that the executor reads the originating Step row from the plan and writes one Step Record per Step; `.vaultspec/rules/agents/vaultspec-low-executor.md`.
- [ ] `W01.P08.S30` - state that the executor reads the originating Step row from the plan and writes one Step Record per Step; `.vaultspec/rules/agents/vaultspec-standard-executor.md`.
- [ ] `W01.P08.S31` - state that the executor reads the originating Step row from the plan and writes one Step Record per Step; `.vaultspec/rules/agents/vaultspec-high-executor.md`.

### Phase `W01.P09` - rewrite the public README

The README is the public-facing introduction. The Phase ends
when the Planning subsection describes the four-tier hierarchy
with worked examples for L2 and L3.

- [ ] `W01.P09.S32` - rewrite the Planning subsection around the four-tier hierarchy, embed worked examples for an L2 plan and an L3 plan, and note that Step is the canonical leaf-row noun mapping one-to-one to the existing Step Record artefact name; `.vaultspec/README.md`.

### Phase `W01.P10` - reconcile adjacent skills

The team-coordination and curate skills mention Phase, Wave, or
Step in passing. The Phase ends when both skills' vocabulary is
reconciled with the canonical hierarchy. No semantic change.

- [ ] `W01.P10.S33` - reconcile any Phase, Wave, or Step references to match the canonical hierarchy in the convention ADR; `.vaultspec/rules/skills/vaultspec-team/SKILL.md`.
- [ ] `W01.P10.S34` - reconcile any Phase, Wave, or Step references to match the canonical hierarchy in the convention ADR; `.vaultspec/rules/skills/vaultspec-curate/SKILL.md`.

## Wave `W02` - vault plan CLI implementation

This Wave delivers the `vault plan` CLI surface and the
rule-extension prose that mandates its use. Authorised by
`2026-05-06-plan-hardening-adr.md`. Wave 2 depends on Wave 1
landing first; the CLI parses, validates, and manipulates plan
documents that conform to the convention from Wave 1. The
Phases below are ordered: the parser and document model land
first (every command depends on them); read commands land
before write commands so the validator stabilises before
mutators run; destructive operations land last; the
rule-extension prose authoring lands after the CLI is functional
so the binding directives can be tested end-to-end.

### Phase `W02.P01` - plan-document parser and model

The parser converts a plan document into an in-memory model and
back. The Phase ends when round-trip parsing preserves
canonical identifiers, document order, and frontmatter exactly,
covered by unit tests.

- [ ] `W02.P01.S35` - create the `vaultspec_core.plan` package with module skeleton, `__init__.py`, and public surface exports; `vaultspec_core/plan/__init__.py`.
- [ ] `W02.P01.S36` - implement frontmatter parsing for `tier`, `related`, `tags`, `date`; `vaultspec_core/plan/frontmatter.py`.
- [ ] `W02.P01.S37` - implement hierarchy parsing for Wave, Phase, and Step blocks against the row contract; `vaultspec_core/plan/parser.py`.
- [ ] `W02.P01.S38` - implement canonical-identifier extraction and per-document next-available counter; `vaultspec_core/plan/identifiers.py`.
- [ ] `W02.P01.S39` - implement display-path computation from current ancestor chain; `vaultspec_core/plan/display_path.py`.
- [ ] `W02.P01.S40` - implement plan-document model serialisation back to markdown preserving document order; `vaultspec_core/plan/serialiser.py`.
- [ ] `W02.P01.S41` - add round-trip parser tests covering L1, L2, L3, and L4 plan shapes; `tests/plan/test_parser_roundtrip.py`.

### Phase `W02.P02` - read commands

The read commands (`status`, `check`, `query`) are independent
of the mutation surface and land first so the validator
stabilises before mutators run. The Phase ends when all read
commands return the human and JSON forms specified in the CLI
ADR and pass tests.

- [ ] `W02.P02.S42` - implement the `vault plan status` command's plan-snapshot collection; `vaultspec_core/plan/commands/status.py`.
- [ ] `W02.P02.S43` - implement the `vault plan status --json` schema and emitter (schema authored in this Wave's plan-management module); `vaultspec_core/plan/commands/status.py`.
- [ ] `W02.P02.S44` - implement the `vault plan check` command's finding-collection harness with severity levels and the finding-object schema; `vaultspec_core/plan/commands/check.py`.
- [ ] `W02.P02.S45` - implement the frontmatter detection rule (presence of `tier`, presence of `related` for non-trivial plans); `vaultspec_core/plan/checks/frontmatter.py`.
- [ ] `W02.P02.S46` - implement the hierarchy-correspondence detection rule (declared tier matches heading shape); `vaultspec_core/plan/checks/hierarchy.py`.
- [ ] `W02.P02.S47` - implement the identifier-hygiene detection rule (per-container append-only, no duplicates, padding); `vaultspec_core/plan/checks/identifiers.py`.
- [ ] `W02.P02.S48` - implement the display-path correctness detection rule against the current ancestor chain; `vaultspec_core/plan/checks/display_path.py`.
- [ ] `W02.P02.S49` - implement the row-contract detection rule (checkbox shape, separator, action, scope, period); `vaultspec_core/plan/checks/row_contract.py`.
- [ ] `W02.P02.S50` - implement the approved-structural-vocabulary detection rule scoped to headings, container-identifier code spans, and row-label position; `vaultspec_core/plan/checks/vocabulary.py`.
- [ ] `W02.P02.S51` - implement the separator-convention detection rule (no em-dash, no en-dash); `vaultspec_core/plan/checks/separator.py`.
- [ ] `W02.P02.S52` - implement the `vault plan check --fix` autofix harness with idempotency guarantees; `vaultspec_core/plan/commands/check.py`.
- [ ] `W02.P02.S53` - implement the checkbox-spacing autofix; `vaultspec_core/plan/fixes/checkbox.py`.
- [ ] `W02.P02.S54` - implement the separator-normalisation autofix; `vaultspec_core/plan/fixes/separator.py`.
- [ ] `W02.P02.S55` - implement the trailing-whitespace autofix; `vaultspec_core/plan/fixes/whitespace.py`.
- [ ] `W02.P02.S56` - implement the display-path-recomputation autofix covering Step rows, Phase headings, and Wave headings; `vaultspec_core/plan/fixes/display_path.py`.
- [ ] `W02.P02.S57` - implement the `vault plan query` command with selectors and predicates; `vaultspec_core/plan/commands/query.py`.
- [ ] `W02.P02.S58` - add unit tests for `status`, `check`, and `query`; `tests/plan/test_read_commands.py`.

### Phase `W02.P03` - additive write commands

The additive commands create new identifiers without mutating
existing content. The Phase ends when every additive command
preserves identifier immutability and document-order
independence per the convention ADR.

- [ ] `W02.P03.S59` - implement `vault plan step add` with `--phase` parent resolution; `vaultspec_core/plan/commands/step_add.py`.
- [ ] `W02.P03.S60` - implement `vault plan step insert` with `--before`/`--after` document-order placement; `vaultspec_core/plan/commands/step_insert.py`.
- [ ] `W02.P03.S61` - implement `vault plan phase add` with `--wave` parent resolution; `vaultspec_core/plan/commands/phase_add.py`.
- [ ] `W02.P03.S62` - implement `vault plan phase insert` with `--before`/`--after`; `vaultspec_core/plan/commands/phase_insert.py`.
- [ ] `W02.P03.S63` - implement `vault plan wave add`; `vaultspec_core/plan/commands/wave_add.py`.
- [ ] `W02.P03.S64` - implement `vault plan wave insert` with `--before`/`--after`; `vaultspec_core/plan/commands/wave_insert.py`.
- [ ] `W02.P03.S65` - add unit tests for additive commands covering identifier-immutability invariants; `tests/plan/test_additive_commands.py`.

### Phase `W02.P04` - state and re-parenting commands

The state commands edit existing rows; the re-parenting
commands move rows between containers. The Phase ends when
state mutations preserve canonical identifiers and re-parenting
recomputes display paths correctly.

- [ ] `W02.P04.S66` - implement `vault plan step toggle`; `vaultspec_core/plan/commands/step_toggle.py`.
- [ ] `W02.P04.S67` - implement `vault plan step check` (idempotent close); `vaultspec_core/plan/commands/step_check.py`.
- [ ] `W02.P04.S68` - implement `vault plan step uncheck` (idempotent open); `vaultspec_core/plan/commands/step_uncheck.py`.
- [ ] `W02.P04.S69` - implement `vault plan step edit` with `--action` and `--scope`; `vaultspec_core/plan/commands/step_edit.py`.
- [ ] `W02.P04.S70` - implement `vault plan step move` with the move-flag-precedence rule; `vaultspec_core/plan/commands/step_move.py`.
- [ ] `W02.P04.S71` - implement `vault plan phase edit` with `--title` and `--intent`; `vaultspec_core/plan/commands/phase_edit.py`.
- [ ] `W02.P04.S72` - implement `vault plan phase move` with the move-flag-precedence rule; `vaultspec_core/plan/commands/phase_move.py`.
- [ ] `W02.P04.S73` - implement `vault plan wave edit` with `--title` and `--intent`; `vaultspec_core/plan/commands/wave_edit.py`.
- [ ] `W02.P04.S74` - implement `vault plan wave move` with `--before`/`--after` and descendant display-path recomputation; `vaultspec_core/plan/commands/wave_move.py`.
- [ ] `W02.P04.S75` - implement `vault plan epic intent --show` and `--edit`; `vaultspec_core/plan/commands/epic_intent.py`.
- [ ] `W02.P04.S76` - add unit tests for state and re-parenting commands covering identifier-preservation invariants; `tests/plan/test_state_commands.py`.

### Phase `W02.P05` - destructive commands

The destructive commands retire identifiers (remove and
demotion) or restructure the document (tier ops). The Phase
ends when cascading retirement, demote-failure-on-multi-child,
and tier-promote intermediate-container instantiation all match
the CLI ADR's specified contract.

- [ ] `W02.P05.S77` - implement `vault plan step remove` with identifier retirement; `vaultspec_core/plan/commands/step_remove.py`.
- [ ] `W02.P05.S78` - implement `vault plan phase remove` with cascading retirement of child Step identifiers; `vaultspec_core/plan/commands/phase_remove.py`.
- [ ] `W02.P05.S79` - implement `vault plan wave remove` with cascading retirement of descendant Phase and Step identifiers; `vaultspec_core/plan/commands/wave_remove.py`.
- [ ] `W02.P05.S80` - implement `vault plan tier --show`; `vaultspec_core/plan/commands/tier_show.py`.
- [ ] `W02.P05.S81` - implement `vault plan tier promote` with transitive-jump support and `--phase-title`/`--wave-title`/`--epic-intent` flag handling; `vaultspec_core/plan/commands/tier_promote.py`.
- [ ] `W02.P05.S82` - implement `vault plan tier demote` with the multi-child refusal predicate and `--force` override; `vaultspec_core/plan/commands/tier_demote.py`.
- [ ] `W02.P05.S83` - add unit tests for destructive commands covering retirement-gap-preservation and demotion-refusal invariants; `tests/plan/test_destructive_commands.py`.

### Phase `W02.P06` - rule-extension authoring and review

This Phase authors the binding-directive prose for each surface
file per the rule-extension mandate of the CLI ADR, runs the
required curator-and-writer review pass, and applies the
approved prose. The Phase ends when every governed surface
mandates `vault plan` use and both reviewers have approved each
extension.

- [ ] `W02.P06.S84` - author rule-extension prose for the plan template's embedded hint blocks naming `vault plan` as the canonical manipulation surface; `.vaultspec/rules/templates/plan.md`.
- [ ] `W02.P06.S85` - author rule-extension prose for the writer-agent persona binding the writer to dispatch `vault plan` subcommands rather than hand-edit; `.vaultspec/rules/agents/vaultspec-writer.md`.
- [ ] `W02.P06.S86` - author rule-extension prose for the write skill naming `vault plan` as the canonical manipulation surface; `.vaultspec/rules/skills/vaultspec-write/SKILL.md`.
- [ ] `W02.P06.S87` - author rule-extension prose for the execute skill specifying executor use of `step check`/`step uncheck`; `.vaultspec/rules/skills/vaultspec-execute/SKILL.md`.
- [ ] `W02.P06.S88` - author rule-extension prose for the low-executor mirroring the execute-skill directive; `.vaultspec/rules/agents/vaultspec-low-executor.md`.
- [ ] `W02.P06.S89` - author rule-extension prose for the standard-executor mirroring the execute-skill directive; `.vaultspec/rules/agents/vaultspec-standard-executor.md`.
- [ ] `W02.P06.S90` - author rule-extension prose for the high-executor mirroring the execute-skill directive; `.vaultspec/rules/agents/vaultspec-high-executor.md`.
- [ ] `W02.P06.S91` - author rule-extension prose for the system rules naming `vault plan` as the structural manipulation surface; `.vaultspec/rules/system/03-vaultspec.md`.
- [ ] `W02.P06.S92` - author rule-extension prose for the public README introducing the `vault plan` CLI to external readers; `.vaultspec/README.md`.
- [ ] `W02.P06.S93` - dispatch the `vaultspec-docs-curator` agent to audit every authored extension for documentation hygiene, wiki-link correctness, frontmatter and tag compliance; `.vault/audit/`.
- [ ] `W02.P06.S94` - dispatch the `vaultspec-writer` agent persona to audit every authored extension for prose clarity, canonical-vocabulary compliance, and mandate-shape phrasing; `.vault/audit/`.

### Phase `W02.P07` - integration and end-to-end verification

This Phase wires the CLI into the existing `vaultspec-core`
Click app, adds CLI help docs, and runs end-to-end tests
against actual plan documents. The Phase ends when `vaultspec- core vault plan --help` lists every documented subcommand and a
clean smoke test executes a full plan-manipulation cycle.

- [ ] `W02.P07.S95` - register the `vault plan` subcommand group on the existing `vaultspec-core` Click app; `vaultspec_core/cli/app.py`.
- [ ] `W02.P07.S96` - add per-subcommand help strings matching the CLI ADR's Subcommand surface table; `vaultspec_core/plan/commands/`.
- [ ] `W02.P07.S97` - update the CLI reference document to enumerate every `vault plan` subcommand, flag, and exit code; `.vaultspec/CLI.md`.
- [ ] `W02.P07.S98` - update the public README to introduce the CLI in the context of the four-tier hierarchy; `README.md`.
- [ ] `W02.P07.S99` - add an end-to-end smoke test that creates a fresh L3 plan, exercises additive, state, re-parenting, and destructive commands, and verifies round-trip integrity; `tests/plan/test_e2e.py`.

## Verification

The plan is complete when every Step in both Waves is closed,
both reviewers (`vaultspec-docs-curator` and `vaultspec-writer`)
have approved every Wave 2 rule-extension, and the end-to-end
smoke test passes. Verification at each Wave boundary:

- Wave 1: `vault check all` reports a clean vault; the writer
  agent persona, the plan template, and the executor personas
  describe the convention without contradiction; the
  social-enforcement surfaces are coherent.
- Wave 2: `vaultspec-core vault plan --help` lists every
  subcommand documented in the CLI ADR; the end-to-end smoke
  test passes; the rule-extension prose has cleared both
  reviewer agents.

The convention ADR's row contract is itself the verification
artefact for plan-shape compliance: any plan document this
plan-management module produces must satisfy `vault plan check` cleanly. This plan document satisfies that constraint
upon Wave 2 landing.
