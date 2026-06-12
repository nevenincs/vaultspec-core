---
tags:
  - '#adr'
  - '#firmware-wording-review'
date: '2026-06-09'
modified: '2026-06-09'
related:
  - '[[2026-06-09-firmware-wording-review-research]]'
---

# `firmware-wording-review` adr: `firmware reconciliation decisions` | (**status:** `accepted`)

## Problem Statement

The 2026-06-09 firmware wording review surfaced 98 raw findings across the
markdown firmware under `src/vaultspec_core/builtins/`: three critical
contradictions with behavioral consequence (a phantom skill name routing the
Plan phase, three competing addresses for the Verify artifact, read-only
personas carrying unfulfillable persistence mandates), a band of sharp
inconsistencies (skills teaching hand-authoring the CLI rule forbids, three
discipline rules stale against the 0.1.26 CLI, a lagging bundled CLI
reference, orphaned templates and personas, an incoherent executor trio,
template placeholder leaks), and a long tail of polish defects. The user
mandate is that every finding is reconciled, not triaged away. This ADR
records the decision for each theme so the follow-up plan can track all
findings to closure.

## Considerations

- The firmware is consumed by agents at session load; contradictory always-on
  mandates degrade every downstream session, so internal consistency
  outranks any individual wording preference.
- Renames are asymmetric in cost: editing prose references is cheap; renaming
  shipped artifacts (skill directories, template files, frontmatter enum
  values) may be bound by Python code, provider sync mappings, or tests, and
  needs a code check before the rename is chosen over the prose edit.
- The three audit-derived discipline rules each contain a Status clause that
  already prescribes how to shorten the rule once the CLI gaps close; the
  CLI cross-check confirmed the gaps have closed at 0.1.26.
- The existing vault corpus is prior art: multiple audits per feature already
  use narrative infixes (for example a `-check-engine-review-audit` stem), so
  the filename convention should document that practice rather than fight it.
- Persona safety posture: the code reviewer is the final verification gate
  and should remain read-only; granting Write to make its persistence
  mandate literal would weaken the gate.

## Constraints

- All edits land in `src/vaultspec_core/builtins/` (canonical) and propagate
  via `vaultspec-core sync` / `install --upgrade`; the deployed
  `.vaultspec/rules/` mirror is never edited directly.
- Tests may assert builtin content (snapshots, parsers, template loaders);
  every rename-class decision carries a mandatory code-binding check, and
  the full test suite plus prek hooks must stay green after each phase.
- The plan-editing discipline rule cannot be shortened until prose
  preservation is confirmed live against a real plan document (the CLI
  cross-check inferred it from `--canonicalise` flag semantics only).
- This feature is documentation-only by intent; any fix that would require
  Python changes beyond trivial name-mapping updates is out of scope and
  must be logged as a follow-up issue instead.

## Implementation

Sixteen decisions, one per finding theme. The follow-up plan maps every
research finding to exactly one decision.

- **D1 - plan skill name.** Standardize on `vaultspec-write`, the shipped
  directory name. Update the three dangling `vaultspec-write-plan`
  references (`system/03-vaultspec.md` pipeline and intent tables,
  `rules/vaultspec.builtin.md` catalog, `vaultspec-code-research` skill).
  The directory is not renamed.
- **D2 - verify artifact address.** The Verify phase's canonical artifact is
  an `<Audit>` document at `.vault/audit/yyyy-mm-dd-{feature}-audit.md`
  with tag `#audit`. An optional narrative infix
  (`yyyy-mm-dd-{feature}-{topic}-audit.md`) is documented as the
  disambiguator for features with multiple audits, retiring the undocumented
  `-code-review-audit` double suffix. The `.vault/exec/.../review` cell in
  the pipeline table is corrected, the `code-review.md` template is kept as
  the review-flavored audit body (tag `#audit` stands), and an Audit node is
  added to the Documentation Hierarchy.
- **D3 - persona persistence contract.** Artifact-producing read-only
  personas (code reviewer, adr researcher, reference auditor) stay
  read-only; their bodies are reworded to return findings to the dispatching
  orchestrator, which persists via `vault add` scaffold plus body-prose
  edit. The `mode:` field's meaning (declared file-mutation intent via
  harness tools; Bash caveat acknowledged) is documented once, and the
  project coordinator's Bash-only mutation path (`gh`, `git`) is noted as
  deliberate.
- **D4 - authoring path.** Skills are rewritten to scaffold documents via
  `vaultspec-core vault add` and then edit body prose, replacing every
  hand-author-from-template instruction. The CLI rule's absolute Mandate is
  qualified to match its own Allowed-manual-edits section.
- **D5 - discipline rule refresh.** The archive and dry-run discipline rules
  are shortened per their own Status clauses (archive `--dry-run`,
  `unarchive`, and exit-1 on bad tags now exist; the upgrade preview is
  populated). The plan-editing rule is shortened only after live
  confirmation of prose preservation. Version anchors become dated
  verification notes.
- **D6 - bundled CLI reference.** `reference/cli.md` is hand-updated to the
  live 0.1.26 surface: `vault add` tier/step flags, archive and unarchive
  coverage, `rename-integrity`, plan-verb parent and preview flags, and a
  sync output-vocabulary section. Automated regeneration is a logged
  follow-up, not part of this feature.
