---
tags:
  - '#plan'
  - '#cli-output'
date: '2026-02-23'
modified: '2026-07-31'
body_hash: 'sha256:92e5659939061b466a6e5335ff90b6d4ad860f7bab9df99026dabf7a20e3b5ed'
tier: L2
related:
  - '[[2026-02-23-cli-output-architecture-adr]]'
  - '[[2026-02-23-cli-output-architecture-research]]'
  - '[[2026-02-22-cli-logging-adr]]'
  - '[[2026-02-22-cli-logging-research]]'
---

# `cli-output` phase-1 plan

## Steps

### Phase `P01` - Infrastructure

Introduce a dedicated output channel that owns stdout program output separately from stderr status messaging.

- [ ] `P01.S01` - create a Printer class that wraps distinct stdout and stderr Console instances; `src/vaultspec_core/console.py`.

### Phase `P02` - Fix channel inconsistencies

Correct the call sites that wrote program output to stderr or status messaging to stdout, breaking pipeable output.

- [x] `P02.S02` - route program output to stdout and status, warning, and error messaging to stderr consistently across CLI handlers; `src/vaultspec_core/console.py`.
