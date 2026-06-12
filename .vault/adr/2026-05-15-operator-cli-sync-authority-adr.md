---
tags:
  - '#adr'
  - '#operator-cli-sync-authority'
date: '2026-05-15'
modified: '2026-05-15'
related:
  - '[[2026-05-15-operator-cli-sync-authority-research]]'
  - '[[2026-05-15-operator-cli-repair-pipeline-reference]]'
---

# `operator-cli-sync-authority` adr: `make top-level sync the only authoritative synchronization surface` | (**status:** `proposed`)

## Problem Statement

VaultSpec exposes both `vaultspec-core sync` and
`vaultspec-core spec <resource> sync`. The broad command is the complete
synchronization path from `.vaultspec/` to provider-facing generated outputs,
but the narrow commands look close enough that operators can reasonably treat
them as equivalent propagation commands.

The observed result is stale provider stubs after a plausible but wrong command
sequence: add a rule, run `spec rules sync`, and expect `AGENTS.md`,
`CLAUDE.md`, and `GEMINI.md` to update. Top-level `sync` handles the complete
refresh; the UX around narrow sync commands makes the wrong command feel
correct.

## Considerations

Option 1: keep every sync command as-is and rely on documentation.

This leaves the footgun in place. Operators discover the distinction only after
generated outputs drift.

Option 2: remove narrow `spec <resource> sync` commands immediately.

This creates a clean command surface but risks breaking scripts that already
use the narrow commands for resource-scoped maintenance.

Option 3: make top-level `vaultspec-core sync` the only authoritative complete
sync surface, then reframe narrow commands as specialized maintenance surfaces
with explicit wording, warnings, and shared implementation boundaries.

This preserves compatibility while fixing the operator contract.

## Constraints

- Existing users may have scripted narrow sync commands.
- Top-level sync already behaves correctly and should remain the normal answer.
- `install --force` is a scaffolding repair path, not the normal propagation
  command after source edits.
- MCP sync updates `.mcp.json` through provider-agnostic merge behavior, so it
  needs distinct wording from provider directory sync.
- Human output should guide interactive users without changing JSON contracts
  unexpectedly.
- Regression tests must exercise real command behavior and generated files.

## Implementation

Adopt Option 3.

Declare `vaultspec-core sync` the authoritative command for complete
synchronization from `.vaultspec/` into enrolled provider outputs.

Update top-level sync help and CLI documentation to include rules, skills,
agents, system prompts, config stubs, and MCPs.

Update narrow sync help and human output so each command states that it is a
resource-scoped maintenance command and that `vaultspec-core sync` is required
for a complete provider-facing refresh.

Update `vaultspec-core spec rules add` success output to say the source rule was
created and provider-facing outputs remain stale until `vaultspec-core sync`
runs.

Add regression coverage for the exact operator scenario: create a rule with
`spec rules add`, run top-level `sync`, and assert that `AGENTS.md`,
`CLAUDE.md`, and `GEMINI.md` reflect the new rule.

## Rationale

The central design problem is conflated command authority. Keeping `sync` as the
one complete synchronization verb matches the existing working implementation
and the operator mental model. Reframing narrow commands avoids a breaking
removal while making their limited scope visible.

This follows CLI design guidance: state changes should be explicit, command
verbs should not carry hidden scope differences, and compatibility-sensitive
command contracts should be changed through clear messaging and regression
tests rather than abrupt removal.

## Consequences

Positive consequences:

- Operators get one normal command after source edits: `vaultspec-core sync`.
- Narrow commands stop presenting themselves as equivalent propagation paths.
- Provider-facing stubs are treated consistently as generated outputs.
- MCP sync receives accurate wording instead of being squeezed into provider
  destination language.

Trade-offs:

- The CLI keeps compatibility aliases or narrow commands for now.
- Help, docs, and output wording need coordinated tests to prevent drift.
- Full deduplication may require follow-up refactoring if narrow commands
  currently bypass shared sync policy.
