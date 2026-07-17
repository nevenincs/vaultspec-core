---
tags:
  - '#adr'
  - '#upgrade-convergence'
date: '2026-07-17'
modified: '2026-07-17'
related:
  - "[[2026-07-17-upgrade-convergence-research]]"
---

# `upgrade-convergence` adr: `managed launch artifacts converge automatically` | (**status:** `accepted`)

## Problem Statement

The static-launch amendment changed the canonical MCP launch bytes for
every deployed workspace, but the reconciliation machinery cannot deliver
the new shape: a managed entry that drifted from its definition is skipped
by plain `sync` and by `install --upgrade` alike unless the operator passes
`--force`, and the upgrade path's mode-flip force seam covers only core's
own entry (`2026-07-17-upgrade-convergence-research`). Legacy workspaces
therefore stay on regressed launch shapes indefinitely while the doctor
hint promises otherwise. Per the user mandate of 2026-07-17, vaultspec-owned
artifacts must converge to the mandated standard automatically on the next
upgrade or sync, regardless of the workspace's provisioned version, with
ample user-facing description of what changed and why.

## Considerations

- The ownership sidecar already fingerprints every managed entry vaultspec
  wrote; the merge algorithm discards it, treating provably-untouched and
  hand-edited entries identically
  (`2026-07-17-upgrade-convergence-research`, fingerprint finding).
- The versioned migrations registry runs on upgrade, lazily on any vault
  verb, and via `migrations run`, gated only by the manifest's recorded
  version - the proven no-flag convergence vehicle
  (`2026-07-17-upgrade-convergence-research`, migrations finding).
- Hooks already converge unconditionally; the gaps are MCP managed entries,
  the core-only mode-flip seam, prek.toml workspaces (log-only), and stale
  companion seeds outside core's write authority
  (`2026-07-17-upgrade-convergence-research`).
- The legacy-absent dependency render bridge is deliberate and must
  survive: convergence targets the guarded shape of the workspace's OWN
  mode, never a mode change (`2026-07-13-install-mode-adr` Q6).
- Ownership discipline is a hard boundary: external entries are never
  adopted and hand-edited content is never overwritten without `--force`
  (`2026-07-15-provider-mcp-enrollment-adr`).

## Considered options

**B1 - fingerprint-verified auto-convergence.** Chosen: the managed-entry
merge gains a third path - an entry that differs from its rendered
definition but byte-matches its recorded ownership fingerprint is provably
untouched since vaultspec wrote it and is updated in place on plain `sync`
and on upgrade, no flag required, reported with a distinct refresh label
and a warning line stating the old shape, the new shape, and the reason.
Hand-edited entries (fingerprint mismatch) keep today's skip-and-warn;
external entries keep the adoption gate. Rejected: defaulting `--force` on
upgrade (overwrites hand edits and adopts external entries - a bigger
hammer than convergence needs). Rejected: status quo plus documentation
(leaves every legacy workspace regressed until manual intervention, the
exact condition the mandate closes).

**B2 - registered convergence migration.** Chosen: a versioned migration
targeting the next release re-renders every declared package's managed MCP
entry through the owning `mcp_sync` verb, riding the B1 path so it is safe
without force. Because the driver fires on `install --upgrade`, lazily on
any vault verb, and on `migrations run`, every legacy workspace below the
target version converges on first contact regardless of flags or floors.
Rejected: sync-only convergence (misses workspaces that run vault verbs
but never sync). Rejected: a migration that hand-rewrites host files
(bypasses the owning verb and the ownership discipline).

**B3 - seam widened to companions.** Chosen: the upgrade path's mode-flip
force seam covers every package declared in the workspace map, not only
vaultspec-core, so a companion's entry migrates atomically in the same run.
Rejected: core-only status quo (documented asymmetry with no rationale
beyond implementation history).

**B4 - user-facing messaging.** Chosen: every automatic refresh is
narrated - the sync result carries a per-entry line naming the entry, the
old and new launch command, and a one-sentence reason; upgrade output
aggregates the same; the doctor's drift hint stays truthful (after B1/B2,
`install --upgrade` genuinely converges); the MCP doc's install-modes
section documents automatic convergence, the hand-edited exception, and
how to opt out (`--skip mcp` at upgrade; hand-edited entries are never
touched). Rejected: silent refresh (mandate requires ample description;
silent mutation of host config erodes the trust the ownership sidecar
exists to protect).

