---
tags:
  - '#adr'
  - '#status-hardening'
date: 2026-06-13
modified: 2026-06-13
related:
  - '[[2026-06-13-status-hardening-research]]'
  - '[[2026-06-12-vault-orientation-adr]]'
---

# status-hardening adr: status discovery mini-framework | (**status:** `accepted`)

## Problem Statement

The orientation surface shipped in 0.1.29 (`2026-06-12-vault-orientation-adr`,
D1-D8) answers "what exists, what is active, what changed" but blind testimonial
review (`2026-06-13-status-hardening-research`) shows it stops short of being the
zeroth-step discovery mini-framework the project wants. Six no-context reviewers
operating only the CLI converged on: agents reach for a top-level `status` that does
not exist (F1); no view gives a one-line per-plan overview of level, open/completed
waves, completed phase, and the current open step (F2); the `vault plan *` commands
reject stems and feature handles with raw tracebacks while `vault status` resolves
all forms (F3); discovering a feature's exact files is clunky and paths hide behind
`--json` (F4); the in-flight headline is empty and misleading (F5); recency knobs
flood the view with exec rows (F6); and the graph/orientation summary relists `index`
documents, double-counting a feature's docs (F8). This ADR decides the hardening:
verb placement, per-plan enrichment, target resolution, file discovery, recency
hygiene, and the firmware move.

## Considerations

- The predecessor ADR's invariants hold: orientation is read-only, descriptive not
  auditing, produces no artifact, keeps the graph an implementation detail, reads the
  CLI-owned `modified:` stamp for recency, and computes everything in one batched pass
  (D1, D3, D5, D6, D7, D8). The hardening composes on these, it does not relitigate them.
- One plan per feature is a hard project rule, so a feature handle resolves to exactly
  one plan document - the basis for handle resolution in the `vault plan *` commands.
- The per-container completion facts (which waves/phases are fully closed, which step is
  next open) are derivable from data the batched core already parses; no new storage or
  traversal is required.
- The brief asks for a **clean** rendering: column-aligned, label-light, no progress
  glyphs by default, and consistent everywhere a plan line appears.
- `firmware-reference-parity` forbids naming an unshipped verb in firmware; the
  top-level `status` verb and its firmware mandate must land in the same change. The
  generated `reference/cli.md` is CLI-owned and regenerated, never hand-edited.

## Constraints

- Removing `vault status` is a breaking change to shipped firmware references and the
  existing test suite; both must move in the same change (accepted, see H1).
- Per-row step recency has no stored signal (predecessor constraint); "next open step"
  is positional (first unchecked step in document order), not time-derived.
- `index` documents are derived aggregates of a feature's other documents; counting or
  relisting them in a summary double-counts (F8).
- Handle resolution must degrade to the same near-match error contract `vault status`
  already uses, never a raw `FileNotFoundError` traceback.

## Implementation

