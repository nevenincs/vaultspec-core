---
tags:
  - '#exec'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S33'
related:
  - "[[2026-07-13-install-mode-plan]]"
---

# Review the complete mode-awareness surface against the ADR's Q1 through Q6 decisions and close out any deviations found

## Scope

- `.vault/adr/2026-07-13-install-mode-adr.md`

## Description

- Trace each ADR decision Q1 through Q6 to its shipped symbol and verify the
  implementation matches the decision.
- Address the three supervision items: the parse_version_tuple dev-suffix LOW
  note from S22, the doctor surfaces added in the P04 revision, and the
  legacy-bridge and migration interplay.
- Regenerate the install-mode feature index and confirm
  `vault check all --feature install-mode` is clean.

## Outcome

Every ADR decision is implemented as specified. Verdict per question:

Q1 (persistence home): CONFORMS. The committed shared declaration is
`WorkspaceDeclaration` persisted to `.vaultspec/workspace.json` by
`write_workspace_declaration` in `core/workspace_mode.py`; the per-machine echo
is `ManifestData.resolved_mode` and `resolved_floor_version` in `core/manifest.py`,
written from the same provision-time resolution via `_persist_resolved_mode` in
`core/commands.py`. The floor lives on the committed declaration, not the
gitignored manifest, as decided.

Q2 (tool-mode MCP launch): CONFORMS. `render_mcp_definition_for_mode` and the
`_MODE_MCP_LAUNCH` table in `core/mcps.py` render tool mode as
`uvx --from vaultspec-core python -m vaultspec_core.mcp_server.app` (module
invocation, immune to the exe-lock class) and dependency mode as the `uv run`
module form. The builtin definition carries mode-neutral tokens substituted at
sync time, the single-copy template approach the ADR preferred over a second
variant.

Q3 (tool-mode hook entries): CONFORMS. `entry_prefix_for_mode` in
`core/commands.py` renders tool mode as `uvx --from vaultspec-core vaultspec-core`,
and `canonical_precommit_hooks_for_mode` sets `language: system`, preserving the
repo's convention and prek compatibility.

Q4 (mode-aware diagnosis and version-skew handshake): CONFORMS.
`collect_precommit_state` in `core/diagnosis/collectors.py` derives the expected
canonical entries from the persisted mode via `resolve_render_mode` rather than a
hardcoded prefix. The floor constraint is the single shared comparator
`evaluate_version_floor` in `core/workspace_mode.py`, consumed by both the
refuse-and-tell path (`_enforce_version_floor` in `core/resolver.py`) and the
report-on-doctor row (`VersionFloorSignal` in `core/diagnosis/diagnosis.py`),
while the manifest-stamp comparison stays as the softer informational drift
warning.

Q5 (provision-time detection and precedence): CONFORMS. `resolve_install_mode`
in `core/workspace_mode.py` implements explicit over persisted over detection
over default, with detection reading pyproject presence plus a vaultspec-core
listing across `[project.dependencies]`, `[project.optional-dependencies]`,
PEP 735 `[dependency-groups]`, and `[tool.uv.dev-dependencies]`. The `--mode`
flag is on `cmd_install` in `cli/root.py`; the impossible combination
(`--mode dependency` with no pyproject) is a hard `VaultSpecError` refusal, not a
silent fallback.

Q6 (migration): CONFORMS. `_infer_upgrade_mode` in `core/commands.py` records an
inferred mode on `install --upgrade` for a workspace with no declaration, and
`resolve_render_mode` returns dependency mode on an absent declaration so a legacy
workspace stays byte-identical until upgrade. The doctor mode-mismatch check is
`collect_mode_mismatch_state` in `core/diagnosis/collectors.py`, surfaced through
`_resolve_mode_mismatch` in `core/resolver.py`, routed through the same
`_observed_precommit_mode` comparator, honoring the no-second-comparator
constraint.

## Notes

Three supervision items, addressed:

(a) parse_version_tuple dev-suffix (S22 LOW note): stands. `parse_version_tuple`
in `core/helpers.py` splits at the first non-digit-or-dot character, so `X.dev0`
parses to the same tuple as `X` and a running `X.dev0` passes a floor of `X`
rather than being treated as below it. This is inherited from the one shared
version comparator the whole codebase uses; introducing a stricter floor-only
comparison would fork version semantics and violate the ADR's no-bespoke-comparator
constraint. Accepted as a documented boundary condition.

(b) doctor surfaces (P04 revision): confirmed present and correct. The doctor
renders a below-floor error row weighted into the exit code, and the mode-mismatch
signal is surfaced as an advisory warning; both route through the shared
comparators (`evaluate_version_floor`, `_observed_precommit_mode`) rather than
parallel checks, satisfying the diagnosis-surface-parity discipline the ADR
requires.

(c) legacy-bridge and migration interplay: coherent, with one operational note.
For any coherent legacy workspace the inference lands on the mode that matches the
deployed shape, because uv-run-shaped hooks presuppose that vaultspec-core
resolves through the project venv (i.e. it is a listed dependency), so the
pyproject-listing signal and the hook-shape signal agree and no artifact is
flipped. The S27 tool-shaped test deliberately removes the pyproject to force a
flip and isolate the render-ordering fix; that contrived state is the only way the
hook-versus-MCP force-gate asymmetry (a managed MCP entry that diverges from the
target mode is skipped under a non-force upgrade, while hooks rewrite
unconditionally) becomes observable, so it is not a real migration defect and no
change is warranted in this plan's scope.

One deviation between the ADR's premise and this repository's reality, recorded
for rollout rather than fixed in code: the ADR states this repository stays
dependency-mode partly on the strength of an "existing pyproject.toml dependency",
but this self-hosting repo does not list vaultspec-core in its own dependency set
(it is the package), and carries no committed `workspace.json` yet. A bare
`install --upgrade` here would therefore infer tool mode. The inference is correct
per Q6; the repository's dependency-mode status must be established by the
explicit-choice path the ADR names (a committed declaration or
`install --mode dependency`) at rollout, before any bare upgrade. This is an
operational action, not a code fix, and is surfaced in the completion report.

Housekeeping: regenerated the install-mode feature index and confirmed
`vault check all --feature install-mode` reports every check clean.
