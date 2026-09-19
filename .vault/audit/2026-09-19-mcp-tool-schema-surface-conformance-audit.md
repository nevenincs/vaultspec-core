---
tags:
  - '#audit'
  - '#mcp-tool-schema'
date: '2026-09-19'
modified: '2026-09-19'
body_schema: 'body-v2'
body_hash: 'sha256:fc9db86975036c06be86024d8c7a3c7436cd32f740ca575917fe7c4f4b14a8a5'
related: []
---

# `mcp-tool-schema` audit: `MCP surface conformance: orientation, cancellation, transport declarations, resources`

## Scope

The MCP server's advertised surface, its provisioning and installation path, and its service lifecycle, audited against the accepted gateway decision and against the current protocol revision. Covers `src/vaultspec_core/mcp_server/`, the mode-neutral definition and rendering path in `src/vaultspec_core/core/mcps*.py`, the committed workspace declaration, the ownership sidecar, and the bundled rules that tell an agent how to call the surface. Protocol-conformance judgements were reviewed with an independent architectural read; findings below are stated where this codebase could be checked directly.

## Findings

### orientation string | high | The advertised tool count and enumeration drifted from the registered surface, and the guard could not fail

`_build_instructions` in `src/vaultspec_core/mcp_server/app.py` announced nine tools and named nine. The registered surface is ten: `log` was added after the decision was recorded and the orientation string never followed. That string is the third version channel named in the decision's Q8 and the only one a host can surface without a round-trip, so a connected agent was told the ledger tool does not exist. Host-side tool search indexes tool names and descriptions, and the long tail behind `invoke` is not in that index, which makes this string the primary discoverability channel for anything it omits.

The guard in `src/vaultspec_core/mcp_server/tests/test_tool_surface.py` asserted `name in instructions` over the full expected set. The assertion is a bare substring test and `log` is a substring of `catalog`, which the string contains twice, so the one tool missing from the enumeration was the one tool the guard could not detect. Every other name passed on its own merits. The check reported green for as long as the defect existed.

### transport declarations | medium | The declared dependency set asserted an HTTP transport the server does not serve

`starlette`, `uvicorn` and `sse-starlette` sat in the runtime dependencies with no HTTP or SSE transport constructed anywhere: `mcp_server/app.py` calls a bare `mcp.run()`, whose default transport is stdio. A deptry ignore block recorded the redundancy but declined to act, on the ground that a direct declaration of a transitive package is also how a security floor is pinned and the intent could not be read from the code.

The intent is recoverable from history. All three floors were introduced by the A2A rewrite commit, whose decision records and plan are no longer in the vault and whose code was never written. The OSV gate reports no advisory against any of the three, and the SDK requires all three itself, so the resolved environment does not change when the declarations are removed. They were an abandoned ambition, not pins.

### gateway cancellation | medium | A long-running gateway call cannot be interrupted

`invoke` runs its subprocess through a blocking call inside an async handler, so the event loop is held for the duration of the child and a cancellation notification is not read until the child exits. The protocol expects a server to stop work on cancel. The per-request isolation wrapper is not implicated: it awaits a task, and cancelling that await cancels the task.

The same non-interruptibility applies to the hot-path handlers, which run synchronous core code inline. That is a different problem with a different remedy - cooperative checks inside the long loops rather than process control - and is recorded here rather than actioned.

### gateway confirmation cost | medium | Every long-tail call pays a destructive confirmation, including read-only ones

`invoke` carries the destructive annotation unconditionally because the catalog mixes mutating and read-only verbs. The decision record names this as an accepted consequence. The cost is real in use: a host that would auto-approve a read-only tool cannot, because the annotation is per tool and static, so it cannot vary with the verb a given call names. The catalog knows more than the annotation can express.

### resources | low | An accepted option was never implemented

The decision's Q4 chose tools as primary with vault document bodies and the verb catalog additionally exposed as addressable resources, and `find` returning resource links where the host supports them. No resource is registered anywhere in the server. `find` returns a `resource_uri` string field inside its structured output, built as a plain file URI; that is neither a registered resource nor a resource-link content block, so a host cannot read what the field points at through the protocol. No protocol promise is broken, because a file URI is readable by the host directly, but the decision and the implementation disagree and the tool description does not say which behaviour to expect.

### provisioning and lifecycle | info | Conformant; no finding

The provisioning path - mode-neutral tokens, per-package committed declaration, rendered launch, ownership recorded outside host schemas, and fingerprint-gated convergence - has no protocol contract to conform to, since host configuration is host-owned, and it matches the conventions hosts expect for a Python stdio server. Enrollment-only installation is the correct boundary: the host owns launch, trust and lifetime, and the tooling does not start, supervise or probe a server process. The stdio lifetime contract is correctly implemented as exit on stdin EOF, and the lifetime watchdog compensates for hosts that leave the pipe open rather than substituting for the contract; it fails open in every path, which is the right disposition given EOF is the only portable signal. One residual risk is noted without a change: user-scope enrollment lives in a host file the host itself rewrites, so a fingerprint there can shift underneath the ownership record. Project scope, which is the default, is not exposed to it.

## Recommendations

Correct the orientation string to name every registered tool, and bind its guard to the registered surface rather than to a list maintained beside it, so a new tool cannot reach the surface without the string following. Remove the advertised count from the prose entirely: a hand-typed count is the same instrument that failed here.

Remove the three transport distributions from the declared dependency set and remove their ignore entries with them, recording the resolved intent so the question is not reopened.

Make the gateway subprocess cancellable, folding the existing timeout path into the same mechanism, and leave the hot-path handlers alone pending separate work on cooperative cancellation.

The confirmation-cost finding names a decision rather than settling one: splitting the gateway into a read-only executor alongside the existing one would let a host auto-approve read-only long-tail calls, at the cost of a second advertised tool and a per-verb read classification the catalog does not currently carry. That is a refinement of the accepted gateway decision and belongs in an amendment to it, not in this record.

The resources finding likewise names a choice: either implement the accepted option, or narrow the decision to the file-URI behaviour the code actually has and say so in the tool description. The second is nearly free and is what the current code already means.
