---
tags:
  - '#research'
  - '#reference-topic-infix'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - '[[2026-06-09-firmware-wording-review-adr]]'
  - '[[2026-06-27-rename-convergence-adr]]'
---

# `reference-topic-infix` research: `scaffolding a second reference or research document per feature`

The question (GitHub issue 205): the owning scaffolder cannot create a second
reference (or research, or audit) document for a feature - the filename always
resolves to `{date}-{feature}-{type}.md` and collides - so the second document is
forced into hand-authored frontmatter, violating the owning-verb mandate. The evidence
picture: the collision is structural in one function, a topic-infix convention already
exists in the firmware for audits (documented but not implemented in the scaffolder
either), the validators already accept infixed filenames, and the change surface is
four sites (filename builder, CLI flag, MCP create tool, firmware filename patterns)
plus the generated CLI reference.

## Findings

### The collision is structural in one filename builder

`create_vault_doc` resolves every non-exec filename as
`f"{date_str}-{feature}-{doc_type.value}.md"`
(`src/vaultspec_core/vaultcore/hydration.py:434`); `title` maps only to the heading
placeholders (`hydration.py:97,127`), never the filename. A second same-day document
of the same type and feature raises `ResourceExistsError` (`hydration.py:439-444`),
and the stem-collision guard (`hydration.py:449-459`) blocks even cross-type stem
duplicates. `--force` overwrites rather than disambiguates.

### The topic-infix convention exists in firmware but no scaffolder implements it

The vaultspec rule documents the audit disambiguation
`yyyy-mm-dd-{feature}-{topic}-audit.md`
(`src/vaultspec_core/builtins/rules/vaultspec.builtin.md`, Audits node and workflow
list), decided by D2 of the firmware-wording-review decision (see `related:`). No
`topic` parameter exists anywhere in the scaffolding path: `create_vault_doc`
(`hydration.py:318-339`) has no such argument, the CLI `vault add` flag set
(`src/vaultspec_core/cli/vault_cmd.py:83-159`) has no `--topic`, and the MCP `create`
tool's `DocumentSpec` (`src/vaultspec_core/mcp_server/tools/documents.py:137`) carries
only `title`. Even a second audit - whose infix form the firmware documents - cannot
be scaffolded through an owning verb today.

### Validators and real corpora already accept infixed filenames

Issue 205 reports two real hand-mirrored infixed reference documents in a downstream
vault validating clean via `vault check all`, and this repo's own audit corpus uses
narrative infixes (e.g. a `-check-engine-review-audit` stem, prior art acknowledged in
the firmware-wording-review decision). The filename checkers do not bind the
`{date}-{feature}-{type}` shape strictly; features are derived from frontmatter tags,
not filenames.

### Known interaction: narrative filenames and feature rename

`vault feature rename` refuses on narrative-filename features (recorded in the
rename-convergence decision, see `related:`); adding more infixed filenames grows that
population. This is a pre-existing, open follow-on of that decision, not a new
regression introduced by an infix flag - but the decision record should acknowledge
it.

### Change surface

- `hydration.py` filename builder and `create_vault_doc` signature: a `topic`
  parameter producing `{date}-{feature}-{topic}-{type}.md`.
- CLI `vault add`: a `--topic` flag; kebab-case validation exists via
  `normalize_feature_tag(value, label=...)` (`vault_cmd.py:240,254` shows the shared
  normalizer pattern for feature and tags).
- MCP `create` tool: `DocumentSpec` field with the same validation, converging on the
  same `create_vault_doc` call (`documents.py:274-277`).
- Firmware: the vaultspec rule's file-name patterns document the infix for the types
  the decision admits; the CLI reference regenerates via `spec reference generate`
  (drift-tested).

### Scope question the decision must settle

Which document types admit the infix. The issue requests `reference`, suggests
`research`; `audit` is already convention. `adr` and `plan` have standing cardinality
rules pointing the other way (one accepted record per decision with amend-or-supersede;
one plan per decision cluster - both in the vaultspec firmware and prior decisions),
and `exec` filenames are machine-derived from plan identifiers. The evidence favors
admitting the infix for the narrative trio (audit, reference, research) and excluding
adr, plan, exec.

## Sources

- `src/vaultspec_core/vaultcore/hydration.py:97`
- `src/vaultspec_core/vaultcore/hydration.py:127`
- `src/vaultspec_core/vaultcore/hydration.py:318-339`
- `src/vaultspec_core/vaultcore/hydration.py:434-459`
- `src/vaultspec_core/cli/vault_cmd.py:83-159`
- `src/vaultspec_core/cli/vault_cmd.py:240-258`
- `src/vaultspec_core/mcp_server/tools/documents.py:137`
- `src/vaultspec_core/mcp_server/tools/documents.py:274-277`
- `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`
- https://github.com/nevenincs/vaultspec-core/issues/205
