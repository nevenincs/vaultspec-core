---
tags:
  - '#research'
  - '#pre-existing-tests'
date: '2026-05-01'
modified: '2026-06-13'
related:
  - '[[2026-05-01-pre-existing-tests-adr]]'
  - '[[2026-05-01-pre-existing-tests-plan]]'
---

# `pre-existing-tests` research: pre-existing test failures (#98, #99)

Two tests have been failing on the source repo through multiple recent PRs as
carve-outs. This research documents what each test was meant to verify, why it
fails today, and what the cleanest fix path is.

## Findings

### Issue #98: `tests/test_mcp_config.py::test_mcp_json_exists`

#### Current behaviour

`tests/test_mcp_config.py` defines seven assertions that all read or stat
`PROJECT_ROOT / ".mcp.json"`. Every assertion fails on the source repo because
the source repo legitimately does not ship `.mcp.json`. `.mcp.json` is an
install-time artifact emitted by `mcp_sync` into consumer workspaces using the
source-of-truth registry under `.vaultspec/rules/mcps/`. The source repo only
ships `.vaultspec/rules/mcps/vaultspec-core.builtin.json` (the registry entry),
not the synthesised top-level `.mcp.json`.

#### Existing coverage that supersedes it

`tests/test_mcps.py` already exhaustively covers the contract the broken file
was probing:

- `TestInstallSeedsMcps::test_install_creates_mcp_json_from_registry` (lines
  1074-1095) does a real `install_run` into a synthetic workspace and asserts:

  - `mcp_json["mcpServers"]["vaultspec-core"]` exists
  - `server["command"] == "uv"`
  - `server["args"] == ["run", "python", "-m", "vaultspec_core.mcp_server.app"]`

  These are exactly the assertions in the broken file's
  `test_command_is_uv` and `test_args_use_module_invocation` cases, but
  rooted in a real install rather than a non-existent source-repo file.

- `TestMcpSync::test_creates_mcp_json_from_scratch` covers the
  `mcpServers` top-level key contract.

- `TestMcpSync::test_preserves_user_entries` and `test_force_overwrites_diff`
  cover write-time invariants the broken file did not even attempt.

- `TestMcpSync::test_dry_run_does_not_write` and `TestMcpSyncPrune::*`
  cover lifecycle / pruning - all using real synthetic workspaces.

The "no hardcoded env" assertion (`test_no_hardcoded_env`) targets the
generated `.mcp.json`, but the contract is defined by the source-of-truth
registry file, which DOES ship in the repo at
`.vaultspec/rules/mcps/vaultspec-core.builtin.json`. That contract is testable
directly against the registry source, but it is also implicitly enforced by
`mcp_sync` writing the registry's keys verbatim - tested by
`TestInstallSeedsMcps`.

#### Root cause

The file was authored against the assumption that `pytest` runs in an
"installed-state" workspace. The source repo workflow runs `pytest` against
the source tree directly, where `.mcp.json` does not and should not exist.
The same source-repo asymmetry that motivated #93 (spec-check false positive,
fixed in #94) applies here.

#### Fix path

Delete `tests/test_mcp_config.py` entirely. Every assertion it makes is
either:

1. Already covered by `tests/test_mcps.py::TestInstallSeedsMcps` and
   `TestMcpSync::*` against real synthetic workspaces, or
1. Tautological for the source repo (asserting an install artifact exists at
   the source root).

Rebuilding the file as a `WorkspaceFactory`-driven test set was considered
but rejected: it would duplicate `tests/test_mcps.py` exactly. The shape
contracts on the registry source file (`vaultspec-core.builtin.json`) are
worth checking, but those checks belong with the other sync tests, not in a
file whose name implies it owns `.mcp.json` shape.

### Issue #99: `TestGeminiCliLoadsRenderedAgents::test_all_source_agents_load`

#### Current behaviour

The test:

1. Renders every shipped source agent under `.vaultspec/rules/agents/` via
   `transform_agent(Tool.GEMINI, ...)`.
