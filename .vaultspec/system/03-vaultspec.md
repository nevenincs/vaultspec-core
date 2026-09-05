---
order: 3
---

# Vaultspec

`.vault/` holds a feature's records; `.vaultspec/` holds this policy. Rules: `vaultspec`
(record types and their verbs), `vaultspec-cli` (tools), `vaultspec-discovery`
(grounding). Vaultspec exists so intent and progress survive the end of a session.

## Vocabulary

- **turn** - one user message and the reply.
- **run** - one agent invocation, from dispatch to its final message.
- **session** - one context window. It ends at compaction, restart, or handoff.
- **feature** - one capability or change the user names; requests on the same
  capability, in this session or a later one, belong to the same feature and share its
  tag.
- **Step** - one unit of planned work: one commit and its rows in the plan's ledger. A
  run may close many Steps.
- **horizon** - how far the work outlives this session: *conversation*, *multi-session*,
  or *multi-week*, as the test under "Size the work first" decides.
- **blocker** - anything the plan and its ADRs do not settle: a Step whose action admits
  implementations of different scope, a failing precondition, a missing dependency.
- **presented** - the record's path and a summary in the reply, followed by a stop.
  **Approval** is the user's reply that accepts the presented record by name, given
  after it exists. An instruction that predates the record, or a request for the next
  phase, is not approval.

## Size the work first

`.vault/` records exist for work whose horizon exceeds the session, or whose result
another worker must build on. Size the feature, not the request.

Conversation horizon needs all four: finishes this session, no handoff, one package (one
top-level module directory), at most ten files. Otherwise the work is multi-session;
when it also crosses calendar weeks or runs several workers at once, multi-week. If
conversation-horizon work then outlives the session, write the ADR and plan the rest.

- **Conversation horizon:** work directly and say in one line that no plan is needed (an
  ADR may still be, per the decision rule below). No approval is required to skip the
  plan. The Execute and Review phases exist only under a plan; unplanned work is
  reviewed in the reply.
- **Multi-session:** plan it at the tier the plan template's criteria select (`L1`-`L3`)
  and execute Step by Step, logging each Step to the plan's ledger; review at Phase
  close and at plan close. Multi-session work always gets an ADR, however short.
- **Multi-week:** `L4` plan, which declares an external tracking artifact (milestone,
  board, roadmap entry).

**Decisions are sized apart from horizon and never rounded down.** Any decision costly
to reverse (boundary, schema, protocol, public interface, any dependency change) gets an
approved ADR before code builds on it, at any horizon, bug fix or not. A decision
reached in conversation, or silently while working, is recorded the same way first. The
ADR's grounding is a Research or Reference record; when the evidence is small, the
record is small. At conversation horizon the approved ADR's Implementation section is
the scope of the direct work.

**Sizing never skips grounding.** Before the first edit to source or vault in a session,
check for a governing decision per the `vaultspec-discovery` rule.

## Orient

Run the `status` tool (CLI: `vaultspec-core status`) before the first edit to source or
vault in a session; it names the in-flight plans and their next open Step. A question, a
docs-only edit, or a diff review needs no orientation, and a dispatched worker inherits
its orchestrator's. Resume in-flight plans through `vaultspec-execute`; otherwise enter
at the phase sizing selects.

## Pipeline

| Phase        | Skill                   | Artifact            | Requires                       |
| ------------ | ----------------------- | ------------------- | ------------------------------ |
| 1a Research  | vaultspec-research      | `.vault/research/`  | -                              |
| 1b Reference | vaultspec-code-research | `.vault/reference/` | -                              |
| 2 Decide     | vaultspec-adr           | `.vault/adr/`       | a Research or Reference record |
| 3 Plan       | vaultspec-write         | `.vault/plan/`      | approved ADR(s)                |
| 4 Execute    | vaultspec-execute       | `.vault/exec/`      | approved Plan                  |
| 5 Review     | vaultspec-code-review   | `.vault/audit/`     | completed Step(s)              |

The dependency chain is strict once a phase is entered: an ADR cites its grounding, a
plan lists every ADR it executes in `related:`, a ledger cites its plan, an audit cites
what it reviewed. Sizing decides which phases are entered; it never removes a
requirement from a phase that is. Research and Reference are alternative entry points; a
feature needs at least one. A plan executes one ADR or a cluster of ADRs; one ADR never
spans several concurrent plans.

