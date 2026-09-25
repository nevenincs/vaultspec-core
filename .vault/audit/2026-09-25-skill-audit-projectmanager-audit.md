---
tags:
  - '#audit'
  - '#skill-audit'
date: '2026-09-25'
modified: '2026-09-25'
body_schema: 'body-v2'
body_hash: 'sha256:242780497662ad63a45bba1fe1cd228ee40bbe2eed3c7e69ab6877ee1e232bab'
related:
  - "[[2026-09-08-framework-reword-adr]]"
  - "[[2026-05-05-plan-hardening-adr]]"
---

# `skill-audit` audit: `Project coordination routing and context audit`

## Scope

Review of `vaultspec-projectmanager`, `vaultspec-project-coordinator`, system routing,
the L4 plan association guidance, provider rendering, and reusable TypeSafe components.
The user specified complex, explicitly requested coordination: epics, boards,
cross-worktree triage and remediation, roadmaps, and a developer's multi-feature day.
Routine local repository and single-PR work is outside that intended trigger. The user
framed TypeSafe project triage as hypothetical optimization. No vaultspec skill was
invoked, remote project state mutated, or new hosted feature implemented. The existing
proportional-routing decision covers these instruction corrections; no plan is needed.

## Findings

### discovery-scope | high | Broad descriptions competed with the user-only body rule

The skill description advertised generic GitHub Projects, issue triage, worktrees and
releases; the persona advertised any project-management task. The body said user-only
but also required loading the persona for all project management. These discovery cues
could select the role before its qualification was read. Resolution: narrow both
metadata descriptions and the always-on route to explicitly requested coordination of
multiple active workstreams. Exclude ordinary branch, worktree and single-PR operations.
This is a routing-language correction, not a programmatic guarantee of agent selection.

### local-coordination | medium | GitHub and Python prerequisites excluded valid projects

The skill required authenticated GitHub and a remote, while the persona hardcoded a
branch base, worktree naming, `uv sync --dev`, and installation. Local multi-feature
coordination does not require these. Resolution: inspect actual repository conventions;
remote access is needed only for remote facts or actions. Keep unavailable state unknown
rather than treating a failed read as an empty backlog. No application setup runs merely
because the coordinator is loaded.

### role-and-output | medium | Indefinite loops and rigid tables displaced useful planning

The persona called the user its orchestrator in the main session but later instructed it
to address only an orchestrator, never the user. It mandated a full initial project
inventory, a query loop until dismissal, and table-only or command-only responses.
Resolution: one bounded request, a sequence grounded in the developer's objective,
explicit assignments, and correct main-session versus delegated return behavior.
Delegation is optional; repeated discovery by the main session and persona is avoided.

### context-continuity | medium | Session-only summaries could not support ongoing coordination

The old skill prohibited vault access for writing and prescribed session-only context,
without a handoff or freshness discipline. Resolution: identify facts by source and
observation time, refresh affected state, distinguish inference from observation, and
preserve priorities, owners, unknowns and next actions in an authorized existing
coordination record or handoff. Keep implementation sequencing in its plan instead of a
second board checklist. The writer authors durable implementation plans; the coordinator
supplies scope and dependencies and manages cross-workstream assignments.

### epic-association | low | External-tracker overhead lacked a clear coordination owner

The L4 template requires an external association and implementation sequencing, while
the project-manager skill treated its scope as entirely outside the pipeline. Resolution:
the coordinator handles user-requested coordination of the program and its tracker;
the plan remains the source of implementation order and progress. Declaring an association
is not itself a request for project coordination. Existing decision, plan and execution
authority remain in force; priority ranking does not grant implementation authority.

### hosted-capability | low | Generic project triage is not an exposed TypeSafe capability

Core exposes vault search and ADR cross-reference workflows, not arbitrary issue/PR
ranking. `src/vaultspec_core/search/_transport.py` already supports typed Choice, Noul,
and Score responses, budgets and usage; `src/vaultspec_core/core/enums.py` owns
`TypeSafeModel.JEV`. These are reusable components, not a project-state product.
Resolution: operative guidance uses existing tools only for supported governing-context
queries, conditional on the configured key. It neither invents a triage command nor
requires credentials to coordinate locally. A dedicated optimization remains a candidate
for a measured spike, outlined below.

## Recommendations

Retain the skill as the context-aggregation and sequencing role for explicitly requested
complex coordination. No new always-on inventory, automatic PM dispatcher, or pipeline
approval gate is warranted.

A prospective backend should first collect a bounded, timestamped snapshot with stable
issue/PR identifiers, worktree paths and branch heads, actual status, ownership, known
dependencies and relevant recent activity. Code handles joins, deduplication, readiness,
known blockers, and dependency ordering. It should return useful signals without a key.

If the API key is configured, shortlist items needing semantic judgment, such as alignment
with today's objective, a possible duplicate, or an ambiguous blocker. Ask independent
questions over a small coherent state together; preserve source identifiers and raw
judgments. Reuse judgments when the relevant input and question meaning are unchanged.
The agent explains tradeoffs and proposes assignments; code checks hard dependencies
and ownership before action. A model score is neither factual proof nor authorization.
Use the canonical model selector and existing credential/transport boundary.

Start with a read-only spike against representative recorded snapshots. Compare the
same tasks using deterministic selection alone and selection plus typed ranking. Measure
bytes and agent tokens needed to reach a usable context view, tool calls, billed API
input tokens, latency, missing-dependency rate, and the developer's acceptance of the
proposed top actions. Include no-key, unavailable-service, stale-state, duplicate-identity
and incomplete-input cases. Measure context acquisition as well as model latency; a
fast API cannot compensate for fetching an unnecessary full project history. No savings,
accuracy gain, threshold or latency budget is established by this audit.

The proposed shortlist and independent dimensions follow TypeSafe's current patterns;
this is a project-specific inference, not a benchmark transferred from those examples.
Sources read on 2026-09-25: `https://docs.typesafe.ai/concepts/state`,
`https://docs.typesafe.ai/patterns/composite-scoring`,
`https://docs.typesafe.ai/cookbooks/rerank_typesafe`, and
`https://docs.typesafe.ai/primitives/score`.

## Routing review

These are manual contract checks, not measured agent evaluations:

- Compare two branches or inspect a PR's failed check: direct repository work.
- Provision one requested worktree: direct operation under repository conventions.
- Read or edit an Epic association: ordinary plan operation without a portfolio scan.
- Coordinate a multi-feature roadmap, dependencies and its board: project manager.
- Plan today's work across several active local features without GitHub: project manager.
- Delegate implementation: existing scope, decision, plan and ownership contracts apply.
- Missing API key or hosted service: local coordination remains available.

## Validation

The combined skill and persona contain 815 whitespace-delimited words versus 854 before
editing. This modest wording reduction accompanies a broader coordination contract; it
is not a runtime token measurement. Existing agent-rendering and builtin-seeding tests
passed 111 cases. All 18 lightweight repository guards, Markdown checks and generated
reference checks passed. No new tests assert prose substrings, and no agent routing
accuracy or hosted project-triage performance claim is made.
