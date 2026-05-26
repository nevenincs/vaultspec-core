---
name: vaultspec
---

# Spec Skills

This project follows agent-driven development with `<ADR>`-backed `<Plan>`s.

The workflow persists the following documents:

- `.vault/plan/yyyy-mm-dd-<feature>-plan.md`: The `<Plan>` to execute.

- `.vault/research/yyyy-mm-dd-<feature>-research.md`: The `<Research>` findings.

- `.vault/adr/yyyy-mm-dd-<feature>-adr.md`: Research-derived `<ADR>`.

- `.vault/reference/yyyy-mm-dd-<feature>-reference.md`: The implementation
  `<Reference>`.

- `.vault/audit/yyyy-mm-dd-<feature>-audit.md`: The `<Audit>` report.

- `.vault/exec/yyyy-mm-dd-<feature>/.../<step>.md`: The individual `<Step Record>`.

- `.vault/exec/yyyy-mm-dd-<feature>/...-summary.md`: The `<Phase Summary>`.

- `.vault/index/<feature>.index.md`: The auto-generated `<Feature Index>` linking every
  document for a feature. Managed by `vaultspec-core vault feature index`; do not author
  by hand.

Where appropriate, use the following skills:

- `vaultspec-research`
- `vaultspec-code-research`
- `vaultspec-adr`
- `vaultspec-write-plan`
- `vaultspec-execute`
- `vaultspec-documentation`
- `vaultspec-codify`

## Documentation Hierarchy

The documentation trail follows a strict dependency graph. Artifacts lower in the
hierarchy should reference those above them.

- **Brainstorm** / **Research / Reference Audit** (`.vault/research/`,
  `.vault/reference/`)

- **Architecture Decision Records (ADR)** (`.vault/adr/`)

  - *Depends on:* brainstorm, research, audits

- **Implementation Plans** (`.vault/plan/`)

  - *Depends on:* ADRs, research, audits, (previous or related feature plans)

- **Execution Records**
  (`.vault/exec/{yyyy-mm-dd-feature}/{yyyy-mm-dd-feature-{phase}-{step}}.md`)

  - *Depends on:* Plans.
  - *References:* The Plan being executed.
  - *Location:* Inside feature-specific folder.
  - *Filename:* `{yyyy-mm-dd-feature-{phase}-{step}}.md` where `{phase}` and `{step}`
    are the canonical container identifiers (`P##`, `S##`) from the plan, zero-padded to
    a minimum of two digits. At `L1` the `{phase}` segment is omitted; at `L3`/`L4` a
    `{wave}` segment (`W##`) is prepended.
  - *Examples:*
    - L1: `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-S01.md`
    - L2: `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-P01-S01.md`
    - L3 / L4:
      `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-W01-P01-S01.md`

- **Summaries**
  (`.vault/exec/{yyyy-mm-dd-feature}/{yyyy-mm-dd-feature-{phase}-summary}.md`)

  - *Depends on:* Execution Logs.
  - *References:* The Plan and key Artifacts produced.
  - *Location:* Inside feature-specific folder.
  - *Filename:* `{yyyy-mm-dd-feature-{phase}-summary}.md` where `{phase}` is the
    canonical Phase identifier (`P##`).
  - *Examples:*
    - L2: `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-P01-summary.md`
    - L3 / L4:
      `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-W01-P01-summary.md`

- **Feature Indexes** (`.vault/index/{feature}.index.md`)

  - *Auto-generated* by `vaultspec-core vault feature index`; never authored by hand.
  - *Filename:* `{feature}.index.md` (no date prefix).
  - *Example:* `.vault/index/editor-demo.index.md`

## Must follow

- We **ALWAYS** use **Obsidian-style Wiki Links** for internal documentation.

- **Always** populate the `related:` field in the YAML frontmatter with
  `'[[wiki-links]]'` (quoted as strings).

- **Never** use relative paths (`../`) in wiki links; assume a flat namespace or
  vault-root resolution.

- **Always** check if a referenced file exists before linking (if possible).

- **Always** include the relevant `#{feature}` tag in the YAML frontmatter using the
  `tags:` field.

- **Always** use the `tags:` field (not `feature:`) as a YAML list.

- **Always** quote wiki-links in YAML: `- '[[file-name]]'`.

## Tag Taxonomy

**ALLOWED TAGS - DO NOT REMOVE - REFERENCE:** `#adr` `#audit` `#exec` `#index` `#plan`
`#reference` `#research` `#{feature}`

Every document in `.vault/` MUST include the required tag pair in the frontmatter
`tags:` field:

- **Directory Tag**: Based on the `.vault/` subfolder location (`#adr`, `#audit`,
  `#exec`, `#index`, `#plan`, `#reference`, `#research`)

- **Feature Tag**: Groups related documents across the feature lifecycle (kebab-case,
  e.g., `#editor-demo`)

**CRITICAL:** No structural tags like `#step`, `#summary`, `#phase*`, or `#design` are
allowed. The required pair is one directory tag plus the `#{feature}` tag; optional
extra tags may be appended when the template allows them.

### Directory Tags (Required for ALL documents)

The directory tag is determined by the file's location in `.vault/`:

