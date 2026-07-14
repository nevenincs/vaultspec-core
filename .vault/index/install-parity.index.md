---
generated: true
tags:
  - '#index'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
related:
  - '[[2026-07-14-install-parity-W01-P01-S01]]'
  - '[[2026-07-14-install-parity-W01-P01-S02]]'
  - '[[2026-07-14-install-parity-W01-P01-S03]]'
  - '[[2026-07-14-install-parity-W01-P01-S04]]'
  - '[[2026-07-14-install-parity-W01-P01-S05]]'
  - '[[2026-07-14-install-parity-W01-P01-S06]]'
  - '[[2026-07-14-install-parity-W01-P01-S07]]'
  - '[[2026-07-14-install-parity-W01-P02-S08]]'
  - '[[2026-07-14-install-parity-W01-P02-S09]]'
  - '[[2026-07-14-install-parity-W01-P02-S10]]'
  - '[[2026-07-14-install-parity-W01-P02-S11]]'
  - '[[2026-07-14-install-parity-W01-P02-S12]]'
  - '[[2026-07-14-install-parity-W01-P02-S13]]'
  - '[[2026-07-14-install-parity-adr]]'
  - '[[2026-07-14-install-parity-plan]]'
  - '[[2026-07-14-install-parity-research]]'
---

# `install-parity` feature index

Auto-generated index of all documents tagged with `#install-parity`.

## Documents

### adr

- `2026-07-14-install-parity-adr` - `install-parity` adr: `companion provisioning parity and the three-placement mode model` | (**status:** `accepted`)

### exec

- `2026-07-14-install-parity-W01-P01-S01` - Add the DEV member to InstallMode with a docstring describing dev-scoped, non-leaking bookkeeping semantics
- `2026-07-14-install-parity-W01-P01-S02` - Add a render_mode aliasing helper that maps DEV to DEPENDENCY and passes TOOL and DEPENDENCY through unchanged, as the single rendering-time comparator
- `2026-07-14-install-parity-W01-P01-S03` - Add a PackageDeclaration dataclass (mode, minimum_vaultspec_version) and bump WORKSPACE_SCHEMA_VERSION to 2.0 for the per-package packages map shape
- `2026-07-14-install-parity-W01-P01-S04` - Rewrite read_workspace_declaration to parse the v2 packages map and fold a legacy v1 single-key file into packages keyed to the current package on read
- `2026-07-14-install-parity-W01-P01-S05` - Rewrite write_workspace_declaration to serialize the v2 packages map canonically with sorted keys and the schema_version 2.0 stamp
- `2026-07-14-install-parity-W01-P01-S06` - Add read_package_declaration and write_package_declaration helpers that read-modify-write a single package's entry under the advisory lock without clobbering sibling packages
- `2026-07-14-install-parity-W01-P01-S07` - Add legacy v1-to-v2 fold tests and mixed-package configuration round-trip tests using WorkspaceFactory and real filesystem writes
- `2026-07-14-install-parity-W01-P02-S08` - Generalize dependency detection to report both project-dependency and default-dev-group evidence for a named distribution, keeping a core-scoped wrapper for the existing call sites
- `2026-07-14-install-parity-W01-P02-S09` - Add a package parameter to resolve_install_mode and insert DEV into the Q5 precedence chain ahead of the TOOL default when dev-group evidence is found
- `2026-07-14-install-parity-W01-P02-S10` - Accept dev as a valid --mode token for cmd_install and update its help text to document all three provisioning modes
- `2026-07-14-install-parity-W01-P02-S11` - Add a warn-only dependency-leak advisory to resolve() that appends a plan warning when a package's declared mode is DEPENDENCY, never refusing the placement
- `2026-07-14-install-parity-W01-P02-S12` - Add DEV precedence and dev-group detection tests covering both packages and the mixed dependency-plus-dev-group configuration
- `2026-07-14-install-parity-W01-P02-S13` - Add resolver tests asserting the dependency-leak advisory fires for a DEPENDENCY-mode package and stays silent for TOOL or DEV mode

### plan

- `2026-07-14-install-parity-plan` - `install-parity` plan

### research

- `2026-07-14-install-parity-research` - `install-parity` research: `companion-project provisioning parity`
