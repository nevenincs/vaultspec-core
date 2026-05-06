---
tags:
  - '#exec'
  - '#pre-existing-tests'
date: '2026-05-01'
related:
  - '[[2026-05-01-pre-existing-tests-plan]]'
  - '[[2026-05-01-pre-existing-tests-adr]]'
  - '[[2026-05-01-pre-existing-tests-research]]'
---

# `pre-existing-tests` self-review: pre-existing test fixes (#98, #99)

Self-review covering both fixes shipped in this PR. Both close the
respective issues with the fix paths chosen in the ADR.

- Removed: `tests/test_mcp_config.py`
- Modified: `src/vaultspec_core/tests/cli/test_agents_render.py`

## Description

### #98 - removed `tests/test_mcp_config.py`

The file's seven assertions all stat or read `PROJECT_ROOT / ".mcp.json"`

- a generated, install-time artifact that the source repo does not ship.
  Every contract the file probed is already enforced by `tests/test_mcps.py`:

- `TestInstallSeedsMcps::test_install_creates_mcp_json_from_registry`
  asserts the same `command='uv'` and module-invocation `args` shape that
  `test_command_is_uv` and `test_args_use_module_invocation` were
  asserting, but rooted in a real `install_run` into a synthetic
  workspace built by `WorkspaceFactory`.

- `TestMcpSync::test_creates_mcp_json_from_scratch` covers the top-level
  `mcpServers` key contract.

- `TestMcpSync::test_force_overwrites_diff` and `test_preserves_user_entries`
  cover write-time invariants the broken file did not even attempt.

No replacement file is needed; rebuilding it would duplicate
`test_mcps.py` exactly.

### #99 - swapped gemini probe to `--skip-trust skills list`

Changed argv inside `TestGeminiCliLoadsRenderedAgents._invoke_gemini`
from `[gemini_bin, "-p", self._PROBE_PROMPT]` to
`[gemini_bin, "--skip-trust", "skills", "list"]`. Removed the now-unused
`_PROBE_PROMPT` constant. Updated the class docstring to describe the
new probe surface and the workspace-trust gate that makes it necessary.

The post-run scraping logic is unchanged. The combined-stream substring
search (`"Agent loading error" in line or "Invalid tool name" in line`)
matches the new probe's stderr identically.

## Tests

Verification ran in this order:

- Empirical pre-flight: planted a broken canary in a tmp workspace,
  confirmed `gemini --skip-trust skills list` emits
  `Agent loading error: Failed to load agent from <path>: Validation failed: Agent Definition: tools.0: Invalid tool name`. Confirmed
  `gemini -p "<prompt>"` does NOT emit any such line under the same
  conditions. This is the empirical justification for the probe swap.
- Marker-targeted: `pytest src/vaultspec_core/tests/cli/test_agents_render.py::TestGeminiCliLoadsRenderedAgents -m gemini` -> 1 passed in 15.5s.
- File-targeted: `pytest src/vaultspec_core/tests/cli/test_agents_render.py` -> 52 passed.
- File-targeted: `pytest tests/test_mcps.py` -> 52 passed (confirms the
  file taking over #98's contract).
- Full suite x2: 1407 passed each run, 0 failures, stable.
- `ty check src/vaultspec_core` -> clean.
- `ruff check` and `ruff format --check` -> clean.
- `vault check all` -> clean.
- `spec doctor` -> exit 0.

## Audit sweep

- One existing `pytest.skip` at `src/vaultspec_core/tests/cli/test_audit_coverage.py:431` is a runtime environmental guard for non-admin Windows symlink creation, not a pre-existing-failure carve-out. Left in place; out of scope.
- No other tests assert install artifacts at the source repo root.
- No other skip / xfail markers found.

## Constraints honoured

- No mocks, patches, stubs, fakes.
- No `pytest.skip` introduced.
- No `--no-verify` used at any point.
- All commits passed pre-commit hooks (ruff, ty, mdformat, vault doctor, provider artifacts, prek).
