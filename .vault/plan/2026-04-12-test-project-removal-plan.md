---
tags:
  - '#plan'
  - '#test-project-removal'
date: '2026-04-12'
modified: '2026-07-31'
body_hash: 'sha256:ea0f9da9e510589be4fa1e8b4877051fd27bb774e2d8b5484ef83591c0a81805'
tier: L2
related:
  - '[[2026-04-12-test-project-removal-adr]]'
  - '[[2026-04-12-test-project-removal-research]]'
---

# `test-project-removal` implementation plan

### Phase `P01` - Lift and extend the synthetic vault generator

Lift synthetic.py from vaultspec-rag into a testing subpackage and extend it with pathology presets and named docs.

- [x] `P01.S01` - create the testing subpackage and lift synthetic.py verbatim from vaultspec-rag with no runtime dependency added; `src/vaultspec_core/testing/synthetic.py`.
- [x] `P01.S02` - add the 14 pathology presets, pathology_details, named_docs, feature_names and graph_density parameters to build_synthetic_vault; `src/vaultspec_core/testing/synthetic.py`.
- [x] `P01.S03` - add synthetic-generator self-tests covering determinism, taxonomy compliance and every pathology; `src/vaultspec_core/testing/tests/test_synthetic.py`.

### Phase `P02` - Pytest fixture wiring and the conftest smell

Delete the git-checkout conftest smell and wire session and function fixtures onto the synthetic vault generator.

- [x] `P02.S04` - delete the _vault_snapshot_reset git-checkout fixture, dead helpers, and TEST_PROJECT/TEST_VAULT constants; `src/vaultspec_core/tests/cli/conftest.py`.
- [x] `P02.S05` - introduce the synthetic_vault and synthetic_project pytest fixtures backed by build_synthetic_vault; `src/vaultspec_core/tests/cli/conftest.py`.

### Phase `P03` - Refactor the consumer test modules

Swap every test-project-backed fixture for the synthetic corpus across all consumer test modules.

- [x] `P03.S06` - refactor every consumer test module (cli, scanner, query, checks, metrics, graph) from the test-project corpus to the synthetic vault fixtures; `src/vaultspec_core/`.

### Phase `P04` - Housekeeping deletions

Delete test-project/ and the issue #67 dead-weight files, cleaning every reference in the ignore and pre-commit configs.

- [x] `P04.S07` - delete test-project/, rsc/, .geminiignore and extension.toml from the repository; `test-project`.
- [x] `P04.S08` - clean the dangling test-project references from .gitignore, .pre-commit-config.yaml and .dockerignore; `.gitignore`.

### Phase `P05` - Validation gate

Run the full pytest, prek and type-check gates and confirm zero git remnants after the refactor.

- [x] `P05.S09` - pass the full pytest, prek and ty gates with zero test-project remnants and zero working-tree git remnants; `src/vaultspec_core/`.
