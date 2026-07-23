---
generated: true
tags:
  - '#index'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
related:
  - '[[2026-07-23-prek-boundary-hardening-P01-S01]]'
  - '[[2026-07-23-prek-boundary-hardening-P01-S02]]'
  - '[[2026-07-23-prek-boundary-hardening-P02-S03]]'
  - '[[2026-07-23-prek-boundary-hardening-P02-S04]]'
  - '[[2026-07-23-prek-boundary-hardening-P02-S05]]'
  - '[[2026-07-23-prek-boundary-hardening-P02-S06]]'
  - '[[2026-07-23-prek-boundary-hardening-P02-S07]]'
  - '[[2026-07-23-prek-boundary-hardening-P02-S08]]'
  - '[[2026-07-23-prek-boundary-hardening-P02-S09]]'
  - '[[2026-07-23-prek-boundary-hardening-P03-S10]]'
  - '[[2026-07-23-prek-boundary-hardening-P03-S11]]'
  - '[[2026-07-23-prek-boundary-hardening-P03-S12]]'
  - '[[2026-07-23-prek-boundary-hardening-P03-S13]]'
  - '[[2026-07-23-prek-boundary-hardening-P03-S14]]'
  - '[[2026-07-23-prek-boundary-hardening-P03-S15]]'
  - '[[2026-07-23-prek-boundary-hardening-adr]]'
  - '[[2026-07-23-prek-boundary-hardening-plan]]'
  - '[[2026-07-23-prek-boundary-hardening-reference]]'
  - '[[2026-07-23-prek-boundary-hardening-research]]'
---

# `prek-boundary-hardening` feature index

Auto-generated index of all documents tagged with `#prek-boundary-hardening`.

## Documents

### adr

- `2026-07-23-prek-boundary-hardening-adr` - `prek-boundary-hardening` adr: `pre-commit-config lifecycle under prek.toml ownership` | (**status:** `accepted`)

### exec

- `2026-07-23-prek-boundary-hardening-P01-S01` - verify prek's config-discovery behavior when prek.toml and .pre-commit-config.yaml are both present (hard error vs warn vs silent precedence) against the current prek release, and record the observed contract in a reference document scaffolded through the owning verb
- `2026-07-23-prek-boundary-hardening-P01-S02` - verify prek's TOML schema for local system hooks, confirm the delimited managed-block rendering shape is expressible in it (falling back to a round-trip TOML writer decision only if it is not), and record the schema in the same reference document
- `2026-07-23-prek-boundary-hardening-P02-S03` - implement the consolidated boundary predicate: prek.toml existence plus a mode-aware canonical-hook content check via tomllib, comparing entries resolved through canonical_hook_entries_for_mode, treating an unparseable prek.toml conservatively as hooks-absent
- `2026-07-23-prek-boundary-hardening-P02-S04` - route the \_scaffold_precommit short-circuit through the boundary predicate, replacing its bare existence check
- `2026-07-23-prek-boundary-hardening-P02-S05` - make collect_precommit_state content-aware through the predicate: emit UNREFRESHABLE only when prek.toml lacks the canonical hooks, add the new ORPHANED signal member for a stale co-present YAML when prek.toml is healthy, and handle ORPHANED in \_resolve_precommit as a no-op in the same change
- `2026-07-23-prek-boundary-hardening-P02-S06` - reshape the doctor precommit row and advisory text for the content-aware states - UNREFRESHABLE says hooks are stranded and names the migration verb, ORPHANED renders as benign info advising superseded-YAML removal - and update every status mapping carrying PrecommitSignal members
- `2026-07-23-prek-boundary-hardening-P02-S07` - route the uninstall YAML hook-stripping path through the boundary predicate and document the retained residue-removal asymmetry as a deliberate leave-no-trace decision
- `2026-07-23-prek-boundary-hardening-P02-S08` - add real-filesystem tests for the content-aware states: prek.toml carrying canonical hooks with a stale YAML reports ORPHANED, an empty or hook-less prek.toml reports UNREFRESHABLE, an unparseable prek.toml reports UNREFRESHABLE, and doctor renders the reshaped advisories
- `2026-07-23-prek-boundary-hardening-P02-S09` - add real-filesystem tests proving the predicate-routed scaffold short-circuit and uninstall behavior remain unchanged for existing prek workspaces
- `2026-07-23-prek-boundary-hardening-P03-S10` - implement the prek.toml hook renderer: emit the mode-resolved canonical_precommit_hooks_for_mode set as a delimited managed text block in the verified local-system-hook TOML shape, appended or replaced without round-tripping operator-authored TOML
- `2026-07-23-prek-boundary-hardening-P03-S11` - add the operator-invoked migration verb under a new spec precommit command group (avoiding the taken spec hooks namespace): transplant canonical hooks into prek.toml, idempotent when hooks are already present, previewable with --dry-run, never deleting the YAML on its own
- `2026-07-23-prek-boundary-hardening-P03-S12` - add operator-gated orphan cleanup: an explicit removal flag on the migration verb that deletes the superseded .pre-commit-config.yaml only after the predicate confirms canonical hooks are present in prek.toml, following the conservative lock-sentinel-prune precedent
- `2026-07-23-prek-boundary-hardening-P03-S13` - add real-filesystem tests for the migration verb: fresh transplant, idempotent re-run as a no-op, --dry-run leaving the tree untouched, dependency-mode and tool-mode entry shapes, and managed-block replacement preserving operator-authored TOML content byte-for-byte
- `2026-07-23-prek-boundary-hardening-P03-S14` - add real-filesystem tests for gated orphan cleanup: removal flag refuses while prek.toml lacks canonical hooks, deletes the YAML once they are present, and the ORPHANED doctor advisory clears afterwards
- `2026-07-23-prek-boundary-hardening-P03-S15` - document the new spec precommit verb group in the CLI reference source and roll it out through sync

### plan

- `2026-07-23-prek-boundary-hardening-plan` - `prek-boundary-hardening` plan

### reference

- `2026-07-23-prek-boundary-hardening-reference` - `prek-boundary-hardening` reference: `verified prek contract`

### research

- `2026-07-23-prek-boundary-hardening-research` - `prek-boundary-hardening` research: `pre-commit-config vs prek.toml lifecycle`
