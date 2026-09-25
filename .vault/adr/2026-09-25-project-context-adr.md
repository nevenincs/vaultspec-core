---
tags:
  - '#adr'
  - '#project-context'
date: '2026-09-25'
modified: '2026-09-25'
body_schema: 'body-v2'
body_hash: 'sha256:f783ac2855193da33080c2eb13c50298264163e1b1521482f3f0cec9697045d1'
related:
  - "[[2026-09-25-skill-audit-projectmanager-audit]]"
  - "[[2026-09-23-typesafe-search-adr]]"
---

# `project-context` adr: `bounded project observations and optional objective ranking` | (**status:** `accepted`)

## Problem Statement

Multi-workstream coordination requires repeated Git and tracker reads before an agent
can propose a useful sequence. The existing project-manager audit identifies a bounded
context collector as a candidate for reducing that acquisition cost. Vault search and
ADR reconciliation do not accept project-state payloads.

## Considerations

Accepted 2026-09-25 under the user's explicit instruction, "It's good. Make the changes",
authorizing the bounded backend proposed after the project-manager audit. Evidence:
`2026-09-25-skill-audit-projectmanager-audit`. Existing hosted transport and credential
constraints remain governed by `2026-09-23-typesafe-search-adr`.

## Considered options

- Require hosted ranking for project coordination: rejected; local facts are useful
  without credentials and hosted availability cannot become a workflow gate.
- Add another first-class MCP tool or always-on project inventory: rejected; coordination
  is an explicitly requested supporting capability, with no reason to expand hot context.
- Expose a bounded CLI collector through the existing gateway: selected. Deterministic
  signals remain authoritative and optional semantic judgments rank objective fit.

## Constraints

The command reads local Git state and GitHub issues/PRs only for an explicit owner/repo.
It writes no repository, tracker, cache or coordination state. Each source reports its
coverage and failures; uncollected dependencies and boards remain unknown. A snapshot is
an observation window, not an atomic project inventory. No branch-name-only joins connect
local work to remote PRs. Proposed attention order does not grant execution authority,
claim merge readiness, or replace implementation plans.

Hosted evaluation is conditional on the existing core TypeSafe credential resolver and
can be disabled per invocation. Use the canonical model enum and existing transport;
no new endpoint, dependency or credential source. Limit collection time, candidates,
request count and hosted time. Service failure preserves deterministic output. Known
blocker signals cannot be overridden by model scores.

A user-supplied previous JSON result can reuse unchanged typed judgments for one hour.
Fingerprints include objective, relevant observed item state, question meaning and the
canonical model selector. Fresh collection always precedes reuse. Do not introduce a
persistent cache or load previous observations as current facts. Usage distinguishes
collection commands, returned coverage, hosted calls/tokens and reuse.

## Implementation

Direct work in one cohesive session: no durable execution sequence is needed. Implement
`project context`, local and explicitly scoped remote collection, deterministic attention
bands, one bounded batch of independent objective-fit Scores, and optional prior-result
reuse. Keep CLI and gateway behavior in the backend. Update the skill, persona, CLI
reference and user guide to the executable contract, without making collection mandatory
when supplied evidence suffices. Cover real Git worktrees and CLI/gateway behavior,
transport-backed ranking, no-key/failure/reuse paths, and bounded output. Record smoke
measurements in the existing audit without making agent productivity claims.

## Rationale

The collector removes repeated low-level acquisition work while preserving the agent's
responsibility for dependencies, assignments and authorization. Narrow typed judgments
can improve ordering without generating another long analysis. Reusing supplied results
reduces repeat calls without adding another maintained source of project truth.

## Consequences

The CLI gains a public read-only surface and the gateway gains one discoverable verb.
A configured key permits sending bounded project summaries to TypeSafe; no file contents
or issue bodies are collected. Lexical fallback and a small shortlist can miss relevant
work, and partial source coverage must remain visible. An attention order needs further
context before becoming an executable sequence. Live smoke measurements establish wiring
and cost only; ranking quality and developer efficiency require representative evaluation.
