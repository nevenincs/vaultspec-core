---
tags:
  - '#exec'
  - '#discovery-fallback'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:08d288de5f0f410e72f78204a7cee669c40a2715695052dfe78a8edc666ddcc5'
related:
  - "[[2026-09-23-discovery-fallback-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `discovery-fallback` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S01` `A` `src/vaultspec_core/search/_capability.py`
- `S01` `A` `src/vaultspec_core/search/_filters.py`
- `S01` `M` `src/vaultspec_core/search/__init__.py`
- `S01` `M` `src/vaultspec_core/search/_models.py`
- `S01` `M` `src/vaultspec_core/search/_remediation.py`
- `S01` `M` `src/vaultspec_core/search/_service.py`
- `S01` `M` `src/vaultspec_core/search/_wire.py`
- `S01` `M` `src/vaultspec_core/search/tests/test_remediation.py`
- `S01` `M` `src/vaultspec_core/search/tests/test_service.py`
- `S01` `M` `src/vaultspec_core/core/diagnosis/collectors_companion.py`
- `S01` `M` `src/vaultspec_core/core/diagnosis/diagnosis.py`
- `S01` `M` `src/vaultspec_core/core/discovery_guidance.py`
- `S01` `M` `src/vaultspec_core/cli/vault_search_cmd.py`
- `S01` `M` `src/vaultspec_core/cli/status_cmd.py`
- `S01` `M` `src/vaultspec_core/tests/cli/test_vault_search_cmd.py`
- `S01` `M` `src/vaultspec_core/tests/cli/test_vault_status.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tools/search.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tools/orientation.py`
- `S01` `M` `src/vaultspec_core/mcp_server/envelope.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tests/test_search_tool.py`
- `S01` `M` `src/vaultspec_core/mcp_server/tests/test_context_budget.py`
- `S01` `M` `pyproject.toml`
- `S01` `verify:` `just check-python check-type check-size check-complexity check-nesting check-toml framework-reference-check; pytest mcp_server search core tests config dev/guards` -> `pass`
- `S01` `by:` `opus-high`
- `S02` `M` `src/vaultspec_core/core/discovery_guidance.py`
- `S02` `M` `src/vaultspec_core/tests/test_discovery_guidance.py`
- `S02` `M` `src/vaultspec_core/builtins/rules/vaultspec-discovery.builtin.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-code-research/SKILL.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`
- `S02` `M` `src/vaultspec_core/builtins/skills/vaultspec-curate/references/reconciliation-playbook.md`
- `S02` `M` `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`
- `S02` `verify:` `just check-python check-type check-markdown check-size check-complexity check-nesting; pytest test_discovery_guidance core/tests cli/test_sync search/test_remediation` -> `pass`
- `S02` `by:` `opus-high`
- `S03` `M` `src/vaultspec_core/cli/reference_gen.py`
- `S03` `M` `src/vaultspec_core/tests/cli/test_cli_reference_generated.py`
- `S03` `M` `src/vaultspec_core/builtins/reference/cli.md`
- `S03` `M` `docs/CLI.md`
- `S03` `verify:` `just fix-markdown, framework-reference, check-markdown, framework-reference-check, check-size check-complexity check-nesting; ruff and ty clean on S03 files; pytest test_cli_reference_generated test_cli_reference_drift guards/test_cli_handbook_drift guards/test_cli_reference_contract_helpers` -> `pass`
- `S03` `by:` `opus-high`
- `S05` `M` `README.md`
- `S05` `M` `docs/framework.md`
- `S05` `M` `docs/CLI.md`
- `S05` `M` `docs/MCP.md`
- `S05` `verify:` `just framework-reference-check` -> `pass`
- `S05` `by:` `opus-medium`
- `S04` `M` `src/vaultspec_core/core/discovery_guidance.py`
- `S04` `M` `src/vaultspec_core/tests/test_discovery_guidance.py`
- `S04` `M` `src/vaultspec_core/builtins/rules/vaultspec-discovery.builtin.md`
- `S04` `M` `src/vaultspec_core/builtins/skills/vaultspec-code-research/SKILL.md`
- `S04` `M` `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`
- `S04` `M` `src/vaultspec_core/builtins/skills/vaultspec-curate/references/reconciliation-playbook.md`
- `S04` `M` `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`
- `S04` `M` `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`
- `S04` `M` `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md`
- `S04` `M` `src/vaultspec_core/builtins/agents/vaultspec-reference-auditor.md`
- `S04` `M` `.vaultspec/rules/vaultspec-discovery.builtin.md`
- `S04` `M` `.vaultspec/skills/vaultspec-code-research/SKILL.md`
- `S04` `M` `.vaultspec/skills/vaultspec-curate/SKILL.md`
- `S04` `M` `.vaultspec/skills/vaultspec-curate/references/reconciliation-playbook.md`
- `S04` `M` `.vaultspec/skills/vaultspec-adr/SKILL.md`
- `S04` `M` `.vaultspec/agents/vaultspec-docs-curator.md`
- `S04` `M` `.vaultspec/agents/vaultspec-code-reviewer.md`
- `S04` `M` `.vaultspec/agents/vaultspec-reference-auditor.md`
- `S04` `M` `.vaultspec/reference/cli.md`
- `S04` `verify:` `install --upgrade, sync, just check-python check-type, pytest test_discovery_guidance test_corpus_contracts test_agents_render test_antigravity_agents test_cli_reference_drift test_seed_builtins cli/test_sync cli/test_install, mdformat and pymarkdown on builtins` -> `pass`
- `S04` `by:` `opus-medium`

## Notes

- `S01` MCP status does not carry the companion record: it measured +439 tool-definition chars against a ceiling the envelope ADR forbids raising; the companion reaches agents as the search next step instead
- `S02` Builtins touched only to swap the routing sentence for the new constant; the S04 rewrite owns their prose. SEARCH_ADR removed: no builtin or backend offers the rag ADR search any more
- `S03` Whole-tree check-python and check-type fail only in the concurrent env-var centralisation lane (search tests, CredentialSource import in search/_models.py, deleted search/_credential.py); none in S03 files
- `S04` S04 dev/guards test_cli_language_contract fails on README.md and docs/ from the concurrent user-docs lane; check-markdown flags this ledger's S03 note (unescaped underscores), machine-owned and left as written
