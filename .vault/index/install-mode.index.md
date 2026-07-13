---
generated: true
tags:
  - '#index'
  - '#install-mode'
date: '2026-07-13'
modified: '2026-07-13'
related:
  - '[[2026-07-13-install-mode-P01-S01]]'
  - '[[2026-07-13-install-mode-P01-S02]]'
  - '[[2026-07-13-install-mode-P01-S03]]'
  - '[[2026-07-13-install-mode-P01-S04]]'
  - '[[2026-07-13-install-mode-P01-S05]]'
  - '[[2026-07-13-install-mode-P02-S06]]'
  - '[[2026-07-13-install-mode-P02-S07]]'
  - '[[2026-07-13-install-mode-P02-S08]]'
  - '[[2026-07-13-install-mode-P02-S09]]'
  - '[[2026-07-13-install-mode-P02-S10]]'
  - '[[2026-07-13-install-mode-P02-S11]]'
  - '[[2026-07-13-install-mode-P03-S12]]'
  - '[[2026-07-13-install-mode-P03-S13]]'
  - '[[2026-07-13-install-mode-P03-S14]]'
  - '[[2026-07-13-install-mode-P03-S15]]'
  - '[[2026-07-13-install-mode-P03-S16]]'
  - '[[2026-07-13-install-mode-P03-S17]]'
  - '[[2026-07-13-install-mode-P04-S18]]'
  - '[[2026-07-13-install-mode-P04-S19]]'
  - '[[2026-07-13-install-mode-P04-S20]]'
  - '[[2026-07-13-install-mode-P04-S21]]'
  - '[[2026-07-13-install-mode-P04-S22]]'
  - '[[2026-07-13-install-mode-P04-S23]]'
  - '[[2026-07-13-install-mode-P04-S24]]'
  - '[[2026-07-13-install-mode-P04-S25]]'
  - '[[2026-07-13-install-mode-P05-S26]]'
  - '[[2026-07-13-install-mode-P05-S27]]'
  - '[[2026-07-13-install-mode-P05-S28]]'
  - '[[2026-07-13-install-mode-P05-S29]]'
  - '[[2026-07-13-install-mode-P05-S30]]'
  - '[[2026-07-13-install-mode-P05-S31]]'
  - '[[2026-07-13-install-mode-P05-S32]]'
  - '[[2026-07-13-install-mode-adr]]'
  - '[[2026-07-13-install-mode-plan]]'
  - '[[2026-07-13-install-mode-research]]'
---

# `install-mode` feature index

Auto-generated index of all documents tagged with `#install-mode`.

## Documents

### adr

- `2026-07-13-install-mode-adr` - `install-mode` adr: `provisioning is mode-aware and tool-first` | (**status:** `accepted`)

### exec

