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

# `vault-scale-performance` `P02` summary

All eleven Steps closed. The non-mutating check pipeline now honours the
single-ingress contract: the graph build (or, after a cache hit, one
explicit read pass) reads each corpus document exactly once, and every
checker in the calculate phase runs from the shared snapshot, the ingress
raw-text map, or ingress-recorded facts. Workspace-global facts (the
attestation ledger) read once per run. Enforcement is physical: a test
deletes the corpus after ingress and the calculate phase must reproduce
its findings byte-for-byte.

- Modified: `src/vaultspec_core/graph/api.py`
- Modified: `src/vaultspec_core/vaultcore/body_schema.py`
- Modified: `src/vaultspec_core/vaultcore/checks/__init__.py`
- Modified: `src/vaultspec_core/vaultcore/checks/_base.py`
- Modified: `src/vaultspec_core/vaultcore/checks/annotations.py`
- Modified: `src/vaultspec_core/vaultcore/checks/body_sections.py`
- Modified: `src/vaultspec_core/vaultcore/checks/encoding.py`
- Modified: `src/vaultspec_core/vaultcore/checks/exec_mapping.py`
- Modified: `src/vaultspec_core/vaultcore/checks/feature_rename_integrity.py`
- Modified: `src/vaultspec_core/vaultcore/checks/features.py`
- Modified: `src/vaultspec_core/vaultcore/checks/markdown.py`
- Created: `src/vaultspec_core/vaultcore/checks/tests/test_single_ingress.py`

## Description

Ingress gained a single bytes-read per document that retains normalised
text, CRLF convention, and encoding failures for the whole run. The five
checks that re-read the corpus (annotations, markdown, encoding, feature
rename integrity) or hammered it with probes and re-parses (exec mapping,
features, body sections via the schema resolver) now consume ingress
state; the rename integrity check was confirmed to read workspace
resources, not the corpus, and exempted with rationale. The attestation
ledger memoization defuses the latent ninety-second regression on the
tool's own documented remediation path. The full vaultcore suite (557
tests) passes, and the corpus-deletion enforcement test plus the scale
gate's exact read budget hold the contract.