| Directory           | Tag          | Description                           |
| :------------------ | :----------- | :------------------------------------ |
| `.vault/adr/`       | `#adr`       | Architecture Decision Records         |
| `.vault/audit/`     | `#audit`     | Audit reports and assessments         |
| `.vault/exec/`      | `#exec`      | Execution records (steps & summaries) |
| `.vault/index/`     | `#index`     | Auto-generated feature indexes        |
| `.vault/plan/`      | `#plan`      | Implementation plans                  |
| `.vault/reference/` | `#reference` | Reference audits and blueprints       |
| `.vault/research/`  | `#research`  | Research and brainstorming            |

### Tag Format

All documents use YAML list syntax with at least 2 tags (one directory tag, one feature
tag; additional tags are allowed):

```yaml
---
tags:
  - '#plan'
  - '#feature-name'
date: 2026-02-06
related:
  - '[[related-file]]'
---
```

**Examples:**

- Plan file: `tags: ['#plan', '#editor-demo']`
- ADR file: `tags: ['#adr', '#editor-demo']`
- Exec step: `tags: ['#exec', '#editor-demo']`
- Exec summary: `tags: ['#exec', '#editor-demo']`
- Research: `tags: ['#research', '#text-layout']`
- Reference: `tags: ['#reference', '#text-layout']`
- Feature index (auto-generated): `tags: ['#index', '#editor-demo']`

### Feature Tags

Feature tags use kebab-case and group all documents related to a specific feature or
work stream:

- Format: `#{feature}` (e.g., `#live-preview-blocks`, `#grid-layout`,
  `#syntax-highlighting`)

- Must be consistent across all documents in the feature's lifecycle

- Always quoted in YAML

## Placeholder Naming Conventions

Templates use curly-brace placeholders `{...}` to indicate values that must be replaced.
Follow these conventions:

### Frontmatter Placeholders

| Placeholder      | Format                | Example                   |
| :--------------- | :-------------------- | :------------------------ |
| `{feature}`      | lowercase, kebab-case | `editor-demo`             |
| `{yyyy-mm-dd}`   | lowercase, ISO 8601   | `2026-02-06`              |
| `{yyyy-mm-dd-*}` | lowercase pattern     | `2026-02-04-feature-plan` |
| `{tier}`         | uppercase enum        | `L1`, `L2`, `L3`, `L4`    |

### Document Body Placeholders

Container identifiers (`{wave}`, `{phase}`, `{step}`) use the canonical uppercase
zero-padded form from the convention ADR. `{feature}` uses lowercase kebab-case.
Narrative placeholders (`{topic}`, `{title}`) use concise prose.

| Placeholder | Format              | Example                   |
| :---------- | :------------------ | :------------------------ |
| `{feature}` | kebab-case          | `editor-demo`             |
| `{wave}`    | uppercase canonical | `W01`, `W02`              |
| `{phase}`   | uppercase canonical | `P01`, `P02`              |
| `{step}`    | uppercase canonical | `S01`, `S02`              |
| `{topic}`   | concise prose       | `event handling`          |
| `{title}`   | concise prose       | `display map integration` |

### General Rules

- **YAML frontmatter**: Always lowercase, kebab-case

- **Document titles/headings**: The shipped templates are canonical for level-one
  headings. Top-level vault documents use backticks around both the `{feature}` segment
  and the narrative `{title}`, `{topic}`, or `{phase}` segment. Examples:
  `# {feature} research: {topic}` represents the literal template heading '# `{feature}`
  research: `{topic}`', and `# {feature} {phase} plan` represents '# `{feature}`
  `{phase}` plan'. Narrative segments should be concise prose; canonical uppercase
  identifiers remain required for `{wave}`, `{phase}`, and `{step}` identifier segments.

- **File names**: lowercase kebab-case for narrative segments (`{feature}`, `{type}`);
  canonical uppercase identifiers for `{wave}`, `{phase}`, `{step}` segments. Patterns:

  - Top-level docs: `yyyy-mm-dd-{feature}-{type}.md` (e.g.,
    `2026-02-04-editor-demo-plan.md`)

  - Exec Steps (L1): `yyyy-mm-dd-{feature}-{step}.md` (e.g.,
    `2026-02-04-editor-demo-S01.md`)

  - Exec Steps (L2): `yyyy-mm-dd-{feature}-{phase}-{step}.md` (e.g.,
    `2026-02-04-editor-demo-P01-S01.md`)

  - Exec Steps (L3 / L4): `yyyy-mm-dd-{feature}-{wave}-{phase}-{step}.md` (e.g.,
    `2026-02-04-editor-demo-W01-P01-S01.md`) inside `.vault/exec/yyyy-mm-dd-{feature}/`
    folder.

  - Exec Summaries (L2): `yyyy-mm-dd-{feature}-{phase}-summary.md` (e.g.,
    `2026-02-04-editor-demo-P01-summary.md`)

  - Exec Summaries (L3 / L4): `yyyy-mm-dd-{feature}-{wave}-{phase}-summary.md` (e.g.,
    `2026-02-04-editor-demo-W01-P01-summary.md`) inside the feature folder.

- **Replace ALL placeholders**: No template should be committed with `{...}`
  placeholders remaining
