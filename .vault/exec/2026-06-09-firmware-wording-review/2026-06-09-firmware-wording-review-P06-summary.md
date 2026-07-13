---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# `firmware-wording-review` `P06` summary

Phase P06 (orphan wiring) closed all nine Steps S49-S57, implementing ADR decisions D7
and D8: the orphaned `ref-audit.md` template is renamed to `reference.md` after the
code-binding check cleared it, the "reference" noun is unified across the rules file,
the code-research skill gained its template mandate, tagging mandate, and persona
pointer, the research skill names the generic researcher persona, the team and
projectmanager skills entered the catalogs, and the reference auditor lost both its
drifted-content snapshot instruction and the retired safety-auditors mention.

- Modified: `src/vaultspec_core/vaultcore/hydration.py`,
  `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-code-research/SKILL.md`,
  `src/vaultspec_core/builtins/skills/vaultspec-research/SKILL.md`,
  `src/vaultspec_core/builtins/system/03-vaultspec.md`,
  `src/vaultspec_core/builtins/agents/vaultspec-reference-auditor.md`
- Renamed: `src/vaultspec_core/builtins/templates/ref-audit.md` to
  `src/vaultspec_core/builtins/templates/reference.md`
- Created: nine Step Records `...-P06-S49.md` through `...-P06-S57.md` in this folder

## Description

S49 (D7, gate): the code-binding check returned **TRIVIALLY-REMAPPABLE** - exactly one
mapping constant binds the `ref-audit.md` filename (`DocType.REFERENCE` in
`vaultcore/hydration.py` `get_template_path`); provider sync walks the builtins tree
with `rglob` and is name-blind, tests discover templates by glob with zero `ref-audit`
literals, and packaging names neither the file nor the directory. The deployed-mirror
copy was flagged as a post-rename orphan owned by P09's propagation Steps.

S50 (D7): the template was renamed via git mv and the single mapping constant updated
to `reference.md`. The full test suite ran green (2035 passed, 0 failed) and a
scratch-safe verification confirmed end-to-end resolution: a fresh install into a temp
directory seeds `reference.md`, and `vaultspec-core vault add reference --dry-run`
against that target resolves to `.vault/reference/yyyy-mm-dd-{feature}-reference.md`.
No Python follow-up needs logging in P09.S126 for the template filename.

S51 (D7): the rules file's hierarchy node dropped the last "Reference Audit" compound
("Brainstorm / Research / Reference") and the directory-table description became
"Implementation references and blueprints", unifying the reference noun with the
workflow document list P01 already corrected.

S52 (D8): the code-research skill gained the template mandate (pointing at the renamed
`.vaultspec/rules/templates/reference.md`), the standard Frontmatter & Tagging Mandate
in the post-P04 scaffold-then-verify framing (directory tag `#reference`, `#{feature}`
placeholder syntax), and an explicit instruction to load the
`vaultspec-reference-auditor` persona with the post-P05 return-findings contract.

S53 (D8): the research skill names the generic `vaultspec-researcher` persona for
multi-researcher coordination, keeping the adr-researcher as the focused default and
the hedged host-environment coordination wording intact.

S54-S55 (D8): the system fragment's supporting-skills table gained Team coordination
(`vaultspec-team`) and Project management (`vaultspec-projectmanager`) rows, and the
rules-file skill catalog grew to all eleven shipped skills with `vaultspec-code-review`,
`vaultspec-codify` reordered pipeline-first and `vaultspec-curate`, `vaultspec-team`,
`vaultspec-projectmanager` appended with the supporting skills.

S56-S57 (D8): the reference auditor's snapshot template no longer instructs body-text
`Related:` lines - related stems now ride with the returned findings for the
orchestrator to seed into frontmatter `related:` via `--related` at scaffold time - and
the retired safety-auditors dispatch bullet became a return-findings-consistent rule
(verification at close-out is the dispatching orchestrator's responsibility). Two
non-referential "safety auditor" strings remain in the code-reviewer persona (a simile
and a provenance note); neither instructs dispatching a persona.

Each Step landed as one commit carrying the edit, its Step Record, and the CLI-driven
plan-state change; all pre-commit hooks pass on every commit and
`vaultspec-core vault check all` reports green.
