---
tags:
  - '#plan'
  - '#packaging-restructure'
date: '2026-02-21'
tier: L1
related:
  - '[[2026-02-21-packaging-restructure-adr]]'
modified: '2026-09-19'
body_schema: body-v2
body_hash: 'sha256:de0f1f61ca3a41be3e6a47d5a6449edc6ba17b0a214f7be7b9660b01e67de923'
---

# `packaging-restructure` plan

Rewrite bare-name production and test imports to the `vaultspec.*` package form and unify the MCP server entry point.

## Description

Reconstructed 2026-09-19 from this feature's historical execution records
(`2026-02-21-packaging-restructure-p1-step05-exec`,
`2026-02-21-packaging-restructure-p1-step06-exec`,
`2026-02-21-packaging-restructure-p1-step09-exec`,
`2026-02-21-packaging-restructure-p1-review-exec`,
`2026-02-21-packaging-restructure-p2-steps18-22-exec`), which recorded
completed work against a Phase 1/2 plan (`2026-02-21-packaging-restructure-p1p2-plan`)
that no longer survives. The Steps below restate what those records report as done;
they are closed on that evidence, not re-executed. S04's evidence is a code-review
record (`REVISION REQUIRED` status); it is treated as a verification Step and its
findings are logged, not as a fix applied within this plan. Authorization is
historical: the work shipped in February 2026 under the packaging restructure the
ADR authorizes.

Decision coverage: `2026-02-21-packaging-restructure-adr` governs the restructure this
plan sequences.

## Steps

- [x] `S01` - rewrite bare-name imports in leaf packages core/ and vaultcore/ to vaultspec.\* prefixed form; `src/vaultspec/vaultcore/scanner.py`.
- [x] `S02` - rewrite bare-name imports in orchestration/, protocol/, and hooks/ to vaultspec.\* prefixed form; `src/vaultspec/orchestration/subagent.py`.
- [x] `S03` - rewrite bare-name imports across the test tree and conftest files to vaultspec.\* prefixed form; `tests/conftest.py`.
- [x] `S04` - verify editable install, test suite, CLI entry points, and MCP importability, and flag remaining bare-name imports and the pyproject dependency-groups gap; `pyproject.toml`.
- [x] `S05` - create the unified vaultspec.server MCP entry point and refactor the subagent server into a registrable module; `src/vaultspec/server.py`.

## Parallelization

None. The Steps are recorded sequentially as the historical records report them, and
the work is complete, so no container is available for concurrent assignment.

## Verification

Verified historically by the execution records this plan reconstructs: import-rewrite
grep scans reported zero remaining bare-name imports per Step, and S04's review ran
`uv sync`, `pytest`, and the CLI/MCP import checks it names. The paths sit under the
pre-rename `src/vaultspec/` tree and were carried forward or renamed by the later
package restructure, so most are not re-checkable at their original locators.
