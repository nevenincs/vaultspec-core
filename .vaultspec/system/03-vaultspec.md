---
order: 3
---

# Vaultspec

`.vault/` preserves decisions and progress across sessions; `.vaultspec/` holds policy.
This section owns routing, decision coverage, approval, and review. The `vaultspec` rule
owns record boundaries; `vaultspec-cli` owns tool usage; `vaultspec-discovery` owns
discovery; the plan template owns tiers and row syntax. Skills and personas apply these
contracts.

## Vocabulary

- **turn** - one user message and the reply.
- **run** - one agent invocation, from dispatch to its final message.
- **session** - one context window, ending at compaction, restart, or handoff.
- **feature** - one named capability or change, sharing a tag across requests.
- **Step** - a cohesive, verifiable unit of planned work, one commit and its ledger
  rows.
- **decision** - a commitment whose reversal requires coordinated migration,
  compatibility work, or material operational change. Boundaries, persisted schemas,
  protocols, public interfaces, and dependency strategy are examples. A routine update
  within settled constraints is not automatically a new decision.
- **execution** - implementation within the user's scope and settled decisions.
- **horizon** - how long intent and progress must survive: conversation, multi-session,
  or multi-week. File count and worker count alone do not determine it.
- **blocker** - a missing prerequisite or unresolved choice that prevents authorized
  execution. Expected file creation, routine corrections, and implementation details
  within approved constraints are not blockers.
- **presented** - the record's path and a concise account of its scope and choices.
- **approval** - explicit user authorization covering the decision or work, including
  advance authorization with that scope. Persist its basis. Neither elapsed time nor an
  agent-written status grants approval. Ask only for authority not already supplied.

## Route by need

Discover governing decisions before changing code or vault records, at every horizon.
Discovery is reading and investigation; it does not itself require a persisted record.
Search across features as well as listing ADRs for the current feature.

Assess decision coverage separately from planning need:

- Reuse an accepted ADR unchanged when it settles the commitments the work depends on. A
  new feature, plan, or session does not require a duplicate ADR.
- Amend a refinement of the same decision; supersede a reversal or invalidated
  rationale; create a separate ADR for a distinct costly decision. Use `vaultspec-adr`.
  Gather missing evidence through Research, Reference, or an evidence-bearing Audit.
  Evidence sufficiency is a judgment; a link's document type alone does not prove it.
- Routine execution needs no new ADR. A question stays in the conversation unless its
  answer establishes a costly decision that implementation will build on.

Work directly when this session can finish it without needing durable sequencing or
handoff. State briefly that no plan is needed. An ADR may still be required by the
decision test; its Implementation section then bounds the direct work. Review unplanned
work in the reply.

Use a plan when scope or progress must survive sessions or handoff, or coordination
needs durable sequencing. Select the smallest useful tier from the plan template. L1 can
describe several major revisions as flat Steps. Duration, packages, files, or parallel
workers do not alone require additional containers or external tracking. If direct work
outlives the session, plan the remaining work and reassess decision coverage; do not
manufacture an ADR for the longer horizon.

A plan links every governing ADR in `related:` and inherits its evidence transitively.
Direct evidence links are optional. If no costly decision is involved and no ADR
governs, state that coverage assessment and the authorized scope in the Description; the
approved plan suffices. Do not create a placeholder ADR or evidence record merely to
satisfy planning. Cross-feature and sequential reuse are valid. Concurrent plans may
share an ADR when their execution scopes, ownership, and dependencies are compatible.

## Orient and enter

Before a session's first source or vault edit, run `status` (CLI:
`vaultspec-core status`) to locate in-flight plans and their next open Step. Read-only
questions and diff reviews need no orientation; dispatched workers inherit the
orchestrator's. Resume a relevant plan through `vaultspec-execute`.

| Need                                  | Skill                   | Artifact  | Precondition                                           |
| ------------------------------------- | ----------------------- | --------- | ------------------------------------------------------ |
| Weigh options on evidence             | vaultspec-research      | Research  | A question needing persisted evidence                  |
| Ground work in real code              | vaultspec-code-research | Reference | A code question needing persisted evidence             |
| Record a costly decision              | vaultspec-adr           | ADR       | Sufficient Research, Reference, or Audit evidence      |
| Preserve execution scope and sequence | vaultspec-write         | Plan      | Decision coverage assessed                             |
| Implement planned work                | vaultspec-execute       | Ledger    | Approved plan and accepted decisions for the next Step |
| Review planned work                   | vaultspec-code-review   | Audit     | Completed Steps to review                              |

