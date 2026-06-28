---
tags:
  - '#adr'
  - '#diagnosis-surface-parity'
date: '2026-06-28'
modified: '2026-06-28'
related:
  - "[[2026-06-28-diagnosis-surface-parity-audit]]"
  - "[[2026-03-27-cli-ambiguous-states-resolver-adr]]"
  - '[[2026-06-28-diagnosis-surface-parity-research]]'
---

# `diagnosis-surface-parity` adr: `single comparator for provider artifact parity` | (**status:** `accepted`)

## Problem Statement

The audit found that `install`, `sync`, and `spec doctor` each decide independently
whether a provider artifact matches its source, and the copies have drifted: the doctor's
`collect_content_integrity` compares filenames only and reports clean files that `sync`
will rewrite, the snapshot lifecycle has no owner for orphan pruning, the MCP writer and
the doctor's foreign-file detector disagree on what may live in a provider directory, and
`install --dry-run` previews at a coarser granularity than `sync`. The ambiguous-states
resolver ADR already specified the intended design - content integrity reuses the sync
infrastructure and SHA-256 compares expected against actual, with a `DIVERGED` signal for
content mismatch - so this is not a new architecture but a restoration of conformance plus
a stated rule against future re-divergence.

## Considerations

The same question - "is this provider file in sync with its source" - is answered today
by `apply_file_sync` (content-exact, canonical), `check_outdated` (content-exact),
`list_modified_builtins` (content-exact), and `collect_content_integrity` (name-only, the
outlier). The canonical comparator already exists and is correct; the defect is that one
surface bypasses it. The fix must not introduce a fifth comparator; it must route the
doctor through the existing one.

## Considered options

- **Route every parity decision through one comparator (chosen).** The doctor computes
  expected rendered content via the same sync rendering path and compares it to the
  destination, emitting `DIVERGED` on mismatch. One body of code owns the decision; the
  three surfaces become views over it. Restores conformance to the resolver ADR.

- **Patch the doctor's name-only check to also read content, independently.** Rejected:
  adds a second content comparator that can itself drift from `apply_file_sync`, which is
  the exact defect being fixed.

- **Make `sync` looser to match the doctor (name-only).** Rejected: would hide real
  content drift and defeats the purpose of sync.

## Constraints

No new dependencies. The change is confined to the diagnosis collectors, the snapshot
module, the MCP/host-native registry, and the install dry-run renderer; it relies on the
existing, stable sync rendering path (`apply_file_sync` and the resource collectors), so
there is no frontier risk. Tests must follow the project's zero-mock standard and assert
against a real workspace rather than patched comparators.

## Implementation

Content integrity is rebuilt as a thin view over the sync renderer: for each managed
provider file the collector obtains the expected rendered text from the shared rendering
path and compares it (hash or bytes) to the on-disk destination, reporting `CLEAN`,
`DIVERGED` (content differs), or `STALE`/orphan (no source). Orphan-snapshot pruning gets
a single owner in the snapshot module, invoked so that retiring a builtin returns
`builtin_version` to clean. The set of files that legitimately live in a provider
directory becomes one registry shared by the MCP writer and the doctor's foreign-file
detector, extended to cover `mcp_config.json` and its lock sibling. The install dry-run
preview is brought to per-file granularity so it matches sync. The redeclared add/update
classifications (codex agents, MCP sync) are folded back onto the canonical comparator or
a single extracted helper.

## Rationale

The resolver ADR already chose content-exact comparison reusing sync; the audit shows the
implementation regressed to name-only. Re-deriving the same decision in multiple places is
the documented root cause of the contradictions, so the durable fix is one comparator with
the surfaces as views, not better-synchronised copies.

## Consequences

The doctor will begin reporting content drift it previously hid (the `DIVERGED` signal
goes live), which may surface latent staleness in existing workspaces - correct, but
louder. Pruning orphan snapshots changes `builtin_version` from a permanent error to a
recoverable state. Centralising the provider-file registry and the comparator reduces the
surface area where drift can reappear, and gives the codebase-wide sweep a concrete
pattern to search for. The risk is incomplete consolidation: if any surface keeps a
private copy of the decision, the contradiction returns, so the sweep is the safeguard.
