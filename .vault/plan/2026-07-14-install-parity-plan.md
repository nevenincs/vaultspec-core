---
tags:
  - '#plan'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
tier: L3
related:
  - '[[2026-07-14-install-parity-adr]]'
  - '[[2026-07-14-install-parity-research]]'
---

# `install-parity` plan

## Wave `W01` - vaultspec-core mode model and rendering parity

Amend the workspace declaration to a per-package schema v2, add the DEV install mode as a rendering alias of DEPENDENCY, generalize detection and resolution to a package parameter, thread per-package rendering through the MCP and pre-commit hook renderers and the doctor's mode-mismatch and version-floor collectors, and update docs and the spec reference; grounded by the install-parity ADR and the install-mode ADR it amends. This wave has no hard ordering dependency and gates wave W02, which floors on the core release this wave ships.

### Phase `W01.P01` - schema v2 and the DEV mode

Move WorkspaceDeclaration from a single-key schema to a per-package map at schema_version 2.0 with a legacy v1 read-fold, and add InstallMode.DEV alongside the single render_mode aliasing helper that lets every renderer treat DEV as DEPENDENCY without a third branch.

- [x] `W01.P01.S01` - Add the DEV member to InstallMode with a docstring describing dev-scoped, non-leaking bookkeeping semantics; `src/vaultspec_core/core/enums.py`.
- [x] `W01.P01.S02` - Add a render_mode aliasing helper that maps DEV to DEPENDENCY and passes TOOL and DEPENDENCY through unchanged, as the single rendering-time comparator; `src/vaultspec_core/core/enums.py`.
- [x] `W01.P01.S03` - Add a PackageDeclaration dataclass (mode, minimum_vaultspec_version) and bump WORKSPACE_SCHEMA_VERSION to 2.0 for the per-package packages map shape; `src/vaultspec_core/core/workspace_mode.py`.
- [x] `W01.P01.S04` - Rewrite read_workspace_declaration to parse the v2 packages map and fold a legacy v1 single-key file into packages keyed to the current package on read; `src/vaultspec_core/core/workspace_mode.py`.
- [x] `W01.P01.S05` - Rewrite write_workspace_declaration to serialize the v2 packages map canonically with sorted keys and the schema_version 2.0 stamp; `src/vaultspec_core/core/workspace_mode.py`.
- [x] `W01.P01.S06` - Add read_package_declaration and write_package_declaration helpers that read-modify-write a single package's entry under the advisory lock without clobbering sibling packages; `src/vaultspec_core/core/workspace_mode.py`.
- [x] `W01.P01.S07` - Add legacy v1-to-v2 fold tests and mixed-package configuration round-trip tests using WorkspaceFactory and real filesystem writes; `src/vaultspec_core/tests/cli/test_workspace_mode.py`.

### Phase `W01.P02` - detection and resolution precedence

Generalize dependency-vs-dev-group detection to a package parameter, add DEV to resolve_install_mode's precedence chain and to the --mode flag vocabulary, and surface a warn-only advisory when a package's declared mode is the full-leak DEPENDENCY state.

- [x] `W01.P02.S08` - Generalize dependency detection to report both project-dependency and default-dev-group evidence for a named distribution, keeping a core-scoped wrapper for the existing call sites; `src/vaultspec_core/core/workspace_mode.py`.
- [x] `W01.P02.S09` - Add a package parameter to resolve_install_mode and insert DEV into the Q5 precedence chain ahead of the TOOL default when dev-group evidence is found; `src/vaultspec_core/core/workspace_mode.py`.
- [x] `W01.P02.S10` - Accept dev as a valid --mode token for cmd_install and update its help text to document all three provisioning modes; `src/vaultspec_core/cli/root.py`.
- [x] `W01.P02.S11` - Add a warn-only dependency-leak advisory to resolve() that appends a plan warning when a package's declared mode is DEPENDENCY, never refusing the placement; `src/vaultspec_core/core/resolver.py`.
- [x] `W01.P02.S12` - Add DEV precedence and dev-group detection tests covering both packages and the mixed dependency-plus-dev-group configuration; `src/vaultspec_core/tests/cli/test_workspace_mode.py`.
- [x] `W01.P02.S13` - Add resolver tests asserting the dependency-leak advisory fires for a DEPENDENCY-mode package and stays silent for TOOL or DEV mode; `src/vaultspec_core/tests/cli/test_resolver.py`.

