---
tags:
  - '#plan'
  - '#install-cmds'
date: '2026-03-16'
modified: '2026-07-31'
body_hash: 'sha256:00e3de54d0c8122c70fe1b43f8251dcd198c98dfa191e801d0187280d7c93060'
tier: L2
related:
  - '[[2026-03-15-install-cmds-plan]]'
  - '[[2026-03-15-install-cmds-capability-audit]]'
  - '[[2026-03-16-managed-content-blocks-adr]]'
  - '[[2026-03-15-claude-code-provider-research]]'
---

# install-cmds execution plan

### Phase `P01` - provider capability enum and resource additions

add ProviderCapability and the WORKFLOWS resource to the shared enums module

- [x] `P01.S01` - add ProviderCapability enum and Resource.WORKFLOWS; `src/vaultspec_core/core/enums.py`.

### Phase `P02` - ToolConfig and init_paths revision

give every provider a correct config location and an explicit capability set

- [x] `P02.S02` - add capabilities field to ToolConfig and correct per-provider config locations in init_paths; `src/vaultspec_core/core/types.py`.

### Phase `P03` - config_gen revision

generate provider config through the standard TOOL_CONFIGS pipeline, including a TOML adapter for Codex agents

- [x] `P03.S03` - remove the special-cased Codex AGENTS.md generator and add the TOML agent adapter and gemini rule-ref config; `src/vaultspec_core/core/config_gen.py`.

### Phase `P04` - provider manifest

track installed providers so uninstall can protect shared directories

- [x] `P04.S04` - define and maintain the providers.json manifest across install and uninstall; `src/vaultspec_core/core/manifest.py`.

### Phase `P05` - install command revision

add provider targeting, dry-run manifests, and safe upgrade to the install command

- [x] `P05.S05` - add provider positional argument, dry-run manifest, and non-destructive upgrade to install; `src/vaultspec_core/cli/root_install.py`.

### Phase `P06` - uninstall command revision

add provider targeting, dry-run manifests, and shared-directory protection to the uninstall command

- [x] `P06.S06` - add provider positional argument, dry-run manifest, and shared-directory protection to uninstall; `src/vaultspec_core/cli/root_install.py`.

### Phase `P07` - sync command revision

drive sync from ProviderCapability and validate the target provider is installed

- [x] `P07.S07` - drive per-provider sync from ProviderCapability and reject sync of an uninstalled provider; `src/vaultspec_core/core/provider_sync.py`.

### Phase `P08` - justfile and CLI registration

keep the developer-facing recipes and CLI registration aligned with the new command surface

- [ ] `P08.S08` - keep CLI command registration aligned with the provider-scoped install and uninstall surface; `src/vaultspec_core/cli/root_install.py`.

### Phase `P09` - tests and contracts

cover the capability model, dry-run manifests, and shared-directory protection with tests

- [x] `P09.S09` - add contract and CLI tests for the capability model, dry-run manifests, and shared-directory protection; `src/vaultspec_core/tests/cli/test_spec_cli.py`.
