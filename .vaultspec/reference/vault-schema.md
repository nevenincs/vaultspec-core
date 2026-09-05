# Vault document schema

Reference for the machine-owned parts of every `.vault/` record. The owning verbs
(`create`/`edit` tools, `vaultspec-core vault add`, `vaultspec-core vault plan`) write
all of this; `vaultspec-core vault check all --fix` repairs it. Authors do not
hand-write any field below; this page exists so a reader can recognise a correct record,
not produce one.

## Frontmatter

```yaml
---
tags:
  - '#plan'
  - '#feature-name'
date: '2026-02-06'
modified: '2026-02-06'
body_hash: 'sha256:...'
body_schema: 'body-v1'
related:
  - '[[related-file]]'
---
```

- `tags:` - a YAML list opening with one directory tag and one feature tag, both quoted;
  further freeform tags may follow (`--tags`); nothing else is structural.
- `date:` - the scaffold date, quoted `yyyy-mm-dd`.
- `modified:` - CLI-maintained last-modified stamp; set equal to `date:` at scaffold,
  refreshed by every mutating verb and by `vaultspec-core vault check all --fix`.
- `body_hash:` - fingerprint of the body that `modified:` attests, written beside the
  stamp by the same verbs. The reconciliation check compares the live body against it;
  file timestamps are never consulted. A record without it makes no claim and is
  reported clean until a verb seeds it.
- `related:` - quoted wiki-links to `.vault/` stems, flat namespace, no relative paths.
  Set with `--related` at scaffold or `vaultspec-core vault link add`.
- Plans add `tier:` (`L1`-`L4`, set by `--tier`, changed by
  `vaultspec-core vault plan tier promote/demote`; older plans without it default to
  `L2`). ADRs gain `superseded_by:` and `supersedes:` from
  `vaultspec-core vault adr supersede`. Feature indexes carry `generated: true`. Every
  record carries `body_schema:` (`body-v1`; the ledger `body-v2`). No other fields.

## Tags

| Directory           | Tag          |
| :------------------ | :----------- |
| `.vault/adr/`       | `#adr`       |
| `.vault/audit/`     | `#audit`     |
| `.vault/exec/`      | `#exec`      |
| `.vault/index/`     | `#index`     |
| `.vault/plan/`      | `#plan`      |
| `.vault/reference/` | `#reference` |
| `.vault/research/`  | `#research`  |

The feature tag is kebab-case (`#editor-demo`), consistent across every record of the
feature.

## Filenames

Narrative segments are lowercase kebab-case; container identifiers are canonical
uppercase, zero-padded to two digits.

| Record           | Pattern                                                                                   |
| :--------------- | :---------------------------------------------------------------------------------------- |
| Top-level record | `yyyy-mm-dd-{feature}-{type}.md`                                                          |
| With topic infix | `yyyy-mm-dd-{feature}-{topic}-{type}.md` (adr, audit, reference, research; via `--topic`) |
| Ledger           | `.vault/exec/yyyy-mm-dd-{feature}/yyyy-mm-dd-{feature}-ledger.md` (the plan's date)       |
| Feature index    | `.vault/index/{feature}.index.md`                                                         |

## Headings

Templates are canonical for the level-one heading. Top-level records wrap the
`{feature}` segment and the narrative segment in backticks, for example the research
heading `{feature} research: {topic}` and the plan heading `{feature} plan`. Narrative
segments are concise prose; `{wave}`, `{phase}`, and `{step}` segments stay canonical
uppercase identifiers. The ADR heading carries the status token; it is the one heading
element the author edits.

## Placeholders

Author-replaced placeholders use curly braces and kebab-case or concise prose:
`{feature}`, `{topic}`, `{title}`. Machine-filled placeholders use snake_case and are
filled by the owning verb, never by hand:

| Placeholder       | Filled by                            | Value                            |
| :---------------- | :----------------------------------- | :------------------------------- |
| `{plan_stem}`     | `vaultspec-core vault exec log`      | The parent plan's filename stem  |
| `{document_list}` | `vaultspec-core vault feature index` | The feature's full document list |

No record is committed with `{...}` residue; `vaultspec-core vault check placeholders`
reports any left in body prose.