1. Writes them into `tmp_path/.gemini/agents/`.
1. Plants a deliberately broken canary file
   `vaultspec-render-canary-invalid.md` with an invalid tool name.
1. Invokes `gemini -p "respond with only the word READY"` from `tmp_path`.
1. Greps stdout/stderr for `Agent loading error` or `Invalid tool name`.
1. Asserts the canary appears in the error list (probe-validation guard) and
   no shipped agent does (the actual contract).

The test self-reports rot:

> Canary check failed: gemini did not emit an Agent loading error for the
> deliberately broken vaultspec-render-canary-invalid.md. The probe command
> no longer triggers agent validation; update the test.

#### Verification of the rot

Empirical verification against `gemini` 0.40.0-preview.4:

- `CI=1 NO_COLOR=1 gemini -p "<prompt>"` from a workspace containing a
  broken agent - no `Agent loading error` line, exits in ~4s without
  validating agents.
- `gemini --skip-trust skills list` from the same workspace - emits
  `Agent loading error: Failed to load agent from <path>: Validation failed: Agent Definition: tools.0: Invalid tool name`, runs in ~18-20s.

The gemini CLI gained an explicit workspace trust check; in non-trusted
mode the agent loader is short-circuited. Headless `-p` mode no longer
loads project-local agents at all. `--skip-trust` re-enables loading
without requiring per-workspace trust persistence.

#### Underlying contract

The contract the test enforces is real and load-bearing:

- vaultspec renders agents from `.vaultspec/rules/agents/*.md` to
  gemini-shaped files via `transform_agent(Tool.GEMINI, ...)`.
- Those files must be loadable by the actual gemini CLI without
  validation errors.

A regression in `_render_gemini_agent` (e.g. emitting a tool name that is
not in `_GEMINI_TOOL_SET`, or a frontmatter shape gemini rejects) would
ship undetected without this canary.

The unit-level `TestSourceAgentCoverage::test_gemini_render_satisfies_schema`
guards against the most common drift (tool not in the local
`_GEMINI_TOOL_SET`), but it does not exercise gemini's actual loader. A
shape that passes the local schema but fails gemini's parser - for example
a YAML field gemini renamed - would slip through.

#### Fix path

Swap the probe from `gemini -p "<prompt>"` to
`gemini --skip-trust skills list`:

- It triggers the agent loader (verified above).
- It emits the same `Agent loading error: ...` text the existing scraper
  matches.
- It does not require a model API call - cuts cost and removes a network
  dependency.
- It is ~3-4x slower in wall time (18-20s vs 4-5s) but the marker
  (`@pytest.mark.gemini`) gates the cost - default test runs do not select it.

The output channel is unchanged (`Agent loading error` / `Invalid tool name`
substring on a single combined stderr+stdout stream), so the existing
post-run scraping logic carries over.

Alternatives considered:

- **Direct loader call.** Would require importing gemini's TypeScript
  loader, which has no Python wrapper. Out of scope; would also replace
  a real-CLI smoke check with a lower-fidelity reimplementation.
- **`gemini extensions validate <path>`.** Tested - this validates
  *extensions* (the gemini-cli extension format), not bare agent files
  under `.gemini/agents/`. Wrong surface.
- **Remove the canary entirely.** Rejected: the contract is real and the
  unit test does not cover gemini's actual loader.
- **Move to a smoke test only when `gemini` is on PATH.** The current
  marker (`@pytest.mark.gemini`) already gates execution; default runs
  skip it. Moving it elsewhere has no functional effect.

## Audit sweep targets

For the post-fix sweep:

- Search for other tests asserting source-repo paths that should not
  exist there (`PROJECT_ROOT / "<install-artifact>"` patterns).
- Search for `pytest.skip`, `pytest.mark.skip`, `pytest.mark.xfail`,
  `xfail_strict` to surface any other silently-skipped tests.
- Surface findings in PR body. Do not fix in this PR (scope discipline).
