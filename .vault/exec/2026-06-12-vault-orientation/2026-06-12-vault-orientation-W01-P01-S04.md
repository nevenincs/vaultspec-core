---
tags:
  - '#exec'
  - '#vault-orientation'
date: '2026-06-12'
modified: '2026-06-12'
step_id: S04
related:
  - '[[2026-06-12-vault-orientation-plan]]'
---

# add stamp model, lenient parsing, and scaffold-stamp tests using real files

## Scope

- `src/vaultspec_core/vaultcore/tests/test_modified_stamp.py`

## Description

- Add `src/vaultspec_core/vaultcore/tests/test_modified_stamp.py` covering the lenient date helpers, the modified validation policy, typed parsing, and scaffold-time stamping
- Cover `parse_lenient_date` acceptance (date and datetime objects, canonical, ISO timestamps with and without zone, space separator, yyyy/mm/dd, unambiguous year-last forms) and rejection (ambiguous year-last values, impossible dates, garbage, non-string non-date objects)
- Cover `normalize_date` identity on canonical input, normalization of noncanonical forms, and None on unparseable input
- Cover `DocumentMetadata.validate`: absent and canonical modified valid, parseable-noncanonical accepted without hard failure, unparseable and ambiguous values each produce exactly one violation
- Cover `parse_vault_metadata` surfacing of quoted, unquoted, absent, and empty modified scalars
- Cover scaffold stamping through `create_vault_doc` against the real shipped builtin templates mirrored into a tmp_path content root: every authored doc type plus exec step records carry modified equal to date, placed directly after the date line, validating clean; templates already carrying the field are not double-stamped; content without frontmatter is untouched

## Outcome

34 new tests; the full vaultcore suite passes at 242 with no mocks, patches, stubs, or skips - scaffold tests exercise real template files on a real filesystem. ruff format, ruff check, and ty check are clean.

## Notes
