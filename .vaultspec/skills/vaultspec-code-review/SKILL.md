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

- Read the plan and the ADRs it executes; list the files the reviewed Steps changed
  (their ledger rows name them).
- Scaffold once per feature, `vaultspec-core vault add audit --feature {feature}` (or
  the `create` tool); every later review appends to it. A separate audit (`--topic`)
  only for a different purpose, such as curation, or when the user asks for one. Read
  `.vaultspec/templates/audit.md`; its `## Findings` section is a rolling log, appended
  per review, never rewritten. Steps already reviewed with no commits since are not
  reviewed again.
- Review in this run, or dispatch the `vaultspec-code-reviewer` persona (parallel
  reviewers only when the diff spans several subsystems), instructed to read the
  grounding documents and return findings for you to append.
- Append findings as `### {topic} | {level} | {summary}` entries, the level lowercase
  (`low` to `critical`), and state the result: `PASS` (no critical or high),
  `REVISION REQUIRED`, or `FAIL`.
- Report `critical` and `high` findings to the executor; they reopen the affected Steps.
  Lower findings stay recorded; fixing them is a Step the user approves.
