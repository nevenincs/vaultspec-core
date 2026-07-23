---
tags:
  - '#adr'
  - '#prek-boundary-hardening'
date: '2026-07-23'
modified: '2026-07-23'
related:
  - '[[2026-07-23-prek-boundary-hardening-research]]'
---

# `prek-boundary-hardening` adr: `pre-commit-config lifecycle under prek.toml ownership` | (**status:** `accepted`)

## Problem Statement

When a workspace carries `prek.toml`, vaultspec-core abandons management of
`.pre-commit-config.yaml` but leaves the file in place, and the diagnosis layer keeps
warning that the hooks "cannot be refreshed" without knowing whether the hooks live
safely in `prek.toml` or nowhere at all. The `2026-07-23-prek-boundary-hardening-research`
findings show the entire boundary is a single opaque `prek.toml` existence check
replicated across the scaffold, the diagnosis collector, and the sentinel prune, with
no parser, no migration path, and no cleanup of the superseded YAML. A decision is
needed now because this under-specified boundary produced a cluster of one-off bugs
this cycle (#231/#236/#241/#243), and #232 fixed only the latest symptom. The core
question: once `prek.toml` owns the hook boundary, what is the intended lifecycle of
`.pre-commit-config.yaml`, and what invariants make the subsystem stop shedding bugs.

## Considerations

- The boundary reads `prek.toml` presence but never its contents, so it cannot tell a
  correct transplant from an empty file (`2026-07-23-prek-boundary-hardening-research`,
  "single opaque existence check").
- `UNREFRESHABLE` is emitted on existence alone and fires as a false positive when
  hooks are already healthy in `prek.toml` - the direct cause of the warning-noise
  class of bugs (research, "false positive").
- The raw material for assisted migration already exists as mode-keyed structured hook
  definitions (`canonical_precommit_hooks_for_mode`); only a `prek.toml` renderer is
  missing (research, "no migration verb").
- The `spec hooks` verb namespace is already occupied by declarative event hooks; a
  pre-commit migration command must not collide with it (research, "namespace taken").
- Install/sync refuse to write the YAML under prek, but uninstall still edits it - an
  asymmetry any lifecycle model must reconcile (research, "uninstall asymmetry").
- The premise that prek reads `prek.toml` exclusively is an embedded, unverified
  assumption that gates a migrate-and-remove policy (research, "external assumption").
- The one existing cross-boundary cleanup (lock-sentinel prune) is deliberately
  conservative and safe; it is the precedent for how far automatic YAML cleanup should
  go (research, "orphan detection today").

## Considered options

**A. Status quo (advisory-only).** Keep the manual-transplant advisory. Rejected: it is
the current state the issue exists to fix; it leaves the false-positive `UNREFRESHABLE`
signal and the orphaned YAML unaddressed.

**B. Keep-both (manage YAML and prek.toml in parallel).** Teach the scaffold to write
both files. Rejected: contradicts the D3 premise that prek treats a co-present
`.pre-commit-config.yaml` as a conflicting duplicate (`.vault/adr/2026-04-21-flow-bugs-adr.md`);
doubles the managed surface and the round-trip-edit bug area rather than shrinking it.

**C. Fully automatic migrate-and-remove.** On detecting `prek.toml`, sync silently
transplants the hooks and deletes `.pre-commit-config.yaml`. Rejected as the default:
it edits a file vaultspec has declared it does not own, hinges on the unverified
exclusive-read assumption, and a silent delete during routine sync is too aggressive
for a destructive, hard-to-undo action.

**D. Content-aware signal + explicit operator-invoked assisted migration + advisory
orphan cleanup (chosen).** Parse `prek.toml` for the canonical hooks so the signal
reflects reality; add a dedicated, explicitly-invoked migration verb that transplants
the canonical hooks into `prek.toml`; detect the orphaned YAML and advise (not force)
its removal; consolidate the three existence checks behind one boundary predicate.
Chosen: it removes the false positive at its root, makes the remediation a single
assisted command instead of hand-editing, and keeps destructive cleanup operator-gated.

## Constraints

- **External tool contract (blocking to verify).** The migrate-and-remove half depends
  on `prek`'s actual config-discovery behavior and its TOML schema for local system
  hooks, both flagged unverified in research. The content-aware signal and the
  assisted-migration renderer must be validated against a real `prek` release before
  the orphan-removal advice hardens into automatic deletion. Until confirmed, cleanup
  stays advisory.
- **Namespace constraint.** The migration verb cannot reuse `spec hooks` (declarative
  event hooks). It should live where the pre-commit boundary already lives (a
  `spec precommit`-style surface or a sync-adjacent verb); exact placement is deferred
  to the plan.
- **No new dependency (writer strategy corrected in review).** TOML reading is
  available in the runtime (`tomllib`), but `tomllib` is read-only and the runtime
  carries no TOML serializer. Rather than adding a round-trip TOML writer, the
  migration verb renders the vaultspec hook section as a delimited managed text block
  appended to (or replaced in) `prek.toml`, following the existing managed-block
  precedent in `gitignore.py`. This deliberately avoids full-file TOML round-tripping,
  the exact fidelity-loss class that produced #241 on the YAML side. A round-trip
  library (`tomlkit`) is admitted only if the verified prek schema cannot be expressed
  as an appendable block.
- **Parent-feature stability.** Builds on the stable `install-mode` mode resolution
  (`resolve_render_mode`) and the settled `flow-bugs` D3 short-circuit; no frontier
  dependencies.

## Implementation

The hardening layers onto the existing boundary in four moves, all grounded in
`2026-07-23-prek-boundary-hardening-research`.

First, a single boundary predicate replaces the three scattered `prek.toml` existence
checks. It answers two questions the current code conflates: does `prek.toml` exist,
and does it already carry the canonical vaultspec hooks. The content check is
mode-aware - it compares against the entries resolved through
`canonical_hook_entries_for_mode(resolve_render_mode(target))`, mirroring the
mode-awareness of the existing YAML-side collector - and parse-error tolerant: an
unparseable `prek.toml` is treated conservatively as hooks-absent (`UNREFRESHABLE`),
never as healthy. This predicate becomes the one owner of the "who manages hooks here"
invariant that the scaffold, the collector, and the sentinel prune currently each
re-derive.

Second, `collect_precommit_state` becomes content-aware. `UNREFRESHABLE` is emitted
only when `prek.toml` exists AND the canonical hooks are absent from it - the genuine
"hooks stranded, cannot auto-refresh" state. When the hooks are present in `prek.toml`,
a co-present stale YAML is reported as an orphan (a new, benign informational state),
not as `UNREFRESHABLE`. This removes the false positive at its source and reshapes the
doctor advisory to say what is actually wrong. Wiring invariant (added in review): the
new signal member must land in the same change as its resolver branch, doctor row
mapping, and status mapping - `_resolve_precommit` falls through to an unknown-signal
warning for any unhandled member, which is precisely how #231 was born.

Third, an explicitly operator-invoked migration verb reads the mode-resolved canonical
hook set (`canonical_precommit_hooks_for_mode`) and transplants it into `prek.toml`,
rendering the local-system-hook TOML shape. It is idempotent (re-running when hooks are
already present is a no-op), previewable with `--dry-run`, and does not delete the YAML
on its own. This turns today's manual advisory into a single assisted command.

Fourth, orphan handling for the superseded `.pre-commit-config.yaml` follows the
conservative precedent of the lock-sentinel prune: detect it, surface it, and advise
removal, but keep the actual deletion operator-gated (either behind the migration verb's
explicit flag or a manual step) until the exclusive-read assumption is verified. The
existing sentinel-prune cleanup is retained unchanged.

The uninstall asymmetry is reconciled by keeping it (a review addition, since the
considerations named it but no move resolved it): uninstall continues to strip
vaultspec hooks from a legacy `.pre-commit-config.yaml` even under prek, because that
is residue removal - leave-no-trace semantics - not management of the file. What
changes is that the uninstall path consults the same boundary predicate as everything
else, so the asymmetry becomes a documented, single-seam decision instead of an
accidental divergence.

Concrete hook-rendering and TOML-schema snippets belong in a follow-on `{reference}`
document authored during planning, once the `prek` schema is verified.

## Rationale

Option D wins on the knockout criterion the research isolates: the boundary's bugs stem
from keying behavior off `prek.toml` existence while never reading its contents, so a
correct workspace and a broken one are indistinguishable. Only a content-aware predicate
removes that class of false positive, and #232 (commit `88e18e0f`) already demonstrated
that patching the resolver without fixing the signal only defers the next symptom. The
assisted-migration verb is justified because the structured hook definitions already
exist mode-keyed in `canonical_precommit_hooks_for_mode`; the gap is purely a missing
renderer, making an assisted command low-cost relative to the recurring hand-transplant
error surface. Keeping orphan deletion advisory rather than automatic is the honest
response to the unverified exclusive-read assumption flagged in research: the safe,
reversible move is to detect and advise, mirroring the deliberately conservative
lock-sentinel prune, and to harden into automatic cleanup only after the `prek`
contract is confirmed.

## Consequences

Gains: the `UNREFRESHABLE` false positive disappears; operators get a one-command
migration instead of hand-editing TOML; the three existence checks collapse to one
predicate, shrinking the surface that shed #231/#236/#241/#243; the doctor advisory
finally tells the truth about whether hooks are stranded.

Difficulties: the boundary predicate must parse `prek.toml`, adding a real TOML read
where there was only an existence check, and the migration renderer must match `prek`'s
expected schema - both gated on verifying the external tool contract. The new orphan
state adds one signal value and a doctor row variant that need test coverage against
the existing `test_convergence_advisories` and `test_flow_bugs` suites.

Pathways opened: a verified `prek` contract later permits promoting orphan cleanup from
advisory to automatic, and the single boundary predicate is the natural seam for any
future alternate-hook-runner support.

In scope: content-aware signal, assisted migration verb, orphan detection with advisory
cleanup, consolidation of the boundary checks. Deferred: automatic YAML deletion
(pending external-contract verification), any `spec hooks` declarative-hook changes,
and adoption-rate-driven questions about whether to actively encourage prek migration.