### Phase `W01.P03` - renderers and diagnosis, per package

Thread the package parameter through resolve_render_mode, the MCP and pre-commit hook renderers, the doctor's mode-mismatch and version-floor collectors, and the upgrade-mode inference path, so each package's renderer and doctor row consult only that package's own entry in the shared map.

- [x] `W01.P03.S14` - Add a package parameter to resolve_render_mode, reading only that package's own entry from the v2 map, with the legacy-absent DEPENDENCY bridge as the default package's fallback; `src/vaultspec_core/core/workspace_mode.py`.
- [x] `W01.P03.S28` - Generalize the MCP launch table from a single hardcoded vaultspec-core module entry to a package-and-module-parameterized render_launch_for_mode helper, keeping vaultspec-core's own launch as the default so companion packages can render through the same sentinel-substitution renderer; `src/vaultspec_core/core/mcps.py`.
- [x] `W01.P03.S15` - Apply the render_mode aliasing helper in render_mcp_definition_for_mode and key mcp_status and mcp_sync's default resolution to resolve_render_mode(target, package='vaultspec-core'); `src/vaultspec_core/core/mcps.py`.
- [x] `W01.P03.S16` - Apply the render_mode aliasing helper in entry_prefix_for_mode and hook_defs_for_mode, and key \_scaffold_precommit's default resolution to resolve_render_mode(target, package='vaultspec-core'); `src/vaultspec_core/core/commands.py`.
- [x] `W01.P03.S17` - Add a package parameter to collect_mode_mismatch_state and collect_version_floor_state, reading the package's own declared mode and floor against its own observed artifact shape; `src/vaultspec_core/core/diagnosis/collectors.py`.
- [x] `W01.P03.S18` - Thread the package parameter through the doctor's mode-mismatch and version-floor rows so core's own row reads core's own map entry; `src/vaultspec_core/core/diagnosis/diagnosis.py`.
- [x] `W01.P03.S19` - Update \_write_mode_declaration and \_infer_upgrade_mode to read and write core's own entry in the v2 packages map via the per-package helpers, preserving sibling package entries untouched; `src/vaultspec_core/core/commands.py`.
- [x] `W01.P03.S20` - Add renderer and doctor tests covering TOOL, DEPENDENCY, and DEV for the core package plus a mixed configuration where a companion package's entry differs, asserting no cross-package branch; `src/vaultspec_core/tests/cli/test_collectors.py`.

### Phase `W01.P04` - docs, reference, and gate

Update user-facing docs and the generated spec reference for --mode dev and per-package declaration, regenerate the reference, and run the full unit gate plus an ADR-conformance review before the wave is considered shippable.

- [x] `W01.P04.S21` - Document the --mode dev flag, the DEV-renders-as-DEPENDENCY nuance, and the v2 per-package workspace.json shape in the MCP and install documentation; `docs/MCP.md`.
- [ ] `W01.P04.S22` - Update the provisioning-mode section to describe the three-mode model and per-package declaration; `README.md`.
- [ ] `W01.P04.S23` - Regenerate the locally-resident CLI reference to reflect the dev mode token and updated --mode help text; `.vaultspec/reference/cli.md`.
- [ ] `W01.P04.S25` - Update the framework overview's install-mode description to name the three-mode model; `docs/framework.md`.
- [ ] `W01.P04.S24` - Run the full unit gate and perform an ADR-conformance review confirming the schema v2 migration, DEV mode, and per-package renderers match the install-parity ADR before the wave is released; `src/vaultspec_core`.

