---
tags:
  - '#audit'
  - '#skill-audit'
date: '2026-09-25'
modified: '2026-09-25'
body_schema: 'body-v2'
body_hash: 'sha256:3f5b755dfc75132483bd2c6a5ac654e24de7ffbb03627d86d1ea6528c45b915f'
related:
  - "[[2026-09-08-framework-reword-adr]]"
  - "[[2026-09-23-adr-crossref-adr]]"
  - "[[2026-09-23-typesafe-search-adr]]"
  - "[[2026-09-23-adr-crossref-research]]"
---

# `skill-audit` audit: `ADR authoring, placement, and persona contracts`

## Scope

Audit requested by the user on 2026-09-25 against commit `8373e597`. Subjects:
`vaultspec-adr`, `vaultspec-research`, `vaultspec-code-research`, their personas and
templates, the adjacent plan writer, shared rules, curation, and the TypeSafe
cross-reference backend. No vaultspec skill was invoked. Skills were read as subjects;
isolated agents received policy text as hypothetical stimuli and could not use tools.
Framework implementation and accepted decisions were not changed.

The user specifically requested shorter, useful decision records; explicit ownership of
placement and reconciliation by the ADR author; and support for implementation findings
that invalidate design hypotheses. A possible TypeSafe check when offering a populated
ADR, with a 10-15 second budget, remains a question for subsequent discussion.

Evidence includes source inspection, a CLI inventory of all 134 ADRs, deterministic
fixtures using production parsers and checks, six completed agent calls covering 36
scenario responses, one separately retained timeout, five completed live TypeSafe probes,
and 65 passing existing tests. Raw
prompts, answers, scripts, and JSON results are retained outside the repository at
`C:/Users/hello/AppData/Local/Temp/vaultspec-adr-audit-w4icj2r2`. The findings and
numerical results below are the durable record; those scratch files are supplementary.

## Findings

### decision-projection | high | Cross-reference input can omit governing commitments

The production projection reads Problem Statement, Implementation, Constraints,
Rationale, and Consequences in that order, then clips their combined text to 6,000
characters: `src/vaultspec_core/crossref/_questions.py:72` and
`src/vaultspec_core/crossref/_corpus.py:205`. Of 134 current ADRs, 57 exceed that bound;
15 have a Constraints section whose heading does not reach the projected text. These are
input-coverage measurements, not measured misclassification rates. They do not mean
every clipped record loses its decisive constraint.

A 549-character synthetic ADR with the standard sections and an added `## Decision`
containing `NEVER_ACKNOWLEDGE_UNCOMMITTED_WRITES` loses that commitment entirely in the
projection. Moving it to `### Durability` inside Constraints retains it. A second
fixture puts the constraint after lengthy context; the resulting 5,998-character
projection omits it. New top-level sections therefore need coordinated support in the
machine reader, even when the document is short. Merely increasing the context ceiling
would not fix the omitted-section case.

The wire field `truncated` describes omitted verdict rows, not clipped decision input:
`src/vaultspec_core/crossref/_wire.py:120`. A future offering check must distinguish
incomplete evidence from a clean judgment. Existing instructions to read relevant pairs
in full remain useful protection. Recent amendments are not universally lost: the
inspected tool-catalog, read-only, and envelope ADR projections retain their recent
amendment notes.

### research-routing | medium | The research skill selects the decision-drafting persona

The dedicated roles exist and are registered in this checkout.
`vaultspec-adr-researcher` drafts decisions; `vaultspec-researcher` returns evidence;
`vaultspec-reference-auditor` investigates code; `vaultspec-writer` writes
implementation plans. The research skill instead recommends the ADR persona first and
mentions the general researcher for parallel threads:
`src/vaultspec_core/builtins/skills/vaultspec-research/SKILL.md:21`. The ADR persona
combines evidence gathering and decision drafting and permits both Research and ADR
output: `src/vaultspec_core/builtins/agents/vaultspec-adr-researcher.md:10`.

