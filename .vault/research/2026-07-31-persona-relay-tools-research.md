---
tags:
  - '#research'
  - '#persona-relay-tools'
date: '2026-07-31'
modified: '2026-07-31'
body_schema: 'body-v1'
body_hash: 'sha256:ad5495ddbaa7ca34041928df9c2541263554bf5dcbf8cb7dbde073117dcc651d'
related:
  - "[[2026-07-09-firmware-mcp-primacy-adr]]"
---

# `persona-relay-tools` research: `backgrounded persona silence and host relay tools`

The question is whether the shipped agent personas need host-orchestration tools in
their `tools:` allowlists to honor the persona contract when dispatched as background
teammates, and if so which tools go to which personas. The evidence picture: the
contract's return path structurally does not exist for a backgrounded persona, the
failure was observed four times in one working session, and an uncommitted candidate
implementation already sits in the tree whose per-persona tool split has no recorded
decision behind it. The evidence favors adding a relay channel; the split and the
render-layer handling are what a decision must settle.

## Findings

### The persona contract has no return path for a backgrounded persona

The assembled system prompt states that `read-only` personas "mutate nothing and
return their findings as their final message for the dispatching orchestrator to
persist" (`src/vaultspec_core/builtins/system/03-vaultspec.md`). That channel is a
property of foreground dispatch: the orchestrator reads the subagent's final message.
A persona dispatched as a background teammate has no final message the orchestrator
reads; its only way to deliver anything is an explicit message-send tool. Before the
candidate change, no shipped persona's `tools:` allowlist carried any host
communication tool (`src/vaultspec_core/builtins/agents/`, ten files, allowlists of
the shape `[Glob, Grep, Read, Write, Edit, Bash]` and variants).

### The failure is observed, not hypothetical

On 2026-07-31, in a single orchestrated session in this repository, four separately
dispatched shipped personas ran as background teammates, performed their work, and
never delivered it: the orchestrator received only idle notifications,
indistinguishable from the persona having found nothing. The silence is structural
per the previous finding, so incidence tracks exactly with backgrounded dispatch,
not with any property of the individual personas involved.

### The tools in question are host tools, not MCP tools

`SendMessage`, `TaskCreate`, `TaskList`, and `TaskUpdate` are host-orchestration
tools: they address the dispatching host's team channel and shared task list, not
the project and not any MCP server. The standing decision on persona allowlists
(`2026-07-09-firmware-mcp-primacy-adr`, Q3 and the follow-on registered in its
Implementation section) froze the allowlists specifically against adding MCP tools,
with supersession gated on empirical confirmation of subagent MCP inheritance. Host
tools are a different subject: no MCP inheritance question bears on them, and none of
that record's rejected failure modes (a persona stranded with no vaultspec access)
applies, because the relay tools carry reporting, not vaultspec access.

### A mutation-intent question exists but dissolves on inspection

The `mode:` field declares mutation intent toward project state. The host team
channel and task list are orchestration state owned by the dispatching host, not
project state; sending a message or updating a task's status mutates no file, no
vault document, and no repository. A `read-only` persona carrying `SendMessage`
therefore still mutates nothing within the meaning of the mode declaration - and
reporting is precisely what `read-only` personas exist to do.

### The uncommitted candidate implementation and its unruled split

The working tree carries an uncommitted implementation: all ten personas under
`src/vaultspec_core/builtins/agents/` gained `SendMessage`; the three executors
additionally gained `TaskList` and `TaskUpdate`; `vaultspec-project-coordinator`
additionally gained `TaskCreate`; `src/vaultspec_core/core/agents.py` gained a
`_CLAUDE_ONLY_HOST_TOOLS` frozenset so the Gemini renderer drops these tools without
a warning; and `src/vaultspec_core/builtins/system/03-vaultspec.md` gained a
paragraph making the relay part of the persona contract in both dispatch shapes.
The implementing agent states the per-persona split was its own judgment call with
no decision behind it.

### The render layer distinguishes typo from by-design absence

The Gemini renderer maps Claude tool vocabulary through `_CLAUDE_TO_GEMINI_TOOLS`
(`src/vaultspec_core/core/agents.py`) and appends a warning for every unmapped tool
so a typo in one authored source cannot silently vanish. Gemini CLI exposes no
counterpart for the host team channel or the shared task list, so host tools in an
allowlist are unmapped by design, not by typo. Left on the warning path, every sync
of every shipped persona would emit warnings for correct sources - a standing
false-positive that trains operators to ignore the warning that exists to catch real
typos. The candidate implementation's silent-drop set is the only shape that keeps
the warning meaningful.

### Alternatives visible in the option space

Foreground-only dispatch (never background a persona) preserves the contract without
any tool change but forfeits parallel teamwork, which the team skill exists to
provide. Prose-only guidance (tell personas to report, add no tool) instructs
personas to use a tool their allowlists exclude - the exact dead-first-attempt
failure `2026-07-09-firmware-mcp-primacy-adr` rejected in its Q1 reasoning.
Granting the full task-tool set to all ten personas maximizes uniformity but hands
work-creating authority to personas whose remit is producing findings, with no
observed need. Not investigated: whether specific host versions propagate host tools
into subagents differently; the observed incidents are all from the current host in
this repository.

## Sources

- `src/vaultspec_core/builtins/system/03-vaultspec.md` - persona contract wording
  (final-message return path; uncommitted relay paragraph).
- `src/vaultspec_core/builtins/agents/` - the ten persona sources and their
  `tools:` allowlists (uncommitted diff adds the host tools per the split above).
- `src/vaultspec_core/core/agents.py` - `_CLAUDE_TO_GEMINI_TOOLS` warning path and
  the uncommitted `_CLAUDE_ONLY_HOST_TOOLS` silent-drop set.
- Session observation, 2026-07-31: four backgrounded shipped personas completed
  work and delivered nothing; orchestrator saw only idle notifications
  (unverifiable after the fact; recorded as the empirical trigger).