## Wave `W02` - vaultspec-rag mode adoption and parity

Adopt the full analogue surface in vaultspec-rag once its vaultspec-core floor carries the DEV mode and schema v2: an install-time --mode flag threaded through core's resolve_install_mode with package=vaultspec-rag, a tokenized mode-neutral MCP builtin definition substituted by core's renderer, doctor mode-and-floor rows, upgrade-time mode inference, and documentation; grounded by the install-parity ADR. This wave executes only after wave W01 lands in a released vaultspec-core version and rag's pyproject floor is bumped to it; its first Phase is the release gate that blocks the remainder of the wave.

### Phase `W02.P05` - release gate

Block the rest of the wave on a released vaultspec-core version that carries the DEV member and schema v2, then bump rag's own vaultspec-core floor to it.

- [ ] `W02.P05.S26` - Verify the released vaultspec-core version on PyPI carries the DEV member and schema v2 API - this step blocks the remainder of the wave; `pyproject.toml`.
- [ ] `W02.P05.S27` - Bump the vaultspec-core dependency floor and refresh uv.lock to the released version carrying the DEV member and schema v2; `pyproject.toml`.

### Phase `W02.P06` - rag mode adoption

Add the --mode tool|dependency|dev flag to rag's install CLI, thread it through core's resolve_install_mode with package=vaultspec-rag, persist via core's per-package writer into the shared workspace.json, tokenize rag's MCP builtin definition for core's renderer, and add upgrade-time mode inference for the rag package.

- [ ] `W02.P06.S29` - Add a --mode tool|dependency|dev option to handle_install and forward it to install_run; `src/vaultspec_rag/cli/_install.py`.
- [ ] `W02.P06.S30` - Add a mode parameter to install_run that resolves through core's resolve_install_mode with package='vaultspec-rag' and persists the result via core's write_package_declaration into the shared workspace.json; `src/vaultspec_rag/commands/_install.py`.
- [ ] `W02.P06.S31` - Replace the static command and args with core's sentinel tokens, rendering through render_launch_for_mode with package='vaultspec-rag' and module='vaultspec_rag.server' for module-invocation exe-lock parity; `src/vaultspec_rag/builtins/mcps/vaultspec-rag.builtin.json`.
- [ ] `W02.P06.S32` - Add upgrade-time mode inference for the vaultspec-rag package, mirroring core's \_infer_upgrade_mode detection evidence and precedence; `src/vaultspec_rag/commands/_install.py`.
- [ ] `W02.P06.S33` - Leave the --local-only flag and its per-host local-only.json marker unchanged as an orthogonal storage-backend choice, and add a regression test asserting it is not folded into the shared mode declaration; `src/vaultspec_rag/config.py`.
- [ ] `W02.P06.S34` - Add tests covering --mode tool, dependency, and dev for the rag package, the mixed core-dependency-rag-tool configuration, and the tokenized MCP definition's rendered launch shape; `src/vaultspec_rag/tests/test_install_provision.py`.

### Phase `W02.P07` - rag diagnosis, docs, and cross-repo parity review

Add mode-and-floor rows to rag's server doctor for the vaultspec-rag entry, update rag's README and docs, run rag's full test gate, and close the wave with a review confirming both CLIs' install --help surfaces are parity-symmetric.

- [ ] `W02.P07.S35` - Add mode-and-floor rows to the doctor output for the vaultspec-rag entry, reading core's per-package mode-mismatch and version-floor collectors; `src/vaultspec_rag/cli/_service_doctor.py`.
- [ ] `W02.P07.S36` - Document the --mode flag, the three provisioning modes, and the shared per-package workspace.json declaration in the installation guide; `docs/installation.md`.
- [ ] `W02.P07.S37` - Run rag's full test gate covering the new mode, renderer, and doctor tests; `src/vaultspec_rag/tests`.
- [ ] `W02.P07.S38` - Review both CLIs' install --help output side by side and confirm the --mode flag vocabulary, help text, and doctor row shape are parity-symmetric between vaultspec-core and vaultspec-rag; `src/vaultspec_core/cli/root.py`.

