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

### plan

- `2026-07-13-install-mode-plan` - `install-mode` plan

### research

- `2026-07-13-install-mode-research` - `install-mode` research: `provisioning as tool versus dependency`
