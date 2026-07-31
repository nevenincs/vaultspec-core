---
tags:
  - '#plan'
  - '#hooks-maturity'
date: '2026-02-23'
modified: '2026-07-31'
body_hash: 'sha256:1a391e85275cb741214e73c9e96b5b97470fb69810ac3d4025426d39eda66ef3'
tier: L2
related:
  - '[[2026-02-23-hooks-maturity-adr]]'
  - '[[2026-02-23-hooks-maturity-research]]'
---

# hooks-maturity implementation plan

### Phase `P01` - Engine hardening

Fix safety-critical bugs in the hooks execution engine before wiring automatic triggers.

- [x] `P01.S01` - kill timed-out shell hook subprocesses instead of leaking zombies; `src/vaultspec_core/hooks/engine.py`.
- [x] `P01.S02` - tokenize shell hook commands with platform-correct shlex posix mode on Windows; `src/vaultspec_core/hooks/engine.py`.
- [ ] `P01.S03` - fix broken agent-dispatch hook action invocation; `src/vaultspec_core/hooks/engine.py`.
- [x] `P01.S04` - remove the YAML fallback parser and rely solely on PyYAML; `src/vaultspec_core/hooks/engine.py`.
- [x] `P01.S05` - deduplicate yaml and yml hook loading by stem name; `src/vaultspec_core/hooks/engine.py`.
- [x] `P01.S06` - guard hook triggering against re-entrant recursive events; `src/vaultspec_core/hooks/engine.py`.

### Phase `P02` - Auto-trigger wiring

Wire automatic lifecycle hook triggers into CLI commands and retire dead events.

- [ ] `P02.S07` - wire fire_hooks into vault document creation, indexing, and audit lifecycle points; `src/vaultspec_core/core/provider_sync.py`.
- [x] `P02.S08` - remove the dead vault.document.modified event from the supported events set; `src/vaultspec_core/hooks/engine.py`.

### Phase `P03` - Tests and documentation

Harden test coverage for the hooks engine and document the hooks system for users.

- [x] `P03.S09` - harden hook engine test coverage for timeouts, deduplication, the re-entrant guard, and fire_hooks integration; `src/vaultspec_core/hooks/tests/test_hooks.py`.
- [ ] `P03.S10` - document the hooks system for users, including schema, events, and debugging; `docs/CLI.md`.
