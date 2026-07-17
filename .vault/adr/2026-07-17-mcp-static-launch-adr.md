---
tags:
  - '#adr'
  - '#mcp-static-launch'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-17-mcp-static-launch-research]]"
---

# `mcp-static-launch` adr: `the MCP launch is side-effect-free static execution` | (**status:** `accepted`)

## Problem Statement

An MCP client connect must never mutate the governed project's environment,
yet the dependency-mode launch the renderer writes into every provider config
does exactly that: bare `uv run` re-syncs the venv on each connect, and on
2026-07-17 one such sync corrupted this repository's own venv mid-flight,
leaving every subsequent connect dead with client error -32000
(`2026-07-17-mcp-static-launch-research`). The launch bytes are governed by
`2026-07-13-install-mode-adr` Q2, which inherited the pre-mode-era shape
without deciding the sync flag. This record amends that Q2 shape - it does
not reopen the mode model - and binds the cross-repo launch-hygiene contract
the sibling package must also meet, following the amendment pattern
`2026-07-14-install-parity-adr` established.

## Considerations

- The dependency-mode MCP launch is the only dependency-mode surface without
  the `--no-sync` guard; hooks and the firmware CLI rule already carry it
  (`2026-07-17-mcp-static-launch-research`, renderer finding).
- Sync-on-connect is documented uv behavior, not a uv bug; only `--no-sync`
  prevents environment mutation (`--frozen` and `--locked` still sync)
  (`2026-07-17-mcp-static-launch-research`, uv semantics finding).
- The client contract is a 5-second connect window, stdout reserved for
  JSON-RPC, and no stdio reconnect within a session; connect-time resolution
  violates it on both latency and stream hygiene
  (`2026-07-17-mcp-static-launch-research`, client contract finding).
- The 2026 registry and ecosystem distribute Python stdio servers as
  ephemeral pinned `uvx`; venv-tethered `uv run` appears nowhere as a
  distribution shape - it is the dev/self-hosting shape in the decided
  two-mode split (`2026-07-17-mcp-static-launch-research`, standards finding).
- The observed-shape matcher reconstructs candidates through the renderer, so
  changed bytes propagate to the doctor automatically, but deployed old-shape
  entries then match neither candidate; migration semantics must be decided,
  not inherited (`2026-07-17-mcp-static-launch-research`, architecture
  finding).
- Rag's shipped tokenized definition omits the tool-spec its own optional
  `mcp` extra requires, and pre-parity workspaces still carry rag's static
  exe-form seed - the banned exe-lock shape and the incident's actual lock
  holder (`2026-07-17-mcp-static-launch-research`, rag findings).
- Cross-repo precedent: a shared contract bound here, implemented by the
  sibling under its own record (`2026-07-16-mcp-stdio-lifetime-adr`).

## Considered options

**A1 - dependency-mode launch bytes.** Chosen: the dependency/dev render
gains `--no-sync` (`uv run --no-sync python -m <module>`), making the launch
a static execution that resolves the existing venv, mutates nothing, and
fails honestly when the venv is broken instead of self-repairing at connect
time. Rejected: keep bare `uv run` (the incident is the refutation; the shape
was inherited, never decided). Rejected: `--frozen`/`--locked` (still sync
the environment). Rejected: demote dependency mode to non-MCP use and force
tool mode for all launches - reverses install-mode's two-first-class-modes
decision and breaks this repository's own self-hosting workflow, without
being required by the defect.

**A2 - tool-mode launch bytes.** Chosen: unchanged
(`uvx --from <spec> python -m <module>`), already static with respect to the
governed project and cache-fast after first resolution. Rejected: the
ecosystem's terser `uvx <package>` exe form - install-mode Q2 already chose
module invocation for the Windows exe-lock class, and this record does not
reopen that trade.

**A3 - old-shape migration.** Chosen: the observed-shape matcher additionally
recognizes the legacy bare-`uv run` module launch as `DEPENDENCY`, so mode
inference and the mode-mismatch signal do not regress on not-yet-refreshed
workspaces; the managed-entry fingerprint machinery treats the byte change as
ordinary drift, remediated by `spec mcps sync --force` and applied
automatically by `install --upgrade` through the existing force-managed seam.
Rejected: matcher returns `None` for the legacy shape (silently degrades
doctor coverage on every existing dependency-mode workspace). Rejected: a
one-shot migration command (the sync/upgrade path already owns definition
refresh; a second mover violates the single-comparator discipline).

