---
tags:
  - '#research'
  - '#cli-plan-body-preservation'
date: '2026-05-17'
related:
  - "[[2026-05-17-cli-simplification-ux-audit]]"
---

# `cli-plan-body-preservation` research: `vault plan step add silently rewrites plan body`

Synthesis note for finding B6 — the plan-editing verb that
destroys author prose. Captures the evidence behind the sibling
ADR.

## Findings

### Three independent reproductions across two agents and two sandboxes

Joan reproduced this in round 1 against the harbor-notes
tag-search plan (finding [17] in Joan's AUDIT.md). Xavi
reproduced it in round 1 against the fake-work snippets plan
(finding [08] in Xavi's SESSION.md). Xavi reproduced it again in
round 2 against the SQLite-rewrite plan (the round-2 friction
point cluster). The bug is decisively confirmed: three
reproductions on two sandboxes by two agents who never spoke to
each other.

### What gets destroyed

The plan template that ships with `vault add plan` instructs the
author to fill in Description, Parallelization, and Verification
prose sections. After the author has written those sections, the
first invocation of `vault plan step add` rewrites the document
body and discards all three sections. Only the LINK RULES block,
the title, the H1, and the appended step rows survive. No
`--dry-run` mode gates the rewrite. No diff is shown in the post-
command output. The success line simply reports the step was
added.

### Workaround agents discovered

Both agents independently arrived at the same workaround in
their second round: add the Steps first, write the prose later.
Xavi noted this in round 3 ([42]): "the round-1 [08] / round-2
[23] prose-destruction friction did NOT recur this round: I had
already learned not to author Description / Verification prose
before adding Steps."

The bug is unchanged across rounds; only the agents adapted.
"Step add then prose" became folklore between rounds 1 and 2.

### Why this is worse than a normal destructive operation

Several first-class destructive operations exist in the CLI
(`uninstall`, `install --force`, `vault feature archive`). Most
require explicit flags, dry-run support, or both. `vault plan
step add` requires nothing. The verb's name is `add` — additive
— but its effect is rewrite. The naming actively misleads the
user about the blast radius.

The plan template's own instructions tell the author to fill
those sections. The CLI's own destructive editor then deletes
them. Two parts of the framework give contradictory instructions;
the destructive part runs without warning.

### Root cause is structural, not cosmetic

The plan-editing surface is built around a structured parse-edit-
serialise cycle. The serialiser does not preserve sections it
does not understand. Author-written prose lives in sections the
parser does not know how to round-trip, so those sections are
silently dropped on serialise.

The fix is at the round-trip layer: either the serialiser
preserves untouched sections verbatim, or the parser refuses to
operate on a document containing sections it does not understand
(forcing the author to canonicalise first).

## Constraints identified

- Plans have a documented structure (frontmatter, H1, optional
  Description/Parallelization/Verification sections, Wave/Phase/
  Step rows, optional RETIRED comments). The serialiser knows
  how to re-emit the structural pieces but throws away
  everything else.
- A parser that refuses to operate on unrecognised content is
  the safer floor but the worse ergonomics. A serialiser that
  preserves unrecognised content verbatim is the better
  ergonomics but requires careful round-tripping of comments
  and unknown section headers.
- The fix interacts with the round-3a `vault check annotations`
  finding: the stripper has a structural-metadata discriminator
  for `<!-- RETIRED -->`. The plan-edit serialiser needs the
  same kind of discriminator for author prose.

## Recommendation

Make the serialiser preserve sections it does not recognise.
Specifically: any heading the parser does not consume (Description,
Parallelization, Verification, plus any author-introduced section
between known structural elements) round-trips verbatim. Land a
`--dry-run` mode on every plan-editing verb that produces a diff
against the existing body. Full design in the sibling ADR.
