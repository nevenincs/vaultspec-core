---
tags:
  - '#plan'
  - '#marketing-and-documentation'
date: '2026-02-20'
modified: '2026-07-31'
body_hash: 'sha256:007391016337c9f1053bb18b76eceffc900a8725d3f053481310e02521851e16'
tier: L2
related:
  - '[[2026-02-20-marketing-and-documentation-research]]'
  - '[[2026-02-20-marketing-and-documentation-adr]]'
---

# `marketing-and-documentation` `phase1` plan

## Steps

### Phase `P01` - Retire

Delete the marketing and persona documentation files being superseded.

- [x] `P01.S01` - delete the retired marketing, persona, and tutorial documentation files; `docs`.

### Phase `P02` - Create .vaultspec/docs/

Consolidate operational documentation into three sub-chapter files deployed with the framework.

- [ ] `P02.S02` - create a merged concepts and tutorial documentation file; `docs`.
- [ ] `P02.S03` - create a merged cli reference and configuration documentation file; `docs/CLI.md`.
- [ ] `P02.S04` - create a trimmed search guide documentation file; `docs`.

### Phase `P03` - Rewrite README.md

Expand the root README to absorb the install flow and a worked pipeline example.

- [ ] `P03.S05` - rewrite the root readme with an expanded quick start and worked pipeline example; `README.md`.

### Phase `P04` - Update .vaultspec/README.md

Link the framework manual to the new documentation sub-chapters.

- [ ] `P04.S06` - link the framework manual to the new documentation sub-chapters; `docs/README.md`.
- [ ] `P04.S07` - preserve the framework manual overview and reference tables unchanged; `docs/README.md`.
