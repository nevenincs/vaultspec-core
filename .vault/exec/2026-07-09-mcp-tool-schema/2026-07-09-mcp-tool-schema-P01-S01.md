---
tags:
  - '#exec'
  - '#mcp-tool-schema'
date: '2026-07-09'
modified: '2026-07-10'
step_id: 'S01'
related:
  - "[[2026-07-09-mcp-tool-schema-plan]]"
---

# Create the vaultcore edit-engine module: move \_resolve_doc_path, \_split_document, \_enforce_blob_hash, \_compose_new_text, \_validate_proposed, \_write_proposed, and \_EditError verbatim, and add a result-returning execute_edit core plus a typed EditResult dataclass (status, path, blob_hash, error, warnings) with no Typer or console coupling (agent: vaultspec-high-executor)

## Scope

- `src/vaultspec_core/vaultcore/edit_engine.py`

## Description

- Create the new `vaultcore.edit_engine` module holding the Typer-free body/frontmatter edit pipeline.
- Move `_resolve_doc_path`, `_split_document`, `_enforce_blob_hash`, `_compose_new_text`, `_validate_proposed`, `_write_proposed`, and the frontmatter-surgery helpers verbatim out of the edit command.
- Rename the structured error to the public `EditError` and add a frozen `EditResult` dataclass carrying status, path, blob_hash, checks, error, warnings, dry_run, and changed.
- Add the result-returning `execute_edit` core that resolves, guards on blob hash, composes, validates, writes, and folds every reachable failure into a failed result with a structured error payload.
- Inline the graph-cache invalidation against the `graph.cache` layer so the engine depends on no `cli` module and imports no Typer or console.

## Outcome

- `vaultcore.edit_engine` publishes `execute_edit`, `EditResult`, and `EditError` with no Typer, console, or `typer.Exit` coupling; type check and lint clean.

## Notes

- `execute_edit` always returns a result rather than raising, so batch callers report conflict and refusal as per-item status while the lower helpers still raise the typed `EditError` for direct callers.
