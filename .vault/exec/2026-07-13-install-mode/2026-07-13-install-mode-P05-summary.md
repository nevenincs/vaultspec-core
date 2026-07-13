---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# `install-mode` `P05` summary

Phase P05 closed the plan: Q6 migration inference for legacy workspaces on
`install --upgrade`, mode-aware documentation across three touchpoints, a regenerated
CLI reference, a full unit-gate run, and a Q1-Q6 ADR conformance review. All eight Steps
(S26-S33) closed clean, with no review revisions required.

- Modified: `src/vaultspec_core/core/commands.py`
- Modified: `src/vaultspec_core/tests/cli/test_migration_triggers.py`
- Modified: `docs/MCP.md`
- Modified: `README.md`
- Modified: `docs/framework.md`
- Modified: `src/vaultspec_core/builtins/reference/cli.md`
- Modified: `docs/CLI.md`

## Description

`_infer_upgrade_mode` (S26) landed in `core/commands.py`: an explicit `--mode` flag wins
first, an already-persisted declaration wins next (making a repeated upgrade
idempotent), and only a legacy workspace with neither falls through to inference from
its deployed state, committing to dependency mode only when the deployed hook shape and
the pyproject dependency listing agree. The declaration is written before the provider
sync and hook scaffold run, so an inferred mode renders correctly-shaped artifacts in
the same run. Three WorkspaceFactory tests (S27) pin a legacy dependency-mode workspace,
a legacy tool-shaped workspace, and idempotency on a second upgrade; the tool-shaped
case is the ordering pin the P03 review demanded.

Documentation was updated across three files: `docs/MCP.md` (S28) gained an Install
modes subsection naming the uvx tool-mode default and the existing uv-run block as the
dependency-mode shape; `README.md` (S29) gained a getting-started paragraph on mode
selection and a note that the MCP launch command follows the install mode;
`docs/framework.md` (S30) gained a Choose an install mode paragraph in the Operate day
to day section. All three were reflowed through `mdformat --wrap 88`.

The CLI reference (S31) had the `--mode` option added to the install command's
hand-authored option list in both `docs/CLI.md` and the bundled `cli.md`, since the
generator-owned command-inventory marker block carries no per-flag detail;
`spec reference generate --check` confirmed both stayed in sync.

## Verification

S32 ran the full unit gate clean: 1652 passed, 1052 deselected, 0 failed, 0 errors, no
new skips, in about 147 seconds.

S33 traced every ADR decision (Q1 through Q6) to its shipped symbol and found all six
CONFORM. Three supervision items were addressed: the `parse_version_tuple` dev-suffix
boundary condition was accepted as inherited from the one shared version comparator the
codebase relies on (introducing a stricter floor-only comparison would fork version
semantics); the P04 doctor-surfacing fixes were confirmed present and routed through the
shared comparators; and the legacy-bridge and migration interplay was found coherent,
with the S27 tool-shaped test's contrived pyproject removal identified as the only way
to observe a hook-versus-MCP force-gate asymmetry that is not a real migration defect.
One operational deviation was recorded rather than fixed in code: this self-hosting
repository lists no `vaultspec-core` dependency in its own `pyproject.toml` and carries
no committed `workspace.json`, so a bare `install --upgrade` here would infer tool mode;
its dependency-mode status must be established by an explicit declaration or
`install --mode dependency` at rollout, before any bare upgrade. The install-mode
feature index was regenerated and `vault check all --feature install-mode` reported
every check clean.
