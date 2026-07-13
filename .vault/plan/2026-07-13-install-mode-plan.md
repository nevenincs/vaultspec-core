---
tags:
  - '#plan'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
tier: L2
related:
  - '[[2026-07-13-install-mode-adr]]'
  - '[[2026-07-13-install-mode-research]]'
---

# `install-mode` plan

## Description

Vaultspec-core is development-harness tooling, not a runtime dependency of the
projects it governs. Today every provisioning surface hardcodes the assumption
that `uv run` resolves inside the target project's own venv: the scaffolded
MCP config, all four canonical pre-commit hooks built from
`CANONICAL_ENTRY_PREFIX`, and the drift detector that is supposed to catch
deviation from that assumption. This plan implements the `install-mode` ADR:
provisioning becomes explicitly mode-aware between tool mode (the default,
launched via `uvx`) and dependency mode (the existing `uv run` shape, kept as
a first-class opt-in and exercised by this repository's own self-hosting).
The mode is resolved once at provision time per the ADR's precedence chain,
persisted in a new committed `.vaultspec/workspace.json` declaration, echoed
into the gitignored manifest for local bookkeeping, and threaded through the
MCP definition renderer, the pre-commit hook renderer, and the doctor's
canonical-entry and version-skew checks so a correctly-provisioned workspace
in either mode is never diagnosed as broken. The plan is grounded in the
`install-mode` ADR and its supporting research.

## Steps

### Phase `P01` - mode model and persistence

Introduce the InstallMode enum, the committed workspace declaration surface under .vaultspec/, and the manifest echo fields that record the resolved mode and floor version.

- [x] `P01.S01` - Add the InstallMode enum with TOOL and DEPENDENCY members; `src/vaultspec_core/core/enums.py`.
- [ ] `P01.S02` - Add the WorkspaceDeclaration dataclass and read_workspace_declaration/write_workspace_declaration functions for the committed .vaultspec/workspace.json surface, including the minimum_vaultspec_version floor field; `src/vaultspec_core/core/workspace_mode.py`.
- [ ] `P01.S03` - Extend ManifestData with resolved_mode and resolved_floor_version echo fields plus their read and write round trip in read_manifest_data and write_manifest_data; `src/vaultspec_core/core/manifest.py`.
- [ ] `P01.S04` - Add WorkspaceFactory-based tests covering workspace.json round trip, missing-file default, corrupted JSON, and malformed mode value handling; `src/vaultspec_core/tests/cli/test_workspace_mode.py`.
- [ ] `P01.S05` - Extend the manifest tests with the ManifestData resolved_mode and resolved_floor_version echo fields, covering read, write, and legacy-manifest backward compatibility; `src/vaultspec_core/tests/cli/test_manifest_v2.py`.

### Phase `P02` - mode resolution at provision time

Add the install --mode flag and the Q5 precedence chain (explicit, persisted, detection, default) that resolves and persists the workspace mode once at provision time, refusing loudly on conflicts.

- [ ] `P02.S06` - Add the --mode option to cmd_install accepting tool and dependency values and thread it through to install_run; `src/vaultspec_core/cli/root.py`.
- [ ] `P02.S07` - Add resolve_install_mode implementing the Q5 precedence chain (explicit flag, persisted declaration, pyproject.toml detection, default tool mode) plus the pyproject.toml dependency probe helper; `src/vaultspec_core/core/workspace_mode.py`.
- [ ] `P02.S08` - Wire resolve_install_mode into install_run so the mode is resolved once at provision time, persisted to workspace.json, and an explicit --mode request that conflicts with detection raises a loud VaultSpecError refusal; `src/vaultspec_core/core/commands.py`.
- [ ] `P02.S09` - Add WorkspaceFactory-based tests for resolve_install_mode precedence ordering: explicit overrides persisted and detected, persisted overrides detected, and detected overrides default; `src/vaultspec_core/tests/cli/test_workspace_mode.py`.
- [ ] `P02.S10` - Add WorkspaceFactory-based tests for the detection signals: absence of pyproject.toml forces tool mode, vaultspec-core listed in project dependencies forces dependency-mode evidence, and absence of both defaults to tool mode; `src/vaultspec_core/tests/cli/test_workspace_mode.py`.
- [ ] `P02.S11` - Add a WorkspaceFactory-based install_run test asserting a hard refusal with a remediation message when --mode dependency is requested in a repo with no pyproject.toml; `src/vaultspec_core/tests/cli/test_ambiguous_states.py`.

### Phase `P03` - mode-aware renderers

Make the builtin MCP definition and the four canonical pre-commit hook entries mode-parameterized, rendering the uvx module-invocation form in tool mode and the existing uv run form in dependency mode.

- [ ] `P03.S12` - Introduce mode placeholder tokens in the builtin MCP definition command and args fields, keeping the seeded builtin snapshot mode-neutral for drift-detection hashing; `src/vaultspec_core/builtins/mcps/vaultspec-core.builtin.json`.
- [ ] `P03.S13` - Add a render_mcp_definition_for_mode function that substitutes the placeholder command and args with the uv run python -m form in dependency mode and the uvx --from vaultspec-core python -m form in tool mode, and apply it in collect_mcp_servers before merge; `src/vaultspec_core/core/mcps.py`.
- [ ] `P03.S14` - Turn CANONICAL_ENTRY_PREFIX, the \_HOOK_DEFS entry values, CANONICAL_PRECOMMIT_HOOKS, and CANONICAL_HOOK_ENTRIES into functions of the resolved InstallMode, rendering uv run --no-sync vaultspec-core in dependency mode and uvx --from vaultspec-core vaultspec-core in tool mode; `src/vaultspec_core/core/commands.py`.
- [ ] `P03.S15` - Update \_scaffold_precommit to read the resolved workspace mode and render hook entries through the mode-parameterized hook definitions; `src/vaultspec_core/core/commands.py`.
- [ ] `P03.S16` - Add WorkspaceFactory-based tests asserting the MCP definition renders the uv run command form in dependency mode and the uvx --from form in tool mode after sync; `src/vaultspec_core/tests/cli/test_mcp_provider_files.py`.
- [ ] `P03.S17` - Add WorkspaceFactory-based tests asserting all four canonical hook entries render the uv run --no-sync vaultspec-core prefix in dependency mode and the uvx --from vaultspec-core vaultspec-core prefix in tool mode; `src/vaultspec_core/tests/cli/test_flow_bugs.py`.

### Phase `P04` - mode-aware diagnosis and floor constraint

Route the precommit canonical-entry check and a new mode-mismatch signal through the persisted mode, and layer a minimum_vaultspec_version refuse-and-tell floor constraint onto the existing version-warning comparator.

- [ ] `P04.S18` - Add the ModeMismatchSignal enum with CLEAN, MISMATCH, and UNKNOWN members; `src/vaultspec_core/core/diagnosis/signals.py`.
- [ ] `P04.S19` - Add the mode_mismatch field to WorkspaceDiagnosis and wire it through the diagnose orchestrator; `src/vaultspec_core/core/diagnosis/diagnosis.py`.
- [ ] `P04.S20` - Add collect_mode_mismatch_state comparing the persisted workspace declaration mode against the observed hook-entry and MCP-command shape, and update collect_precommit_state to derive the expected canonical entries from the persisted mode instead of the hardcoded CANONICAL_HOOK_ENTRIES; `src/vaultspec_core/core/diagnosis/collectors.py`.
- [ ] `P04.S21` - Add a resolution step for ModeMismatchSignal.MISMATCH with a fix hint pointing at install --upgrade or an explicit --mode re-run, and reword the non-canonical precommit warning to be mode-aware; `src/vaultspec_core/core/resolver.py`.
- [ ] `P04.S22` - Layer a minimum_vaultspec_version refuse-and-tell check onto \_resolve_version_warning that hard-refuses with a remediation message when the running package version is below the persisted floor constraint; `src/vaultspec_core/core/resolver.py`.
- [ ] `P04.S23` - Add WorkspaceFactory-based tests for collect_mode_mismatch_state detecting uv run hook entries and a non-uvx MCP command in a tool-mode workspace, and the reverse mismatch in a dependency-mode workspace; `src/vaultspec_core/tests/cli/test_collectors.py`.
- [ ] `P04.S24` - Add WorkspaceFactory-based tests asserting the resolver emits a mode-mismatch fix-hint step with the correct remediation target and that collect_precommit_state reports COMPLETE for a correctly-provisioned tool-mode workspace; `src/vaultspec_core/tests/cli/test_collectors.py`.
- [ ] `P04.S25` - Add WorkspaceFactory-based tests asserting the floor-constraint refusal fires when the running package version is below minimum_vaultspec_version and passes when at or above it; `src/vaultspec_core/tests/cli/test_migration_triggers.py`.

### Phase `P05` - migration, docs, and hardening

Infer and persist mode for legacy workspaces on install --upgrade, update mode-aware documentation touchpoints, regenerate the CLI reference, and close with a full gate run and review.

- [ ] `P05.S26` - Implement Q6 migration inference in install_run so install --upgrade against a workspace with no persisted mode infers dependency mode from a uv run-shaped canonical hook entry and a pyproject.toml dependency listing, tool mode otherwise, and records the inferred declaration; `src/vaultspec_core/core/commands.py`.
- [ ] `P05.S27` - Add WorkspaceFactory-based tests for the install --upgrade migration inference covering a legacy dependency-mode workspace, a legacy tool-shaped workspace, and idempotency on a second upgrade run; `src/vaultspec_core/tests/cli/test_migration_triggers.py`.
- [ ] `P05.S28` - Update the MCP setup section with mode-aware launch command guidance for both tool mode and dependency mode; `docs/MCP.md`.
- [ ] `P05.S29` - Update the getting-started and MCP touchpoints to describe install mode selection and the tool-mode default; `README.md`.
- [ ] `P05.S30` - Update the framework overview to document the mode axis alongside the existing provisioning concepts; `docs/framework.md`.
- [ ] `P05.S31` - Regenerate the CLI reference so the install --mode option and its help text appear in the generator-managed reference; `src/vaultspec_core/builtins/reference/cli.md`.
- [ ] `P05.S32` - Run the full unit gate and fix any regressions surfaced by the mode-awareness changes; `src/vaultspec_core`.
- [ ] `P05.S33` - Review the complete mode-awareness surface against the ADR's Q1 through Q6 decisions and close out any deviations found; `.vault/adr/2026-07-13-install-mode-adr.md`.

## Parallelization

Phases carry a hard dependency chain and are executed in sequence: P02's mode
resolution depends on P01's persistence surface; P03's renderers depend on
P02 resolving and persisting a mode to render against; P04's diagnosis and
floor-constraint checks depend on P03's mode-parameterized renderers existing
to compare against; P05's migration inference and documentation depend on
every prior phase landing. Within each phase, the implementation Steps are
sequential (a Step that edits a module generally precedes the Step that wires
a caller into it), but the test Step or Steps closing out a phase may run in
parallel with each other once the implementation Steps in that phase are
closed, since each test Step targets an independent test module or an
independent scenario within one test module.

## Verification

The plan is complete when every Step is closed (`- [x]`). Concretely:

- `uv run --no-sync pytest src/vaultspec_core -m "unit and not gemini and not claude"`
  passes with zero failures and zero new skips.
- A WorkspaceFactory-built tool-mode workspace renders the MCP definition and
  all four canonical hook entries in the `uvx --from vaultspec-core` form, and
  `collect_precommit_state` and `collect_mode_mismatch_state` report a clean
  state for it.
- A WorkspaceFactory-built dependency-mode workspace renders the existing
  `uv run --no-sync vaultspec-core` form unchanged, and this repository's own
  self-hosted dependency-mode workspace continues to diagnose clean.
- `install --mode dependency` in a repository with no `pyproject.toml`
  refuses with a remediation message instead of silently falling back to
  tool mode.
- `install --upgrade` against a legacy workspace with no persisted mode
  infers and persists a mode per the Q6 detection order, and a second
  upgrade run is idempotent.
- A workspace whose running package version is below its persisted
  `minimum_vaultspec_version` refuses at invocation start with a remediation
  message.
- `docs/MCP.md`, `README.md`, `docs/framework.md`, and the generated CLI
  reference describe the mode axis and contain no leftover `{...}`
  placeholders.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-07-13-install-mode-plan.md`
  and `uv run --no-sync vaultspec-core vault check all --feature install-mode`
  report clean.
- The P05 review Step confirms every one of the ADR's Q1 through Q6 decisions
  is implemented as specified, with any deviation recorded and resolved.