**Approval gates.** An ADR is `proposed` until its approval reply, then `accepted`; an
amendment needs the same reply. A plan runs only after its approval reply; on approval
write `Approved yyyy-mm-dd` as the first line of its Description, and present again any
plan that lacks that line. A Step changed after approval, even a corrected path, is
presented again and waits for a reply; a row that records the user's blocker answer is
quoted and run. Under a plan, source changes happen only against an approved Step,
whoever makes them: the orchestrator, a persona, or a host agent.

**Review** produces an audit for planned work at each Phase close, at plan close, and
before the work is handed off for merge, by pull request or by reporting it done; when
these fall on the same commits, one review covers them. A Step closes on its own
verification; review does not gate each Step. Findings below `high` are recorded, and
fixed only under a Step the user approves. Parallel workers are dispatched only over
containers the plan's Parallelization section names as concurrent; `vaultspec-team`
supervises them.

Without skills (Codex, Gemini), produce each phase's artifact through the
`vaultspec-core` CLI under the same requirements; the phase table is the procedure.

## Roles by lifetime

Research, ADR, plan, and review each finish in one run; one that lacks its precondition
stops and names the missing phase. Execution spans sessions. Its checkpoint is a closed
Step with its ledger rows and commit. On a plan's first entry read it whole; on resume,
`status`, then the next open Step's row and the ADR sections that Step depends on, not
the whole document cluster. Under an approved plan the plan is the approval: do not ask
between Steps. Stop at a blocker and ask the user (a dispatched persona raises it to its
orchestrator, who asks); the answer is written into the Step row (`plan_edit`) and is
that row's approval, the one exception to approval by name. No one sharpens a Step on
their own judgment.

## Plans

Plans nest `Epic > Wave > Phase > Step` and declare a tier: `L1` Steps only, `L2` adds
Phases, `L3` adds Waves, `L4` adds an Epic with an external tracking association. The
leaf is always a Step, and every ledger row names its Step. Structure and Step state
change only through the owning plan verbs, never by hand: the `plan_progress` and
`plan_edit` tools for Steps, the `vaultspec-core vault plan` CLI for everything above a
Step. Tier criteria and row conventions live in the hint blocks of
`.vaultspec/templates/plan.md`.

## Supporting skills

| Need               | Skill                    | Purpose                                                        |
| ------------------ | ------------------------ | -------------------------------------------------------------- |
| Curate             | vaultspec-curate         | Reconcile ADRs against each other and the code                 |
| Documentation      | vaultspec-documentation  | Write or revise user-facing documentation                      |
| Team coordination  | vaultspec-team           | Supervise parallel workers over a plan's concurrent containers |
| Project management | vaultspec-projectmanager | Issues, milestones, worktrees, releases; user-invoked only     |

Intent to skill, once sizing says the vault is warranted:

| User intent                         | Skill                   |
| ----------------------------------- | ----------------------- |
| "Research X" / "Investigate"        | vaultspec-research      |
| "How does [codebase] implement X?"  | vaultspec-code-research |
| "Decide on X" / "Create an ADR"     | vaultspec-adr           |
| "Plan the implementation"           | vaultspec-write         |
| "Execute the plan" / "Build it"     | vaultspec-execute       |
| "Review the feature" / "Verify"     | vaultspec-code-review   |
| "Reconcile the ADRs" / "Curate"     | vaultspec-curate        |
| "Write documentation for {subject}" | vaultspec-documentation |

A question is answered in the conversation; if the answer is a decision code will build
on, it becomes an ADR first. A review of a diff with no plan behind it is a reply.

## Agents

Personas live in `.vaultspec/agents/`. Dispatch them as parallel sub-agents for focused
work, or as a team over an `L3`/`L4` plan through the host environment. Each persona
declares `mode:` - `read-write` personas mutate project state; `read-only` personas
return findings as their final message and the orchestrator persists them (scaffold with
`vaultspec-core vault add`, then edit the body) - and `tier:` (`LOW`, `STANDARD`,
`HIGH`), the difficulty of work it takes. The declaration is persona discipline, not a
sandbox. Dispatched personas use the CLI; MCP tools are not assumed inside a sub-agent.
Background personas relay findings through `SendMessage`; every shipped persona carries
it.
