---
tags:
  - '#research'
  - '#status-hardening'
date: 2026-06-13
modified: 2026-06-13
related:
  - '[[2026-06-12-vault-orientation-adr]]'
  - '[[2026-06-12-vault-orientation-research]]'
---

# status-hardening research: blind testimonial peer review of the status surface

## Goal

The `vault status` orientation surface shipped in 0.1.29 (see
`2026-06-12-vault-orientation-adr`, decisions D1-D8). This research hardens it
toward a **status discovery mini-framework**: the zeroth move of the pipeline,
encoded in both firmware and CLI, that an agent or developer uses to discover and
investigate the codebase, the vault, in-flight features, and recent modifications.

To ground the hardening in real usage rather than code reading, six **blind
testimonial reviewers** were run: no-context agents barred from reading any source
or vault file, permitted only to operate `vaultspec-core` from the shell. Each was
given a distinct developer goal and reported friction verbatim. This document
ingests those testimonials and maps them to a ranked hardening surface.

## Method

Six personas, each Bash-only against the real ~733-document vault, no file reads:

- **cold-start newcomer** - orient in an unfamiliar repo from zero.
- **completion auditor** - quantitatively verify an "almost done" claim.
- **file-discovery agent** - enumerate the exact files (with paths) of one feature.
- **resumption agent** - find the next open step to continue an in-flight plan.
- **targeting stress-tester** - map which target forms each command accepts/rejects.
- **recency / staleness triager** - sweep for fresh vs stale work; test `--since`/`--limit`.

Convergence across independent personas is treated as signal; a lone complaint is
noted but not prioritized.

## Convergent findings (ranked)

### F1 - `status` is not the zeroth-step top-level verb agents reach for (5/6)

Every persona that started cold typed `vaultspec-core status` first. It errors
(`No such command 'status'`). The orientation verb is two levels deep at
`vault status`, and nothing in top-level `--help` hints at it. The shipped firmware
already teaches `vault status` as the zeroth move (D8), but the *ergonomic* entry
point the user's brief calls for - a top-level `status` - does not exist.
**Maps to the brief: "Status is going to be the top-level command, encoded in both
the firmware and the CLI."**

### F2 - No one-line per-plan status enrichment anywhere (6/6)

This is the dominant finding and the centre of the user's brief. No single view
shows, for a plan, its **level (tier)**, **open vs completed waves**, **completed
phase**, and **current open step / open status**:

- The rollup's *Active features* line shows only `name  N docs  plan  date` - no
  tier, no completion, no open-step signal.
- The rollup's *Recent changes* plan rows show only `stem  date`.
- `vault plan status <path>` is the *only* place tier + wave/phase/step counts +
  completion% appear together - but it shows aggregate counts only: no per-wave or
  per-phase completion breakdown, and never "the next open step is X".
- The grounding trace (`vault status <target>`) lists steps flat with **no `[x]`/`[ ]`
  markers** and no "you are here" cursor; on a 126-step plan it is an unreadable wall.

Personas had to stitch three commands (`vault status <stem>` + `vault plan status <path>` + `vault plan query --open`) and still could not answer "which wave is
active and what is the next open step?" in one glance.
**Maps to the brief: the requested one-line enrichment (level, open/completed waves,
completed phase, completed step or open status).**

### F3 - The `vault plan *` commands reject stems and feature handles; only raw paths work, and rejection crashes (5/6)

`vault status` is a flexible resolver: it accepts a bare feature name,
`#feature` tag, plan stem, `stem.md`, relative path, and absolute path - all six work,
and unresolvable input yields a clean "Did you mean: ...?" near-match hint.

`vault plan status` / `query` / `check` / `step` accept **only a literal filesystem
path**. A stem or feature name raises a raw Python `FileNotFoundError` traceback
(40+ lines, internal paths) with no near-match help. The asymmetry is acute because
**`vault status`'s own "Suggested Next Step" advisory prints a stem** -
`> vaultspec-core vault plan status 2026-06-12-vault-orientation-plan` - and that
suggested command then crashes. `vault plan step toggle` with a bad target swallows
the error and prints nothing at all (`plan_cmd.py` handler does not convert
`FileNotFoundError` to a user-facing message).
**Maps to the brief: "the plan CLI should allow passing in relative file names as
well as feature handles ... a plan with a feature [tag] would always resolve" (one
plan per feature).**

### F4 - File discovery for a feature is clunky; human output is stems, openable paths hide behind `--json` (4/6)

The natural "show me this feature's files" command is `vault status <feature>`, but
its grounding trace - even in `--json` - emits **stems only, never paths**. Real
openable absolute paths appear only in `vault list --feature <tag> --json` and
`vault graph --feature <tag> --json`. So the file-discovery flow is: run the trace,
discover it lacks paths, switch to a *different* command with `--json`, and parse
JSON. The `vault graph --feature` tree is visually rich but titles are truncated
mid-sentence and it still gives no paths in human mode.
**Maps to the brief: "The graphing implementation is clunky. If an agent wants to
discover the exact files being referenced by a feature, it is somewhat difficult."**

### F5 - "Plans in flight" is always empty and its criterion is invisible (4/6)

