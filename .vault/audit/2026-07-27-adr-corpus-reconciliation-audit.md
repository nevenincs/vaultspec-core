---
tags:
  - '#audit'
  - '#adr-corpus-reconciliation'
date: '2026-07-27'
modified: '2026-07-28'
body_schema: 'body-v1'
related:
  - '[[2026-07-27-body-schema-attestation-adr]]'
---

# `adr-corpus-reconciliation` audit: `decision status against shipped code`

## Scope

Reconciliation of the architecture decision corpus against the code it governs,
run immediately after the 0.1.53 release. The pass covered every ADR's declared
status, the supersession and relatedness edges, and each recently-landed
feature's lifecycle documents against the single-home-fact boundary. Mechanical
hygiene was ceded to the CLI first, so what follows is only what no check can
decide.

## Findings

### Decision declared proposed while governing shipped code - actioned

The `body-schema-attestation` decision was recorded as `proposed`, but its
decision was implemented and published to the package index as part of 0.1.53.
A decision that governs released code while declaring itself unratified makes
the corpus an unreliable map of the architecture, which is the precise
divergence this reconciliation exists to close. Status advanced to `accepted`.
No wording changed: the decision recorded is the decision that shipped.

### Feature index absent for a landed feature - actioned

`markdown-feature-scope` carried no feature index despite having a full document
set. Regenerated through the owning verb.

### Plan without a governing decision - needs judgment

`2026-06-28-codebase-drift-sweep-plan` has no ADR behind it. The plan describes
a codebase-wide sweep for a defect pattern, so the missing record is a genuine
gap rather than a tagging error: nothing states what was decided about the
sweep's scope or its stopping condition. This has been outstanding across
multiple sessions. Either author the governing decision or archive the plan;
leaving it open keeps a permanent warning that trains readers to ignore the
check.

### Execution record pointing at a retired Step - needs judgment

An execution record declares Step `W02.P04-P06`, which does not exist in
`2026-05-17-cli-simplification-ux-plan`. The identifier shape is not canonical
either, so this predates the current Step conventions. Resolve with the exec
recovery verb or archive the record.

### Plans without research grounding - accepted by design in one case

Three plans carry no research reference. For `2026-07-27-vault-scale-performance`
this is deliberate and already justified: the feature grounds on its audit under
the audit-as-pipeline-start path, and that audit is linked. The other two,
`2026-06-10-cli-reference-automation` and `2026-06-28-codebase-drift-sweep`, are
legacy and unreviewed. The check is advisory and correctly cannot distinguish a
deliberate grounding choice from an omission.

## Recommendations

- Decide `codebase-drift-sweep`: author its governing decision or archive the
  plan. It is the only finding here that represents genuinely unfinished work
  rather than historical residue.
- Repair or archive the execution record naming the retired Step.
- Consider whether the research-grounding check should recognise an audit or
  reference as valid grounding, since the framework already sanctions both. As
  written it will keep flagging correctly-grounded plans, and a check that cries
  wolf on conforming documents erodes the value of the whole suite.
- Report volume is capped for the check and graph surfaces but not for listings,
  so `vault list` still renders every row on a large corpus. Extending the
  existing cap policy to listings is a user-visible output change and belongs to
  a decision rather than to this reconciliation.