In two research-only scenarios, Sol low returned both research and an unsolicited
proposed ADR under the current policy. Luna extra-high returned research only, while
still selecting the ADR persona. A targeted experimental variant routed research to the
general researcher, limited the ADR persona to drafting from supplied evidence, and
removed its Research return block. Both models then returned research only. This
demonstrates a model-sensitive instruction conflict, not universal agent failure.
Registration and these hypothetical responses do not establish historical invocation
frequency in any host.

### adr-placement | medium | Placement exists but reconciliation output is underspecified

The ADR skill already distinguishes unchanged reuse, amendment, supersession, and a
distinct decision. Its cross-reference step is optional and occurs after drafting:
`src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md:14`. The persona's return
contract specifies Research and ADR bodies, without explicitly requiring proposed
changes to other governing ADRs. This leaves responsibility for a coherent affected
decision set implicit.

Six placement scenarios covered an authorized subsection refinement, cross-feature
reuse, conflicting older wording, supersession order, compatible decisions in one
feature, and incomplete cross-reference results. Current and experimental policies both
selected sensible placement in all six, without additional review gates or unnecessary
permission requests. The explicit variant made the author responsible for proposed
wording in the older ADR as well as the new draft. The current response returned a
conflict and proposed resolution to the orchestrator. This supports clarifying ownership
and output, not claiming the existing placement rules are absent or consistently fail.

There are positive examples already in the corpus. The TypeSafe and cross-reference
rollout amended `2026-08-01-mcp-read-only-adr` and `2026-07-09-mcp-tool-schema-adr`,
including an explicit replacement of the old tool-count constraint. That practice should
be made an authoring contract. One feature may have several compatible decisions; a
shared tag alone is not grounds for consolidation.

### decision-form | medium | Structural completeness does not establish a decision

The ADR schema mandates seven nonempty sections but no explicit Decision Outcome:
`src/vaultspec_core/vaultcore/body_schema.py:92`. A synthetic accepted ADR whose seven
sections all say that alternatives remain under evaluation passes both body-section and
grounding-schema checks. A concrete 41-word decision with Context, Decision, and
Consequences receives six missing-section warnings. These are warnings, not hard
rejections, and structural validation is not a semantic decision evaluator.

The template divides related reasoning among Problem Statement, Considerations,
Constraints, Implementation, and Rationale. Combined with mandatory completion and
whole-record reading, this can encourage padding and make the ruling hard to locate. The
ADR skill, ADR persona, and ADR template contain 453, 546, and 531 whitespace-delimited
words respectively. Corpus bodies, excluding frontmatter and comments, have a median of
1,057.5 words, a nearest-rank 90th percentile of 2,165, and a maximum of 6,953; 76
exceed 1,000 words. The 27 records dated since 2026-08-01 have a median of 1,504. This
measures length, not the cause of that length or the usefulness of each record.

Nygard's original guidance favors a short, significant decision with context, rationale,
status, and consequences. MADR explicitly names Decision Outcome and makes confirmation
and several supporting elements optional. These support evaluating a concise core,
without adopting another template wholesale:
https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions and
https://raw.githubusercontent.com/adr/madr/develop/template/adr-template.md.

### decision-evolution | medium | Expected rollout and invalidated hypotheses need distinct treatment

The system already permits routine implementation choices within settled constraints and
amendment or supersession when commitments or rationale change. Both models allowed an
authorized locking implementation to change while preserving the accepted ordering and
durability invariant. Both retained the accepted durability requirement when actual code
violated it. Neither forced acceptance after an inconclusive, time-bounded spike. The
probe does not support a blanket claim that the current ADR workflow forbids learning.

Curation nevertheless classifies an accepted decision not reflected in code as advisory
drift, and no implementation as potentially stranded, without an explicit
planned-rollout distinction:
`src/vaultspec_core/builtins/skills/vaultspec-curate/references/reconciliation-playbook.md:93`.
It correctly prohibits silently rewriting authority to match code. Authoring should make
binding commitments, provisional implementation hypotheses, and reasons to reconsider
the decision distinguishable. Expected implementation differences need not create new
ADRs; an invalidated commitment needs an evidenced, authorized revision. Acceptance
records authority, not proof that rollout is complete.