**A4 - sibling contract.** Chosen: bind the contract only - every rendered
launch, both packages, is side-effect-free and stdout-clean; rag adds
`_vaultspec_mode_tool_spec` naming its `mcp` extra to its tokenized builtin
and re-enrollment refreshes stale seeds - with rag implementing under its own
record, mirroring the stdio-lifetime precedent. Rejected: fixing rag's
builtin from core's repo (crosses the repo boundary the enrollment
architecture deliberately keeps one-way). Rejected: core hardcoding a rag
tool-spec fallback table (reintroduces the per-package table the
parameterized renderer exists to avoid).

## Constraints

- Amends, does not supersede, `2026-07-13-install-mode-adr`: only Q2's
  rendered dependency bytes change; the mode model, persistence schema, and
  precedence chain stand.
- The single-comparator discipline holds: renderer, doctor matcher, and every
  test assert through `render_launch_for_mode`; no second hardcoded launch
  copy may appear.
- The launch must keep stdout clean for JSON-RPC; no wrapper that prints may
  enter the command line.
- Deployed old-shape entries are managed by fingerprint; the refresh must ride
  the existing sync/upgrade force-managed seam, not bypass ownership.
- Rag-side changes ship in the rag repository on its own release cadence; core
  must not floor on them, and the contract must degrade gracefully (a rag
  definition without the tool-spec key renders as today).
- The in-flight `mcp-stdio-lifetime` plan owns `src/vaultspec_core/mcp_server/`;
  this feature must not touch that tree.

## Implementation

The dependency branch of the launch renderer gains the `--no-sync` argument;
the derived convenience table, the observed-shape matcher's candidates, and
every launch-shape assertion in the test suites move with it automatically or
by test-text update. The matcher grows one explicit legacy-shape recognition
(bare `uv run python -m <module>` maps to `DEPENDENCY`) so pre-refresh
workspaces keep honest doctor output with a drift signal pointing at
`spec mcps sync --force` or `install --upgrade`. Documentation (the MCP doc
and the CLI reference's rendered-launch examples) states the static-execution
contract: an MCP connect never installs, resolves, or repairs; environment
repair is an explicit dev action. On the rag side, tracked as a rag issue
under its own record: the tokenized builtin gains
`_vaultspec_mode_tool_spec: "vaultspec-rag[mcp]"`, and rag re-enrollment
refreshes the stale static seed in pre-parity workspaces. This workspace's
own recovery (venv repair, seed refresh, orphan sweep) is operational
remediation alongside the feature, not part of the decision.

## Rationale

The incident is the knockout: a launch shape that can uninstall its own
server package at connect time is disqualified as a distribution artifact,
and `2026-07-17-mcp-static-launch-research` shows the guard flag is already
the decided convention on every sibling surface - the MCP launch omitting it
was inertia, not intent. Amendment beats supersession because install-mode's
architecture (two first-class modes, tokenized definitions, one comparator)
is exactly what makes the fix one line plus its comparator echoes; reopening
the model would discard the machinery that contains the blast radius. The
legacy-shape recognition in A3 is what keeps the doctor truthful during the
migration window at the cost of one bounded, comparator-derived candidate,
where the alternatives either lie (`None` on every existing workspace) or
fork the mover. Binding rag by contract rather than by patch follows the
proven stdio-lifetime shape for cross-repo defects and respects the one-way
enrollment boundary.

## Consequences

- Good: an MCP connect becomes read-only with respect to the governed
  project on every mode and both packages; the venv-corruption class is
  closed at its cause, and a broken venv now fails the connect with an
  honest remediation-shaped error instead of a destructive self-repair.
- Good: doctor coverage survives the migration window; old-shape workspaces
  are flagged as drifted with a working fix hint rather than unrecognized.
- Bad: dependency-mode connects no longer self-heal a stale venv - a
  contributor who pulls a lockfile change must run the sync explicitly or
  see the MCP server fail until they do; this is the accepted price of
  static execution and lands in the docs as a stated contract.
- Bad: the legacy-shape recognition is permanent matcher surface until a
  future record retires it; it must be tested so it cannot drift into
  accepting arbitrary un-guarded shapes.
- Bad: rag's fix is release-coupled to the rag repository; until it ships,
  tool-mode rag renders remain broken (as today) and stale seeds persist in
  pre-parity workspaces.
- Neutral: tool-mode bytes, hooks, the mode model, and the enrollment
  architecture are untouched; test churn is confined to launch-shape
  assertions that already route through the comparator.
