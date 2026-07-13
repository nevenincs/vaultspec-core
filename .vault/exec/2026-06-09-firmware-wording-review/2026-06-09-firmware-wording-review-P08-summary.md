---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# `firmware-wording-review` `P08` summary

Phase P08 (style and typo sweep) closed all forty-two Steps S79-S120, implementing ADR
decisions D13 and D15: every typo from the research inventory is corrected, the single
style pass (American spelling, spaced hyphens, the bold-label mandate form, canonical
announce lines, curly-brace tag-example placeholders, ordinal-free discipline-rule
openers) is applied, the vocabulary drift items (doubled vault phrasing, host-specific
tool id, Execution Records noun, tier-conditional execute entry point) are unified, the
two embedded documentation agents gained the shared persona frontmatter schema, and the
codify trio now states one supersession procedure and one codification bar end to end.

- Modified: `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-research/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-execute/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-team/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-codify/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-documentation/agents/wireframe-agent.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-documentation/agents/editorial-reviewer.md`,
  `src/vaultspec_core/builtins/templates/adr.md`,
  `src/vaultspec_core/builtins/templates/exec-step.md`,
  `src/vaultspec_core/builtins/system/01-core.md`,
  `src/vaultspec_core/builtins/system/02-operations.md`,
  `src/vaultspec_core/builtins/system/03-vaultspec.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-codifier.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-writer.md`,
  `src/vaultspec_core/builtins/rules/vaultspec-codify.builtin.md`,
  `src/vaultspec_core/builtins/rules/vaultspec-dry-run-discipline.builtin.md`,
  `src/vaultspec_core/builtins/rules/vaultspec-plan-editing-discipline.builtin.md`,
  `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`,
  `src/vaultspec_core/builtins/reference/cli.md`
- Created: forty-two Step Records `...-P08-S79.md` through `...-P08-S120.md` in this
  folder

## Description

The phase ran in two parts: S79-S99 landed as commits `be78b38` through `40a39f1`, and
S100-S120 as commits `da08851` through `c1bce86`. Each Step landed as one commit
carrying the edit, its Step Record, and the CLI-driven plan-state change; all
pre-commit hooks passed on every commit.

S79-S87 (D15, typo inventory): the adr skill's "fundations", "considere null and void",
and missing conjunction; the write skill's "agent personaa"; the code-review skill's
"continously" and garbled rolling-log phrase; the research skill's broken description
fragment; the adr template's "constrainst", "condense but clear", and "descision"; the
exec-step template's "Succint", twice-occurring "failiures", "Scafolds", and stray
punctuation; the operations fragment's tone-label fragment, i.e.-for-e.g. misuse, and
bullet punctuation drift; the core fragment's three bold-label conventions unified to
the single Label-colon-sentence mandate form; and the codifier persona's
"project-bondedness" neologism, verb-less back-pointer sentence, and unordered tool
list.

S88-S95 (D15, locale and dash sweep): British spellings became American forms in the
codify rule, codify skill, and codifier persona; em dashes became spaced hyphens in the
CLI reference and the codify rule. Three rows were no-ops resolved by the P02 rule
shortenings, with grep evidence in their Step Records: S88 and S95 (plan-editing rule,
spelling and dashes, resolved by P02.S14) and S93 (archive rule, dashes, resolved by
P02.S11).

S96-S103 (D15, announce lines and tag examples): the execute and team skills gained the
canonical announce line, the write skill's divergent form was normalized, and the
literal `'#feature'` tag example became the `'#{feature}'` convention placeholder in
the five skills carrying it (adr, research, write, curate, execute). The write skill's
`_Syntax:_` underscore emphasis and the execute skill's italic Feature Tag label were
normalized to the sibling form in the same touch.

S104-S108 (D15, fragile structure): the "Second worked example" and "Third worked
example" ordinals were dropped from the plan-editing and dry-run rule openers (real
edits; the P02 shortenings had left the openers intact), the numbered-list conversion
rows S106 and S107 were no-ops already resolved by P02.S12 and P02.S14 (grep evidence
in the records), and the orphan end-conventions comment marker was removed from the
system fragment.

S109-S113 (D15, vocabulary drift): the doubled "the .vault vault" phrasing became "the
.vault/ documentation vault" in the curate skill and the docs-curator persona; the
writer persona's host-specific `read_file` tool id became provider-neutral "file
reads"; and the Execution Records noun was unified, replacing "Execution Logs" in the
rules hierarchy and "the execution-log artifact" in the system fragment.

S114-S116 (D13, codify trio): the rule, skill, and persona now state one supersession
procedure (a Status section in both rule bodies naming successor and superseded, then
`vaultspec-core spec rules remove <name>` once teammates are aware) and the rule gained
the no-first-encounter execution-cycle guard the persona and skill already stated, so
all three surfaces name the same codification bar.

S117-S120 (D15, embedded agents and entry point): the wireframe and editorial-reviewer
documentation agents gained the four-field persona frontmatter schema (description,
tier STANDARD, mode read-only, tools Read - both are pure evaluators that return
findings only); the wireframe agent's duplicated diataxis-rules read mandate was
deduplicated and its square-bracket placeholders converted to the curly-brace
convention; and the execute skill's unconditional "Start with Phase P##" instruction
became the tier-conditional entry point (Step S## at L1, Phase P## at L2, display path
at L3 / L4).

One out-of-scope observation was logged in the S112 and S113 records rather than
edited: the phrase "the execution-log artifact" also appears in
`src/vaultspec_core/builtins/agents/vaultspec-writer.md`, which no P08 row scopes; it
is left for the P09 close-out to pick up or log.

After the last edit the relevant test set ran green (automation contracts, template
annotations, CLI language contract, agents render: 85 passed, 0 failed) and
`vaultspec-core vault check all` reports all eleven checkers clean.
