---
tags:
  - '#audit'
  - '#skill-audit'
date: '2026-09-25'
modified: '2026-09-25'
body_schema: 'body-v2'
body_hash: 'sha256:3a7e9542b1825e6110c9049f9a3698c13d064e64dbfa09435381f34e95c8469f'
related:
  - "[[2026-09-08-framework-reword-adr]]"
  - "[[2026-05-05-plan-hardening-adr]]"
  - '[[2026-09-25-project-context-adr]]'
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

## Backend implementation and smoke, 2026-09-25

The user authorized the proposed backend with "It's good. Make the changes". The
public interface and data-flow decision is `2026-09-25-project-context-adr`.
Implementation is direct, within one cohesive session, without invoking vaultspec
skills. The earlier hypothetical capability finding is resolved by the implemented
command; the evidence below does not claim a measured improvement in agent behavior.

### context-surface | resolved | One bounded read supplies local and optional remote observations

`src/vaultspec_core/project/collect.py` reads up to 30 recent branches, inspects eight
worktrees, and optionally reads 20 open issues and 20 open PRs from an explicit GitHub
repository. A shared ten-second deadline bounds subprocess collection. Source failures,
truncation, omitted dependencies and untracked files remain explicit. Stable worktree
identities preserve separate checkouts sharing a branch and flag that overlap. Local
unmerged files, failed CI, conflicting PRs and requested changes remain deterministic
attention signals. Branch names never join fork PRs to local worktrees.

`src/vaultspec_core/project/context.py` owns the reply and optional credential use;
`src/vaultspec_core/cli/project_cmd.py` exposes it through the CLI and existing gateway.
No hot MCP tool, always-on inventory, repository mutation, or tracker mutation is added.
Skill and persona guidance reuse supplied observations and fetch missing context only.
The five-item default reply proposes attention, not an executable dependency schedule.

### hosted-reuse | resolved | Objective judgments are bounded and optional

`src/vaultspec_core/project/ranking.py` shortlists twelve items, then optionally asks one
batch of independent objective-fit Scores within five seconds. The canonical selector,
credential resolver and existing transport remain the only hosted path. No key or an
explicit disable makes no call. Provider failure falls back to a consistent lexical
ranking rather than mixing cached model scores with unscored candidates. Model scores
cannot override observed blocker or shared-branch attention bands.

A supplied prior result reuses judgments only for the same objective, item facts,
question semantics and canonical selector, for up to one hour. Every invocation gathers
fresh observations. There is no persistent cache and old facts never replace fresh
ones. Typed probabilities, score ranges, bounded input files and invalidation paths are
covered by tests. The serving model identity comes from the API response.

### measured-smoke | information | Wiring and reuse work; productivity remains unmeasured

One live sequence used this repository's two local worktrees, four open issues and one
open PR, scoped to `nevenincs/vaultspec-core`. Each invocation made seven source commands
and read 4,699 stdout bytes. The objective was to prepare a release across active
features. Five items were returned from seven observed items.

| Mode                          | Backend elapsed | Reply bytes | Hosted calls | Input tokens | Reused judgments |
| ----------------------------- | --------------- | ----------- | ------------ | ------------ | ---------------- |
| Deterministic                 | 1,879.56 ms     | 4,192       | 0            | 0            | 0                |
| Hosted                        | 2,285.49 ms     | 5,234       | 1            | 3,020        | 0                |
| Fresh observations plus reuse | 1,625.44 ms     | 5,223       | 0            | 0            | 7                |

The hosted evaluation took 610.36 ms and reported 282 output tokens. A prior local-only
smoke took 186.87 ms and five Git commands. These are single observations, not latency
percentiles. Reply bytes are UTF-8 JSON bytes, not measured agent tokens; source bytes
exclude subprocess stderr and HTTP framing. The hosted reply is larger than the raw
source stdout in this small example because it carries provenance, unknowns and reusable
judgments. No token-saving percentage, ranking accuracy, dependency recall, agent tool-use
reduction or developer productivity improvement is established. The concrete reuse gain
is seven retained judgments with no second API call after fresh collection.

## Backend validation

Twenty-three focused project tests pass, using real Git repositories/worktrees and the
real HTTP transport against a local scripted provider. They cover duplicate identities,
shared branches, local merge conflicts, source windows, no-key and explicit-disable
behavior, invalid credentials, hosted failures, changed evidence, stale/invalid cached
scores, and preservation of blocker priority. Thirty-seven gateway, catalog and MCP
context-budget tests pass, including invoking the command through MCP without adding a
hot tool. All 18 lightweight repository guards pass after correcting environment-helper
use and fully qualifying runnable CLI examples. Source lint, full type checks, Markdown
checks and generated-reference checks pass. Live smoke confirms installed GitHub CLI
field compatibility and the TypeSafe API path. No vaultspec skill or delegated persona
was invoked, and no remote repository or tracker state was changed.
