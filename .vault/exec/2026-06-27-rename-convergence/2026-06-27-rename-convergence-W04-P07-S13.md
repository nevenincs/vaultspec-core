---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S13'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Implement check_feature_rename_integrity for segment-vs-tag, exec-folder-vs-tag, and orphaned old-feature drift

## Scope

- `src/vaultspec_core/vaultcore/checks/feature_rename_integrity.py`

## Description

- Add a new read-only checker module exporting `check_feature_rename_integrity(root_dir)`, returning a `CheckResult` named `feature-rename-integrity` with `supports_fix=False`.
- Walk the exec subtree directly, skipping symlinks, non-directories, and `_archive`/`.obsidian` subtrees, mirroring the scanner exclusions.
- For each folder matching the `{plan_date}-{feature}` shape, compare every record's `#feature` tag against the folder feature segment and flag the folder once as an ERROR when a record carries a different tag.
- Skip records that are symlinks, unreadable, non-UTF-8, untagged, or tagged `#uncategorized`, mirroring how `check_features` skips uncategorized.
- Emit observed-vs-expected text and a `vault feature rename` remediation hint per drifted folder.

## Outcome

- The checker detects exec folder-vs-tag drift and yields zero findings on the repository's own vault.
- Authored-document filename-segment-vs-tag is intentionally NOT checked. The repository's authored filenames legitimately use narrative topic segments distinct from the feature tag, and `vault check all` ratifies that as clean; read-only probes showed the literal rule firing on 40 such docs, a per-feature-consistency variant on 34, and the narrowest cross-feature variant still on 5, all clean docs. A genuinely drifted authored doc is structurally indistinguishable from a legitimately narrative-named one without rename history, so the comparison is a false-positive generator. A candidate exec record filename-vs-folder class was also dropped after a probe showed 2 real records would false-positive.

## Notes

- Scope deviation from the originating Step row, which named three drift classes (segment-vs-tag, exec-folder-vs-tag, orphaned old-feature): only the exec folder-vs-tag class is implemented. The authored filename-segment and orphaned-old-feature classes were deferred because they false-positive on the clean repository vault. The deferral was established by read-only probes and approved before implementation.
- Index existence and staleness defer to `check_features`; filename and directory grammar defer to `check_structure`. A folder whose name lacks the dated-feature shape is skipped here as a grammar concern.
