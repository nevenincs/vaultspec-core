---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# `install-mode` `P04` summary

Phase P04 routed the precommit canonical-entry check and a new mode-mismatch signal
through the persisted mode, and layered a `minimum_vaultspec_version` refuse-and-tell
floor constraint onto the existing version-warning comparator. All eight Steps (S18-S25)
closed; review found and fixed three gaps, all recorded in a batch of
`install-mode P04 review` commits.

- Modified: `src/vaultspec_core/core/diagnosis/signals.py`
- Modified: `src/vaultspec_core/core/diagnosis/diagnosis.py`
- Modified: `src/vaultspec_core/core/diagnosis/collectors.py`
- Modified: `src/vaultspec_core/core/resolver.py`
- Modified: `src/vaultspec_core/core/workspace_mode.py`
- Modified: `src/vaultspec_core/cli/spec_cmd.py`
- Modified: `src/vaultspec_core/tests/cli/test_collectors.py`
- Modified: `src/vaultspec_core/tests/cli/test_migration_triggers.py`

## Description

`ModeMismatchSignal` (S18) landed in `core/diagnosis/signals.py` with `CLEAN`,
`MISMATCH`, and `UNKNOWN` members, `UNKNOWN` documented as the legacy pre-install-mode
bridge case rather than a warning. The `mode_mismatch` field (S19) was threaded into
`WorkspaceDiagnosis` and the `diagnose()` orchestrator, pinned to `CLEAN` as a
placeholder ahead of the real collector.

`collect_mode_mismatch_state` (S20) landed in `core/diagnosis/collectors.py`: it reads
the persisted declaration, returns `UNKNOWN` when none exists, and otherwise compares
the declared mode against the observed hook-entry and MCP-command shape via
`_observed_precommit_mode` and `_observed_mcp_mode`, both of which reuse the renderer's
own shape sources (`entry_prefix_for_mode`, `_MODE_MCP_LAUNCH`) rather than a second
hardcoded comparator. The collector is wired into `diagnose()` behind the existing
exception guard so a malformed workspace degrades to `CLEAN`.

The resolver (S21) gained `_resolve_mode_mismatch`, an advisory warning naming both
remediation commands (`install --upgrade` and an explicit `--mode` re-run) on
`MISMATCH`, and the non-canonical precommit advisory was reworded to name the
mode-appropriate entry prefix instead of a hardcoded dependency-mode string.

`_enforce_version_floor` (S22) landed in `core/resolver.py`: it reads the committed
declaration's `minimum_vaultspec_version` and raises a typed `VaultSpecError` naming the
floor, the running version, and the upgrade command when the running package version
parses below the floor. No declaration, no floor, or unparseable versions are all
treated as "no constraint."

WorkspaceFactory-based tests closed the phase: S23 verifies
`collect_mode_mismatch_state` in both directions against artifacts from real installs of
the opposite mode; S24 verifies the resolver's mismatch advisory fires only on
`MISMATCH` and that `collect_precommit_state` reports `COMPLETE` for a correctly
provisioned tool-mode workspace; S25 verifies the floor refusal at all three thresholds
(above, at, and below the running version) through the real `resolve()` invocation
surface.

## Review revisions

Three fixes landed after phase review:

- `d4c8f634` (CRITICAL): surfaced the mode-mismatch and floor signals on `doctor`, which
  S21 and S22 had left un-surfaced because `resolve()` short-circuits to an empty plan
  for the `DOCTOR` action. The floor evaluation was extracted into a single shared
  comparator, `evaluate_version_floor`, consumed by both the refuse-and-tell path and a
  new report-on-doctor error row weighted into the exit code.
- `ff75f3a3`: routed the preflight `resolve()` refusal through the clean error handler
  so a below-floor invocation exits cleanly instead of crashing.
- `93ecf848`: added tests pinning the mode-mismatch partial-state guarantees and
  recorded a LOW note (carried into the S33 ADR review) that `parse_version_tuple`
  strips PEP 440 dev/pre suffixes, so a running version such as `X.dev0` compares equal
  to `X` against a floor of `X`.

## Verification

Collector and resolver tests stayed green throughout (58 and 45 passed respectively at
each checkpoint). `ruff check` and `ty check` were clean. The doctor-surfacing gap and
the preflight crash were both CRITICAL findings closed before phase sign-off.
