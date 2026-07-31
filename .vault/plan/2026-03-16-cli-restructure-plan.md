---
tags:
  - '#plan'
  - '#cli-restructure'
date: '2026-03-16'
modified: '2026-07-31'
body_hash: 'sha256:2450115d18964416700337b88e47a3559e46f6c54fa583a6f57d6c5170a46623'
tier: L2
related:
  - '[[2026-03-05-cli-engine-typer-adr]]'
  - '[[2026-02-22-cli-ecosystem-factoring-adr]]'
  - '[[2026-03-23-cli-restructure-research]]'
---

# CLI Restructure Implementation Plan

### Phase `P01` - Foundation: console and global options

Fix the Windows Unicode console crash and simplify global CLI options before any downstream restructuring.

- [x] `P01.S01` - enable safe_box on non-UTF-8 terminals to prevent Unicode crashes on Windows; `src/vaultspec_core/console.py`.
- [x] `P01.S02` - remove --verbose, fix --target help text, and suppress shell completion options; `src/vaultspec_core/cli/_app.py`.

### Phase `P02` - Backend hardening

Build the query, archive, sync-filtering, revert, and dry-run library functions the restructured CLI needs before wiring commands to them.

- [x] `P02.S03` - add the vault query engine composing scan, filter and list over parsed documents; `src/vaultspec_core/vaultcore/query.py`.
- [x] `P02.S04` - add the feature archive mechanism that moves a feature's documents into .vault/_archive/; `src/vaultspec_core/vaultcore/query_archive.py`.
- [x] `P02.S05` - make sync_to_all_tools manifest-aware so it skips providers not installed; `src/vaultspec_core/core/sync.py`.
- [x] `P02.S06` - add the revert mechanism restoring builtin firmware resources to their package original; `src/vaultspec_core/core/revert.py`.
- [x] `P02.S07` - add the Rich tree renderer for coloured dry-run previews; `src/vaultspec_core/core/dry_run.py`.

### Phase `P03` - CLI namespace restructure

Rewrite the flat CLI surface as a domain-grouped package and delete the superseded flat modules.

- [x] `P03.S08` - create the domain-grouped cli package with root, vault, and spec command modules; `src/vaultspec_core/cli/`.
- [x] `P03.S09` - delete the superseded flat cli.py, spec_cli.py and vault_cli.py modules; `src/vaultspec_core/`.

### Phase `P04` - Fix top-level commands

Bring install, uninstall and sync behaviour in line with the CLI contract: force gates, dry-run trees, and manifest awareness.

- [x] `P04.S10` - wire install --force and a coloured dry-run tree preview; `src/vaultspec_core/cli/root_install.py`.
- [x] `P04.S11` - add the uninstall --force safety gate and the core-provider removal cascade; `src/vaultspec_core/cli/root_install.py`.
- [x] `P04.S12` - wire sync to the manifest-aware backend and reject core as a sync target with an explicit error; `src/vaultspec_core/cli/root_sync.py`.

### Phase `P05` - Implement vault commands

Wire the vault command stubs (add, stats, list, feature list, feature archive, doctor) to the Phase 2 backend.

- [x] `P05.S13` - wire vault add, stats, list, feature list, feature archive and health-check commands to the query and archive backends; `src/vaultspec_core/cli/vault_cmd.py`.

### Phase `P06` - Rewrite CLI tests and dev namespace

Rewrite the CLI test suite for the new domain-grouped namespace, including the planned dev command group.

- [x] `P06.S14` - rewrite the main, vault and spec CLI test suites for the domain-grouped namespace; `src/vaultspec_core/tests/cli/`.
- [ ] `P06.S15` - add the dev command group and its test suite; `src/vaultspec_core/cli/dev_cmd.py`.

### Phase `P07` - Justfile alignment

Resolve the sync/deps naming collision and add passthrough recipes for the new vault and spec command groups.

- [x] `P07.S16` - rename the dependency-sync recipe to deps to resolve the collision with vaultspec-core sync; `justfile`.
- [ ] `P07.S17` - add vault and spec passthrough recipes to the justfile; `justfile`.

### Phase `P08` - Help text quality pass

Audit every command and option help string across the CLI for clarity.

- [x] `P08.S18` - audit and rewrite help strings across every CLI command and option; `src/vaultspec_core/cli/`.
