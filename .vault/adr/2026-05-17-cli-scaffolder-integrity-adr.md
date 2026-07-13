---
tags:
  - '#adr'
  - '#cli-scaffolder-integrity'
date: '2026-05-17'
modified: '2026-06-13'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
  - '[[2026-05-17-cli-scaffolder-integrity-research]]'
---

# `cli-scaffolder-integrity` adr: `Scaffolders must not emit invalid values: require inputs or refuse to write` | (**status:** `accepted`)

## Problem Statement

Two CLI scaffolders emit values that the framework's own
validators on the same surface reject. `vault add plan` writes
`tier: L{#}` (finding B2). `vault plan tier promote` writes
`TODO: Phase title` (finding B5). Both are observed three rounds
running; both produce uncaught Python tracebacks on the next
validation call; both require the new user to either crash or
hand-edit a frontmatter the framework's own rules forbid hand-
editing.

This is the same antipattern as `vault feature archive` writing a
directory `vault check structure` rejects (B9). The shape
generalises: scaffolders produce state that subsequent CLI
operations declare illegal.

## Considerations

- Two ways out: require the missing input at scaffold time, or
  refuse to write when the input is missing. The first is more
  ergonomic; the second is safer when no sensible default exists.
- `tier` for plans has four valid values (`L1`..`L4`). A default
  of `L1` is reasonable; the verb can accept `--tier` with that
  default and never emit a placeholder.
- `vault plan tier promote` from L1 to L2 must produce a new
  phase. The phase needs a title and an intent. Today the verb
  invents `TODO: Phase title`; the fix is to require those values.
- The general invariant matters across the framework. Today the
  scaffolders work by string-substitution against templates;
  unhydrated placeholders survive into the output. Linting the
  emit step against the validator schema would prevent recurrence
  by construction.

## Constraints

- Existing automation that calls `vault add plan` without `--tier`
  will start failing once the flag becomes required (or default
  changes silently). The transition needs a one-release
  deprecation window with a warning, then becomes required.
- The framework's templates contain HTML guidance comments with
  `{token}` placeholders intended for the human author. Those are
  not the same as frontmatter placeholders; the linter that
  catches B2/B5 must not fire on the legitimate template
  guidance comments either (a related paper cut also captured in
  this finding cluster).
- The fix must coordinate with the memory-lifecycle ADR.
  `vault rule promote` and `vault adr supersede` are new
  scaffolders subject to the same invariant from day one.

## Implementation

**Invariant.** Adopt as a framework-wide rule: a scaffolder may
not emit a value into a frontmatter field whose validator would
reject it. Two acceptable strategies, applied per field:

- The scaffolder accepts the value as a CLI flag with a
  documented default that the validator accepts. Default is the
  most common correct value, not a placeholder.
- The scaffolder refuses to write the document if the required
  value is missing and the flag has no usable default.

**Specific changes.**

- `vault add plan` gains a `--tier` flag with values `L1`..`L4`.
  Default `L1`. The literal `L{#}` placeholder is removed from
  the template. Scaffolded plans always carry a valid tier.
- `vault plan tier promote` from `L1` to `L2` requires
  `--phase-title` and `--phase-intent` flags. If invoked without
  them, the verb refuses to write and prints a one-line message
  naming the required flags. The literal `TODO: Phase title`
  placeholder is removed from the synthesised phase template.
- Symmetric work lands on every scaffold path that synthesises
  a frontmatter or body value the validator can reject.

**Linter at emit time.** Add a check in the document-writing
pipeline that runs the same validator the read pipeline runs,
against the just-emitted output, before the file lands on disk.
If the validator would reject the emitted document, the
scaffolder fails before writing and prints the validator's
error message. This makes B2/B5/B9-shape regressions impossible
by construction.

**Unhydrated-placeholder warnings.** The round-1 paper-cut
warnings that fire against `{adr}`, `{research}`, `{reference}`
tokens inside HTML guidance comments are scoped down. The
warning fires only when the token appears outside an HTML
comment region — i.e., in user-visible body content or
frontmatter. Tokens inside `<!-- ... -->` regions are treated as
intentional template guidance.

**Companion language updates.**

- The framework manual section on document templates is updated
  to state the invariant explicitly: templates never hold
  validator-illegal frontmatter values.
- The `vault add` help text gains a one-line summary of the
  invariant ("This command will not write a document the
  framework's own validator would reject").
- Builtin rule files that explain the document lifecycle are
  updated to remove any reference to hand-editing scaffolded
  placeholders — there are no placeholders left to hand-edit.

## Rationale

The audit reproduces B2 across rounds 1, 2, and 3 unchanged. B5
reproduces in round 2. B9 reproduces the same shape on a
different verb in round 3. The antipattern is real, persistent,
and the single most user-hostile pattern in the framework: a
brand-new user runs the canonical first command and gets a
Python traceback on the next.

Requiring the inputs is preferable to refusing to write when the
default is usable. `--tier L1` as a default keeps the verb
ergonomic. Where no usable default exists (`--phase-title`,
`--phase-intent` for L1→L2 promotion), refusing to write is the
safer choice; an ergonomic message naming the required flag is
more useful than a placeholder that crashes the next command.

The emit-time linter is the structural fix. Without it, future
scaffolders will recur with the same antipattern. With it, B2/B5/
B9 cannot exist by construction.

## Consequences

Gains. New-user onboarding does not crash. The "do not hand-edit
frontmatter" rule becomes possible to follow because the
scaffolder never produces frontmatter that demands it.
Validator-respecting output becomes an invariant, not a
discipline.

Difficulties. Existing automation that does not pass `--tier`
will break across the deprecation window. The breaking-change
deprecation window must be announced in release notes and
mirrored in `--help` output during the transition.

Pitfalls. The emit-time linter must run cheaply or it slows
down every scaffold. Sharing the validator implementation with
the read path keeps the cost low; a second parallel implementation
is the wrong shape.

Pathways. Once this ADR lands, the round-1 paper-cut "unhydrated
placeholder warnings on every fresh `vault add`" finding closes
along with B2/B5. The framework's first-contact surface becomes
quietly correct.
