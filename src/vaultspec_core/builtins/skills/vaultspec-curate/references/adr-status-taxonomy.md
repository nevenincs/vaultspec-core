# ADR status and supersession

The core library's `AdrStatus` enum defines the vocabulary. The vaultspec system section
owns approval and transitions; this reference explains how curation applies them.

| Status       | Meaning                                              |
| ------------ | ---------------------------------------------------- |
| `proposed`   | Drafted decision awaiting authorization.             |
| `accepted`   | Authorized commitment; rollout need not be complete. |
| `rejected`   | Declined proposal retained as history.               |
| `superseded` | Replaced by a named successor ADR.                   |
| `deprecated` | Retired without a direct successor.                  |

## Encoding and evidence

The canonical declaration is the body H1:

```markdown
# `feature` adr: `Title` | (**status:** `accepted`)
```

The predecessor's frontmatter carries `superseded_by: '<successor-stem>'`; the
successor's `supersedes:` list names the predecessor. These fields describe the
transition. An ordinary `related:` link or a newer date does not. Read the records to
resolve authority; graph node frontmatter exposes the same fields.

`vaultspec-core vault check adr-status` warns about missing or unknown H1 status,
unquoted tokens, legacy `## Status` declarations (including alongside a canonical H1),
and disagreement between `superseded` status and `superseded_by`. It does not prove that
acceptance was authorized or that a successor relationship is substantively correct.

`--fix` only quotes an otherwise known token and preserves a status changed after its
snapshot. Legacy sections or tables, conflicting declarations, and supersession repairs
need inspection. A historical successor can itself be retired; do not reactivate it to
repair an older record's heading.

## Repair boundary

Normalize only an unambiguous existing state. For a legacy declaration, confirm the
recorded authority before moving it to the H1 and removing redundant status prose.
Missing status, an unfamiliar value, contradictory declarations, or incomplete edges are
findings until evidence establishes the state. Do not choose the nearest status to make
the checker pass. Neither implemented code nor an accepted-looking label supplies
approval.

Use owning body verbs for confirmed encoding repairs. New supersession uses
`vaultspec-core vault adr supersede OLD --by NEW` only when the successor is accepted
and the transition is authorized. The reconciliation playbook covers proposed semantic
changes and historical metadata repairs.
