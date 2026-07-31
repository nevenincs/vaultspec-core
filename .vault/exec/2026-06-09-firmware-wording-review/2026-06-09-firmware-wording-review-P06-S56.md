---
tags:
  - '#exec'
  - '#firmware-wording-review'
date: '2026-06-10'
modified: '2026-06-13'
body_hash: 'sha256:20a333d9adc2b60f968cb6223e8a3c6e534a72b665920c3831f797aac98b5d1a'
step_id: S56
related:
  - '[[2026-06-09-firmware-wording-review-plan]]'
---

# replace the body-text Related lines instruction in the snapshot template with frontmatter related guidance (D8)

## Scope

- `src/vaultspec_core/builtins/agents/vaultspec-reference-auditor.md`

## Description

- Drop the body-text `Related:` line from the Reference Snapshot Template, leaving the
  Module(s) and File(s) lines
- Add guidance below the template: name related ADR, Research, or Plan documents
  alongside the returned findings so the orchestrator seeds them into the scaffolded
  document's frontmatter `related:` field via the `--related` flag at scaffold time
- State the prohibition explicitly: no body-text `Related:` lines, because body
  metadata is the drifted-content class the curator must repair
- Format with mdformat at wrap 88

## Outcome

The persona no longer instructs the exact Class A drifted-content violation
(`Related:` metadata lines in the document body) that the docs-curator persona is
told to repair. The replacement guidance is consistent with the post-P05 read-only
contract: the auditor returns findings plus related stems; the orchestrator owns the
scaffold and the frontmatter, and the `related:` field is populated through the CLI
rather than hand-edited.

## Notes

None.
