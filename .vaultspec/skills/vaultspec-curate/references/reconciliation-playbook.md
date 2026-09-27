# Reconciliation playbook

The skill owns scope, workflow, and completion. This reference owns how to compare
records and choose an action. Status meanings are in `adr-status-taxonomy.md`.

## Build only the context the review needs

List ADRs through the CLI, following `next_offset` while the result is `truncated`. Read
each selected record's heading, commitments, evidence links, and `supersedes` /
`superseded_by` frontmatter. Use
`vaultspec-core vault graph --json --node <stem> --depth 1` or `--feature <feature>`
when a relationship is unclear. Read supersession from node frontmatter or the records
themselves; ordinary graph links are not proof of supersession. Follow named successors
even when outside the graph's displayed scope.

For a candidate conflict, read both records fully. Resolve their scope, status,
exceptions, chronology, and authorization before treating different wording as a
contradiction. Historical predecessors and complementary decisions can coexist without
consolidation. Inspect supporting research, audits, and active plans where needed; a
shared feature does not require reading every lifecycle document.

For code comparisons, locate the affected implementation under the discovery rule and
read enough surrounding code to test the commitment. An accepted ADR can precede its
rollout; a retired implementation can remain during an authorized migration. Record
those conditions separately from violations. Lack of a search hit or a graph edge does
not establish an abandoned decision.

## Optional hosted relationship check

Use TypeSafe only when `VAULTSPEC_CORE_TYPESAFE_API_KEY` is configured. Without it, use
local discovery; do not request or install credentials as part of curation.

Start with `vaultspec-core vault adr crossref --feature <feature> --json`, named ADRs,
or `--all` for a corpus pass. `--isolated` narrows to ADRs without declared ADR links;
it cannot establish general conflict coverage. Automatic sweeps exclude superseded,
rejected, and deprecated sources; name a historical ADR explicitly when needed.

The default batch takes 10 sources. Use one default batch unless the assignment supplies
a larger source, time, or spend budget. A batch accepts `--max-sources` up to 50, with
at most two extra sources to settle refusals; the backend enforces a 15-second source
deadline and a 300-second sweep budget. Resume within the assigned budget using the same
selector and the returned `next_after` as `--after`. A batch boundary does not require
renewed approval within that budget. Reuse existing judgments for unchanged records.

Read `remaining`, `stopped`, source statuses, `coverage`, `unjudged_declared`, reply
`truncated`, and `usage.unscored`. Candidate `input_truncated` and coverage flags mean
that the model did not see all the prose. Reply truncation means some verdict rows were
not delivered; record that gap rather than treating the count of evaluated sources as
completed semantic review. Do not rerun a sweep merely to recover omitted rows.

A `link` verdict may already be declared; only an undeclared, independently confirmed
relationship needs adding. Read relevant pairs to assess the advisory `relation` and
`weak` verdicts. Bounded ranking can miss a conflict; supplement it with scoped local
search and supersession/evidence links. Do not repeat the same discovery per pair.

On `not_configured` or service failure, use the named discovery fallback once and
continue with available evidence. Retain the returned cursor and reason for an
incomplete sweep. Do not invent a later cursor, run extra paid refusal probes, or
silently skip a refused source. A refusal already behind the returned cursor is still
unreviewed evidence to record. No hosted verdict authorizes a status change, removal, or
semantic edit, and a successful call does not certify the corpus conflict-free.

## Findings and actions

- **Status encoding.** Use `vaultspec-core vault check adr-status` and the taxonomy.
  Quoting a known token preserves authority. Missing, unknown, or conflicting status
  needs recorded authority before repair; never infer acceptance from implemented code.
- **Unpropagated supersession.** Confirm reciprocal `superseded_by` / `supersedes`
  metadata and the recorded transition. Then repair the predecessor's body through
  `vaultspec-core vault set-body` or `vaultspec-core vault edit`. An intermediate
  successor can itself be superseded. Ambiguous edges are findings, not permission to
  reconstruct history. New supersession uses `vaultspec-core vault adr supersede` after
  authorization and successor acceptance.
- **Contradictory commitments.** Identify the exact clauses, their common scope, and why
  exceptions or chronology do not resolve them. Propose concrete replacement wording and
  necessary edits to affected ADRs together. Apply when existing or new authorization
  covers the choice.
- **Duplication or fragmentation.** Establish that records decide the same commitment,
  rather than separate compatible choices. Recommend unchanged reuse, an amendment, or
  consolidation as warranted. Do not force one accepted ADR per feature or erase a
  legitimate historical chain.
- **Decision versus code.** Cite the commitment and the implementation evidence. State
  whether this is rollout, an implementation hypothesis, a violation, or insufficient
  evidence. Report violations without rewriting authority to match code. A requested
  retrofit can produce a proposed decision or amendment; acceptance still depends on
  authorization covering that decision.
- **Missing or weak relationship.** Add a confirmed missing link with
  `vaultspec-core vault link add` within write scope. Never rerun with `--apply` to
  write reviewed links: it buys new judgments and writes those results. A weak score
  alone does not justify removing an existing link.
- **Duplicated evidence.** Replace duplicated detail with a source-stem citation only
  when the source contains that substance. Preserve enough context, options, rationale,
  and consequences for the ADR to stand on its own. Unique evidence is not duplication;
  propose relocation when its proper home is unclear.
- **Displaced ruling or forked fact.** Distinguish claims of current authority from
  dated recommendations, alternatives, observations, and findings. Historical evidence
  can disagree with the chosen option without being wrong. Preserve it; clarify its
  historical role and point to the ruling where needed. Remove redundant current ruling
  language only when an accepted ADR records the same commitment and no evidence is
  lost. Conflicting observations remain findings; an accepted ADR does not make an
  empirical claim true. Surface a commitment with no authorizing ADR as a decision gap.

Use owning body and link verbs for record edits; never hand-edit frontmatter. Apply
content-preserving repairs only within write authority. Changes to accepted commitments
follow the system contract, including prior authorization and separate proposed text.

## Verify and checkpoint

Check the affected documents or feature after edits. Read the changed passages with
enough context to confirm that references resolve, retained evidence still supports the
claims, and repairs preserve decision meaning. Use a whole-vault check when the changes
have whole-vault scope; existing unrelated findings are not a completion gate.

Persist findings and resolutions in the reconciliation audit. Record scope reviewed,
scope deferred, failed repairs, uncertainty, and any hosted usage and continuation. Stop
when the bounded assignment is covered or its budget is reached. Resume from that
checkpoint when work continues; repeat verification only when relevant evidence changes.