### typed-backend | low | Existing backend capabilities support further evaluation

TypeSafe returns typed Choice, Score, and Noul judgments over supplied state. Its
primary documentation recommends focused questions, batching independent questions over
the same state, and composing their answers in code. These are not free-text
coding-agent responses: https://docs.typesafe.ai/primitives. The existing backend
already combines candidate retrieval, pair judgments, typed failures, and bounded
transport. Relationship labels are advisory; applying results only adds links to the
source ADR, without reconciling bodies: `src/vaultspec_core/crossref/_models.py:103` and
`src/vaultspec_core/crossref/_service.py:122`.

The current single-source service has a 60-second deadline; the 15-second constant is a
sweep-start threshold, not an offering-check budget:
`src/vaultspec_core/crossref/_questions.py:133`. Existing research on section defects
and lineage is recorded in `2026-09-23-adr-crossref-research`; it should be reused
before designing another evaluator. The initial read-only CLI probe returned
`not_configured` in 1.226 seconds and changed no source. It judged zero pairs and
provides no live TypeSafe latency or accuracy result. The host-agent timings below must
not be used as TypeSafe timings. The credential-enabled follow-up below resolves this
initial configuration limitation.

### live-typesafe | low | Measured latency fits the proposed budget; coverage remains bounded

On 2026-09-25, the user authorized credential recovery from the RAG or classification
worktrees and configuration of core's main worktree. The RAG environment files had no
populated TypeSafe variable. The classification main environment supplied
`TYPESAFE_API_TOKEN`; core's main environment now has
`VAULTSPEC_CORE_TYPESAFE_API_KEY`. The destination is Git-ignored and untracked. No
credential value was printed, committed, or included in probe artifacts. The probe
loaded that credential into its process environment and CLI child.

All three cross-reference runs returned `ok`, with zero unscored evaluations and zero
writes. Times are wall-clock observations, not provider-only timing. The CLI row includes
process startup. Backend rows include corpus loading, index construction, client setup,
and evaluation, with a deadline set 15 seconds from before that setup.

| Live probe                         | Seconds | Evaluations | Billed input tokens | Suggested links |
| ---------------------------------- | ------: | ----------: | ------------------: | --------------: |
| CLI, cross-reference ADR           |   2.551 |          37 |             132,425 |               5 |
| Backend, cross-reference ADR, 15 s |   1.821 |          37 |             131,235 |               5 |
| Backend, hosted-search ADR, 15 s   |   1.665 |          37 |             131,060 |               8 |

The sources were `2026-09-23-adr-crossref-adr` and
`2026-09-23-typesafe-search-adr`. Both bounded backend runs used `jev-1.13.0`, loaded
134 ADRs, formed a 133-candidate pool, and judged 32 pairs; neither left a declared link
unjudged. The CLI surfaced the known read-only and tool-schema refinements. Evaluation
counts are logical requests, not independently measured HTTP attempts or agent tool
calls. No dollar cost was inferred. Successful bounded retrieval is not exhaustive
corpus reconciliation or evidence that every suggestion is correct.

A separate Noul question asked whether two simultaneously governing requirements
contradict each other, treating an explicit scoped exception as compatible. The draft
allowed configured hosted search to send vault text to TypeSafe while prohibiting other
remote operations. An existing absolute local-only requirement scored **0.94** for
conflict in **0.607 seconds** (405 input tokens). Replacing it with an explicit exception
for that hosted search scored **0.27** in **0.573 seconds** (413 input tokens). Each
returned 26 output tokens. These are two synthetic observations from a focused question,
not the production relationship classifier, calibrated error rates, or proof that 0.27
is an acceptable threshold.

The scratch harness initially failed while serializing an immutable answer mapping
after one successful remote response. It was corrected, the missing wording probe was
rerun, and the three completed cross-reference runs were retained without rerunning.
Usage for that unrecorded response is unavailable. Read-only mode and Git checks confirm
that no ADR was changed; hashes also matched across the resumed wording probes.