Enter only the phases the work needs. Research and Reference are alternative evidence
sources, not mandatory predecessors for every feature. An Audit can ground a follow-on
decision when its findings suffice. Missing evidence routes to the appropriate evidence
skill; obtaining it does not require a separate user turn unless input is missing. When
skills are unavailable, use the owning CLI verbs under the same contracts.

## Approval and decision state

An ADR starts `proposed` and becomes `accepted` once its content is authorized. For an
amendment, preserve the accepted body while presenting the proposed revision separately
for approval; apply it only once authorized. If it must survive handoff, retain the
proposal in a separate proposed ADR using `--topic`, link it to the existing record, and
retire that proposal after the approved amendment is applied. A declined proposal leaves
the accepted record intact. A reversal's successor must be accepted before
`vaultspec-core vault adr supersede OLD --by NEW` retires the predecessor.

On plan approval, write `Approved yyyy-mm-dd` as the first Description line and record
the authorization basis. If authorization already exists, persist it and proceed;
otherwise present the concrete record and ask. Draft plans may link proposed decisions,
but no Step executes on unaccepted authority. Completed plans retain historical links;
reopening work requires reassessing the decisions for the affected Step.

The approved plan authorizes its Steps and in-scope corrections. Use the plan verbs to
record routine path corrections or clarifications and continue. A material scope change,
new costly decision, or action requiring new external authority needs user input. Record
the answer in the affected Step or decision; it authorizes that change. A worker raises
uncovered choices to the orchestrator, who checks existing authority before asking.

## Execute and recover

On first entry read the plan whole. On resume, read `status`, the next open Step, and
the decision sections it depends on. Ground the affected code, implement, verify, log,
close the Step through the owning verb, and commit. A run may close many Steps.
Execution spans sessions; preserve the plan stem, feature tag, Step id, and unresolved
state at handoff. Other skills finish a bounded artifact or report the missing input.

Plans nest `Epic > Wave > Phase > Step`: L1 has Steps, L2 adds Phases, L3 adds Waves,
and L4 adds an Epic with an external tracking association. Structure and Step state
change only through the owning plan verbs. Each ledger row names its Step.

## Review

Formal review applies to planned work at each actual Phase close, at plan close, and
before handoff for merge or reporting completion. L1 has no Phase-close gate. One review
covers coincident gates on the same changes. A Step closes on its own verification;
review does not gate each Step or each document.

Review the integrated behavior against the plan and governing decisions, tracing
affected workflows across their interfaces. For framework work this includes rules,
skills, personas, templates, and executable checks together. Review files as evidence of
that behavior, not as independent approval units. Findings are appended to a rolling
Audit. Critical and high findings reopen affected Steps and must be resolved before
proceeding. Lower findings are recorded; in-scope fixes use approved Steps, while new
scope or decisions require authorization. Re-review changed behavior and its
interactions; do not repeat unchanged reviews. Completion requires all Steps closed and
the final review passing.

## Supporting skills and agents

Use `vaultspec-curate` for semantic reconciliation, `vaultspec-documentation` for
user-facing documents, `vaultspec-team` to supervise approved parallel assignments, and
`vaultspec-projectmanager` for user-requested external project coordination. Supporting
skills do not add decision or approval gates to already authorized work.

Personas live in `.vaultspec/agents/`. Their `tier:` (`LOW`, `STANDARD`, `HIGH`) selects
difficulty, not plan hierarchy. Their `mode:` is discipline, not a sandbox: read-only
personas return findings for the orchestrator to persist; read-write personas mutate
only their assigned scope. Dispatched personas use the CLI; MCP is not assumed. Use the
host's available messaging mechanism for progress and final findings.

Parallel execution requires explicit assignments in the plan's Parallelization section:
Steps at L1, Steps or Phases at L2, and suitable containers at higher tiers. Keep write
ownership disjoint and isolate working trees or serialize shared metadata and commits.
`vaultspec-team` supervises workers. Independent review can prepare while implementation
proceeds, but final review evaluates a stable, completed set of changes.
