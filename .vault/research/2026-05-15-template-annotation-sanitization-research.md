---
tags:
  - '#research'
  - '#template-annotation-sanitization'
date: '2026-05-15'
modified: '2026-06-13'
related: []
---

# template-annotation-sanitization research: generated annotation lifecycle

VaultSpec templates need agent-facing guidance while documents are being filled
out, but those annotations should not remain in finalized vault records unless an
operator deliberately leaves them there.

## Findings

The `.vaultspec/rules/templates/` audit found the bug pattern in every template:
YAML frontmatter used `# ...` comment lines for agent instructions, while body
guidance used Markdown HTML comments. That mixed syntax made the template
contract harder to read and left generated documents with two annotation forms.

Template hydration in `src/vaultspec_core/vaultcore/hydration.py` should not
strip instructions. Agents need those instructions in newly generated files to
complete the scaffold correctly. Sanitization therefore belongs in explicit fix
surfaces, not in document creation.

The vault maintenance surfaces already centralize fix behavior in
`src/vaultspec_core/vaultcore/checks/__init__.py`,
`src/vaultspec_core/cli/vault_cmd.py`, and
`src/vaultspec_core/vaultcore/repair.py`. Adding an annotations checker there
lets `vault check all --fix` and `vault repair` handle the same capability
without duplicating business rules.

Plan documents use a hidden `<!-- RETIRED: ... -->` ledger for identifier
safety. A sanitizer must preserve that ledger and avoid rewriting fenced code or
inline prose examples that mention HTML comments.

Pre-commit and local fix recipes are part of the operator path. The canonical
hook definitions in `src/vaultspec_core/core/commands.py`, the repository
`.pre-commit-config.yaml`, and `justfile` need to expose the sanitizer as a
separate command so operators can see it as a first-class capability.

The source templates should retain instructions but avoid frontmatter comment
directives. Moving frontmatter guidance into Markdown comment blocks after the
frontmatter keeps YAML clean while preserving the agent guidance in generated
documents.
