---
tags:
  - '#plan'
  - '#mcp-tool-schema'
date: '2026-09-19'
tier: L1
related:
  - '[[2026-07-09-mcp-tool-schema-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:f483621232e8f13ff553ec1755651562772048e83a6473e47b31985297efa992'
---

# `mcp-tool-schema` plan

## Description

Approved 2026-09-19. Basis: the user directed "You have to drive the actual feature to completion" after an audit of the MCP implementation, its provisioning, and its service lifecycle, having already scoped the server-identity rename as part of the same feature. The execution shape was reviewed with the MCP-EXPERT peer session.

Seven Steps harden the MCP surface across four concerns: what the server tells a host about itself, whether a long-running gateway call can be interrupted, whether the declared dependency set is honest, and whether a read-only long-tail call must cost a destructive confirmation.

Decision coverage. The accepted `2026-07-09-mcp-tool-schema-adr` governs this surface and every Step inherits it. S01, S02, S03, S06 and S07 are execution within its settled constraints and establish no new commitment. S04 and S05 add an advertised tool, which is a compatibility commitment: they refine the gateway decision that ADR already records, including its explicit accepted consequence that a single broad `invoke` forces conservative host confirmation on every long-tail call including read-only ones. That refinement is carried as a proposed amendment to the same ADR rather than a separate record, and S04 and S05 do not execute until the amendment is accepted.

Dropping the unwired HTTP distributions in S03 is a correction to an existing shipping principle rather than a costly decision. All three are already required transitively by the MCP SDK, so removing them from the declared set needs no migration and reverses at no cost; the declared surface simply stops asserting a transport the server does not serve. No separate decision record is warranted and none is created.

## Steps

- [x] `S01` - Name every registered tool in the server instructions string and bind the guard to the live registry; `src/vaultspec_core/mcp_server/app.py, src/vaultspec_core/mcp_server/tests/test_tool_surface.py`.
- [x] `S02` - Make the invoke subprocess cancellable: extract \_run_verb as an anyio coroutine with terminate-grace-kill discipline, folding the timeout path into it; `src/vaultspec_core/mcp_server/tools/gateway.py, src/vaultspec_core/mcp_server/tests/test_gateway.py`.
- [x] `S03` - Drop starlette, uvicorn and sse-starlette from the declared dependency set and any allowance table that names them; `pyproject.toml, uv.lock`.
- [ ] `S04` - Derive a read_only classification per verb from its own declaration, guarded by a build-time invariant that rejects a read verb exposing a mutating flag; `src/vaultspec_core/cli/, src/vaultspec_core/mcp_server/catalog.py, src/vaultspec_core/mcp_server/tests/test_catalog.py`.
- [ ] `S05` - Add the invoke_read tool with read-only annotations, surface read_only on discover's verb schemas, and register it in the read-only server mode; `src/vaultspec_core/mcp_server/tools/gateway.py, src/vaultspec_core/mcp_server/app.py, src/vaultspec_core/mcp_server/tests/`.
- [x] `S06` - State in the find tool description that the host reads resource_uri paths directly, and refresh the generated MCP tool inventory; `src/vaultspec_core/mcp_server/tools/documents.py, docs/MCP.md`.
- [x] `S07` - Record the console script, binary and tool-surface changes as release notes; `docs/MCP.md, docs/channels.md`.

## Parallelization

No Steps are assigned to run concurrently. S02 and S03 were executed against disjoint files while both were open - the gateway module and its tests against the project manifest and lock - but they are sequenced rather than parallel assignments, and no two Steps share write ownership of a file.

S04 and S05 are ordered after S02 because the read executor is built on the subprocess path S02 extracts. S05 depends on S04's classification and ships with it. S04 and S05 do not execute until the proposed amendment to the governing decision is accepted.

## Verification

Every Step runs the project's lint, type and markdown gates and the MCP server suite. Beyond those, each Step names a check that can distinguish done from not-done:

- S01: the orientation guard fails when the string omits a registered tool. Demonstrated by regressing the string and observing the failure before accepting the fix.
- S02: a cancelled call leaves no surviving child process, verified by process identifier rather than by the process object; a timed-out call returns the timeout kind and also leaves no child; a cancelled request writes no response.
- S03: the dependency audit passes with the ignore entries removed, not merely with the declarations removed, and the lock diff touches only this project's own dependency list while the three distributions still resolve transitively at unchanged versions.
- S04: catalog construction fails when a verb declared read-only exposes a mutating flag, and the built read set contains the orientation verbs.
- S05: a write verb submitted to the read executor is refused with the subprocess runner patched to raise if reached; the read-only server advertises exactly its five tools.
- S06: the generated tool inventory regenerates without hand editing.
- S07: the release notes name the console script rename, the binary rename, and the tool-surface change.

A final review covers the integrated surface against the governing decision before the work is reported complete.

## Context

Authorized by the user on 2026-09-19: "You have to drive the actual feature to completion", following an audit of the MCP implementation, its provisioning, and its service lifecycle. The audit findings and the execution brief were reviewed with the MCP-EXPERT peer session.

Decision coverage: the accepted `2026-07-09-mcp-tool-schema-adr` governs this surface and is inherited by every Step here. Two Steps are execution within its settled constraints and need no new decision. The `invoke_read` split reverses an accepted consequence that ADR records explicitly ("`invoke` is a single broad tool whose destructive annotation forces conservative host confirmation on every long-tail call, including read-only ones"), so it is a refinement of that same decision and is carried as a proposed amendment to it rather than a new record. That Step does not execute until the amendment is accepted.

Dropping the unwired HTTP dependencies is a correction to an existing shipping principle, not a costly decision: the three distributions are already required transitively by `mcp` 2.2.0, so removing them from the declared set needs no migration and reverses at no cost. Rationale recorded here rather than in a separate record.
