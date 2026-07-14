---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S38'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Review both CLIs' install --help output side by side and confirm the --mode flag vocabulary, help text, and doctor row shape are parity-symmetric between vaultspec-core and vaultspec-rag

## Scope

- `src/vaultspec_core/cli/root.py`

## Description

- Capture `vaultspec-core install --help` and `vaultspec-rag install --help` side
  by side and compare the shared option surface.
- Verify the full user story on real workspaces: a fresh non-project directory
  defaulting to tool mode end to end, and a mixed workspace staying stable across
  both CLIs' syncs.

## Outcome

Parity verdict: PASS. The shared install surface is symmetric between the two
CLIs. `--mode [tool|dependency|dev]` carries byte-identical help text and the same
token vocabulary in both. `--target`, `--upgrade`, `--dry-run`, `--force`,
`--skip`, and `--json` are all present with analogous semantics (core's `--json`
reads "Output as JSON", rag's "Emit JSON for scripts"; both emit the same shape).
The rag-only extras are correctly scoped and documented as rag-only in the help
text: `--torch-config`/`--no-torch-config`, `--torch-group`, `--yes`, `--sync`,
`--provision`/`--no-provision`, `--mcp`/`--no-mcp`, `--local-only`, and the
`--skip-torch`/`--skip-models`/`--skip-qdrant` trio, all GPU, provisioning, or
backend concerns with no core analogue. Core's only unmatched surface is the
`[PROVIDER]` positional and `--no-hints`, both core-specific UX with no parity
obligation. The doctor rows are likewise symmetric: rag's `server doctor`
provisioning block reads the same core collectors and weights below-floor as an
error and mode mismatch as a warning, matching core's `spec doctor`.

User story 1 (fresh directory defaults tool mode): a fresh non-project directory
run through `vaultspec-rag install --no-provision --no-torch-config --no-mcp`
wrote `workspace.json` declaring `vaultspec-rag` at `install_mode: tool` under
`schema_version: 2.0` and rendered its `.mcp.json` entry as the `uvx --from vaultspec-rag python -m vaultspec_rag.server` tool launch natively through core's
sync, with no post-sync re-render.

User story 2 (mixed workspace stable across both CLIs): a workspace declaring both
distributions installed core at `dependency` and rag at `tool`; the initial state
rendered core as `uv run` and rag as `uvx`. After a plain `vaultspec-core sync`
followed by a `vaultspec-rag install --upgrade`, both entries held their own mode
in `.mcp.json` and the provider mirror, and a subsequent `vaultspec-core sync --dry-run` reported zero drift. Each package's entry stays rendered at its own
declared mode across either CLI's sync.

## Notes

During the interleaved mixed-workspace setup, the first `vaultspec-core sync`
after the rag install emitted a transient "MCP server 'vaultspec-rag' differs from
definition (use --force)" advisory. This is the benign sibling-differs skip the
per-package sync tolerates by design: the plain sync preserved rag's tool entry
rather than clobbering it to core's mode, and the next sync converged the provider
mirror. A direct render-versus-deployed comparison confirmed the rendered rag
entry equals the deployed one, and the post-convergence `--dry-run` sync is drift
free, so this is expected interleaving behaviour, not a parity gap.

A formal `vaultspec-code-reviewer` audit of the rag-side change set is
recommended before the wave is closed; this record captures the executor's
cross-repo parity review only.