**B5 - advisory signals for what cannot converge.** Chosen: warn-only
doctor advisories for the two convergence holes core cannot fix itself - a
prek.toml workspace whose canonical hooks cannot be refreshed, and a
companion-named definition still in the static pre-parity shape (stale
seed, remediation: re-run the companion's install). Rejected: silent
log-only status quo (invisible in the surface operators actually read).

## Constraints

- Ownership discipline unchanged: no external adoption, no hand-edit
  overwrite, without explicit `--force`; B1 refreshes only entries whose
  bytes match the recorded fingerprint exactly.
- The legacy-absent dependency render bridge holds; convergence never
  changes a workspace's mode, only the shape of its own mode's launch.
- The migration must be idempotent and route through `mcp_sync`; a re-run
  after success is a no-op (`unchanged`).
- Sync-result vocabulary stays within the established set; the refresh
  reports through the existing `updated` counter with a distinguishing
  item label so downstream consumers of counts are unaffected.
- Workspaces whose ownership sidecar predates fingerprints (name-only
  records) cannot be fingerprint-verified; they keep skip-and-warn and the
  doctor hint names `--force` for them honestly.
- The pipeline stays within core; companion seed content remains the
  companion's to fix (rag issue 231).

## Implementation

The merge algorithm reads the recorded fingerprints alongside the managed
name set and adds the refresh path between `unchanged` and the force gate:
recorded-fingerprint match plus definition mismatch updates the entry,
re-fingerprints it, counts as `updated` with a refresh-labeled item, and
appends a warning line describing old command, new command, and reason.
The upgrade path passes every declared package to the mode-flip seam
instead of the core-only set. A new migration module registers against the
next release version and invokes `mcp_sync` per enrolled provider at
project scope, letting B1 do the byte work; its result feeds the standard
migration reporting. The doctor's mode-mismatch and drift hints are
re-worded to the now-truthful remediation set, and the doctor gains the
two B5 advisories. The MCP documentation's install-modes section grows a
convergence-on-upgrade passage stating the automatic behavior, the
hand-edit exception, and the opt-outs. Tests cover: untouched-entry
refresh on plain sync, hand-edited entry preserved with warning, name-only
legacy sidecar preserved with honest hint, migration idempotence on real
workspaces in both modes, companion entry refresh through the widened
seam, and the two advisories.

## Rationale

The fingerprint path is the narrowest mechanism that satisfies automatic
convergence regardless of version without weakening the ownership
discipline the enrollment decision established: it converts information
the sidecar already records into the safety proof the force gate lacked,
so the only entries that converge are the ones vaultspec itself wrote and
nobody touched since (`2026-07-17-upgrade-convergence-research`). The
migration extends the same convergence to workspaces that never run `sync`
directly, reusing the registry's proven triggers instead of inventing a
new hook. Widening the seam and re-wording the hints correct documented
asymmetries surfaced by the same research. Messaging is a first-class
deliverable rather than an afterthought because the mandate says so
explicitly, and because automatic mutation of host configuration is only
trustworthy when it explains itself.

## Consequences

- Good: every vaultspec-written launch artifact converges to the mandated
  standard on the workspace's next upgrade, sync, or vault verb; the
  regressed-legacy class closes without operator flags, and the operator
  reads exactly what changed and why in the command output.
- Good: hand-edited entries and external entries remain untouchable
  without `--force`; the safety boundary is sharper than before, not
  looser, because the refresh path demands fingerprint proof.
- Bad: a workspace whose sidecar predates fingerprints converges only via
  `--force`; the honest hint mitigates but does not remove the manual step
  for that cohort.
- Bad: automatic refresh means a workspace's committed provider config can
  change on a routine vault verb via the lazy migration trigger; the
  narrated output and idempotence bound the surprise, but a diff appearing
  outside an explicit sync is new behavior operators must learn.
- Neutral: sync-result counters are unchanged in shape; the refresh rides
  `updated`. The mode model, render bridge, floors, and enrollment
  boundaries are untouched.
