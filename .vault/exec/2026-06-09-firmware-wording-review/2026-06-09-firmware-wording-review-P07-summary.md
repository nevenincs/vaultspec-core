---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# `firmware-wording-review` `P07` summary

Phase P07 (template sweep) closed all twenty-one Steps S58-S78, implementing ADR
decision D14: every template placeholder leak the research inventoried is fixed
against the documented placeholder conventions, the machine-filled placeholder class
is documented by name, and the shared FRONTMATTER RULES hint defects (uppercase date
form, garbled DO-NOT hint) are corrected in all eight templates that carry the block.

- Modified: `src/vaultspec_core/builtins/templates/plan.md`,
  `src/vaultspec_core/builtins/templates/code-review.md`,
  `src/vaultspec_core/builtins/templates/exec-step.md`,
  `src/vaultspec_core/builtins/templates/exec-summary.md`,
  `src/vaultspec_core/builtins/templates/audit.md`,
  `src/vaultspec_core/builtins/templates/adr.md`,
  `src/vaultspec_core/builtins/templates/index.md`,
  `src/vaultspec_core/builtins/templates/reference.md`,
  `src/vaultspec_core/builtins/templates/research.md`,
  `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`,
  `src/vaultspec_core/vaultcore/hydration.py`,
  `src/vaultspec_core/vaultcore/tests/test_hydration.py`
- Created: twenty-one Step Records `...-P07-S58.md` through `...-P07-S78.md` in this
  folder

## Description

S58 (D14): the plan template's `tier: <tier>`, the firmware's only angle-bracket
placeholder, became the quoted curly-brace form `tier: '{tier}'`. A trivial hydration
remap accompanied it: the tier key gained a quoted-form substitution pattern that
strips the quotes, so scaffolded plans keep the unquoted scalar the plan frontmatter
contract documents, and the quoted template no longer needs the mdformat
inline-map workaround (the legacy `{tier}`, `<tier>`, and `{tier: null}` patterns
remain supported). One covering unit test was added.

S59-S61 (D14): the plan template H1 dropped the stale `{phase}` segment (a fossil of
the one-plan-per-phase model; the filename pattern never had a phase segment), the
rules' General Rules heading example was updated to the same phase-less form, and the
Verification hint's completion criterion was retiered from "every Step in every Wave"
to the tier-neutral "every Step in the plan".

S62-S63 (D14): the code-review template H1 was lowercased to the convention every
sibling follows, and the uppercase ad-hoc placeholders (TOPIC, LEVEL, Summary,
DESCRIPTION) moved out of the rendered body into a FINDINGS FORMAT hint comment using
lowercase convention-compliant names and the critical/sharp/minor severity
vocabulary; sanitize now strips the entire format scaffold.

S64-S65 (D14): the exec-step template annotates its four snake_case placeholders
(heading, scope_block in the body; step_id, plan_stem in frontmatter) as
machine-filled by the exec scaffolding verb, without renaming them (hydration fills
them by literal token); the exec-summary template's instructional boilerplate and the
file1/file2 placeholders moved inside a hint comment so they no longer survive into
persisted documents.

S66-S68 (D14): the audit template's `related:` field is seeded with the same
wiki-link placeholder entry every sibling carries instead of the empty list its own
hint forbade; the adr template's H1 status enum gained the proposed state with a
lifecycle note in the frontmatter hint (the matching known-placeholder constant in
the hydration module was updated, the only other occurrence repo-wide); and the index
template documents its `generated: true` field as the machine-generated marker owned
by the feature-index command.

S69-S70 (D14): the rules file's Placeholder Naming Conventions gained a Machine-Filled
Placeholders subsection tabling all five CLI-filled placeholders (heading, step_id,
plan_stem, scope_block, document_list) with owning verb and value, plus the
snake_case-marks-machine-filled naming rule; and the Tag Format example's date became
the quoted form the templates actually scaffold.

S71-S78 (D14): the shared FRONTMATTER RULES hint block in all eight templates that
carry it (adr, audit, code-review, exec-step, exec-summary, plan, reference,
research) had its uppercase YYYY-MM-DD wiki-link example lowercased to the convention
form and its garbled "DO NOT add frontmatter fields outside the frontmatter" hint
reworded to the intended constraint: "DO NOT add fields beyond those scaffolded;
metadata lives only in the frontmatter". S77 applied its row to
`templates/reference.md`, the post-P06.S50 name of the `ref-audit.md` file the row
scopes. A closing grep across the templates directory finds zero remaining uppercase
date tokens and zero garbled hints.

Each Step landed as one commit carrying the edit, its Step Record, and the CLI-driven
plan-state change; all pre-commit hooks pass on every commit. After the last template
edit the full test suite ran green (2036 passed, 0 failed), including the template
annotation, hydration, CLI language-contract, and rule-contract suites, and
`vaultspec-core vault check all` reports green.
