---
tags:
  - '#audit'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - "[[2026-07-13-install-mode-plan]]"
  - "[[2026-07-13-install-mode-adr]]"
---

# `install-mode` audit: `mode-aware provisioning verification`

## Scope

This audit closes out the Verify phase for the `install-mode` feature: the `InstallMode` axis threaded through workspace persistence (`core/workspace_mode.py`), provision-time resolution (`core/commands.py`, `cli/root.py`), the mode-aware MCP and pre-commit renderers (`core/mcps.py`, `core/commands.py`), the doctor's mode-mismatch and version-floor diagnosis (`core/diagnosis/`, `core/resolver.py`, `cli/spec_cmd.py`), and the `install --upgrade` migration inference. Plan `2026-07-13-install-mode-plan` closed 33/33 steps across five phases; this audit consolidates the five phase-boundary reviews recorded in the step records and commit history, then adds independent spot checks: a fresh tool-mode install end to end, this repository's own now-pinned dependency-mode declaration, and the below-floor refusal message on `sync`.

## Findings

### mode-neutral-mcp-comparator | critical | resolved: doctor compared deployed MCP entries against unrendered placeholder tokens

The P03 phase review found `collect_mcp_config_state` comparing the deployed `.mcp.json` entries against `collect_mcp_servers()` called with no mode, so the expected side was the mode-neutral token-shaped builtin, which can never equal a rendered entry in either mode. `spec doctor` therefore reported a registry drift warning on every workspace, including this repository's own self-hosted state, contradicting the plan's requirement that this repo diagnose clean. Fixed in commit `8e72b6ec` by resolving the render mode via `resolve_render_mode` (legacy-absent bridges to dependency mode) and threading it into `collect_mcp_servers`, mirroring the pattern `collect_precommit_state` already used. New WorkspaceFactory coverage provisions real tool- and dependency-mode workspaces and asserts the ok signal, plus a hand-altered-entry case asserting registry drift, closing the test gap that let the defect ship (the prior tests never reached the comparison branch).

### preflight-refusal-traceback | high | resolved: resolve refusals escaped the clean error handler on preflight paths

The P04 phase review found `_run_preflight` in `cli/root.py` called the resolver directly with no exception handling, so a typed refusal (the below-floor version constraint) surfaced as a raw traceback on `sync` and other preflight-routed commands instead of the clean, human- or JSON-formatted error the mutating install path already used. Fixed in commit `ff75f3a3` by routing the resolver call through the same `_handle_error` path other commands use. Independently reproduced end to end: a scratch workspace with a floor of `999.0.0` and `sync` run against it now exits 1 with the below-floor error message and a `uv tool upgrade` hint, no traceback.

### doctor-missing-mode-signals | high | resolved: mode-mismatch and version-floor signals computed but never rendered

The P04 phase review found `ModeMismatchSignal` and the version-floor evaluation were wired into `WorkspaceDiagnosis` but never reached `_render_diagnosis_table` or `_doctor_exit_code` in `cli/spec_cmd.py`, so a mismatched or below-floor workspace showed no signal on `spec doctor` at all, an intent-domain gap against the ADR's Q4 decision that doctor gains a mode-mismatch check and a floor error row. Fixed in commit `d4c8f634`: an install-mode row (ok, warn on mismatch, or informational on an undeclared legacy workspace) and a version-floor error row now render through the shared `evaluate_version_floor` and `_observed_precommit_mode` comparators, and both feed the exit-code aggregation (mismatch as warning, below-floor as error). A fresh tool-mode scratch install shows the install-mode ok row on `spec doctor`.

### install-mode-refusal-coverage | low | resolved: refusal path and declaration validation gaps closed

Two smaller P02 phase-review findings: the dependency-mode refusal path (no `pyproject.toml`) lacked gate-visible unit coverage (fixed in `f6ffde8c`), and `resolve_install_mode` did not fail fast on a corrupt persisted `workspace.json`, deferring the error to a later, less clear failure point (fixed in `c721a774`, which validates the persisted declaration up front). Both are test-and-validation hardening with no behavioral surprise beyond the fix itself.

### vault-check-hygiene-drift | low | resolved at closeout: feature vault check brought back to clean

At audit time `vault check all --feature install-mode` reported leftover template annotations in the phase-summary records and a stale feature index. Resolved during closeout by the summary-authoring pass (`vault sanitize annotations`, `vault check all --fix`, `vault feature index -f install-mode`); the closing verification below reflects the post-fix state.

### mode-flip-force-asymmetry | medium | open: migration inference can leave the MCP entry stale on a mode flip

On `install --upgrade`, the pre-commit hook renderer rewrites its canonical entries unconditionally, but the MCP sync path is force-gated: a pre-existing managed entry that diverges from the newly-inferred mode is skipped unless `--force` is passed. In a real migration where a stale MCP entry from the old mode is still present, a bare upgrade can flip the persisted declaration and the hook entries to the new mode while leaving the MCP launch command in the old mode's shape until a forced re-sync. This does not corrupt state, and the mode-mismatch doctor signal catches and reports the divergence, but the migration is not atomic across all three renderers in the non-force path. Tracked as a follow-up: either force the MCP renderer on a detected mode flip specifically, or warn explicitly at upgrade time.

### workspace-declaration-committed | medium | resolved at closeout: this repository's own mode declaration pinned

This self-hosting repository does not list `vaultspec-core` in its own dependencies (it is the package), so a bare `install --upgrade` would have inferred tool mode, contradicting the ADR's premise that this repo stays dependency-mode by explicit choice. Resolved at closeout: `install --mode dependency --upgrade` wrote the committed `.vaultspec/workspace.json` declaring dependency mode, and `spec doctor` reports the install-mode ok row. No `minimum_vaultspec_version` floor is set for this repo yet; setting one is a discretionary follow-up now that the mechanism exists.

### version-floor-dev-suffix | low | open, accepted: dev-suffix versions pass a floor they are technically below

`parse_version_tuple` in `core/helpers.py` strips at the first non-digit-or-dot character, so a dev build of the floor version parses equal to the floor and passes the hard refusal. This is inherited from the single shared version comparator the codebase uses everywhere; forking a stricter floor-only comparator would violate the ADR's no-bespoke-comparator constraint. Accepted and documented; revisit only if pre-release floor precision becomes a real need.

## Recommendations

- Track the upgrade-time MCP force-gate asymmetry as a small follow-up: force the MCP renderer on a detected mode flip, or surface an explicit upgrade-time warning when the declaration and hooks flip while the MCP entry is left unforced.
- Consider setting a `minimum_vaultspec_version` floor for this repository now that the mechanism exists.
- No action on the version-floor dev-suffix behavior beyond the documentation already in place.

**Verdict: PASS.** All CRITICAL and HIGH findings from the phase-boundary reviews are resolved and independently reproduced as fixed. The three independent spot checks hold: a fresh tool-mode install renders `uvx` artifacts and diagnoses clean, this repository's committed dependency-mode declaration diagnoses the install-mode ok row, and a below-floor workspace refuses `sync` with a clean remediation message. The full unit gate stands at 1652 passed with zero failures. The one open MEDIUM item is a bounded, doctor-visible migration asymmetry tracked as a follow-up; it does not block merge.
