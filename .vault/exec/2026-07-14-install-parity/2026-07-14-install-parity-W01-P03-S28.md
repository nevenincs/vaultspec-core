---
tags:
  - '#exec'
  - '#install-parity'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S28'
related:
  - "[[2026-07-14-install-parity-plan]]"
---

# Generalize the MCP launch table from a single hardcoded vaultspec-core module entry to a package-and-module-parameterized render_launch_for_mode helper, keeping vaultspec-core's own launch as the default so companion packages can render through the same sentinel-substitution renderer

## Scope

- `src/vaultspec_core/core/mcps.py`

## Description

- Add `render_launch_for_mode(mode, package, module)`: the single, package- and
  module-parameterized launch comparator that returns the `uv run` shape for
  dependency-rendered modes and the `uvx --from <package>` shape for tool mode,
  collapsing `DEV` onto `DEPENDENCY` through the shared render_mode helper before
  choosing the shape.
- Define the per-definition token contract: two optional metadata keys a
  mode-neutral builtin may carry to name its own distribution and runnable
  module, defaulting to core's package and module so core's token-only builtin
  renders byte-identically.
- Re-derive core's convenience launch table from the generalized helper so the
  table and the renderer can never drift, keeping the two rendered shapes the
  observed-shape matcher and the mode-flip tests read.

## Outcome

`render_launch_for_mode` renders correct launches for any package/module pair
(core and a rag-shaped example verified), and `DEV` renders identically to
`DEPENDENCY`. Core's own launch table is byte-identical to before. The mode-flip
tests pass and `ty check` is clean. The renderer's consumption of the token
contract lands in the S15 step that rewires `render_mcp_definition_for_mode`.

## Notes

No incidents. Core's builtin JSON is unchanged (it carries no package/module
keys and defaults to core's values).
