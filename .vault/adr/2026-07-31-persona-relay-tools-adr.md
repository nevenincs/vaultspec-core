---
tags:
  - '#adr'
  - '#persona-relay-tools'
date: '2026-07-31'
modified: '2026-07-31'
body_schema: 'body-v1'
body_hash: 'sha256:95ae9eafde9df20ca3fbac19e834fdcc005574b883f53483c6311cf748c35363'
related:
  - "[[2026-07-31-persona-relay-tools-research]]"
  - "[[2026-07-09-firmware-mcp-primacy-adr]]"
---

# `persona-relay-tools` adr: `host relay and task tools in persona allowlists` | (**status:** `accepted`)

## Problem Statement

Shipped personas dispatched as background teammates go silent: they perform their work
and never deliver it, because the persona contract's return path is the subagent's
final message and a backgrounded persona has no final message the orchestrator reads.
`2026-07-31-persona-relay-tools-research` records the structural gap, four observed
incidents in one session, and an uncommitted candidate implementation whose
per-persona tool split has no decision behind it. The standing allowlist freeze in
`2026-07-09-firmware-mcp-primacy-adr` raises the prior question of whether that record
must be superseded before any allowlist changes. A decision is needed on whether the
re-scope lands, in what exact per-persona shape, and how the record relationship is
expressed.

## Considerations

- The frozen stance and its supersession trigger concern MCP tools and subagent MCP
  inheritance; `SendMessage` and the task tools are host-orchestration tools, outside
  that subject (`2026-07-31-persona-relay-tools-research`, host-tools finding).
- The relay addresses host orchestration state, not project state, so `read-only`
  mode discipline is preserved by carrying it (research, mutation-intent finding).
- Prose-only guidance without an allowlist change reproduces the dead-first-attempt
  failure the prior record's Q1 rejected; the tool must be declared where the
  instruction is given.
- The Gemini renderer's unmapped-tool warning exists to catch typos; host tools are
  unmapped by design, so routing them through the warning path would make the warning
  fire on every sync of every shipped persona (research, render-layer finding).
- Silence is indistinguishable from finding nothing, which corrupts orchestration
  decisions downstream - the cost is misinformation, not just lost work.

## Considered options

- **Reject: keep allowlists frozen, dispatch personas foreground-only.** Honest to the
  current contract but forfeits parallel teamwork and leaves the observed failure
  standing whenever a persona is backgrounded anyway. Rejected.
- **Supersede the prior record and re-scope allowlists wholesale.** Wrong instrument:
  the prior record's Q3 stance is about MCP tools and its supersession trigger
  (empirical MCP-inheritance confirmation) has not fired. Superseding it would retire
  wording that remains correct and governing. Rejected.
- **Fresh narrow record adding host relay and task tools, MCP freeze untouched
  (chosen).** The host-tool re-scope lands on its own subject; the prior record
  remains accepted and its MCP stance intact.
- **Uniform grant: full task-tool set on all ten personas.** Simpler to state, but
  hands work-creating and work-mutating authority to personas whose remit is
  producing findings; scope discipline is persona discipline, and allowlists are the
  one enforcement surface available. Rejected.

## Constraints

- Persona `tools:` allowlists remain the authoritative declaration surface; no
  conditional logic on host capabilities exists in firmware, so the wording must be
  true whether a persona runs foreground or backgrounded.
- The Gemini render must keep its typo-catching warning meaningful; any by-design
  Claude-only tool must bypass the warning path explicitly, not by ad-hoc exclusion.
- This record does not touch the MCP question: no MCP tool enters any allowlist, and
  the supersession trigger registered by `2026-07-09-firmware-mcp-primacy-adr` stands
  unchanged for that subject.

## Implementation

The re-scope lands in the shape already present as the uncommitted candidate, now
ratified with the following per-persona rule:

- **`SendMessage` on all ten personas.** Returning findings is the persona contract
  in both dispatch shapes; the relay is the only channel a backgrounded persona has.
  It is a reporting tool, so `read-only` personas carry it without violating their
  mode declaration.
- **`TaskList` and `TaskUpdate` on the three executors only** (standard, low, high).
  Executors are the personas dispatched against tracked work items; they must see the
  shared work state and update the status of the item assigned to them. They do not
  get `TaskCreate`: creating work is scoping authority, and an executor that can mint
  its own work items can expand its own scope past the step it was dispatched for.
- **`TaskCreate` (plus `TaskList`, `TaskUpdate`) on the project coordinator only.**
  Its remit is triage and coordination; creating and reshaping work items is the job.
- **No task tools on the writer, curator, researchers, auditors, or reviewer.** Their
  deliverables are documents and findings, relayed via `SendMessage`; plan structure
  lives in the vault under the plan verbs, and host task materialization belongs to
  the orchestrator.

The render layer ships the `_CLAUDE_ONLY_HOST_TOOLS` set in
`src/vaultspec_core/core/agents.py`: the Gemini renderer drops these four tools
silently because their absence from Gemini is by design, and the warning path stays
reserved for genuine typos. The system-prompt paragraph in
`src/vaultspec_core/builtins/system/03-vaultspec.md` stating the relay contract is
ratified as-is; it is the prose half of the same decision and stands or falls with
the allowlist change. Rollout is the ordinary builtins path: edit sources, `sync`,
dogfood here, ship in the next release.

## Rationale

The knockout criterion is that an instruction to report must be backed by a declared
tool, and the observed incidents show the cost of the gap is silent misinformation,
not merely inefficiency. A fresh narrow record wins over supersession because the
prior record's frozen subject (MCP tools, gated on inheritance evidence) is simply
not the subject here; retiring an accepted record to change something outside its
subject would blur what supersession means in this corpus. The per-persona split
follows one principle: every persona reports, so every persona gets the relay; task
tools follow authority over the shared work state, which executors hold for their own
item's status and only the coordinator holds for creation. The silent render drop is
the only handling that preserves the unmapped-tool warning's signal value.

## Consequences

- Backgrounded personas can deliver findings; silence stops being a structural
  certainty and becomes diagnosable as an actual empty result or a genuine failure.
- Every managed project's provider agent files change on next sync - the same
  accepted diff-noise class as the prior record's reword.
- The allowlists now encode a three-tier authority model (report / update own work /
  create work); future persona additions must pick a tier deliberately rather than
  copying a neighbor's tool list.
- Claude-only host tools are now a recognized vocabulary class in the renderer; a
  future host tool added to personas must be added to `_CLAUDE_ONLY_HOST_TOOLS` or it
  will warn on every sync - a small, loud, self-correcting failure.
- The MCP allowlist question remains open and governed by
  `2026-07-09-firmware-mcp-primacy-adr`; nothing here preempts it.