Decisions stated as the option chosen and its shape (H-numbered, continuing the
orientation ADR's D-series):

- **H1 - Status moves to top-level; `vault status` is removed.**
  `vaultspec-core status [TARGET]` is the orientation verb: no argument renders the
  vault-wide rollup, a target (plan stem, plan path, or feature handle) renders the
  grounding trace. `vault status` is removed entirely - the project chose a clean
  surface over back-compat. The orientation data core
  (`vaultcore/orientation.py`) is unchanged; only the CLI mounting moves from
  `cli/vault_cmd.py` to `cli/root.py`. The deep single-plan validator remains at
  `vaultspec-core vault plan status` (unchanged scope).

- **H2 - Per-plan enrichment in the batched core.** `PlanStatus`
  (`plan/status.py`) gains `waves_completed`, `phases_completed`, and
  `next_open_step` (the canonical display path of the first unchecked step, or `None`
  when the plan is complete). A wave/phase is "completed" when every step it contains
  is checked. These are computed inside the existing single batched pass (D6) and
  carried through `PlanInFlight` (`orientation.py`). `status_to_json_dict` and the
  status JSON envelope gain the new fields (contract addition, not a break).

- **H3 - One clean plan line, consistent across surfaces.** The canonical line is
  column-aligned, no glyphs:

  ```
  <feature>   <tier>   W<c>/<T>   P<c>/<T>   <k>/<N> steps   <p>%   next <display-path>
  ```

  Waves/phases render `-` when the tier has no such container (L1 has neither; L2 has
  phases, no waves). `<display-path>` is the next open step's tier-conditional id
  (e.g. `W02.P05.S21`). The same line renders in the rollup "Plans in flight"
  section; the rollup "Active features" rows carry the condensed tail
  `<tier> <k>/<N> <p>%`; and the targeted trace prints the line as a header above its
  step list. This is the codified clean look - one renderer, reused, so the surfaces
  cannot drift.

- **H4 - Check-state in the targeted trace.** Each step row in the grounding trace
  shows `[x]`/`[ ]`, and the first open step is marked as the cursor. The trace
  becomes self-sufficient for "what is the next open step" without a follow-up
  `vault plan query --open`.

- **H5 - In-flight criterion surfaced; recently-completed bucket (F5).** The rollup
  annotates the in-flight section with its criterion (>=1 open step) and adds a
  "Recently completed" section: plans at 100% whose `modified:` falls within the
  active recency window, ordered most-recent first. A just-finished plan is visible
  rather than silently absent.

- **H6 - Recency knobs bound exec noise (F6).** `--limit` applies uniformly to every
  document-type group, `exec` included. The rollup collapses the `exec` group to one
  line per feature (record count + latest date) by default; a `--verbose-exec` flag
  restores per-record rows. `--since` honours the same per-group cap.

- **H7 - File discovery surfaces paths (F4).** The grounding trace gains a `--paths`
  human mode that prints each document's repo-relative path beside its stem, and the
  trace `--json` carries a `path` field alongside every stem (steps' record paths,
  summaries, grounding docs). Paths come from the existing graph nodes; no new
  traversal, and the graph itself still never leaks into output (D5/D7 preserved).

- **H8 - Summaries drop `index` documents (F8).** `index` documents are excluded from
  the rollup's recent-documents grouping, from the active-feature and any graph
  summary counts, and from the grounding grouping, so a feature's documents are never
  double-counted or relisted via its index aggregate.

- **H9 - Shared plan-target resolver; stems and feature handles resolve (F3).** A
  single resolver (promoted to `cli/_target.py`, consumed by both the orientation verb
  and every `vault plan *` command) accepts a literal path (absolute or relative),
  `stem`, `stem.md`, a feature name, or `#feature` tag, resolving a handle to the
  feature's one plan at `.vault/plan/<stem>.md`. Unresolvable input raises the same
  near-match "Did you mean: ...?" error the orientation verb uses - never a raw
  traceback. `vault plan query` gains `--target`; `vault plan status`/`check`/`step`
  resolve against the target vault rather than CWD. The `vault plan step` handler
  converts resolution failures into the user-facing error contract.

- **H10 - Firmware and generated reference move with the verb (parity).**
  `builtins/system/03-vaultspec.md` (orient-first) and
  `builtins/rules/vaultspec-cli.builtin.md` (zeroth-move prose + command table) are
  rewritten to teach `vaultspec-core status` and its targeted form;
  `builtins/reference/cli.md` is regenerated through the CLI-owned generator. All land
  in the same change that ships the verb, satisfying `firmware-reference-parity`.

- **H11 - Secondary gaps (F7).** When `.vaultspec/` is absent the CLI emits a graceful
  error that names the missing directory and suggests `--target` / the nearest vault
  rather than a bare failure. `vault feature list` gains a `latest_activity` column
  (human + JSON) and a `--stale-days N` filter. The per-plan line appends a small
  `!<n>` flag when `exec_missing_ids` is non-empty (steps checked but lacking an
  execution record), making the checked-but-ungrounded state distinct from open steps.

## Rationale

The enrichment is composition, not new storage: the batched core already parses every
plan's containers and checkboxes once, so per-wave/per-phase completion and the
first-open-step cursor fall out of the same pass (H2/D6). One reused renderer (H3)
keeps the clean look identical in the rollup, the active-features rows, and the trace
header, which is why the format is codified once rather than per call site. Moving
`status` to the top level (H1) honours the brief's "status is the top-level command"
literally and makes the zeroth move the most reachable verb; removing `vault status`
was chosen over an alias because the project favours a clean surface and the firmware
and tests move in the same change anyway. Handle resolution (H9) leans on the
one-plan-per-feature rule so a feature name is an unambiguous target, and it reuses the
orientation verb's existing near-match error so the two surfaces finally agree on what
a target is. Dropping `index` from summaries (H8) removes the double-count the
reviewers saw without touching the graph's internal use of those nodes. Throughout, the
predecessor invariants hold: read-only, no artifact, graph stays an implementation
detail, recency stays the `modified:` stamp.

## Consequences

- `vaultspec-core status` is the single reachable orientation entry point; firmware,
  the generated reference, and the test suite move together (H1, H10). External muscle
  memory for `vault status` breaks - called out in release notes.
- The per-plan line answers level / open-completed waves / completed phase / next open
  step in one glance, in the rollup and the trace, without command-stitching (H2-H4).
- The status JSON envelope grows fields (`waves_completed`, `phases_completed`,
  `next_open_step`, per-document `path`); additive, but downstream parsers gain data.
- Every `vault plan *` command accepts the same target forms as the orientation verb,
  ending the asymmetry and the tracebacks (H9); `vault plan query` gains `--target`.
- Recency output is bounded and readable even on active vaults (H6); the in-flight
  headline stops misleading (H5); summaries stop double-counting index docs (H8).
- Scope is deliberately broad this cycle (F1-F8); the plan sequences it into waves so
  the core enrichment lands before the surfaces that render it.

## Codification candidates

- **Rule update (not new):** the existing `orientation-before-work` / zeroth-move
  mandate in `vaultspec-cli.builtin.md` is edited to name `vaultspec-core status`
  (gated on H1/H10 shipping in the same change).
- **No new always-on rule** for the per-plan line or resolver: both are
  implementation-enforced (renderer and resolver), and a rule restating them would be
  tautological context cost, consistent with the predecessor ADR's stance on the
  `modified:` stamp.
