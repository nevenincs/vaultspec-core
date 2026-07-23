---
tags:
  - '#plan'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
tier: L2
related:
  - '[[2026-07-23-prek-boundary-hardening-adr]]'
  - '[[2026-07-23-prek-boundary-hardening-research]]'
---

# `prek-boundary-hardening` plan

Harden the prek/pre-commit hook boundary: one content-aware boundary predicate, a truthful diagnosis signal, an assisted migration verb, and operator-gated orphan cleanup.

## Description

This plan executes the accepted prek-boundary-hardening decision (option D): replace
the three scattered `prek.toml` existence checks with a single mode-aware,
parse-error-tolerant boundary predicate; emit `UNREFRESHABLE` only when `prek.toml`
genuinely lacks the canonical hooks and report a healthy-prek stale YAML as a new
benign `ORPHANED` state; add an explicitly operator-invoked migration verb that
transplants the mode-resolved canonical hook set into `prek.toml` as a delimited
managed block (idempotent, previewable, never auto-deleting); and gate orphan YAML
removal behind an explicit flag following the conservative lock-sentinel-prune
precedent. Phase one verifies the external prek contract (config-discovery precedence
and local-hook TOML schema) before any renderer or predicate hardens against it,
because both were flagged unverified in research.

Deferred by decision: automatic deletion of `.pre-commit-config.yaml` remains out of
scope until the prek exclusive-read contract is verified and has soaked; any
`spec hooks` declarative-event-hook changes; adoption-rate-driven prek promotion.

## Steps

### Phase `P01` - verify the external prek contract

Empirically confirm the prek tool behaviors the whole hardening rests on, before any renderer or predicate hardens against them.

- [x] `P01.S01` - verify prek's config-discovery behavior when prek.toml and .pre-commit-config.yaml are both present (hard error vs warn vs silent precedence) against the current prek release, and record the observed contract in a reference document scaffolded through the owning verb; `.vault/reference/2026-07-23-prek-boundary-hardening-reference.md`.
- [x] `P01.S02` - verify prek's TOML schema for local system hooks, confirm the delimited managed-block rendering shape is expressible in it (falling back to a round-trip TOML writer decision only if it is not), and record the schema in the same reference document; `.vault/reference/2026-07-23-prek-boundary-hardening-reference.md`.

### Phase `P02` - boundary predicate and content-aware signal

Collapse the three scattered prek.toml existence checks into one mode-aware, parse-error-tolerant boundary predicate and make the diagnosis signal reflect prek.toml contents.

- [ ] `P02.S03` - implement the consolidated boundary predicate: prek.toml existence plus a mode-aware canonical-hook content check via tomllib, comparing entries resolved through canonical_hook_entries_for_mode, treating an unparseable prek.toml conservatively as hooks-absent; `src/vaultspec_core/core/prek_boundary.py`.
- [ ] `P02.S04` - route the \_scaffold_precommit short-circuit through the boundary predicate, replacing its bare existence check; `src/vaultspec_core/core/commands.py`.
- [ ] `P02.S05` - make collect_precommit_state content-aware through the predicate: emit UNREFRESHABLE only when prek.toml lacks the canonical hooks, add the new ORPHANED signal member for a stale co-present YAML when prek.toml is healthy, and handle ORPHANED in \_resolve_precommit as a no-op in the same change; `src/vaultspec_core/core/diagnosis/collectors.py, src/vaultspec_core/core/diagnosis/signals.py, src/vaultspec_core/core/resolver.py`.
- [ ] `P02.S06` - reshape the doctor precommit row and advisory text for the content-aware states - UNREFRESHABLE says hooks are stranded and names the migration verb, ORPHANED renders as benign info advising superseded-YAML removal - and update every status mapping carrying PrecommitSignal members; `src/vaultspec_core/cli/spec_cmd.py`.
- [ ] `P02.S07` - route the uninstall YAML hook-stripping path through the boundary predicate and document the retained residue-removal asymmetry as a deliberate leave-no-trace decision; `src/vaultspec_core/core/commands.py`.
- [ ] `P02.S08` - add real-filesystem tests for the content-aware states: prek.toml carrying canonical hooks with a stale YAML reports ORPHANED, an empty or hook-less prek.toml reports UNREFRESHABLE, an unparseable prek.toml reports UNREFRESHABLE, and doctor renders the reshaped advisories; `src/vaultspec_core/tests/cli/test_convergence_advisories.py`.
- [ ] `P02.S09` - add real-filesystem tests proving the predicate-routed scaffold short-circuit and uninstall behavior remain unchanged for existing prek workspaces; `src/vaultspec_core/tests/cli/test_flow_bugs.py`.

