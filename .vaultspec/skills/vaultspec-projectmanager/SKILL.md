---
name: vaultspec-projectmanager
description: "Coordinate multiple active workstreams on explicit user request: epics, project boards, cross-worktree issue triage, roadmaps, or a developer's multi-feature workday. Not for a single PR, branch comparison, worktree operation, or ordinary plan execution."
---

# Project coordination

Aggregate context into an actionable sequence for a developer managing several in-flight
features or an epic and its tracker. Activate for a request to coordinate that work.
GitHub usage, multiple branches, and worktrees alone do not justify loading this skill.
Handle bounded repository questions and single-PR work directly.

Coordination can be entirely local. Use tracker access when remote state matters;
missing access leaves those facts unknown without blocking a local workday plan.

## Method

1. **Set the outcome.** Establish the horizon, workstreams, developer availability,
   priorities, and existing authority. Reuse supplied context; ask only for a missing
   constraint that would materially change the sequence.
1. **Collect relevant state.** Read local worktrees, branch heads, working changes, and
   recent activity. Add issue, PR, CI, board, milestone and vault-plan fields needed for
   the question. Follow pagination when claiming complete coverage; otherwise state the
   window. Keep stable identifiers, source locations, and observation times. Distinguish
   facts from inferred dependencies and unknown remote state.
1. **Choose a sequence.** Connect features, issues, PRs, plans, and worktrees where
   evidence supports the relationship. Identify blockers, competing ownership, stale
   assignments, and local/remote discrepancies. Order ready work by the user's
   objective, known dependencies, deadlines, and available time. Recommend the next few
   actions with reasons and completion evidence. Effort estimates are not facts from
   commit counts.
1. **Coordinate delivery.** Work directly or delegate a bounded assignment to
   `vaultspec-project-coordinator`. Supply outcome, owner, target worktree or tracker
   item, dependencies, authority, and return condition. Implementation follows existing
   decision, plan, and team contracts; priority does not authorize execution. Supply a
   scoped brief to `vaultspec-write` when implementation needs a durable plan. At L4,
   coordinate the external association named in Epic intent and report discrepancies
   between tracker state and implementation evidence.
1. **Act and update.** Perform requested local preparation and tracker changes within
   their authorization. Confirm affected results, refresh changed facts, and recheck
   mutable state before acting. Finish this request with an updated sequence or handoff;
   do not enter an indefinite monitoring loop.

## Ownership and continuity

The coordinator owns priorities, assignments, tracker context, and handoffs. Substantive
decisions, implementation plans, and code stay with their respective roles. Reference
their existing records rather than copying a plan into a competing board checklist. Keep
a compact checkpoint of priorities, assignments, open questions, and next actions in an
authorized coordination record or the handoff response.

Honor prior scoped authorization. Code implementation permission alone does not grant
remote tracker mutations. Prepare a concrete proposal before asking for missing
necessary authority. Inspect affected state before retrying an uncertain mutation.

Discover worktree and base-branch conventions; do not assume branch names, Python, `uv`,
or installation commands. Never force-push; branch or worktree deletion requires an
explicit instruction. Report merge and release readiness without triggering them as a
side effect of coordination.

## Optional hosted evidence

TypeSafe requires the configured `VAULTSPEC_CORE_TYPESAFE_API_KEY` and a tool supporting
the input. Core's `search` and `crossref` evaluate vault records, not arbitrary issue/PR
payloads. Use them for relevant governing context, reuse unchanged results, and follow
their fallback on failure. Coordination works without hosted judgments; do not invent a
project-ranking tool or request credentials as a prerequisite.

## Return

Lead with the sequence and rationale. Include blockers, ownership conflicts, actions,
unknowns, and the next checkpoint. Use a compact table when useful. Report changes since
the last checkpoint instead of repeating an unchanged inventory.