- **D7 - reference doc type noun.** The noun "reference" wins in all prose
  (hierarchy node, pipeline phase wording, directory description). The
  template file `ref-audit.md` is renamed to `reference.md` only if the
  code-binding check shows the name is unbound or trivially remappable;
  otherwise the filename stays and prose alone is unified.
- **D8 - orphan wiring.** `vaultspec-code-research` gains the template
  mandate, the standard frontmatter-and-tagging mandate, and an explicit
  pointer to the `vaultspec-reference-auditor` persona. The
  `vaultspec-researcher` persona is named by `vaultspec-research` as the
  generic persona for multi-researcher coordination. `vaultspec-team` and
  `vaultspec-projectmanager` are added to the supporting-skills tables.
- **D9 - executor trio.** The low executor gets a tier-appropriate mission
  (simplicity, pattern-following, minimal blast radius) and the mandatory
  code-review section. The middle tier is named "standard" everywhere; the
  frontmatter enum moves `MEDIUM` to `STANDARD` pending the code-binding
  check. The writer's routing table gains the low executor, and the trio's
  Documentation sections are made parallel (all three reference the
  `exec-step.md` template).
- **D10 - ADR authorship.** `vaultspec-adr-researcher` owns ADR drafting,
  matching its own description; its "context enhancer only" restriction is
  amended, and the `vaultspec-adr` skill names it in place of
  `vaultspec-writer`, whose mandate stays plan-only.
- **D11 - curate contract.** The persona's delegate model wins: the curator
  orchestrates fixes through loaded personas rather than editing in-place,
  and the persona gains the audit-report persistence obligation the skill
  already promises.
- **D12 - team dispatch wording.** The hedged wording wins:
  `system/03-vaultspec.md` describes teams as coordinated through the host
  environment, dropping the "team dispatch tools" infrastructure claim.
- **D13 - codify trio.** One supersession procedure: a Status section naming
  the successor in both rule bodies, then `spec rules remove` once
  teammates are aware. The no-first-encounter execution-cycle guard moves
  into the rule so persona, skill, and rule state the same criteria.
- **D14 - template system.** Placeholder leaks are fixed against the
  conventions: `tier:` becomes a quoted curly-brace placeholder; the plan H1
  drops the stale `{phase}` segment (rules' heading example updated in
  step); machine-filled placeholders (`{heading}`, `{step_id}`,
  `{plan_stem}`, `{scope_block}`, `{document_list}`) are documented as a
  named class in the conventions; uppercase ad-hoc placeholders in
  `code-review.md` move into comments using convention-compliant names;
  `exec-summary.md` boilerplate moves inside comments; `audit.md` seeds
  `related:`; H1 case is normalized; hint-block `YYYY-MM-DD` is lowercased;
  the date-quoting style of templates becomes the documented form; the
  garbled shared hints are reworded; `generated:` is documented; the ADR
  status enum gains `proposed`; the wave-assuming plan hint is retiered.
- **D15 - style and typos.** One sweep: American spelling, spaced hyphens
  replace em dashes, the "**Label:** sentence" mandate form, the canonical
  announce line in every skill, `'#{feature}'` placeholder examples,
  discipline-rule ordinals dropped, the orphan end-marker removed, and
  every typo from the research's inventory corrected.
- **D16 - mirror reconciliation.** After source edits, `vaultspec-core sync`
  propagates and `install --upgrade` clears the three-file reflow drift;
  `vault check all` and `spec doctor` close out the feature.

## Rationale

The research showed the firmware's structural skeleton (tier model, tag
taxonomy, filename schemas) is sound while its cross-reference layer has
rotted at the seams where artifacts were renamed or the CLI advanced. The
decisions therefore prefer the cheapest consistent state: shipped artifact
names win over prose (D1, D7, D9), the documented taxonomy wins over ad-hoc
variants (D2, D14), hedged capability claims win over asserted
infrastructure (D3, D12), and the CLI-mediated authoring path wins over
hand-authoring because the CLI rule is the newer, enforcement-backed surface
(D4). The discipline-rule refresh (D5) is not a judgment call at all: each
rule's own Status clause prescribed its shortening once the umbrella plan
steps landed, and the live CLI cross-check confirmed they have.

## Consequences

- One large documentation-only change set across roughly 40 firmware files;
  no behavioral Python changes, but rename-class steps (template file, tier
  enum) may touch name mappings and tests, gated by explicit checks.
- Agents loading the firmware after this lands receive one coherent story:
  one plan skill name, one audit address, one authoring path. Until the plan
  fully executes, partially reconciled states are possible; the plan orders
  decision propagation before polish to keep intermediate states safe.
- Shortening the discipline rules removes operator ballast but depends on
  the CLI staying truthful; the dated verification notes replace version
  pins so future staleness is detectable.
- The deferred items (automated `cli.md` regeneration, any Python work the
  checks surface) become logged follow-up issues rather than silent scope
  creep.

## Codification candidates

- **Rule slug:** `firmware-reference-parity`.
  **Rule:** Every skill, persona, template, or CLI verb named in firmware
  prose must resolve to a shipped artifact of exactly that name; renames
  must update every referencing surface in the same change.
