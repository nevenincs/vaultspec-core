---
tags:
  - '#plan'
  - '#cli-architecture'
date: '2026-03-05'
modified: '2026-07-31'
body_hash: 'sha256:a20b1a437ae3203b5946e96cefa998649a6bcff2fc3cedf092a4bc90c5161050'
tier: L2
related:
  - '[[2026-03-05-cli-path-resolution-adr]]'
  - '[[2026-03-05-cli-engine-typer-adr]]'
  - '[[2026-03-05-cli-architecture-audit]]'
  - '[[2026-03-23-cli-architecture-research]]'
---

# `cli-target-refactor` plan

### Phase `P01` - Un-brick the repository

Fix the hanging AGENTS_SRC_DIR import that crashed CLI boot before any refactor work could proceed.

- [x] `P01.S01` - fix hanging AGENTS_SRC_DIR import crash preventing the CLI from booting; `src/vaultspec_core/core/__init__.py`.

### Phase `P02` - Config layer overhaul

Replace the split root/content-dir config with a unified target directory paradigm.

- [x] `P02.S02` - refactor WorkspaceLayout to the target_dir paradigm with eager path resolution; `src/vaultspec_core/config/workspace.py`.
- [x] `P02.S03` - replace VAULTSPEC_ROOT_DIR and VAULTSPEC_CONTENT_DIR with VAULTSPEC_TARGET_DIR in the config registry; `src/vaultspec_core/config/config.py`.

### Phase `P03` - Typer engine bootstrap

Replace argparse with Typer as the CLI engine and unify logging on RichHandler.

- [x] `P03.S04` - install Typer and build the master CLI app with a global --target/--debug callback; `src/vaultspec_core/cli/_app.py`.
- [x] `P03.S05` - unify logging on rich.logging.RichHandler and drive level from the Typer callback; `src/vaultspec_core/logging_config.py`.

### Phase `P04` - Subcommand porting, IO governance and type stripping

Port core functions and subcommands off argparse.Namespace and printer.py onto native kwargs and typer/rich IO.

- [x] `P04.S06` - refactor core function signatures to drop argparse.Namespace in favor of explicit kwargs and raise typer.Exit; `src/vaultspec_core/core/`.
- [x] `P04.S07` - purge printer.py and route output through typer.echo and rich.print; `src/vaultspec_core/core/`.
- [x] `P04.S08` - port vault, spec, hooks and mcp subcommands to Typer command groups; `src/vaultspec_core/cli/`.

### Phase `P05` - Initialization upgrade and hooks isolation

Fix init scaffold ordering and isolate hook subprocess execution context.

- [x] `P05.S09` - fix init scaffold to re-resolve the workspace after writing framework.md so provider scaffolding reads fresh config; `src/vaultspec_core/cli/root_install.py`.
- [x] `P05.S10` - clone os.environ, inject VAULTSPEC_TARGET_DIR, and pass cwd into hook subprocess execution; `src/vaultspec_core/hooks/engine.py`.

### Phase `P06` - Test suite migration

Migrate the CLI test suite off subprocess invocation onto Typer's CliRunner.

- [x] `P06.S11` - migrate CLI tests from subprocess invocation to typer.testing.CliRunner; `src/vaultspec_core/tests/cli/`.
