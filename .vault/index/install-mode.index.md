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

### plan

- `2026-07-13-install-mode-plan` - `install-mode` plan

### research

- `2026-07-13-install-mode-research` - `install-mode` research: `provisioning as tool versus dependency`
