---
tags:
  - '#plan'
  - '#cli-logging'
date: '2026-02-22'
modified: '2026-07-31'
body_hash: 'sha256:74b17a5077566451e802902cdcd5b4fbb5ad688099577fdc249e661099d22f8a'
tier: L2
related:
  - '[[2026-02-22-cli-logging-adr]]'
  - '[[2026-02-22-cli-logging-research]]'
---

# `cli-logging` plan

### Phase `P01` - CLI logging infrastructure

Replace the plain StreamHandler with a TTY-aware RichHandler across all CLI entry points and add a --quiet verbosity flag.


Standardize all CLI logging with Rich and overhaul agent feed formatting for
colorized, readable output. Implements \[[2026-02-22-cli-logging-adr]\].

- [x] `P01.S01` - add the rich dependency to the project manifest; `pyproject.toml`.
- [x] `P01.S02` - rewrite configure_logging with TTY-aware handler selection and a verbosity ladder; `src/vaultspec_core/logging_config.py`.
- [x] `P01.S03` - add the --quiet flag and wire the verbosity ladder through the shared CLI options; `src/vaultspec_core/cli/`.
- [x] `P01.S04` - remove the redundant configure_logging double-initialisation at the spec entry point; `src/vaultspec_core/cli/`.

### Phase `P02` - Agent feed formatting

Rewrite agent feed output to use styled Rich Console output, achieving visual parity through the shared callback convergence point.

- [x] `P02.S05` - add a styled Rich Console to the agent feed client and restyle tool-call, thinking, and response output; `src/vaultspec_core/protocol/`.
- [x] `P02.S06` - verify the shared subagent callback convergence point is unaffected by the restyling; `src/vaultspec_core/protocol/`.