## Description

This plan implements the install-parity ADR, which amends the install-mode ADR's
persistence schema and flag vocabulary and extends the resulting three-mode model to
vaultspec-rag. Wave W01 does the core-side work: WorkspaceDeclaration moves from a
single-key schema to a per-package map at schema_version 2.0 with a legacy v1 read-fold,
InstallMode gains a DEV member that renders byte-identically to DEPENDENCY through one
shared aliasing helper, detection and resolution gain a package parameter and a
dev-group evidence branch, and every coupling point install-mode already identified
(MCP renderer, pre-commit hook renderer, doctor's mode-mismatch and version-floor
collectors, upgrade-mode inference) is threaded to read and write only its own
package's entry in the shared map. Wave W02 does the rag-side work described in the
install-parity research's parity table: an install-time --mode flag, a tokenized
mode-neutral MCP definition substituted by core's generalized renderer, doctor
mode-and-floor rows, and upgrade-time mode inference, all calling into core's
workspace_mode module rather than a rag-owned implementation. Wave W02's records live
in this vault even though its Steps' file scopes sit in the vaultspec-rag repository
(Y:/code/vaultspec-rag-worktrees/main); the wave's first Phase is a release gate that
blocks the remainder of the wave on a released vaultspec-core version carrying the DEV
member and schema v2, since rag's own pyproject.toml floors on that core version as a
direct dependency.

## Parallelization

Wave W01 must complete, release, and have its version consumed by rag's floor bump
before Wave W02 can begin; W02.P05 is the explicit gate that enforces this. Within Wave
W01, Phase P01 (schema v2 and the DEV mode) has no dependency on the other Phases and
can start immediately. Phase P02 (detection and resolution) depends on the DEV member
and render_mode helper from P01.S01 and P01.S02, and on the packages-map read and write
path from P01.S03 through P01.S06, so it follows P01. Phase P03 (renderers and
diagnosis) depends on the package-aware resolve_install_mode from P02 and, for its
MCP-renderer step, on the launch-table generalization it introduces in the same Phase;
it follows P02. Phase P04 (docs, reference, and gate) depends on every prior Phase's
surface being final and runs last within the wave. Within Wave W02, Phase P06 (rag mode
adoption) depends on P05's gate and on core's generalized render_launch_for_mode helper
from W01.P03; its Steps are largely sequential since the CLI flag, the resolver call,
the tokenized MCP definition, and upgrade inference build on one another within the
same install path. Phase P07 (rag diagnosis, docs, and cross-repo parity review) follows
P06 and closes the wave. Within each Phase, the dedicated test Step follows the
implementation Steps it covers rather than running in parallel with them.

## Verification

The plan is complete when every Step in this plan is closed (- [x]). Wave W01 is
additionally verified by: the full vaultspec-core unit gate (pytest src/vaultspec_core
-m unit) passing with the new schema-v2, DEV-mode, per-package renderer, and advisory
tests included; `vaultspec-core vault plan check` and `vaultspec-core vault check all --feature install-parity` reporting clean; and the ADR-conformance review Step (P04.S24)
confirming the shipped schema v2 shape, the DEV-renders-as-DEPENDENCY rendering
invariant, and the per-package renderer and doctor wiring match the install-parity
ADR's Implementation section without introducing a second mode comparator. Wave W02 is
additionally verified by: rag's full test gate passing with the new --mode, renderer,
and doctor tests included; the mixed-configuration case (one package dependency-mode,
the other tool- or dev-mode) exercised by both repositories' test suites per the ADR's
Constraints; and the closing cross-repo parity review Step (P07.S38) confirming both
CLIs' install --help output and doctor mode-and-floor rows are symmetric.
