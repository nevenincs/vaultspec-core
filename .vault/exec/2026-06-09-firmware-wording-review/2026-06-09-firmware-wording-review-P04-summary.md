---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# `firmware-wording-review` `P04` summary

Phase P04 (skills authoring path) closed all seven Steps S20-S26, implementing ADR
decision D4: every artifact-producing skill now scaffolds its document via
`vaultspec-core vault add` and authors body prose, and the CLI rule's absolute Mandate
is qualified to match its own Allowed-manual-edits section, removing the
hand-authoring contradiction agents previously received as two always-on conflicting
mandates.

- Modified: `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-research/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-code-research/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`,
  `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`
- Created: seven Step Records `...-P04-S20.md` through `...-P04-S26.md` in this folder

## Description

S20 (adr skill): the "MUST save document to" step became a scaffold step
(`vault add adr --feature {feature} --related <research-stem>`); the Frontmatter &
Tagging Mandate was reframed from hand-authoring imperatives to
scaffold-produces-verify wording with drift reported via `vault check all`.

S21 (research skill): the "Save findings to" line became a scaffold step
(`vault add research`); the dispatched researcher now returns findings that are
written into the scaffolded document's body instead of persisting to a hand-addressed
path; tagging mandate reframed as in S20.

S22 (write skill): the plan Persistence rule now scaffolds via
`vault add plan --feature {feature} --tier <L1..L4> --related <adr-stem>`, builds
structure with the existing `vault plan` verbs (the structure-via-CLI mandate kept
verbatim), and authors only the prose sections as body edits; `tier:` is described as
set by `--tier` at scaffold time and changed via `tier promote | demote`, replacing
the writer-adds-the-field-on-first-edit hand instruction.

S23 (code-review skill): the audit artifact is born via `vault add audit`; the
Location and Tags bullets describe what the scaffold creates rather than instructing a
hand save; the D2 narrative-infix disambiguator wording from P01.S07 is preserved. A
dry-run confirmed `--title` does not alter the scaffolded filename, so the infix
remains descriptive prose.

S24 (code-research skill): the reference document is born via `vault add reference`
with findings authored as body prose; the missing template and persona mandates were
deliberately left for P06.S52.

S25 (curate skill): the curation audit report is scaffolded via
`vault add audit --feature docs-curation`; the dispatch instruction, the Auto-fixed
report bucket, the Non-destructive requirement, and the skill description all now
prefer `vault check all --fix` and the CLI repair paths over direct renames and
frontmatter edits; the tagging mandate is reframed as the validation schema the
curator checks. The curator delegate-model reconciliation is left for P05.S47.

S26 (CLI rule): the Mandate's "Do not edit `.vault/` documents directly" became a
qualified prohibition (never hand-write frontmatter, filenames, plan structure, or new
documents; body-prose edits of scaffolded documents permitted), pointing at the
Allowed manual edits section it previously contradicted.

Scaffold flags were verified against the live `vault add --help` (`--feature`,
`--related`, `--tier`, `--title`, `--dry-run`). Literal `'#feature'` tag examples,
inventoried typos, and announce-line drift in the touched files were left for their
dedicated P08 Steps. Each Step landed as one commit carrying the edit, its Step
Record, and the CLI-driven plan-state change; all pre-commit hooks pass on every
commit.
