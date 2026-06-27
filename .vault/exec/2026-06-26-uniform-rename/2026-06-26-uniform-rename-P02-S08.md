---
tags:
  - '#exec'
  - '#uniform-rename'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S08'
related:
  - "[[2026-06-26-uniform-rename-plan]]"
---

# Implement rename_feature plan computation and collision detection with refuse-default and force-merge

## Scope

- `src/vaultspec_core/vaultcore/query.py`

## Description

- Add a plan dataclass and a pure plan-computation helper that categorizes each source document into authored renames, exec records grouped by their folder, and the existing index, without mutating anything.
- Derive every old-to-new path through the path transforms, refusing with a clear error when a document or exec folder does not match its expected shape.
- Build the wiki-link stem map that feeds the related-link cascade, including the index stem so stray incoming references to it are caught.
- Detect destination collisions both within the rename set and against a pre-existing file at a destination, and surface the colliding pairs.

## Outcome

- Plan computation yields the full rename set, exec-folder renames, the index plan, the stem map, and any collisions. The orchestrator refuses the whole operation with a message listing the colliding pairs when collisions are present, under force or otherwise.

## Notes

- Pre-existing-file collision detection keys on a file at the destination, so an unexpected directory at a destination path is left for the apply path to catch and roll back rather than being treated as a normal collision. The cross-feature incoming-link analysis mirrors the archive verb for reporting parity.
