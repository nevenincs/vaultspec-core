---
name: vaultspec-code-review
description: Audit planned work for safety, intent, and quality into a rolling audit record. Use at each point of the review cadence.
---

# Code review (vaultspec-code-review)

Produces or extends an audit for work executed under a plan. Precondition: completed
Steps to review. A diff with no plan behind it is reviewed in the reply, not here. This
skill terminates within one run and never modifies the codebase; fixes go back to
`vaultspec-execute`.

## Steps

- Read the plan's coverage assessment and any governing ADRs; list the files the
  reviewed Steps changed (their ledger rows name them).
- Scaffold once per feature, `vaultspec-core vault add audit --feature {feature}` (or
  the `create` tool); every later review appends to it. A separate audit (`--topic`)
  only for a different purpose, such as curation, or when the user asks for one. Read
  `.vaultspec/templates/audit.md`; its `## Findings` section is a rolling log, appended
  per review, never rewritten. Steps already reviewed with no commits since are not
  reviewed again unless changed interactions warrant it.
- Review cohesive behavior across the affected workflow, not each file as a separate
  gate. For framework work, trace scenarios through rules, entry metadata, skills,
  personas, templates, executable checks, repair, and resume. Apply the system's
  tier-aware cadence; L1 needs no invented Phase.
- Review in this run, or dispatch the `vaultspec-code-reviewer` persona (parallel
  reviewers only when the diff spans several subsystems), instructed to read the
  grounding documents and return findings for you to append.
- Append findings as `### {topic} | {level} | {summary}` entries, the level lowercase
  (`low` to `critical`), and state the result: `PASS` (no critical or high),
  `REVISION REQUIRED`, or `FAIL`.
- Report `critical` and `high` findings to the executor; they reopen the affected Steps.
  Lower findings stay recorded. Fixes within approved scope return to approved Steps;
  new scope or costly decisions require authorization under the system contract.
