---
tags:
  - '#research'
  - '#cli-scaffolder-integrity'
date: '2026-05-17'
modified: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
---

# `cli-scaffolder-integrity` research: `Scaffolders emit invalid values their own validators then reject`

Synthesis note for the scaffolder-antipattern cluster. Captures
the evidence behind the sibling ADR.

## Findings

### B2 — `vault add plan` ships `tier: L{#}` as a literal frontmatter value

Round 1 evidence (Joan, finding [11]). On a freshly scaffolded plan
document, the frontmatter contains:

```
tier: L{#}
```

The literal string `L{#}` is intended as a placeholder. The plan
validator on the same CLI surface then rejects the document with
an uncaught `PlanFrontmatterError: tier must be one of L1, L2, L3, L4; got 'L{#}'` and prints a Python traceback to stderr.

Joan crashed on it within minutes of first install. Xavi spotted
it on round 1 and hand-patched the value before invoking any plan
command. Joan reproduced the same friction unchanged in round 2.
Xavi reproduced it unchanged in round 3 ([41] in his SESSION.md
round-3 list). Three rounds; same wart.

### B5 — `vault plan tier promote` writes literal `TODO: Phase title`

Round 2 evidence (Joan, finding [23]). Running `vault plan tier promote ... --target L2` with the minimum flags writes a
synthesised phase containing `TODO: Phase title` as the phase
title. The very next `vault check all` flags the document as
failing.

Same antipattern as B2: the scaffolder emits a value the validator
on the same surface rejects.

### The shared shape

Both findings have the same structure:

- The scaffolder needs a value that is mandatory for the validator.
- It does not have one.
- It writes a recognisable placeholder.
- The validator does not recognise the placeholder; it rejects the
  document.

The fix is to either (a) make the input mandatory at scaffold time
(via a CLI flag), or (b) make the scaffolder refuse to write
when the input is missing.

### Why this matters more than it looks

These are not cosmetic. The scaffolder is the user's first contact
with each document type. The user reasonably assumes that a CLI
command named `vault add plan` produces a valid plan. When the
next command in the workflow then declares the document broken,
the user's mental model of "what does this tool do" is destabilised
on the first action. New-hire onboarding is exactly the moment
this antipattern is most expensive.

For Joan, the experience was: install vaultspec, create a feature,
crash on the very next command. The recovery story (hand-edit the
frontmatter) requires the new hire to violate the framework's
"do not hand-edit" rule on their first day, with no
acknowledgement from the CLI that what they were forced to do is
the prescribed recovery.

### A third instance worth flagging

The round-2 archive verb's silent breakage of cross-feature
`related:` links (B9) is the same antipattern at a different
verb: a CLI operation that produces a state subsequent CLI
operations reject. The shape recurs.

## Constraints identified

- `tier` for plans has four valid values and reasonable defaults
  may be project-specific. A `--tier` flag with a documented
  default (e.g., `L1`) is the obvious shape.
- `vault plan tier promote` requires a phase title and intent when
  promoting from L1 to L2 (round-2 evidence). The minimum-flags
  invocation today writes the literal `TODO: Phase title`; the
  fix is to require those flags for the promotion path.
- A retroactive change to the `vault add plan` interface that
  requires a previously-optional flag is a breaking change. The
  flag can land as required with a one-release deprecation
  window for the placeholder-emitting path.

## Recommendation

Make both scaffolders refuse to emit invalid values. Either
require the missing input as a CLI flag, or fail closed and
print a clear error suggesting the right flag. Generalise the
rule as a framework-wide invariant: scaffolders never write
values their own validators reject. Full design in the sibling
ADR.