Because every recent plan is 100% complete, the rollup's most prominent section
reads "Plans in flight: none" on every run. Reviewers could not tell whether this
meant "all done", "broken", or "misconfigured". A plan that crosses 100% silently
vanishes from the rollup with no "recently completed" trace, which actively misleads
an auditor checking on recent work. The in-flight definition (>=1 open step, per D2)
is correct but unexplained and, in this vault state, yields an empty headline.

### F6 - `--limit` does not bound exec records; `--since` floods the view (2/6)

`--limit N` trims adr/plan/research/audit groups but leaves the `exec` group
uncapped; `--since 7` dumps 200+ individual exec step records, drowning signal.
`--limit 3 --since 7` is still hundreds of lines. There is no per-type cap and no
"collapse exec to one line per feature" mode.

### F7 - Secondary surface gaps (target discovery, feature dates, exec-missing)

- **Target/vault discovery** (6/6 hit it, but partly an artifact of this worktree
  lacking `.vaultspec/`): no walk-up to the nearest vault, no `vault locate`, and a
  bare error when `.vaultspec/` is absent. Worth a graceful error + discovery hint;
  *not* the headline, as it is environment setup more than status design.
- **`vault feature list`** has no `latest_activity` column (human or JSON carries
  only `earliest_date`) and no `--stale-days` filter, so staleness must be inferred.
- **`exec_missing` vs `open`** are different concepts with no bridging query (a step
  can be `[x]` yet have no execution record); only `vault plan status --json` exposes
  `exec_missing_ids`.
- **`vault plan query` lacks `--target`** and `vault plan status` resolves its path
  relative to CWD, ignoring `--target` (a real bug, tangled with F3).

## Mapping to the user's brief

| Brief item                                                                                               | Finding | Priority      |
| -------------------------------------------------------------------------------------------------------- | ------- | ------------- |
| Status as top-level command (firmware + CLI), the zeroth step                                            | F1      | High          |
| One-line per-plan enrichment: level, open/completed waves, completed phase, completed step / open status | F2      | High (centre) |
| Plan CLI accepts relative filenames AND feature handles                                                  | F3      | High          |
| Graphing clunky; hard to discover a feature's exact files                                                | F4      | High          |
| (emergent) In-flight headline misleads; no recently-completed                                            | F5      | Medium        |
| (emergent) recency knobs flood with exec noise                                                           | F6      | Medium        |
| (emergent) target discovery, feature dates, exec-missing                                                 | F7      | Low           |

## Hardening surface (implementation anchors)

- **Top-level verb** - `src/vaultspec_core/cli/root.py` registers top-level commands;
  `status` would mount here, delegating to the existing orientation core. `vault status`
  stays (alias or retained) for back-compat and firmware-reference-parity.
- **Per-plan enrichment** - the data core in `src/vaultspec_core/vaultcore/orientation.py`
  (`PlanInFlight`, `compute_rollup`) and `src/vaultspec_core/plan/status.py`
  (`PlanStatus`, `collect_status`). Today `PlanStatus` carries `tier`, `wave_count`,
  `phase_count`, `step_count`, `steps_completed`, `completion_percent` but **no per-wave
  / per-phase completion and no next-open-step**. Enrichment adds those, and the
  renderer prints the one-line summary.
- **Plan-CLI resolution** - `src/vaultspec_core/cli/plan_cmd.py` and
  `cli/_target.py`. `vault status` already resolves stem/tag/path in
  `orientation._resolve_target`; a shared resolver should back the `vault plan *`
  `PATH` argument so a stem or feature handle resolves to `.vault/plan/<stem>.md`
  (one plan per feature makes a feature handle unambiguous), with a clean
  near-match error instead of a traceback.
- **File discovery** - `compute_trace` / `PlanTrace` / `StepTrace` already hold the
  graph neighbours; surfacing paths (a `--paths` mode and/or `path` fields in the
  trace JSON) closes F4 without new traversal.
- **Firmware** - `builtins/system/03-vaultspec.md` (orient-first),
  `builtins/rules/vaultspec-cli.builtin.md` (zeroth-move + command table), and the
  CLI-owned generated `builtins/reference/cli.md`. Per `firmware-reference-parity`,
  firmware may name the top-level `status` verb only in or after the change that
  ships it; the generated reference is regenerated, never hand-edited.

## Constraints carried from the predecessor ADR

- Orientation is **read-only, no artifact, descriptive not auditing** (D1/D8). The
  hardening must not turn `status` into a checker or a mutator.
- Recency reads the CLI-owned `modified:` stamp leniently, falling back to `date:`
  then filename (D3/D3b); enrichment must not introduce a new recency source.
- The graph stays an **implementation detail**: output is stems/paths and hints, never
  edge lists or node-link JSON (D5/D7). File-discovery hardening surfaces paths, not
  the graph.
- The batched status core (D6) is the single pass; per-wave/per-phase enrichment must
  extend that core, not add per-plan rescans.

## Open design forks (for ADR)

1. Top-level `status`: a thin alias delegating to `vault status`, or the canonical
   home with `vault status` retained as alias? (back-compat, firmware parity, tests)
1. One-line enrichment format and where it appears (rollup in-flight rows only, or
   also active-features rows and the targeted trace header).
1. Plan-CLI resolution: shared resolver promoted to `cli/_target.py` vs local helper;
   error contract (near-match parity with `vault status`).
1. Scope: include the medium/low emergent findings (F5/F6/F7) in this cycle or defer.
