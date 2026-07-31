---
tags:
  - '#plan'
  - '#workspace-paths'
date: '2026-02-19'
modified: '2026-07-31'
body_hash: 'sha256:f3915eb619481b97d64d6625188a6b261896a5cbec73ef43de73f029c99a70c2'
tier: L2
related:
  - '[[2026-02-19-workspace-path-decoupling-adr]]'
  - '[[2026-02-19-workspace-path-decoupling-research]]'
---

# `workspace-paths` `implementation` plan

## Steps

### Phase `P01` - Core Module and Config

Build the workspace resolution module and config wiring, independent of external callers.

- [x] `P01.S01` - implement git-aware workspace layout resolution decoupled from a single root dir; `src/vaultspec_core/config/workspace.py`.
- [ ] `P01.S02` - add a content-root config field split from the output root; `src/vaultspec_core/config/config.py`.
- [x] `P01.S03` - add unit tests covering every workspace resolution mode; `src/vaultspec_core/config/tests/test_workspace.py`.

### Phase `P02` - Bootstrap and CLI Integration

Wire workspace resolution into the CLI entry points.

- [x] `P02.S04` - rewrite the bootstrap path resolver to call workspace resolution; `src/vaultspec_core/cli/_target.py`.
- [ ] `P02.S05` - wire a content-dir override into the primary cli entry point; `src/vaultspec_core/cli`.
- [ ] `P02.S06` - wire a content-dir override into the subagent entry point; `src/vaultspec_core/core/executor.py`.
- [ ] `P02.S07` - wire a content-dir override into the vault subcommand entry points; `src/vaultspec_core/cli`.

### Phase `P03` - Packaging and Extension Manifest

Align packaging metadata and companion-project discovery with the new workspace model.

- [ ] `P03.S08` - align packaged runtime dependencies with pyproject.toml; `pyproject.toml`.
- [ ] `P03.S09` - publish an extension manifest for companion-project discovery; `pyproject.toml`.
