---
tags:
  - '#plan'
  - '#install-cmds'
date: '2026-03-15'
modified: '2026-07-31'
body_hash: 'sha256:805f4c642b2ef2608f77dd91b5050f955c76d3ba4beea1b14e410f8e1c4ea4f7'
tier: L2
related:
  - '[[2026-03-16-managed-content-blocks-adr]]'
  - '[[2026-03-15-claude-code-provider-research]]'
---

# `install-cmds` implementation plan

## Steps

### Phase `P01` - grounding research

verify each provider's official config, rules, skills, agents, and hooks locations before implementation

- [x] `P01.S01` - verify each provider's root config, rules, skills, agents, and hooks locations against official docs; `.vault/research/2026-03-15-claude-code-provider-research.md`.

### Phase `P02` - provider capability model

formalize provider capabilities as an enum instead of implicit None-checking on ToolConfig fields

- [x] `P02.S02` - add ProviderCapability enum and populate capabilities on ToolConfig per provider; `src/vaultspec_core/core/enums.py`.

### Phase `P03` - install command

add provider targeting, dry-run manifests, and safe upgrade behavior to the install command

- [x] `P03.S03` - add provider positional argument, dry-run manifest, and non-destructive upgrade to the install command; `src/vaultspec_core/cli/root_install.py`.

### Phase `P04` - uninstall command

add provider targeting and dry-run manifests to the uninstall command

- [x] `P04.S04` - add provider positional argument and dry-run manifest to the uninstall command; `src/vaultspec_core/cli/root_install.py`.

### Phase `P05` - sync command

drive sync from the provider capability model with clear errors for uninstalled providers

- [x] `P05.S05` - drive per-provider sync from ProviderCapability and reject sync of an uninstalled provider with a clear error; `src/vaultspec_core/core/provider_sync.py`.

### Phase `P06` - user-level scope model

document the project-vs-user scope extension point without implementing it in this feature

- [ ] `P06.S06` - define the project-vs-user scope extension point without implementing user-level scope; `src/vaultspec_core/core/types.py`.