The observed latency makes a 10-15 second offering check plausible for this corpus.
There is one sample per condition, no tail-latency or outage measurement, and no
production offering hook in this test. Projection omissions identified above remain a
more immediate correctness concern than latency. A future check should reuse the
backend, expose incomplete coverage, and return actionable reconciliation candidates;
these measurements do not justify a mandatory approval gate or repeated unchanged
reviews.

### spike-results | low | Results are directional and reproducible within stated limits

Each response-only run contained six independent scenarios. All completed runs made zero
tool calls, as explicitly required by the fixture. Token counts are reported by the CLI
and include its harness; output includes reported reasoning tokens. Cached input is part
of total input, not an additional chargeable total.

| Model and policy               | Seconds | Input tokens | Cached input | Output tokens |
| ------------------------------ | ------: | -----------: | -----------: | ------------: |
| Sol low, current               |   14.65 |       21,353 |       11,904 |           545 |
| Sol low, role-specific retry   |   14.39 |       21,327 |       11,904 |           624 |
| Luna extra-high, current       |  149.16 |       21,174 |        7,936 |         7,447 |
| Luna extra-high, role-specific |   71.87 |       21,148 |       13,056 |         3,220 |
| Sol low, current placement     |   16.02 |       21,409 |       11,904 |           697 |
| Sol low, explicit placement    |   16.74 |       21,617 |       11,904 |           731 |

The first Sol role-specific call timed out at 150.52 seconds without completed usage;
the successful retry is shown separately. There is one completed sample per condition,
varying cache state, and no production authoring workload. Luna's lower output and time
in this pair do not establish a general efficiency improvement. The placement addition
increased prompt size from 4,784 to 4,960 words; it was an isolation probe, not a
proposed final wording patch.

Existing checks passed: 65 tests across cross-reference service, MCP cross-reference
transport, CLI supersession, and ADR grounding. Run with
`python -m pytest src/vaultspec_core/crossref/tests/test_service.py src/vaultspec_core/mcp_server/tests/test_crossref_tool.py src/vaultspec_core/tests/cli/test_vault_adr_supersede.py src/vaultspec_core/tests/cli/test_check_adr_grounding.py -q`.
The cross-reference service tests use a scripted local provider; they test integration,
not hosted model accuracy. No broad suite or repeated formal reviews were commissioned.

### implementation | low | Authorized findings applied across the authoring path

On 2026-09-25 the user authorized applying the findings to skills, personas, wording
rules and backend, with every TypeSafe call conditional on the configured API key. The
user separately required removal of numbered Jev identifiers from production and tests.
The changes amend the existing cross-reference, hosted-search and framework-routing
ADRs, citing this audit, rather than adding duplicate decisions.

- The ADR skill requires one configured, advisory pass on a populated draft. It reuses
  supplied results for unchanged relevant state, uses local discovery without a key,
  and does not make a provider failure an authoring gate. No network call was added to
  edit, deterministic checks or commit hooks. Delegation remains optional.
- The author owns placement and concrete proposed reconciliation of affected older
  wording. The research skill selects the general researcher; the ADR persona drafts
  from evidence and no longer returns a Research body. Rules, template and curation
  distinguish binding commitments, implementation hypotheses and expected rollout gaps.
- CLI `--body-file` and MCP `body` judge proposed prose in memory under an existing
  ADR's identity and links. The draft cannot apply links or sweep. Accepted bytes remain
  intact; successful results identify the draft. Both normal and read-only MCP surfaces
  support this input. Source judgment uses a 15-second deadline; a single-source call
  starts that deadline before corpus and client setup.
- Projection retains custom and repeated sections, shares the 6,000-character budget
  across sections, and exposes clipping in state, candidate rows and source coverage.
  Corpus, pool and selected-pair counts remain visible. No context ceiling was raised.
