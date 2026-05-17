---
tags:
  - '#research'
  - '#cli-blast-radius-gating'
date: '2026-05-17'
related:
  - "[[2026-05-17-cli-simplification-ux-audit]]"
---

# `cli-blast-radius-gating` research: `Destructive verbs are gated asymmetrically`

Synthesis note for findings S4 (round 1) and S14 (round 3a).
Captures the evidence behind the sibling ADR.

## Findings

### S4 — `install` is destructive-by-default; `uninstall` requires `--force`

Round-1 finding [09]. The `install` verb writes about seventy
files into the target on first run, silently appends a managed
block to `.gitignore`, writes `.mcp.json`, and creates
`CLAUDE.md`. None of this requires a flag. The `uninstall` verb,
which removes the same content, explicitly requires `--force`
with the message "Uninstall is destructive".

The asymmetry is inverted relative to the actual blast radius.
Adding seventy files into a workspace and rewriting top-level
configuration files is at least as hard to undo as removing
them. Yet only removal is gated. A teammate who runs `install`
in the wrong directory has a harder cleanup story than a
teammate who runs `uninstall` in the wrong directory.

### S14 — `install --upgrade` has no preview and no preservation summary

Round-3a finding [51]. `install --upgrade --dry-run` produces
an empty preview. The real run cleanly preserves all authored
content but the success line never names what was preserved.
The highest-blast-radius verb in the CLI ships without a
preview path.

The verb is also the path that handles framework version
bumps — exactly the operation a user wants to preview before
running on a production project.

### B9 archive — same shape at a different verb

Round-3b critical finding. `vault feature archive` has no
`--dry-run`, no reversal, no preservation guarantee. The
verb that retires a feature ships with weaker gating than
the verb that adds steps to a plan.

### The pattern across the three findings

Three first-class destructive verbs (`install`, `install
--upgrade`, `vault feature archive`) all ship with inadequate
gating. One forces `--force` for removal but not for
addition (S4). One has no preview (S14). One has no preview
and no reversal (B9). The framework's gating choices appear
to be per-verb decisions rather than a framework-wide
discipline.

### What gating should look like

For a verb to be safe in production:

- `--dry-run` mode that previews exactly what would change.
  Shows a unified diff or a per-item action list, depending
  on what's natural for the verb. Must produce no side
  effects.
- `--force` flag required when the verb would overwrite or
  remove existing state. Required is the floor; some verbs
  may also require interactive confirmation.
- A preservation guarantee documented in the verb's
  `--help` text where preservation is part of the contract
  (e.g., `install --upgrade` preserves authored content).
  The success-line output names what was preserved.
- A reversal verb where the operation is destructive (the
  archive case).
- Honest exit codes per the spec-edit-safety ADR's
  invariant.

## Constraints identified

- Backwards-compat: existing scripts that call `install`
  without flags should not start failing. Adding a new
  required flag is a breaking change; a one-release
  deprecation window with a warning is the standard
  transition.
- Some destructive operations are part of expected workflows
  (a fresh-install developer expects files to be created).
  The fix is not to gate every state-changing verb, but
  to gate the destructive paths within otherwise-additive
  verbs.
- `--dry-run` must produce useful, accurate output. An empty
  preview (S14) is worse than no preview because it
  affirmatively misleads the user.

## Recommendation

Adopt a framework-wide gating discipline. Every verb that
writes or removes state gets a `--dry-run` mode that
produces accurate, non-empty output. Every verb that
overwrites existing state requires `--force`. Every verb
with a preservation guarantee names what was preserved in
its success line. Every destructive verb has a documented
reversal path. Full design in the sibling ADR.
