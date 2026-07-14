# ADR reconciliation playbook

The detailed Ground -> Reconcile -> Act -> Verify loop the curator runs. It applies the
validated discovery sequence - locate by meaning, read the epicenter whole, confirm with
grep - to architecture decisions. Read `adr-status-taxonomy.md` first; this playbook
assumes the canonical status set.

## Ground: build the decision inventory

1. Run the preconditions: `vaultspec-core vault check all --fix` for structural hygiene
   (this includes `adr-status`, which surfaces the status divergences in the taxonomy
   reference), and confirm the semantic index is live (`vaultspec-rag server doctor`;
   index with `vaultspec-rag index --type vault` and `--type code` if empty).
1. Enumerate the corpus: `vaultspec-core vault list adr --json`. This gives path, name,
   feature, date, and tags - but not status, which lives in the body.
1. Parse each declared status from the body H1 (and any legacy `## Status` section) per
   the taxonomy. Record status, the `superseded_by` / `supersedes` frontmatter edges,
   and the feature for every ADR.
1. Pull the decision topology: `vaultspec-core vault graph --json` (scope with
   `--feature`, or `--node <stem> --depth N` for one decision's neighbourhood). The
   supersession and relatedness edges expose chains, forks, and stranded nodes.

## Reconcile decision-vs-decision (intra-corpus)

For each cluster of decisions on a shared concept:

- Surface the cluster by meaning:
  `vaultspec-rag search "<decision intent and domain nouns>" --type vault --doc-type adr`.
  Semantic recall finds same-topic ADRs that share no obvious filename or feature tag.
- Read the candidate ADRs whole. Judge them against each other for the conflict classes
  below. Do not rely on titles; two ADRs can agree in title and contradict in Rationale.
- Walk each feature's supersession chain end to end. A chain whose links are refinements
  of one decision - not pivots - is a fragmented decision, even when every marker is
  formally correct; so are sibling `accepted` records sharing one scope.

## Reconcile decision-vs-code

For each `accepted` decision (and each `superseded` / `deprecated` one, inverted):

- Locate the implementation by meaning:
  `vaultspec-rag search "<concept and domain nouns>" --type code` (narrow with
  `--language`, `--path`, `--include-path`, `--function-name`, `--class-name`,
  `--prefer production`).
- Read the epicenter file whole - the breakthrough step. Confirm the decision is
  actually implemented as the ADR describes.
- Confirm exact symbols and insertion points with a targeted grep.
- For `superseded` or `deprecated` decisions, invert the test: confirm the retired
  approach no longer dominates the code. A retired decision still governing the codebase
  is drift.

## Reconcile document-vs-document (lifecycle boundary)

Each fact has one home: research grounds, the ADR decides, audits find. For each feature
that has an ADR, enumerate its lifecycle documents
(`vaultspec-core vault list --feature <feature> --json`, or the feature index), read
them whole, and judge against the boundary:

- An ADR passage whose substance the related research or reference already records is
  restated grounding, not decision content.
- Decision language in a research or audit body - a chosen option stated as settled, "we
  will", a recommendation phrased as the decision - is a displaced decision.
- The same fact carried by two documents with diverging substance is a forked fact.

## Conflict taxonomy

Classify every finding into one of these, because the action differs by class:

- **Status drift (mechanical).** Declared status disagrees with the canonical encoding,
  or frontmatter supersession disagrees with the body status. Safe to fix.
- **Unpropagated supersession (mechanical).** `superseded_by` is set but the body status
  was never rewritten (typically a legacy `## Status` ADR). Safe to fix.
- **Contradiction (judgment).** Two ADRs make incompatible decisions on the same
  concept, and neither supersedes the other. Needs human resolution.
- **Duplication (judgment).** Two ADRs decide the same thing; one should supersede or
  reference the other.
- **Fragmented decision (judgment).** Several ADRs in one feature cluster are
  refinements of a single decision: a supersession chain of non-pivots, or sibling
  `accepted` records - possibly contradictory - sharing one scope. The markers can all
  be formally correct; the fragmentation itself is the finding.
- **Decision-vs-code drift (advisory).** An `accepted` ADR is not reflected in the code,
  or a retired decision still governs it. Report only; never auto-amend the ADR.
- **Orphaned or stranded decision (advisory).** A decision with no implementation and no
  successor, or disconnected from the decision graph.
- **Off-taxonomy or missing status (mechanical).** A status value outside the canonical
  set, or none at all.
- **Restated grounding (content-preserving).** An ADR re-narrates evidence its grounding
  documents record, substance identical. Safe to fix.
- **Displaced decision (content-preserving when homed; judgment when homeless).** A
  research or audit body records a decision. Safe to fix when an accepted ADR records
  the same decision; a decision no ADR records is homeless - surface it.
- **Forked fact (judgment, one exception).** The same fact in two documents with
  diverging substance. Surface it - except where one side is an accepted ADR's decision
  and the other a grounding document's recommendation: the ADR is authoritative, and the
  grounding side is safe to fix.

## Act: the action for each class

- **Status drift, off-taxonomy, missing status.** Normalize toward the canonical
  encoding. Prefer `vaultspec-core vault set-frontmatter` / `vault edit` for frontmatter
  and the CLI mutators over raw edits so stamps and the contract stay canonical.
- **Unpropagated supersession.** Re-run
  `vaultspec-core vault adr supersede OLD --by NEW` (use `--dry-run` first) so the
  frontmatter and body status converge. For legacy `## Status` ADRs the tool cannot
  rewrite, correct the body status to match via `vault set-body` / `vault edit`.
- **Contradiction, duplication.** Do not silently rewrite. Record the conflicting ADRs,
  the nature of the contradiction, and a recommended resolution in the audit for human
  approval. Apply the chosen resolution only once approved.
- **Fragmented decision.** Propose the consolidation in the audit: fold the chain's
  refinements into the record that currently governs (amending its body in place, per
  the amend-over-supersede rule the `vaultspec-adr` skill mandates) and supersede or
  deprecate the rest, so exactly one record is `accepted` for the scope. Apply only once
  approved.
- **Decision-vs-code drift.** Report as a finding in the audit. ADRs drive rollout, so
  never retrofit the ADR to the code automatically. If the human explicitly requests the
  ADR-from-codebase retrofit (legitimate for late-adopting projects), amend the ADR's
  Implementation prose via `vault set-body` / `vault edit` and note it in the audit.
- **Orphaned or stranded.** Surface in the audit with the graph evidence.
- **Restated grounding.** Confirm the fact exists in the grounding document; if the ADR
  is its only home, relocate it into the grounding body first. Then replace the ADR's
  restatement with a stem citation (e.g. "per `2026-02-04-editor-demo-research`, ...")
  via body-prose edit. The decision, the option set, the rationale's conclusions, and
  the consequences must read semantically unchanged afterward; when unsure, propose
  instead of applying.
- **Displaced decision.** Where an accepted ADR records the decision, strip the decision
  language from the research or audit body, leaving a one-line pointer to the ADR stem;
  keep the evidence and option framing intact. Where no ADR records it, never author one
  on your own - surface the homeless decision in the audit as an ADR candidate for the
  human to take through `vaultspec-adr`.
- **Forked fact.** ADR-vs-grounding: rewrite the grounding side to defer - keep its
  evidence, drop the contradicted conclusion, point at the ADR stem. Any other fork:
  record both locations and both readings in the audit; do not pick a winner.

## Verify

- Re-run `vaultspec-core vault check all` and re-scan the touched ADRs' status and
  edges.
- After boundary conformance edits, re-read each touched document pair whole and confirm
  the invariants held: every removed fact still has a home, every citation resolves to a
  document that carries the cited substance, and no decision changed.
- Loop until the mechanical classes are clean and every judgment-class finding is
  recorded.
- Persist the audit via `vaultspec-core vault add audit --feature <feature>`, then
  author the inventory, the findings by class, the actions applied, and the
  recommendations.
