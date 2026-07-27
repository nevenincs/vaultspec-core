---
tags:
  - '#exec'
  - '#vault-scale-performance'
date: '2026-07-27'
modified: '2026-07-27'
body_schema: 'body-v1'
related:
  - "[[2026-07-27-vault-scale-performance-plan]]"
---

# `vault-scale-performance` `P04` summary

All three Steps closed. The D8 native-leaf decision is implemented: the
libyaml frontmatter loader was verified already live on the parse hot path
(7.3x over the pure-Python loader, measured on the real corpus), and the
opt-in betweenness analysis now routes through the C-backed rustworkx
engine with pure networkx as the automatic fallback (13.2x measured at
1,181 nodes, maximum score delta 1.6e-19). Native code stays confined to
leaf computations behind existing seams; no semantics were duplicated.

- Modified: `src/vaultspec_core/graph/api.py`
- Modified: `pyproject.toml`
- Created: `src/vaultspec_core/graph/tests/test_analysis_engine.py`

## Description

The seam converts the built graph and runs the same Brandes algorithm
with identical normalisation and endpoint semantics; a four-test parity
suite runs both real engines on the same graphs and requires agreement to
1e-12, and the full graph suite including the envelope contract tests
passes against the engine-computed scores. The dependency is declared
with a version floor and guarded by the fallback so platforms without the
wheel lose speed, never the surface. A dedicated native calculation
engine was explicitly rejected in the amended decision record; it
revisits only under a new record if a far larger corpus target or a
sub-100ms interactive consumer materialises.
