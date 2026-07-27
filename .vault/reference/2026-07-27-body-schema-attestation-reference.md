---
tags:
  - '#reference'
  - '#body-schema-attestation'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
related:
  - "[[2026-07-27-body-schema-attestation-adr]]"
---

# `body-schema-attestation` reference: `body-schema provenance ledger and warning surface`

A `vault check all` sweep of this workspace was traced through
`resolve_body_schema`, `check_body_sections`, and the body-schema baseline
ledger to ground the 1,049 provenance warnings reported across `.vault/`.

## Summary

`resolve_body_schema` (`src/vaultspec_core/vaultcore/body_schema.py:377-483`)
resolves a document's required body sections through one of five sources:
`declared` (frontmatter `body_schema` equals the current `body-v1` schema,
`body_schema.py:401-409`), `unknown` (a non-empty `body_schema` value that is
neither `body-v1` nor a `legacy-*` id, `body_schema.py:411-417`),
`attestation_required` (a `legacy-*` declaration or ledger entry the evidence
contradicts - absent path, hash mismatch, or shape mismatch,
`body_schema.py:422-464`), `attested` (path, hash, and shape all match a
ledger entry, `body_schema.py:479-483`), and `missing` (no `body_schema`
declared and no ledger entry for the document's path,
`body_schema.py:431-443`). `required_sections` is `None` for every source
except `declared` and `attested`.

`check_body_sections` (`src/vaultspec_core/vaultcore/checks/body_sections.py:92-184`)
does not currently branch on `resolution.source`; it appends the same
`CheckDiagnostic` whenever `required_sections` is `None`, so `missing`,
`attestation_required`, and `unknown` all render identically today.

The ledger (`BASELINE_RELATIVE_PATH = '.vaultspec/body-schema-baseline.json'`,
`body_schema.py:39`) does not exist in this workspace. No production code
writes it: `_read_baseline`, `_read_baseline_file`, and `_parse_baseline`
(`body_schema.py:270-354`) are readers only; the sole writers anywhere in the
repository are test-setup helpers that hand-construct the JSON directly
(`src/vaultspec_core/vaultcore/tests/test_body_schema.py:31-38`,
`src/vaultspec_core/vaultcore/checks/tests/test_body_sections.py:20,287`). No
CLI verb, MCP tool, or migration populates it; `vault --help` and a grep of
`src/vaultspec_core/migrations/` for `baseline`/`body_schema`/`legacy-` show
no such surface.

`BODY_SCHEMA_REGISTRY` (`body_schema.py:122-266`) defines 16 `legacy-*`
schemas plus `body-v1`. At least eight `legacy-*` ids -
`legacy-adr-v3`, `legacy-audit-v1`, `legacy-exec-v3`, `legacy-exec-v4`,
`legacy-index-v1`, `legacy-plan-v1`, `legacy-reference-v1`, and
`legacy-research-v2` - have a `required_sections` tuple byte-identical to
`body-v1` for their `(DocType, is_summary)` shape, so heading-text matching
alone cannot distinguish those legacy ids from `body-v1` or from each other;
only the ledger's `(path, sha256)` pair disambiguates
(`body_schema.py:429-464`).

A corpus-wide `vault check all --json` run measured the warning distribution:
`adr` 99/100, `audit` 59/62, `exec` 668/699, `plan` 88/88, `reference` 20/20,
`research` 115/115, `index` 0/116 (index documents are exempt from this
check). All warnings observed carry the `missing` source: no document in this
corpus declares a legacy `body_schema` id, and the ledger is empty because it
does not exist.

`check_modified_stamp` (`src/vaultspec_core/vaultcore/checks/modified_stamp.py`)
is the closest existing precedent for a CLI-maintained frontmatter provenance
field with a real `--fix` path (`supports_fix=True`, `atomic_write`-based
`_write_stamp`, `.bak` safety, exact-match reconciliation) - the shape a
future body-schema populator would need to follow if one is ever authorized.

`2026-07-27-vault-scale-performance-adr` decision D4
(`.vault/adr/2026-07-27-vault-scale-performance-adr.md`, lines 184-190) scopes
only read-once memoization of the ledger read path ("the baseline ledger
memoization is its first application" of the workspace-facts-read-once rule);
it does not scope populating the ledger or changing the checker's default.
`2026-07-27-markdown-feature-scope-adr` governs an unrelated `scan_vault`
migration-bypass boundary and contains no body-schema or provenance content.
