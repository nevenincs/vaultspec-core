---
tags:
  - '#audit'
  - '#mcp-testing'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-17-mcp-testing-plan]]"
  - "[[2026-02-22-mcp-testing-adr]]"
---

# `mcp-testing` audit: `functional assertion floor review`

## Scope

Stacked-diff review of the functional assertion floor (branch stacked on
the watchdog-parity PR): the raw JSON-RPC serving probes added to
`tests/unit/mcp_server/test_watchdog.py` and
`tests/mcp/test_mcp_entrypoint.py`, against the 2026-07-17 amendment to
the testing decision. Reviewed by the code-reviewer persona for protocol
correctness, deadlock and flakiness hazards, assertion strength versus
the floor, test integrity, and conventions.

## Findings

### protocol-correctness | low | Exchange confirmed valid MCP end to end

Framing, initialize params, the initialized notification ordering, and
the id-keyed receive loops were confirmed correct; server logging is
stderr-only so stdout carries pure JSON-RPC, and the 20-message skip
bound tolerates id-less notifications. CLEAN: no action.

### stderr-backpressure | low | Serving-EOF test piped stderr it never drained

The serving-session EOF test blocked on stdout mid-handshake while
stderr accumulated in an undrained pipe - a latent buffer deadlock,
ceiling-bounded by the suite timeout. RESOLVED: stderr is discarded for
that test, with the rationale recorded inline.

### orphan-on-failure | low | Failed serving assertion could leak the pipe-holding sleeper

The leaked-pipe test's new serving assertions ran before the inner
cleanup that reaps the 120-second sleeper. RESOLVED: the sleeper reap
was hoisted into the outer cleanup covering every exit path.

### blocking-readline | low | Handshake reads rely on the suite-wide timeout ceiling

Bare blocking reads during the handshake are bounded only by the
300-second function-scoped pytest ceiling. ACCEPTED: stdout is pure
protocol and the response is prompt; a per-read guard would only
tighten failure latency.

### assertion-strength | low | Floor satisfied; single sanctioned exception verified

Every spawned-server test asserts served capability (handshake identity
and/or the exact nine-tool surface); the zero-input EOF test is the
decision's documented exception and states it. CLEAN: no action.

## Recommendations

- Ship after the two resolved findings; verdict PASS-with-notes, no
  revision cycle required.
- The rag half of the floor is tracked on that repo's board with the
  inventory and the reference probe; no core follow-up.
