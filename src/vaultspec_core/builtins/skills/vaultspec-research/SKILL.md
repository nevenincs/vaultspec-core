---
name: vaultspec-research
description: Ground a decision in evidence before it is made. Use when an ADR is warranted and the options have not been weighed on evidence already in the vault or the code.
---

# Research (vaultspec-research)

Produces a Research record: the evidence a later ADR decides on. Enter it when the
vaultspec sizing warrants an ADR and the options are not already weighed in the vault or
the code. A question this session can answer without new evidence is answered in the
conversation; if that answer then becomes an ADR, this record is written first, however
short. This skill terminates within one run.

## Steps

- Ground per the `vaultspec-discovery` rule, decisions first: prior ADRs and research on
  the feature, read whole. Link what already exists; do not restate it.
- Scaffold: `vaultspec-core vault add research --feature {feature}` (or the `create`
  tool). Read `.vaultspec/templates/research.md`; its hint blocks fix the body shape:
  answer-first lead, claim-first `## Findings`, closing `## Sources`.
- Research in this run, or dispatch the `vaultspec-adr-researcher` persona (and
  `vaultspec-researcher` for parallel threads) with "Conduct research on `{topic}`", and
  transfer the returned findings into the body without diluting their locators.
- When the decision needs grounding in real code, branch to `vaultspec-code-research`
  for a Reference record and link it in `related:`.
- Fill every section this session; never leave or present an unfilled record.
- Verify with `vaultspec-core vault check all`.

## Quality gate

Judged by decision value per token; later phases re-read this record.

- **Answer-first.** The lead states question, stakes, and conclusion; each finding opens
  with its claim.
- **Locator-anchored.** Every non-obvious claim carries a re-fetchable locator (URL,
  `file:line`, commit SHA, `package@version`, RFC); an unanchored claim is marked as
  opinion.
- **Comparative and specific.** Alternatives named with why each was kept or rejected;
  versions, dates, and numbers pinned.
- **Grounding, not deciding.** At most name the option the evidence favours and what the
  ADR must settle. Decisions are recorded only in the ADR.
- **Bounded and lean.** Uninvestigated areas stated; link, do not copy; no hedging, no
  restated prompt, no closing summary.

## Next

Proceed to `vaultspec-adr`, in this run or the next; the ADR's approval covers the
findings, so this record needs no reply of its own. If the user faults the findings,
revise this record's body in place.
