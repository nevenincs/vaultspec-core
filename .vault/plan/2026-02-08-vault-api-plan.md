---
tags:
  - '#plan'
  - '#vault-api'
date: '2026-02-08'
modified: '2026-07-31'
body_hash: 'sha256:74bbf561b2172c1098cb71132277d73834287460af0d35dac6ffe5f1b20ce940'
tier: L2
related:
  - '[[2026-02-08-vault-api-adr]]'
  - '[[2026-02-08-vault-api-research]]'
---

# vault-api plan: Implementation of Docs Verification and Scaffolding

## Steps

### Phase `P01` - Core API and Auditing

Formalize the markdown rule system into a modular Python API with connectivity analysis and reporting.

- [x] `P01.S01` - implement modular vault, verification, graph, and metrics package structure; `src/vaultspec_core/vaultcore`.
- [x] `P01.S02` - implement robust frontmatter parsing and validation; `src/vaultspec_core/vaultcore/parser.py`.
- [x] `P01.S03` - build the graph API to find hotspots, orphans, and invalid links; `src/vaultspec_core/graph/api.py`.
- [x] `P01.S04` - implement the reporting CLI with summary, verify, and graph output; `src/vaultspec_core/cli`.
- [x] `P01.S05` - add a json flag for machine-readable audit output; `src/vaultspec_core/cli`.

### Phase `P02` - Write API and Scaffolding

Add template hydration and document scaffolding to the vault API.

- [x] `P02.S06` - implement the template hydration system; `src/vaultspec_core/vaultcore/hydration.py`.
- [x] `P02.S07` - implement document scaffolding with compliant naming and metadata; `src/vaultspec_core/vaultcore/index.py`.

### Phase `P03` - Vertical Integrity

Validate cross-type relationships, execution mapping, and body schema conformance across the vault.

- [x] `P03.S08` - validate that every feature has a master plan; `src/vaultspec_core/vaultcore/checks/features.py`.
- [x] `P03.S09` - validate markdown body sections against document templates; `src/vaultspec_core/vaultcore/checks/body_sections.py`.
- [x] `P03.S13` - verify exec records link back to phases in their parent plan; `src/vaultspec_core/vaultcore/checks/exec_mapping.py`.

### Phase `P04` - MCP and Advanced Analysis

Expose the vault API through MCP and add auto-healing and semantic search capabilities.

- [x] `P04.S10` - wrap the vault API into a model context protocol server; `src/vaultspec_core/mcp_server`.
- [x] `P04.S11` - implement auto-healing for broken wiki-links; `src/vaultspec_core/vaultcore/checks/dangling.py`.
- [x] `P04.S12` - integrate vector-based rag for semantic document lookup; `src/vaultspec_core/core/workspace_mode.py`.
