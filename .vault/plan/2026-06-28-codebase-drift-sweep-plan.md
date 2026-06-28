---
tags:
  - '#plan'
  - '#codebase-drift-sweep'
date: '2026-06-28'
modified: '2026-06-28'
tier: L2
related:
  - '[[2026-06-28-diagnosis-surface-parity-audit]]'
  - '[[2026-06-28-diagnosis-surface-parity-adr]]'
---

# `codebase-drift-sweep` plan

## Description

A codebase-wide hunt for the root pattern the diagnosis-surface-parity audit exposed: the
same decision made by divergent bodies of code, which drift into contradiction. Each phase
sweeps one class of that pattern with RAG-led, rg-confirmed discovery, records findings,
and collapses confirmed duplications onto one source of truth.

## Steps

### Phase `P01` - Decision-logic duplication

RAG and rg sweep for the add/update/freshness/comparison decision re-implemented outside the canonical apply_file_sync (codex agent sync and MCP sync are the seed instances from the audit), then fold each onto the canonical comparator.

- [ ] `P01.S01` - Sweep for content and freshness comparisons re-implemented outside apply_file_sync and record each site; `src/vaultspec_core/core/`.
- [ ] `P01.S02` - Fold confirmed duplications onto the canonical comparator or one shared helper, with tests; `src/vaultspec_core/core/sync.py`.

### Phase `P02` - Source-of-truth registry duplication

Hunt for registries and resolvers maintained in more than one place (host-native file lists, provider-file sets, path resolution, template-name maps) where a writer and a checker can disagree.

- [ ] `P02.S03` - Sweep for registries and resolvers maintained in more than one place and record each writer-checker pair; `src/vaultspec_core/core/`.
- [ ] `P02.S04` - Collapse each confirmed duplicate registry to one source of truth, with tests; `src/vaultspec_core/core/`.

### Phase `P03` - Lifecycle ownership gaps

Find artefacts created but never pruned or reconciled (the orphan-snapshot class): snapshots, manifests, generated provider files, lock files, caches, each needing a single prune or reconcile owner.

- [ ] `P03.S05` - Sweep for created-but-never-reconciled artefacts and record each lifecycle gap with its missing owner; `src/vaultspec_core/core/`.
- [ ] `P03.S06` - Assign each confirmed gap a single prune or reconcile owner, with tests; `src/vaultspec_core/core/`.

### Phase `P04` - Preview vs apply parity

Audit every destructive verb for dry-run and apply granularity and outcome parity (install versus sync was the seed); a preview that understates or misreports the apply is a finding.

- [ ] `P04.S07` - Audit every destructive verb for dry-run and apply parity and record mismatches; `src/vaultspec_core/cli/`.
- [ ] `P04.S08` - Bring confirmed previews to apply-faithful granularity, with tests; `src/vaultspec_core/cli/`.

### Phase `P05` - Version and tooling shadowing

Sweep for shadowing where two resolvable copies disagree: stale global binary versus editable source, deployed template mirror versus package source, generated reference versus live surface.

- [ ] `P05.S09` - Sweep for shadowing between resolvable copies and record each; `src/vaultspec_core/`.
- [ ] `P05.S10` - Document the canonical invocation and add cheap drift guards where warranted, with tests; `src/vaultspec_core/`.

## Parallelization

The five phases are independent sweeps and may run concurrently; the collapse step within
each phase depends only on that phase's discovery step.

## Verification

Each collapse lands with tests and leaves spec doctor, the lint suite, and the unit gate
green.
