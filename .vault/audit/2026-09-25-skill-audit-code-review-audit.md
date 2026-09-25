---
tags:
  - '#audit'
  - '#skill-audit'
date: '2026-09-25'
modified: '2026-09-25'
body_schema: 'body-v2'
body_hash: 'sha256:96ad8acb53362f3c66bc5ff1d352d7c2c91c4b22e6c12c3d51300954f4e77a34'
related:
  - "[[2026-09-08-framework-reword-adr]]"
  - "[[2026-07-16-firmware-code-boundary-adr]]"
---

# `skill-audit` audit: `Review evidence reuse and parallel check ownership`

## Scope

The code-review skill and reviewer persona, traced through execution handoffs, team
supervision, always-on rules, provider rendering, and the public review guide. Baseline:
commit `b6bee7c1`. The user authorized clarification of redundant verification and
parallel resource contention during the ongoing bundled-skill audit. No VaultSpec skill
was invoked and no agents were dispatched. This cohesive wording correction needs no
new plan or costly decision; the linked accepted decisions already govern proportional
review and the development-record boundary.

The semantic code search returned a tool error. Discovery used the full ADR listing,
relevant accepted decisions and their evidence, supplied scope, and targeted source
reads. Static inspection establishes contradictory instructions, not the frequency or
cost of agents following them. No agent behavior benchmark was run.

## Findings

### check-ownership | high | Reviewer instructions duplicate executor checks without ownership

At the baseline, `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md:23`
unconditionally tells each reviewer to run tests, lint, and type checks, although the
execute skill already permits reuse. Team supervision coordinates shared file writes
but does not assign check ownership. Independent reviewers can therefore launch the
same expensive suite, compete for services, or confuse resource failure with a defect.
Resolved in `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md:39`,
`src/vaultspec_core/builtins/skills/vaultspec-team/SKILL.md:29`, and the reviewer method:
reuse applicable evidence, name one owner for shared, expensive, or stateful checks,
and continue independent analysis while that check runs. Isolated worktrees do not
imply isolated runtime resources. This is instruction-level coordination, not an
implemented process lock or test scheduler.

### review-outcome | high | No-findings output can hide missing verification

The baseline reviewer defines PASS only by absence of critical or high findings and
permits a no-findings reply without evidence. It does not distinguish unavailable
infrastructure, in-flight checks, and confirmed defects. The skill now orders outcomes
by critical findings, high findings, unresolved required verification, then applicable
passing evidence. PENDING is a prose review outcome, not a new persisted schema or CLI
enum. Every verdict carries coverage; missing evidence alone neither invents a defect
nor reopens a Step. A required long-running check is never silently waived.
Locators: `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md:31` and
`src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md:54`.

### bounded-review | medium | Whole-file reads and immutable plan wording encourage unnecessary work

The baseline method requires whole-file reading regardless of the affected behavior,
and its drift criterion treats anything the plan did not ask for as a defect. The
accepted workflow distinguishes binding commitments from implementation hypotheses.
Review now expands reading through affected contracts and callers as needed, reuses
supplied grounding, and judges scope and constraint violations by demonstrated impact.
Uncommitted changes participate in scope and evidence freshness; a commit identifier
alone is neither a reason to rerun nor proof that evidence applies. Locators:
`src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md:16` and
`src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md:37`.

### record-boundary | high | Reviewer and always-on wording forbid legitimate product-domain paths

The baseline reviewer marks any vault mention as high while its own footer permits
product documentation about the vault. The accepted boundary decision forbids references
to the project's own development records, not product-domain paths. Corrected both the
canonical mandate and the reviewer criterion, retaining the opt-in commit-trailer
exception. Locators: `src/vaultspec_core/builtins/system/01-core.md:21` and
`src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md:42`.

### review-guidance | medium | The public guide can trigger another suite and blanket mutation checks

The guide previously directed another tests/lint/type run before completion and described
mutation checking without a condition for using it. It now explains evidence reuse,
ownership, required checks, and unresolved verification. Mutation checks apply when a
guard's sensitivity is in doubt or a project requires them. The reviewer footer was
shortened and team reporting now names the host's available messaging mechanism, while
provider tool metadata remains intact. Locators: `docs/correctness.md` and
`src/vaultspec_core/builtins/skills/vaultspec-team/SKILL.md`.

## Recommendations

Keep the existing review cadence and project verification requirements. Review
independence concerns judgment, not separate executions of an identical command. Use
existing CI, ledger, and handoff evidence rather than adding another record or gate.

The TypeSafe skill and live documentation support a possible bounded claim/evidence
triage spike. Its citation-check cookbook separates exact-quote checks in code from
semantic support judgments. That is an analogy for checking whether a specific source
snippet supports a suspected finding, not evidence that the service can verify arbitrary
code. Sources: `https://docs.typesafe.ai/introduction/coding-agents` and
`https://docs.typesafe.ai/cookbooks/citation_check`.

Current VaultSpec semantic search and ADR reconciliation can supply governing context;
they are not a code-review triage endpoint. Project ranking already separates factual
priority from optional semantic relevance in `src/vaultspec_core/project/ranking.py`.
If a future spike is authorized, measure relevant-context selection and finding support
on fixed diffs, including false positives, latency, agent tokens, and duplicated tool
runs. Keep diff identity, check ownership, freshness, and completion deterministic.
Hosted judgments must not suppress required checks or grant PASS. Opt-in still requires
a configured API key; this workspace reported none, and no hosted calls were made.

### Validation

Manual scenario checks covered unchanged applicable evidence, changed test/runtime
inputs, dirty working trees, one in-flight shared suite, independent focused checks,
timeouts, known high findings with unfinished verification, and authorized implementation
adaptations. The written contracts give consistent outcomes without adding an approval
gate. These are desk checks, not agent evaluations or measured resource savings.

The initial renderer run caught frontmatter damage from using the formatter API without
its extensions. The edit was repaired using the configured CLI formatter; the targeted
builtin-seeding and agent-rendering suite then passed all 111 tests. Final validation
results are appended below once complete.

Final validation: `python -m pytest src/vaultspec_core/tests/test_seed_builtins.py src/vaultspec_core/tests/cli/test_agents_render.py dev/guards -m 'unit or precommit' -q`
passed 129 tests with 158 outside the selected markers. Markdown formatting and lint
passed for all changed Markdown. Parsed Codex configuration retains the reviewer
metadata and exact body; the three deployed skills match their source bodies. No
Python runtime logic or provider capability metadata changed. Sync also refreshed the
managed ignore entries for the private environment file and its variants. The two
pre-existing reference edits remain byte-identical and are excluded from this change.

Whitespace word counts, including metadata: reviewer 680 to 528; review skill 312 to
523; combined 992 to 1051 (about six percent more). The new evidence contract costs
context, partly offset by removing repeated persona boilerplate. These are document
word counts, not token usage or an agent-efficiency measurement. The five findings
above are addressed by the coordinated instruction and guide edits; no unresolved
critical or high finding remains from this bounded audit.
