---
tags:
  - '#adr'
  - '#cli-blast-radius-gating'
date: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
  - '[[2026-05-17-cli-blast-radius-gating-research]]'
---

# `cli-blast-radius-gating` adr: `Gate every destructive verb consistently` | (**status:** `accepted`)

## Problem Statement

The CLI gates destructive verbs asymmetrically: `install`
writes ~70 files with no gating, `uninstall` requires
`--force`, `install --upgrade` has an empty `--dry-run`,
`vault feature archive` has no `--dry-run` and no reversal.
Per-verb gating choices appear to have been made independently;
there is no framework-wide discipline.

Findings S4, S14, and the gating dimension of B9.

## Considerations

- A framework-wide gating contract is small to specify and
  large in payoff. It applies to every verb that writes or
  removes state.
- Some verbs are additive in the common case (install creates
  files where none existed). Gating must distinguish between
  additive and destructive paths within a single verb rather
  than applying blanket `--force` everywhere.
- `--dry-run` is the central mechanism. Every state-changing
  verb gets it; the implementation cost is small if the verb
  is built around an explicit state diff.
- The fix coordinates with the sync-vocabulary ADR: the
  canonical outcome words give every `--dry-run` output a
  consistent shape (each affected item carries its prospective
  outcome word).

## Constraints

- Adding `--force` as required on `install` is a breaking
  change for any automation that runs unattended. A one-release
  deprecation window with a warning is the standard transition.
- `--dry-run` must produce accurate output. A wrong preview
  is worse than no preview. Implementations must share code
  paths with the real run so the preview and the run cannot
  drift apart.
- Reversal verbs (where defined) must also be safe. A
  `vault feature unarchive` must itself have `--dry-run` and
  honest exit codes.

## Implementation

**Gating contract.** Every CLI verb that writes or removes
state declares against the framework-wide contract:

- **Additive paths** (create-only, no overwrite): no `--force`
  required.
- **Destructive paths** (overwrite, remove, or move existing
  state): `--force` required.
- **Mixed paths** (e.g., `install --upgrade` which preserves
  authored but overwrites builtin): the destructive sub-path
  requires `--force` independently. Additive sub-path runs
  without gating. The verb prints in advance which sub-path
  is active.

**Universal `--dry-run`.** Every state-changing verb
implements `--dry-run`:

- Reads current state.
- Computes the prospective change.
- Renders the change as a unified diff (for file mutation) or
  per-item action list (for batch operations).
- Produces no side effects.
- Exits 0 on success, non-zero on errors that would prevent
  the real run.

Empty-preview output is a bug; the verb must produce either a
non-empty diff (changes would happen) or an explicit "no
changes" line (changes would not happen).

**Preservation contracts in success lines.** Every verb with
a preservation guarantee names what it preserved:

- `install --upgrade` success line names how many authored
  resources were preserved and how many builtin resources
  were updated (sync-vocabulary ADR's `updated` word). The
  S14 paper cut closes.
- `vault feature archive` success line names how many
  cross-feature `related:` links were rewritten (per the
  memory-lifecycle ADR's archive fix).
- `vault check ... --fix` success line names how many
  findings were resolved and how many were unfixable.

The preservation summary is one line. It is human-readable.
It is also a top-level field in `--json` output.

**Reversal verbs for destructive paths.**

- `uninstall` is the reversal of `install`. Exists today; gets
  `--dry-run` added.
- `vault feature unarchive` is the reversal of
  `vault feature archive` (per the memory-lifecycle ADR).
- `spec * restore <name>` reverses `spec * remove <name>` if
  the resource was a customised builtin; for authored
  resources, removal is permanent (the operator's
  responsibility to keep version control).
- Where no clean reversal verb exists, the verb's `--help`
  must state plainly that the operation is one-way and point
  the user at recovery strategies (restore from git,
  re-author from notes).

**Interactive confirmation gate.** When a destructive verb is
invoked without `--force` AND stdin is a TTY (interactive
session), the verb prints the diff and prompts for
confirmation. Non-interactive invocations require `--force`
explicitly. The two modes are documented in `--help`.

**Companion language updates.**

- Framework manual section on destructive operations is
  rewritten to describe the contract uniformly.
- `--help` text on every state-changing verb names the
  contract's gating shape ("destructive operation: requires
  `--force` or interactive confirmation").
- Builtin rule files that discuss when to use each verb are
  updated to recommend `--dry-run` first as standard practice.
- Agent personas adopt "always `--dry-run` before applying a
  destructive verb" as a documented behaviour.

## Rationale

The audit found three first-class destructive verbs with
three different gating shapes. Each was probably chosen on its
own when the verb was written. The fix is to define the
contract once and require new verbs to honour it.

Universal `--dry-run` is the foundation. With it, every
operation is previewable, every diff is inspectable, and the
risk of "install in the wrong directory" recedes from a
cleanup story to a confirmation friction.

The preservation summary changes how `install --upgrade`
feels in production. Today the operator runs it and hopes;
the new success line names the preserved set. The change is
small (one line of output) but the trust gain is large.

Reversal verbs round out the contract. Some destructive
operations (file removal at the OS layer) are not reversible
through CLI mechanism; the manual is honest about that and
points at version-control recovery.

## Consequences

Gains. Destructive operations are no longer surprising. Every
state-changing verb has a preview. Every overwrite requires
explicit consent. The "asymmetric gating" finding closes
because all verbs share the same contract.

Difficulties. Existing automation that calls `install` without
flags will warn for one release, then break in the release
after. The deprecation must be announced. Pre-commit hooks
that invoke `install` or `sync` non-interactively are common;
they need migration to `--force`.

Pitfalls. `--dry-run` is a performance burden if naively
implemented twice (once for preview, once for real). The
implementations must share code paths so they cannot drift
apart. A `--dry-run` that lies about what the real run will
do is the worst case.

Pathways. Once gating is uniform, the failure modes the
audit found around `install` / `uninstall` / `install --upgrade` / `archive` collapse into one shape. Future
destructive verbs (rule remove, agent remove, etc.) inherit
the contract.
