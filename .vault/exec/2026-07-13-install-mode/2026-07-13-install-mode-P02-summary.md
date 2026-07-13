---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# `install-mode` `P02` summary

Phase P02 added the `install --mode` flag and the Q5 precedence chain that resolves and
persists the workspace mode once at provision time, refusing loudly on the one
impossible combination. All six Steps (S06-S11) closed; review found two gaps in the
refusal coverage and landed two follow-up fixes.

- Modified: `src/vaultspec_core/cli/root.py`
- Modified: `src/vaultspec_core/core/commands.py`
- Modified: `src/vaultspec_core/core/workspace_mode.py`
- Modified: `src/vaultspec_core/tests/cli/test_workspace_mode.py`
- Modified: `src/vaultspec_core/tests/cli/test_ambiguous_states.py`

## Description

The `--mode` typer option (S06) was added to `cmd_install`, typed as
`InstallMode | None` so it accepts exactly `tool` and `dependency` and auto-detects when
omitted, threaded through to `install_run` alongside a new `_persist_resolved_mode`
helper that writes the committed declaration and mirrors it into the manifest echo.

`resolve_install_mode` (S07) implements the Q5 precedence chain: explicit flag over
persisted declaration over pyproject detection over the tool-mode default. It refuses
the impossible combination (explicit dependency mode with no `pyproject.toml`) with a
typed `VaultSpecError` and a remediation hint, while permitting an explicit mode that
merely differs from detection evidence. The accompanying
`_pyproject_declares_vaultspec_dependency` probe spans `[project.dependencies]`,
`[project.optional-dependencies]`, `[dependency-groups]`, and
`[tool.uv.dev-dependencies]`, normalizing PEP 508 requirement names per PEP 503.

`install_run` (S08) was rewired to call `resolve_install_mode` in place of the prior
trivial explicit-or-default resolution, so the refusal now fires before any scaffolding,
including on an impossible `--mode dependency --dry-run` combination.

Precedence ordering (S09, three cases) and detection signals (S10, four cases) were
pinned with WorkspaceFactory-based tests driven against real `pyproject.toml` fixtures
and a real committed declaration, no mocks or stubs. An `install_run` integration test
(S11) asserts the hard refusal fires with a remediation message and that no
`.vaultspec/` directory is scaffolded before the refusal, proving it fires ahead of
provisioning.

## Review revisions

Two fixes landed after phase review, both recorded as `install-mode P02 review` commits:

- `f6ffde8c` added a unit-marked `TestResolveRefusal` test to `test_workspace_mode.py`
  so the conflict-refusal path is exercised by the CI-visible unit gate; the original
  S11 integration test lives in a file-wide `integration`-marked module excluded from
  that gate.
- `c721a774` hardened `resolve_install_mode` to validate the persisted declaration
  fail-fast rather than letting a corrupt declaration surface later in the resolution
  chain.

## Verification

The install, workspace-mode, and flow-bug suites passed (61 tests) after S08; the
workspace-mode module grew to 17 tests after S10. `ruff check` and `ty check` were clean
throughout.
