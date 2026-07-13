---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S11'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Add a WorkspaceFactory-based install_run test asserting a hard refusal with a remediation message when --mode dependency is requested in a repo with no pyproject.toml

## Scope

- `src/vaultspec_core/tests/cli/test_ambiguous_states.py`

## Description

- Add `TestInstallModeConflictRefusal` exercising `install_run` with `--mode dependency` in a workspace that has no `pyproject.toml`.
- Assert the raised `VaultSpecError` names the impossible combination and the
  target path, and that its hint carries an actionable remediation (both
  `--mode tool` and `pyproject.toml`).
- Assert the refusal happens before any provisioning by checking that no
  `.vaultspec/` directory is scaffolded.

## Outcome

The hard refusal is covered end to end through `install_run` against a real
factory-built workspace: the error message and remediation hint are asserted,
and the absence of a scaffolded `.vaultspec/` proves the refusal fires ahead of
provisioning rather than after a partial install. This test lives in
`test_ambiguous_states.py`, which is file-wide `pytest.mark.integration` and is
therefore excluded from CI's `-m "unit and not gemini and not claude"` gate; run
directly the file passes (16 tests). The gate-visible coverage of the refusal
path is the unit-marked `TestResolveRefusal` in `test_workspace_mode.py`, added
during P02 review, which calls `resolve_install_mode` with an explicit
dependency request and no `pyproject.toml`. Ruff is clean.

## Notes

The test uses the shared `factory` fixture and the real `install_run`, no mocks
or stubs. Asserting on both the message and the `.vaultspec/` absence guards two
distinct regressions: a silent fallback to tool mode, and a refusal that fires
only after scaffolding has already run. The integration test is intentionally
retained as the end-to-end no-scaffold guarantee alongside the CI-visible unit
test; see the P02 review follow-up commits.
