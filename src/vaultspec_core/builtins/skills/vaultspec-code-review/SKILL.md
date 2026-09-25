---
name: vaultspec-code-review
description: Review completed planned work for safety, intent, and quality using applicable verification evidence. Use at the system's review cadence.
---

# Code review (vaultspec-code-review)

Produces or extends an audit for work executed under a plan. Precondition: completed
Steps to review. A diff with no plan behind it is reviewed in the reply, not here. This
skill terminates within one run and never modifies the codebase; fixes go back to
`vaultspec-execute`.

## Steps

- Establish the reviewed Steps, diff base and target (including uncommitted changes),
  governing constraints, and unresolved risks. Reuse supplied grounding and verification
  evidence; inspect the plan, relevant ADR sections, ledger, and code to fill gaps.
- Scaffold once per feature, `vaultspec-core vault add audit --feature {feature}` (or
  the `create` tool); every later review appends to it. A separate audit (`--topic`)
  only for a different purpose, such as curation, or when the user asks for one. Read
  `.vaultspec/templates/audit.md`; its `## Findings` section is a rolling log, appended
  per review, never rewritten. Reuse completed analysis while the reviewed behavior and
  its interactions remain unchanged, including any uncommitted work.
- Trace affected workflows across interfaces. Apply the system's integrated review
  contract and cadence; files are evidence, not separate approval units.
- Review in this run, or dispatch the `vaultspec-code-reviewer` persona (parallel
  reviewers only for independent scopes that benefit from it). Supply the scope,
  grounding, evidence, and active check owners. Reviewers return findings for you to
  append; independent judgment does not require duplicate test runs.
- Append findings as `### {topic} | {level} | {summary}` entries, the level lowercase
  (`low` to `critical`). Report `FAIL` for critical findings, `REVISION REQUIRED` for
  high findings, otherwise `PENDING` when required verification is unresolved, or `PASS`
  when required checks have applicable passing evidence. Always report verification
  coverage alongside the verdict.
- Report `critical` and `high` findings to the executor; they reopen the affected Steps.
  Lower findings stay recorded. Fixes within approved scope return to approved Steps;
  new scope or costly decisions require authorization under the system contract.

## Verification evidence

Use existing CI results, ledger entries, or handoffs. Evidence identifies the command
and scope, checked revision or working-tree state, outcome, relevant environment, and
where to inspect results. Reuse it while relevant code, tests, dependencies, and check
conditions remain applicable; a commit identifier alone cannot establish freshness. Do
not introduce a separate evidence record or repeat checks just to sign the review.

Shared, expensive, or stateful checks have one owner, coordinated by the supervisor (the
reviewing agent when solo). Consult active check status before launching another run.
Continue code analysis while checks run. Cheap focused checks may run concurrently when
their resources are independent. Worktrees do not isolate machine capacity, services,
ports, or external quotas.

Run additional checks for a concrete coverage gap, changed relevant inputs, a suspected
defect, or an explicit project requirement. Choose the smallest useful check. Report
timeouts, unavailable infrastructure, and unfinished checks as evidence gaps, naming the
owner and next action; never silently skip required checks. Missing evidence alone does
not invent a defect or reopen a Step. Resume pending review with the missing results and
any changed interactions, without repeating completed analysis.
