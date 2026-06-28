---
name: vaultspec-curate
description: 'Reconcile the ADR architecture corpus against the codebase so decisions stay a single curated, non-contradictory set. Use to audit ADR status and supersession, find ADR-vs-ADR and ADR-vs-code conflicts, and action them. Mechanical .vault/ hygiene is the CLI''s job; this skill does the semantic reconciliation the CLI cannot.'
---

# ADR architecture reconciliation skill (vaultspec-curate)

**Announce at start:** "I'm using the `vaultspec-curate` skill to reconcile the ADR
architecture corpus against the codebase."

This skill keeps the architecture decision record (ADR) corpus and the code it governs a
single, curated, internally-consistent set of decisions. It reconciles each decision's
declared status and supersession against reality, finds where decisions contradict each
other or the codebase, and actions the result: propagating status, amending wording, and
surfacing gaps, conflicts, and errors that need human judgment.

Mechanical `.vault/` hygiene - frontmatter, wiki-links, filenames, tag pairs, template
compliance - is no longer this skill's work. The `vaultspec-core` CLI owns it
deterministically. This skill spends its judgment on what no check can decide: whether
an `accepted` decision is actually implemented, whether two ADRs disagree, and whether a
superseded decision still governs the code.

## When to use

- Periodically, to keep the ADR corpus a trustworthy map of the architecture.
- After a feature lands, to confirm the decisions it claimed are reflected in the code.
- When ADRs are suspected to contradict each other, or to lag behind what was built.
- Before a release or audit that depends on the decision record being accurate.
- For a project adopting the pipeline late, to reconcile an existing codebase against a
  thin or absent ADR corpus (the ADR-from-codebase retrofit; human-requested only - see
  Autonomy boundaries).

## Preconditions (cede the mechanical layer first)

Reconciliation reasons over a structurally-correct corpus and a populated semantic
index. Before any semantic work:

- **Structural hygiene to the CLI.** Run `vaultspec-core vault check all --fix`. This
  repairs frontmatter, links, names, stamps, and template drift. Never hand-fix these;
  the CLI is the source of truth for mechanical correctness.
- **Ensure the semantic index is live.** `vaultspec-rag` powers decision and code
  recall, but a freshly checked-out worktree is often unindexed. Confirm with
  `vaultspec-rag server doctor`; if the vault or code index is empty, populate it with
  `vaultspec-rag index --type vault` and `vaultspec-rag index --type code` before
  relying on search. Where rag is unavailable, fall back to the CLI discovery verbs and
  grep.

## Workflow

Dispatch the `vaultspec-docs-curator` agent persona to run the reconciliation. Instruct
it to: "Reconcile the ADR architecture corpus against the codebase. Establish the
decision inventory and declared status, reconcile decisions against each other and
against the code, action the mechanically-safe findings, and surface the rest in an
audit report."

The persona operates a **Ground -> Reconcile -> Act -> Verify** loop, the discovery-rule
sequence (locate by meaning, read the epicenter whole, confirm with grep) applied to
decisions:

- **Ground.** Build the decision inventory: `vaultspec-core vault list adr --json` for
  the set, the body H1 (and any legacy status section) for each declared status, and
  `vaultspec-core vault graph --json` for the supersession and relatedness edges.
- **Reconcile decision-vs-decision.** Use
  `vaultspec-rag search "<intent>" --type vault --doc-type adr` to surface ADRs covering
  the same concept, read them whole, and judge agreement, duplication, or contradiction.
- **Reconcile decision-vs-code.** For each live decision,
  `vaultspec-rag search "<concept and domain nouns>" --type code`, read the epicenter
  file whole, and confirm the decision is implemented; grep to confirm exact symbols.
- **Act and Verify.** Apply the safe actions, surface the rest, re-run
  `vaultspec-core vault check all`, and re-scan until clean.

The full query patterns, the conflict taxonomy, and the per-class actions live in
`references/reconciliation-playbook.md`. Read it before reconciling.

## Canonical status taxonomy

The curator enforces one canonical ADR status set and one supersession convention. The
authoritative definition - the values, their meaning, the canonical encoding, and the
divergences the curator must detect - is in `references/adr-status-taxonomy.md`. Read it
before judging any status. This set is the single source of truth the core library, the
ADR template, and the supersede tool all derive from; where the corpus or tooling
diverges, the curator reconciles toward it.

## Actions and autonomy boundaries

The curator acts on what is mechanically safe and proposes what needs judgment.

- **Act directly (mechanically safe).** Status propagation through
  `vaultspec-core vault adr supersede OLD --by NEW`; status-encoding and stamp
  normalization. Prefer the CLI mutators (`vault adr supersede`, `vault set-body`,
  `vault edit`, `vault link`) over raw file edits so the frontmatter contract and the
  `modified` stamp stay canonical.
- **Propose for approval (judgment).** Rephrasing or amending conflicting ADR wording,
  and any contradiction whose resolution is not obvious, are written into the audit as
  recommendations, not applied unprompted.
- **Never auto-retrofit ADRs to code.** ADRs drive codebase rollout, not the reverse.
  The curator reports decision-vs-code drift as a finding but does not rewrite an ADR to
  match the code on its own. Amending an ADR to reflect existing code (the legitimate
  ADR-from-codebase retrofit for late-adopting projects) is offered and executed **only
  on explicit human request**.

## Audit persistence

Persist findings as an audit report. Scaffold it with
`vaultspec-core vault add audit --feature <feature>` so the CLI owns the filename and
frontmatter, then author the body: the decision inventory, the conflicts found by class,
the actions applied, and the recommendations requiring author judgment. The audit report
is the one document the curator authors directly.

## Artifact linking

- Link persisted documents with quoted `'[[wiki-links]]'` in the `related:` frontmatter
  field.
- Do not use `@ref` links or `[label](path)` links for internal vault pages.

## Additional resources

- `references/adr-status-taxonomy.md` - the canonical status set, encodings,
  supersession convention, and the divergences to detect.
- `references/reconciliation-playbook.md` - the Ground/Reconcile/Act/Verify loop in
  detail: query patterns, the conflict taxonomy, and the action for each class.
