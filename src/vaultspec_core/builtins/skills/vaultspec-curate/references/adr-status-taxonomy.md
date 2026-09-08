# ADR status taxonomy and supersession convention

This reference explains the canonical status vocabulary encoded by the core library's
`AdrStatus` type. Approval and transition policy belongs to the vaultspec system
section. The curator checks that records, templates, and tools agree with both
contracts.

## The canonical status set

An ADR carries exactly one status. The canonical values:

- **proposed** - the decision is drafted but not yet ratified. The default at scaffold.
- **accepted** - the decision is ratified and governs the codebase. It is expected to be
  reflected in the code.
- **rejected** - the decision was considered and declined. It does not govern anything;
  it is retained so a future reader can see the path was evaluated.
- **superseded** - the decision was replaced by a specific newer ADR. It records history
  and points forward to its successor. Set mechanically by
  `vaultspec-core vault adr supersede`.
- **deprecated** - the decision is retired and no longer applies, but no single
  successor ADR replaces it. Distinct from `superseded`, which always names a
  replacement.

The line between `superseded` and `deprecated` is whether a successor ADR exists. A
decision replaced by a named newer ADR is `superseded` and carries `superseded_by`. A
decision retired without a direct replacement is `deprecated`.

## Canonical encoding

Status lives in the document body H1, in the canonical form:

```
# `feature` adr: `Title` | (**status:** `accepted`)
```

The status token is backtick-quoted. The supersession relationship is recorded in
frontmatter, not the body: the superseded ADR carries `superseded_by: '<new-stem>'` and
the superseding ADR carries the old stem in its `supersedes:` list. These frontmatter
edges are what `vaultspec-core vault graph` reads to build the decision topology.

## Divergences the curator must detect

Divergences to detect:

- **Legacy status section.** Older ADRs declare status in a `## Status` section with a
  bare value (for example `Accepted`) instead of the H1 token, and a few encode it in a
  table. These read as the same decision but evade any H1-based tooling.
- **Quoting drift.** Some H1 tokens are bare (`status:** accepted`) rather than
  backtick-quoted. Normalize to the quoted canonical form.
- **Frontmatter-versus-body divergence.** `vaultspec-core vault adr supersede` rewrites
  the H1 status to `superseded` only when it matches the H1-inline regex. A legacy
  `## Status` ADR that is superseded therefore gains `superseded_by` in frontmatter
  while its visible body status stays stale (often `Accepted`). The curator must flag
  this mismatch: the frontmatter says superseded, the body does not.
- **Off-taxonomy values.** Any status token outside the canonical set (or a typo of one)
  is a violation to surface and normalize.
- **Missing status.** An ADR with no parseable status at all.

## Mechanical complement

The `vaultspec-core vault check adr-status` check is the mechanical backstop for these
divergences. It parses each ADR's H1, detects the legacy `## Status` section, validates
the token against the canonical `AdrStatus` set, and flags off-taxonomy or missing
values, bare (unquoted) tokens, and frontmatter-versus-body supersession drift. All
findings are warnings, so the check never hard-fails an existing corpus; `--fix` applies
safe encoding normalization, including already-recorded supersession. It does not
authorize a new decision or supersession. Run it (directly, or via
`vaultspec-core vault check all`) as part of the structural precondition, then reason
over what it surfaces. The check derives its vocabulary from the same `AdrStatus` enum
named above, so the two never drift.