### Phase `P03` - assisted migration verb and advisory orphan cleanup

Turn the manual-transplant advisory into an idempotent, previewable migration command with operator-gated orphan cleanup of the superseded YAML.

- [ ] `P03.S10` - implement the prek.toml hook renderer: emit the mode-resolved canonical_precommit_hooks_for_mode set as a delimited managed text block in the verified local-system-hook TOML shape, appended or replaced without round-tripping operator-authored TOML; `src/vaultspec_core/core/prek_boundary.py`.
- [ ] `P03.S11` - add the operator-invoked migration verb under a new spec precommit command group (avoiding the taken spec hooks namespace): transplant canonical hooks into prek.toml, idempotent when hooks are already present, previewable with --dry-run, never deleting the YAML on its own; `src/vaultspec_core/cli/spec_cmd.py`.
- [ ] `P03.S12` - add operator-gated orphan cleanup: an explicit removal flag on the migration verb that deletes the superseded .pre-commit-config.yaml only after the predicate confirms canonical hooks are present in prek.toml, following the conservative lock-sentinel-prune precedent; `src/vaultspec_core/cli/spec_cmd.py, src/vaultspec_core/core/prek_boundary.py`.
- [ ] `P03.S13` - add real-filesystem tests for the migration verb: fresh transplant, idempotent re-run as a no-op, --dry-run leaving the tree untouched, dependency-mode and tool-mode entry shapes, and managed-block replacement preserving operator-authored TOML content byte-for-byte; `src/vaultspec_core/tests/cli/test_flow_bugs.py`.
- [ ] `P03.S14` - add real-filesystem tests for gated orphan cleanup: removal flag refuses while prek.toml lacks canonical hooks, deletes the YAML once they are present, and the ORPHANED doctor advisory clears afterwards; `src/vaultspec_core/tests/cli/test_convergence_advisories.py`.
- [ ] `P03.S15` - document the new spec precommit verb group in the CLI reference source and roll it out through sync; `src/vaultspec_core/builtins`.

## Parallelization

Phases are strictly sequential: P01 gates P02 and P03 because the predicate's content
check and the renderer's TOML shape both harden against the contract P01 verifies.
Within P02, S03 must land first; S04, S05, and S07 then parallelize (independent call
sites of the predicate), S06 follows S05, and the test Steps S08 and S09 close the
Phase. Within P03, S10 precedes S11, S12 follows S11, S13 and S14 follow their
subjects, and S15 lands last.

## Verification

- `P01` produces a reference document recording prek's verified config-discovery
  precedence and local-hook TOML schema; the renderer and predicate cite observed
  behavior, not assumption.
- A workspace with canonical hooks in `prek.toml` and a stale co-present YAML reports
  `ORPHANED` (benign info), never `UNREFRESHABLE`; an empty, hook-less, or unparseable
  `prek.toml` reports `UNREFRESHABLE`.
- No code path outside the consolidated predicate performs a bare `prek.toml`
  existence check.
- The migration verb is idempotent (second run is a byte-for-byte no-op), honors
  `--dry-run`, renders mode-correct entries, and never deletes the YAML without the
  explicit removal flag; the flag refuses while `prek.toml` lacks the canonical hooks.
- The full unit gate, `test_convergence_advisories`, and `test_flow_bugs` pass with
  the new real-filesystem coverage; `vaultspec-core vault plan check` and
  `vaultspec-core vault check all` report this plan clean.
- The plan is complete when every Step row is closed.
