# ADR status taxonomy and supersession convention

This is the canonical reference the curator enforces when judging an ADR's status. The
status set defined here is the single source of truth; the core library status type, the
ADR template, and the `vault adr supersede` tool all derive from it. Where the corpus or
the tooling diverges from this set, the curator reconciles toward it.

## The canonical status set

An ADR carries exactly one status. The canonical values:

- **proposed** - the decision is drafted but not yet ratified. The default at scaffold.
- **accepted** - the decision is ratified and governs the codebase. It is expected to be
  reflected in the code.
- **rejected** - the decision was considered and declined. It does not govern anything;
  it is retained so a future reader can see the path was evaluated.
- **superseded** - the decision was replaced by a specific newer ADR. It records history
  and points forward to its successor. Set mechanically by `vault adr supersede`.
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
edges are what `vault graph` reads to build the decision topology.

## Divergences the curator must detect

The corpus predates a uniform encoding, so reconciliation must catch these:

- **Legacy status section.** Older ADRs declare status in a `## Status` section with a
  bare value (for example `Accepted`) instead of the H1 token, and a few encode it in a
  table. These read as the same decision but evade any H1-based tooling.
- **Quoting drift.** Some H1 tokens are bare (`status:** accepted`) rather than
  backtick-quoted. Normalize to the quoted canonical form.
- **Frontmatter-versus-body divergence.** `vault adr supersede` rewrites the H1 status
  to `superseded` only when it matches the H1-inline regex. A legacy `## Status` ADR
  that is superseded therefore gains `superseded_by` in frontmatter while its visible
  body status stays stale (often `Accepted`). The curator must flag this mismatch: the
  frontmatter says superseded, the body does not.
- **Off-taxonomy values.** Any status token outside the canonical set (or a typo of one)
  is a violation to surface and normalize.
- **Missing status.** An ADR with no parseable status at all.

## Mechanical complement

The `vault check adr-status` check is the mechanical backstop for these divergences. It
parses each ADR's H1, detects the legacy `## Status` section, validates the token
against the canonical `AdrStatus` set, and flags off-taxonomy or missing values, bare
(unquoted) tokens, and frontmatter-versus-body supersession drift. All findings are
warnings, so the check never hard-fails an existing corpus; `--fix` applies only the
safe normalization of quoting a bare canonical token. Run it (directly, or via
`vault check all`) as part of the structural precondition, then reason over what it
surfaces. The check derives its vocabulary from the same `AdrStatus` enum named above,
so the two never drift.
