---
tags:
  - '#plan'
  - '#system-prompt'
date: '2026-02-18'
modified: '2026-07-31'
body_hash: 'sha256:66a07d7b78ad1ad9406e426701c8f842d8a79b88083099db347fd41ffeb44721'
tier: L2
related:
  - '[[2026-02-18-system-prompt-restructure-adr]]'
  - '[[2026-02-18-system-prompt-architecture-research]]'
---

# system-prompt restructure plan

### Phase `P01` - Content Restructuring

Split tool-specific content out of shared system prompt files and fix small defects.

- [x] `P01.S01` - split tool-specific references out of the shared operations content; `src/vaultspec_core/builtins/system/02-operations.md`.
- [x] `P01.S02` - remove the fixed persona name from the shared base prompt; `src/vaultspec_core/builtins/system/01-core.md`.
- [x] `P01.S03` - add explicit order frontmatter to control assembly sequencing; `src/vaultspec_core/builtins/system/01-core.md`.
- [x] `P01.S04` - fix small defects in the shared operations content; `src/vaultspec_core/builtins/system/02-operations.md`.
- [ ] `P01.S05` - fix forward-references in tool-specific system content; `src/vaultspec_core/builtins/system`.

### Phase `P02` - CLI Pipeline Changes

Support explicit assembly ordering and generate a Claude behavioral rule file alongside the assembled system prompt.

- [x] `P02.S06` - sort assembled system prompt parts by order frontmatter; `src/vaultspec_core/core/system.py`.
- [x] `P02.S07` - assemble shared behavioral content into a standalone system-rules generator; `src/vaultspec_core/core/system.py`.
- [x] `P02.S08` - generate the claude behavioral rule file during system sync; `src/vaultspec_core/core/system.py`.

### Phase `P03` - Shell Example Relocation

Move verbose shell tool examples out of the system prompt and into skill files.

- [ ] `P03.S09` - trim verbose shell tool examples out of the assembled system prompt; `src/vaultspec_core/builtins/system`.
- [ ] `P03.S10` - enrich shell tool skill files with the detailed usage examples; `src/vaultspec_core/builtins/skills`.

### Phase `P04` - Test Updates

Cover assembly ordering and behavioral rule generation with tests, and confirm no regressions.

- [x] `P04.S11` - add assembly-order test coverage for the generated system prompt; `src/vaultspec_core/tests/cli/test_sync_collect.py`.
- [x] `P04.S12` - add behavioral rule generation and exclusion test coverage; `src/vaultspec_core/tests/cli/test_sync_operations.py`.
- [x] `P04.S13` - add pipeline config exclusion test coverage for rule generation; `src/vaultspec_core/tests/cli/test_sync_collect.py`.
- [x] `P04.S14` - run the full cli test suite to confirm no regressions; `src/vaultspec_core/tests/cli`.
