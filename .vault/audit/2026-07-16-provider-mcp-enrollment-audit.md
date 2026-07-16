---
tags:
  - '#audit'
  - '#provider-mcp-enrollment'
date: '2026-07-16'
modified: '2026-07-16'
related:
  - "[[2026-07-15-provider-mcp-enrollment-plan]]"
---

# `provider-mcp-enrollment` audit: `atomic-writer-integrity`

## Scope

Formal corrective-release review of the shared atomic byte writer, its `.gitignore` and
`.gitattributes` callers, every MCP JSON/TOML/ownership caller reached through the
shared UTF-8 seam, and the real-filesystem regression matrix. The review must confirm
exclusive unpredictable scratch creation, descriptor-only content writes,
identity-guarded promotion and cleanup, atomic fail-closed replacement,
destination-mode retention, link topology behavior, Windows behavior, and
package/release readiness.

## Findings

No blocking or non-blocking code findings remain.

The frozen diff replaces every production PID-derived writer with one shared
descriptor-based byte writer. Temporary nodes are created exclusively with an
unpredictable short name in the destination directory, content is written and
synchronized through the opened descriptor, the named node's device and inode are
verified before promotion, and cleanup removes the path only while that identity still
matches. Replacement failure is fail-closed; the former Windows copy fallback that
could follow a destination link is gone. Existing regular-file modes are retained,
while destination links are replaced as nodes without writing their targets.

The audit traced all MCP JSON, Codex TOML, ownership, workspace, manifest, provider-hook,
ignore, and attributes writes through the shared seam. No production PID-derived
temporary writer remains. The real-filesystem matrix covers pre-existing regular,
relative-link, broken-link, and directory nodes at the legacy sibling name; regular,
linked, broken-linked, directory, missing-parent, and long-name destinations; and the
managed ignore, attributes, resource-rename, and MCP caller surfaces. Converted
resource-rename cases no longer claim rollback coverage; independent real mid-apply
rollback tests remain in the rename transaction and feature suites.

The implementing agent reported 138 focused passes and an effective 1,773-of-1,773 unit
ledger after isolating pytest temporary state outside the Git worktree, with Ruff,
format, Ty, and diff checks green. The formal reviewer independently reran the complete
new atomic-writer file plus both managed-file caller regressions against an external
temporary root: 12 of 12 passed with exact node and byte assertions.

Verdict: **PASS — the corrective implementation is ready for packaging and release
gates, with no CRITICAL, HIGH, MEDIUM, or MINOR findings.**

## Recommendations

Run the clean external-temporary-root unit ledger to one terminal result, then require
the ordinary build, source-distribution, wheel-install, and project-scoped Claude and
Codex MCP smoke gates before merge and publication. Publish a corrective Core release
and require RAG to adopt that public version as its minimum dependency before RAG's own
release audit begins.