- `2026-07-13-install-mode-P01-S01` - Add the InstallMode enum with TOOL and DEPENDENCY members
- `2026-07-13-install-mode-P01-S02` - Add the WorkspaceDeclaration dataclass and read_workspace_declaration/write_workspace_declaration functions for the committed .vaultspec/workspace.json surface, including the minimum_vaultspec_version floor field
- `2026-07-13-install-mode-P01-S03` - Extend ManifestData with resolved_mode and resolved_floor_version echo fields plus their read and write round trip in read_manifest_data and write_manifest_data
- `2026-07-13-install-mode-P01-S04` - Add WorkspaceFactory-based tests covering workspace.json round trip, missing-file default, corrupted JSON, and malformed mode value handling
- `2026-07-13-install-mode-P01-S05` - Extend the manifest tests with the ManifestData resolved_mode and resolved_floor_version echo fields, covering read, write, and legacy-manifest backward compatibility
- `2026-07-13-install-mode-P02-S06` - Add the --mode option to cmd_install accepting tool and dependency values and thread it through to install_run
- `2026-07-13-install-mode-P02-S07` - Add resolve_install_mode implementing the Q5 precedence chain (explicit flag, persisted declaration, pyproject.toml detection, default tool mode) plus the pyproject.toml dependency probe helper
- `2026-07-13-install-mode-P02-S08` - Wire resolve_install_mode into install_run so the mode is resolved once at provision time, persisted to workspace.json, and an explicit --mode request that conflicts with detection raises a loud VaultSpecError refusal
- `2026-07-13-install-mode-P02-S09` - Add WorkspaceFactory-based tests for resolve_install_mode precedence ordering: explicit overrides persisted and detected, persisted overrides detected, and detected overrides default
- `2026-07-13-install-mode-P02-S10` - Add WorkspaceFactory-based tests for the detection signals: absence of pyproject.toml forces tool mode, vaultspec-core listed in project dependencies forces dependency-mode evidence, and absence of both defaults to tool mode
- `2026-07-13-install-mode-P02-S11` - Add a WorkspaceFactory-based install_run test asserting a hard refusal with a remediation message when --mode dependency is requested in a repo with no pyproject.toml
- `2026-07-13-install-mode-P03-S12` - Introduce mode placeholder tokens in the builtin MCP definition command and args fields, keeping the seeded builtin snapshot mode-neutral for drift-detection hashing
- `2026-07-13-install-mode-P03-S13` - Add a render_mcp_definition_for_mode function that substitutes the placeholder command and args with the uv run python -m form in dependency mode and the uvx --from vaultspec-core python -m form in tool mode, and apply it in collect_mcp_servers before merge
- `2026-07-13-install-mode-P03-S14` - Turn CANONICAL_ENTRY_PREFIX, the \_HOOK_DEFS entry values, CANONICAL_PRECOMMIT_HOOKS, and CANONICAL_HOOK_ENTRIES into functions of the resolved InstallMode, rendering uv run --no-sync vaultspec-core in dependency mode and uvx --from vaultspec-core vaultspec-core in tool mode
- `2026-07-13-install-mode-P03-S15` - Update \_scaffold_precommit to read the resolved workspace mode and render hook entries through the mode-parameterized hook definitions
- `2026-07-13-install-mode-P03-S16` - Add WorkspaceFactory-based tests asserting the MCP definition renders the uv run command form in dependency mode and the uvx --from form in tool mode after sync
- `2026-07-13-install-mode-P03-S17` - Add WorkspaceFactory-based tests asserting all four canonical hook entries render the uv run --no-sync vaultspec-core prefix in dependency mode and the uvx --from vaultspec-core vaultspec-core prefix in tool mode
- `2026-07-13-install-mode-P04-S18` - Add the ModeMismatchSignal enum with CLEAN, MISMATCH, and UNKNOWN members
- `2026-07-13-install-mode-P04-S19` - Add the mode_mismatch field to WorkspaceDiagnosis and wire it through the diagnose orchestrator
- `2026-07-13-install-mode-P04-S20` - Add collect_mode_mismatch_state comparing the persisted workspace declaration mode against the observed hook-entry and MCP-command shape, and update collect_precommit_state to derive the expected canonical entries from the persisted mode instead of the hardcoded CANONICAL_HOOK_ENTRIES
- `2026-07-13-install-mode-P04-S21` - Add a resolution step for ModeMismatchSignal.MISMATCH with a fix hint pointing at install --upgrade or an explicit --mode re-run, and reword the non-canonical precommit warning to be mode-aware
- `2026-07-13-install-mode-P04-S22` - Layer a minimum_vaultspec_version refuse-and-tell check onto \_resolve_version_warning that hard-refuses with a remediation message when the running package version is below the persisted floor constraint
- `2026-07-13-install-mode-P04-S23` - Add WorkspaceFactory-based tests for collect_mode_mismatch_state detecting uv run hook entries and a non-uvx MCP command in a tool-mode workspace, and the reverse mismatch in a dependency-mode workspace
- `2026-07-13-install-mode-P04-S24` - Add WorkspaceFactory-based tests asserting the resolver emits a mode-mismatch fix-hint step with the correct remediation target and that collect_precommit_state reports COMPLETE for a correctly-provisioned tool-mode workspace
- `2026-07-13-install-mode-P04-S25` - Add WorkspaceFactory-based tests asserting the floor-constraint refusal fires when the running package version is below minimum_vaultspec_version and passes when at or above it
- `2026-07-13-install-mode-P05-S26` - Implement Q6 migration inference in install_run so install --upgrade against a workspace with no persisted mode infers dependency mode from a uv run-shaped canonical hook entry and a pyproject.toml dependency listing, tool mode otherwise, and records the inferred declaration
- `2026-07-13-install-mode-P05-S27` - Add WorkspaceFactory-based tests for the install --upgrade migration inference covering a legacy dependency-mode workspace, a legacy tool-shaped workspace, and idempotency on a second upgrade run
- `2026-07-13-install-mode-P05-S28` - Update the MCP setup section with mode-aware launch command guidance for both tool mode and dependency mode
- `2026-07-13-install-mode-P05-S29` - Update the getting-started and MCP touchpoints to describe install mode selection and the tool-mode default
- `2026-07-13-install-mode-P05-S30` - Update the framework overview to document the mode axis alongside the existing provisioning concepts
- `2026-07-13-install-mode-P05-S31` - Regenerate the CLI reference so the install --mode option and its help text appear in the generator-managed reference
- `2026-07-13-install-mode-P05-S32` - Run the full unit gate and fix any regressions surfaced by the mode-awareness changes

### plan

- `2026-07-13-install-mode-plan` - `install-mode` plan

### research

- `2026-07-13-install-mode-research` - `install-mode` research: `provisioning as tool versus dependency`
