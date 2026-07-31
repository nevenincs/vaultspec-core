---
tags:
  - '#exec'
  - '#cli-target-refactor'
date: '2026-03-05'
modified: '2026-06-13'
body_hash: 'sha256:8158a4a81997fc5ea8ed0d9dfd9052f802bdebbfa9a1d26a4ffe2757f97fc6cc'
related:
  - '[[2026-03-05-cli-target-refactor-plan]]'
---

# `cli-target-refactor` `phase2` `step2`

Unified the CLI logging by utilizing `rich.logging.RichHandler`.

- Modified: `src/vaultspec/logging_config.py`
- Modified: `src/vaultspec/cli.py`

## Description

- Replaced the contents of `src/vaultspec/logging_config.py` to strictly use `rich.logging.RichHandler`.
- Removed idempotency locks from logging initialization, allowing multiple re-configurations gracefully (which enables the Typer callback to dictate the global log level).
- Configured the Typer master callback in `cli.py` to call `configure_logging()` with the appropriate verbosity and debug levels.

## Tests

- Initialization allows dynamic re-setting of the root logger without accumulating duplicate handlers.
