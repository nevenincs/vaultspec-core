---
tags:
  - '#adr'
  - '#pre-existing-tests'
date: '2026-05-01'
related:
  - '[[2026-05-01-pre-existing-tests-research]]'
  - '[[2026-05-01-pre-existing-tests-plan]]'
---

# `pre-existing-tests` adr: pre-existing test failure fix paths (#98, #99) | (**status:** `accepted`)

## Problem Statement

Two tests fail on every `pytest` run against the source repo. They have been
treated as carve-outs across multiple recent PRs. Both must be repaired in
this work without skips, mocks, patches, or stubs.

- #98 - `tests/test_mcp_config.py` asserts an install-time artifact
  (`.mcp.json`) exists at the source repo root.
- #99 - `TestGeminiCliLoadsRenderedAgents::test_all_source_agents_load`
  uses a gemini probe command that no longer triggers agent validation.

## Considerations

- The project rules forbid mocks, skips, patches, stubs, fakes. Real
  filesystem only.
- `tests/test_mcps.py` already exhaustively covers the install-time
  `.mcp.json` shape via real `install_run` and `mcp_sync` calls into
  synthetic workspaces.
- gemini 0.40.0-preview.4 added a workspace-trust gate. Headless `-p`
  mode no longer loads project agents. `--skip-trust skills list` does
  trigger the loader and emits the same `Agent loading error: ...` text
  the existing scraper matches.
- Direct loader access requires importing gemini's TypeScript loader;
  no Python wrapper exists.

## Constraints

- No `pytest.skip` / `xfail` markers. No mocks.
- The gemini probe must verify real CLI behaviour, not a reimplementation.
- Changes must be self-contained: do not leak into adjacent test files.

## Implementation

### #98 - delete `tests/test_mcp_config.py`

Every assertion the file makes is either:

- Already covered by `tests/test_mcps.py::TestInstallSeedsMcps::test_install_creates_mcp_json_from_registry`
  (asserts `mcpServers.vaultspec-core` shape on a real install), or
- Covered by `tests/test_mcps.py::TestMcpSync::test_creates_mcp_json_from_scratch`
  (top-level `mcpServers` key + entry shape), or
- Tautological for the source repo (asserting an install artifact at the
  source root).

No replacement file is needed. The contract is fully exercised by the
existing synthetic-install tests.

### #99 - swap probe to `gemini --skip-trust skills list`

In `TestGeminiCliLoadsRenderedAgents._invoke_gemini`:

- Replace argv `[gemini_bin, "-p", self._PROBE_PROMPT]` with
  `[gemini_bin, "--skip-trust", "skills", "list"]`.
- Drop `_PROBE_PROMPT` (no longer used).
- Update the class docstring to reflect the new probe.

Empirically verified: with this argv, gemini emits exactly the
`Agent loading error: Failed to load agent from <path>: Validation failed: Agent Definition: tools.0: Invalid tool name` line the existing
scraper grep matches. The combined stdout+stderr substring search
(`"Agent loading error" in line or "Invalid tool name" in line`) requires
no change.

## Rationale

#98: the file was authored against the wrong workspace assumption. Every
useful assertion already runs in a more correct shape elsewhere. Rewriting
it as a `WorkspaceFactory`-driven duplicate of `test_mcps.py` adds noise
without coverage. Deletion is the smallest correct change.

#99: the probe needed updating; the contract is real. Direct loader access
is not viable (no Python binding). The new probe is slower in absolute
terms but still gated behind `@pytest.mark.gemini` and avoids an LLM API
round-trip, so opt-in cost is comparable.

## Consequences

- One whole file removed; no replacement. PR diff makes the dead-code
  rationale clear.
- `_PROBE_PROMPT` constant becomes unused and is removed alongside the
  argv change.
- The marker-gated test goes from ~5.9s to ~18-20s per run when selected.
  Default `pytest` runs do not select `@pytest.mark.gemini` (test docs
  describe this as opt-in), so non-gemini contributors see no change.
- The probe is now resilient against future gemini changes that defer
  agent loading in headless mode. The canary check inside the test itself
  is the long-term guard against future probe rot.
