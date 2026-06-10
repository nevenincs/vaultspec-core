---
tags:
  - '#exec'
  - '#graph-backend'
date: '2026-06-10'
related:
  - '[[2026-06-10-graph-backend-plan]]'
---

# `graph-backend` `P03` summary

Phase `P03` added the `vault link` command group so a GUI can create, list, and remove
graph edges through the CLI by mutating only `related:` frontmatter. A shared
CRLF-preserving atomic line-surgery helper, extracted from the dangling fixer, backs both
the new verbs and the existing fixer. The phase passed code review after a remediation
pass that closed one critical and one high data-safety finding.

- Created: `src/vaultspec_core/vaultcore/related_surgery.py`
- Created: `src/vaultspec_core/cli/link_cmd.py`
- Created: `src/vaultspec_core/vaultcore/tests/test_link_surgery.py`
- Created: `src/vaultspec_core/tests/cli/test_link_cli.py`
- Modified: `src/vaultspec_core/vaultcore/checks/dangling.py`
- Modified: `src/vaultspec_core/cli/vault_cmd.py`
- Modified: `src/vaultspec_core/builtins/reference/cli.md`
- Modified: `docs/CLI.md`

## Description

`S20` extracted the `related:`-frontmatter line surgery from the dangling fixer into a
shared `related_surgery` module providing `remove_related_entries` and
`append_related_entry`, both CRLF-preserving with atomic temp-and-replace writes; the
fixer was refactored to call the shared helper and its tests stayed green.

`S21` created the `vault link` group with the `list` verb, listing a document's outgoing
and incoming edges from the built graph, scoped to a source if given, with feature and
JSON options.

`S22` implemented `vault link add`, resolving the destination, refusing to create a
dangling edge unless forced, exiting with a failed envelope on refusal, idempotent when
the edge already exists, with dry-run preview.

`S23` implemented `vault link remove`, deleting the matching entry through the shared
surgery, treating a missing edge as a reported no-op rather than an error, with dry-run
preview.

`S24` registered the group on the vault app and wired the exit-code contract, keeping the
bundled reference in sync. `S25` and `S26` added CRLF, atomic-write, and round-trip
tests for the helper and CLI tests for all three verbs. `S27` ran the authoritative
reference regeneration and provider sync.

## Outcome

Code review returned BLOCK with one critical and one high finding, both since resolved.
The critical: `append_related_entry` corrupted a document whose `related:` was an inline
flow sequence into unparseable YAML, violating the ADR guarantee that the surgery cannot
corrupt unusual-but-valid YAML. The high: for normal block lists the helper prepended
rather than appended, contradicting its docstring, with the documented append branch
dead. A remediation pass normalises an inline flow list to block form before appending
(raising rather than writing corrupt bytes if it cannot parse), routes the populated
block case through the append-at-end branch, and tightened the round-trip test to assert
byte identity of the body and non-related frontmatter. A direct probe confirmed an
inline `related: ['[[a]]']` now normalises to a valid block list and re-parses cleanly.

## Notes

Both fixes shipped together in the critical commit because splitting the shared
`if/elif` rewrite of `append_related_entry` would have produced a non-compiling
intermediate; the high commit carries the order and byte-identity assertions. Edge CRUD
deliberately touches only `related:` frontmatter; body wiki-links remain a read-only edge
source per the ADR.
