---
tags:
  - '#plan'
  - '#cli-output'
date: '2026-02-23'
modified: '2026-07-31'
body_hash: 'sha256:bd118203e83b359a2d1d407716ff229128b20df8262a3ff3714af3f6a633e08f'
tier: L2
related:
  - '[[2026-02-23-cli-output-architecture-adr]]'
  - '[[2026-02-23-cli-output-architecture-research]]'
  - '[[2026-02-22-cli-logging-adr]]'
  - '[[2026-02-22-cli-logging-research]]'
---

# `cli-output` phase-1 plan

### Phase `P01` - Infrastructure

Introduce a dedicated output channel that owns stdout program output separately from stderr status messaging.

- [ ] `P01.S01` - create a Printer class that wraps distinct stdout and stderr Console instances; `src/vaultspec_core/console.py`.

### Phase `P02` - Fix channel inconsistencies

Correct the call sites that wrote program output to stderr or status messaging to stdout, breaking pipeable output.

- [x] `P02.S02` - route program output to stdout and status, warning, and error messaging to stderr consistently across CLI handlers; `src/vaultspec_core/console.py`.
