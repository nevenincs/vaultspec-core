---
name: vaultspec-adr
description: Record a new or changed costly decision after checking accepted decision coverage and sufficient Research, Reference, or Audit evidence.
---

# ADR (vaultspec-adr)

Records one costly decision. Apply the coverage and approval contract in the vaultspec
system section before creating a record. Reuse an accepted ADR unchanged when it covers
the work, including across features; return its stem without drafting a duplicate.

## Steps

- Discover governing decisions across features and read them whole, then their evidence.
  Classify the need as unchanged reuse, amendment, supersession, or a distinct decision.
- Confirm sufficient Research, Reference, or Audit evidence. Gather missing evidence
  through `vaultspec-research` for option research or `vaultspec-code-research` for code
  patterns. Do not copy an adequate Audit into a new Research merely for its type.
- For a new decision, scaffold:
  `vaultspec-core vault add adr --feature {feature} --related <evidence-stem>` (or
  `create`). Read `.vaultspec/templates/adr.md`.
- Draft the decision, or dispatch `vaultspec-adr-researcher` with the existing evidence
  and requested decision scope; it returns content for persistence.
- Once the decision sections are persisted, cross-reference the ADR with `crossref`
  (CLI: `vaultspec-core vault adr crossref <adr-stem>`). This step is optional and
  recommended. Read each `link` verdict's ADR and add the ones you confirm to `related:`
  with `vaultspec-core vault link add`, or rerun with `--apply` once all are confirmed.
  Read in full every pair labelled `supersedes`, `refines`, or `conflicts` before you
  settle amendment, supersession, or a distinct decision. The label marks a pair to
  read; it never decides. Without a hosted-search key the reply names the manual listing
  to use instead.
- For an amendment, preserve accepted content while proposing the revision separately.
  Follow the system's pending-proposal procedure if it must survive handoff.
- For a reversal, draft the successor first. After its content is authorized, set it
  `accepted`, then run `vaultspec-core vault adr supersede OLD --by NEW`.
- Verify with `vaultspec-core vault check all`. Present the record and authorization
  basis. If authorization is missing, ask and stop. Otherwise persist acceptance and
  continue with the authorized work. Rejected proposals remain as evidence; rejection
  never changes the accepted predecessor.

## Document boundary

Evidence stays in Research, Reference, or Audit. Cite it by stem; add missing facts to
their evidence home before using them. The ADR owns the decision, rationale, and
consequences. Decision language found in evidence moves here only when authorized.