- `TypeSafeModel.JEV` in `core/enums.py` is the sole model selector. The API resolves
  the stable alias and supplies the actual serving model in its response. Transport and
  usage retain that returned identity. Source, tests and product documentation contain
  no numbered Jev references; a lexical-test example now uses a generic product name.
  The API contract is https://docs.typesafe.ai/api and https://docs.typesafe.ai/models.

The final live CLI amendment probe completed in **2.534 seconds**, with **38 logical
evaluations**, **138,892 billed input tokens**, zero unscored requests and zero writes.
It selected 33 pairs from a 133-candidate pool over 134 ADRs. The source and 24 selected
candidate inputs were explicitly marked clipped. Two link suggestions and four weak
declared links were returned; full-record reading remains necessary. All ADR hashes
matched before and after the probe. Scratch evidence: `final-offering-outcome.json` and
`final-offering-summary.json` in the directory named under Scope.

Across the corpus, **zero Constraints headings are now omitted**, versus 15 in the
original projection inventory, and no input exceeds its character bound. **91 records
report clipping**: all sections now count toward the budget, unlike the original
five-section projection. This is an input-coverage improvement, not a measured recall
or accuracy gain. Full-corpus content, source wording and the selection changed, so the
new live result is not a controlled comparison with the earlier timing rows.

The ADR skill, ADR persona, research skill and template total 1,882 words versus 1,914
before these edits, despite the added amendment and reconciliation guidance. The MCP
crossref definition remains within its original 2,550-character budget, and the whole
MCP surface remains within its existing ceiling. Bundled policy and eight matching local
policy sources were updated together and synced into Codex, including its inline persona
prompts. The separately installed TypeSafe skill remains available.

Verification covered the search transport and engine, cross-reference corpus and
service, CLI and MCP parity, no-key/no-send behavior, proposed-body nonmutation,
invalid draft/apply combinations, coverage propagation, reply/context budgets and
API-reported model identity. The main focused run passed 387 tests; its context-budget
failure was corrected and passed in the subsequent checks. The follow-up CLI/MCP and
documentation-guard run passed 209 tests and found one runtime-patching violation in a
new test. That test was changed to exercise an actual expired deadline without patching;
the four relevant checks then passed. Fourteen lexical tests also passed after removing
the model-specific tokenizer example. Ruff, Markdown formatting/lint and the project-wide
type check passed. The unchanged suites were not repeated after these narrow corrections.

The seven-section immutable body schemas remain compatible. Decision clarity is improved
through authoring guidance; the structural validator still does not certify that prose
contains a sound decision. No blanket semantic pass/fail gate or automatic authority
change was introduced.

## Recommendations

- Fix the research-to-persona mapping and make the ADR persona's output
  decision-specific. Keep delegation optional; a missing historical invocation count
  does not justify mandatory worker dispatch.
- Make placement and proposed reconciliation of affected existing wording part of the
  ADR author's work. Distinguish unchanged reuse, a subsection or amendment to the same
  commitment, supersession, and a distinct new decision. Preserve authority and history
  while applying already-authorized changes coherently.
- Evaluate a clearer decision core with binding constraints, scope, consequences, and
  explicit hypotheses or reconsideration conditions where relevant. Coordinate any
  section changes with immutable body schemas and search/cross-reference consumers; a
  template-only rename would be incomplete.
- Preserve bounded context while ensuring commitment-bearing sections reach the judge
  and incomplete coverage is visible. Do not solve omissions by silently raising the
  text budget. Assess the distinction between canonical evidence ownership and the
  minimum context needed to understand a decision without reopening every evidence file.
- Keep expected rollout, in-scope adaptation, invalidated hypotheses, and unauthorized
  divergence distinct. The code is evidence about reality; it does not silently retire
  the accepted decision.
- Revisit the proposed TypeSafe offering check after these findings. A follow-on
  decision would need to settle its trigger, 10-15 second budget, input coverage,
  incomplete-result behavior, and reuse of unchanged results. No hook policy or
  implementation is decided by this audit, and no new review gate is introduced.
