---
name: vaultspec-curate
description: 'Audit and reconcile existing ADRs, implementation, and supporting records when the user requests vault curation or retrofit. Report decision conflicts and coverage gaps, and apply authorized repairs without rewriting decision history.'
---

# Vault curation

Use this standalone maintenance workflow for a user-requested feature, decision cluster,
or corpus audit. It is not a pipeline stage or a prerequisite for ordinary ADR
authoring. The ADR author owns reconciliation for the decision being written; curation
examines existing records across a wider scope.

Finish a bounded pass with findings, applied repairs, and an honest coverage statement.
A partially reviewed corpus is a valid checkpoint, not a clean bill of health.

## Scope and ownership

Use the requested scope and existing authorization. A review-only request produces
findings without repairing reviewed records. A curation request permits confirmed,
content-preserving repairs within scope; changes to decision authority follow the
system's approval contract. Prior authorization counts.

Work directly, or delegate a bounded assignment to `vaultspec-docs-curator` when useful.
Give a delegate the scope, write authority, relevant evidence, and any continuation or
service budget. One owner persists the audit and coordinates shared writes; do not run
the same reconciliation independently in both sessions.

Read `references/reconciliation-playbook.md` for the method and action boundaries. Read
`references/adr-status-taxonomy.md` when interpreting or repairing status.

## Workflow

1. **Inventory.** List the requested ADRs with `vaultspec-core vault list adr --json`,
   adding `--feature <feature>` when scoped. Follow `next_offset` with `--offset` while
   `truncated` is true. Record counts and unresolved coverage, not a copy of every body.
   Follow relevant relationships beyond the feature boundary without expanding write
   scope.
1. **Establish structural findings.** Run `vaultspec-core vault check all --json` once,
   scoped with `--feature` when appropriate, or reuse a current result. Start read-only;
   select owning repairs for actual findings within authority. Unrelated warnings do not
   prevent semantic work on readable records. Use the discovery rule's code-search
   fallback when RAG is unavailable; index provisioning is not a curation prerequisite.
1. **Compare decisions.** Read relevant full records and their status and supersession
   metadata. Use the playbook's optional TypeSafe pass when configured. Judge
   overlapping commitments, missing relationships, and contradictory current wording.
   Similar titles or a shared feature do not establish duplication.
1. **Compare implementation and evidence.** Inspect the code that implements the
   relevant commitments and the supporting records needed to test each finding.
   Distinguish rollout gaps and adaptable implementation details from violations of an
   accepted commitment. Preserve historical recommendations and evidence.
1. **Repair and verify.** Apply authorized, unambiguous repairs through owning verbs.
   Verify affected records and relationships once after the edits. Repeat only for a
   changed result, a failed repair, or new evidence; record unresolved problems instead
   of looping until the vault is clean.
1. **Persist and return.** Reuse the relevant reconciliation audit or scaffold one with
   `vaultspec-core vault add audit --feature <feature> --topic reconciliation`. Author
   findings in the audit format and link their supporting records with
   `vaultspec-core vault link add`. For a corpus audit, use the maintenance feature tag
   supplied by the user or a descriptive tag for this audit.

## Result

Report reviewed and unreviewed scope, findings with evidence and concrete resolutions,
actions taken, validation, and the audit stem. Include hosted-check usage, coverage
limits, and continuation when applicable. Distinguish a completed scoped review from a
partial pass. A finding resolved by an authorized repair stays in the audit with its
resolution; do not require a second review of unchanged evidence.
