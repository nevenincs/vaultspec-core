---
tags:
  - '#plan'
  - '#roadmap'
date: '2026-02-17'
modified: '2026-07-31'
body_hash: 'sha256:1d1a28dd375a5b30511cc782ea4f0db2c093b752bc148dfee9ebfb8e68918f5a'
tier: L2
related:
  - '[[2026-02-17-audit-summary-audit]]'
  - '[[2026-02-17-bootstrap-prompt-adr]]'
  - '[[2026-03-23-roadmap-research]]'
---

# vaultspec Roadmap: Wave-Based Rollout Plan

## Steps

### Phase `P01` - Critical Blocking Bugs

Fix issues that prevent core features from working.

- [x] `P01.S01` - fix the crash-on-import bug in the agent dispatch entry point; `src/vaultspec_core/core/executor.py`.
- [ ] `P01.S02` - correct the cli test runner's test discovery path; `src/vaultspec_core/tests`.
- [ ] `P01.S03` - add skip markers to the a2a end-to-end tests; `src/vaultspec_core/tests`.
- [x] `P01.S04` - fix the development typo in the framework readme; `docs/README.md`.

### Phase `P02` - Self-Dogfooding and Credibility

Clean up the vault corpus and agent persona content so the project practices what it governs.

- [ ] `P02.S05` - fix vault verification errors across the corpus; `.vault`.
- [x] `P02.S06` - resolve the phantom workflows directory reference; `.claude/workflows`.
- [ ] `P02.S07` - populate project-specific context for the workspace; `CLAUDE.md`.
- [x] `P02.S08` - remove stale rust-specific language from agent persona files; `src/vaultspec_core/builtins/agents/vaultspec-adr-researcher.md`.
- [ ] `P02.S09` - rename the readme template to documentation-standards; `src/vaultspec_core/builtins/templates`.

### Phase `P03` - Onboarding Documentation

Give newcomers a coherent path from README to concepts to CLI reference.

- [x] `P03.S10` - rewrite the top-level readme; `README.md`.
- [ ] `P03.S11` - write a getting started guide; `docs`.
- [x] `P03.S12` - write a concepts document; `docs/framework.md`.
- [x] `P03.S13` - write a cli reference document; `docs/CLI.md`.
- [ ] `P03.S14` - write a configuration reference document; `docs`.
- [ ] `P03.S15` - write a rag query syntax guide; `docs`.
- [ ] `P03.S16` - embed architecture diagrams in the concepts document; `docs/framework.md`.
- [x] `P03.S17` - separate human-facing and agent-facing documentation; `src/vaultspec_core/builtins`.

### Phase `P04` - CLI Completeness

Round out the CLI surface with the commands and flags users expect.

- [x] `P04.S18` - add an init/install command; `src/vaultspec_core/cli/root_install.py`.
- [x] `P04.S19` - add remove commands for rules, agents, and skills; `src/vaultspec_core/cli/spec_cmd_rules.py`.
- [x] `P04.S20` - add show commands for rules, agents, and skills; `src/vaultspec_core/cli/spec_cmd_rules.py`.
- [x] `P04.S21` - add rename commands for rules, agents, and skills; `src/vaultspec_core/cli/spec_cmd_rules.py`.
- [x] `P04.S22` - add edit commands for rules, agents, and skills; `src/vaultspec_core/cli/spec_cmd_rules.py`.
- [x] `P04.S23` - add a version flag to the cli; `src/vaultspec_core/cli/root_app.py`.
- [x] `P04.S24` - add a doctor command; `src/vaultspec_core/cli/root_doctor.py`.
- [x] `P04.S25` - add a template flag to agent and skill add commands; `src/vaultspec_core/cli/spec_cmd_skills.py`.
- [ ] `P04.S26` - remove gpu/cuda language from search command help text; `src/vaultspec_core/cli`.

### Phase `P05` - Ecosystem Integration

Align with external ecosystem standards for agent manifests, embeddings, protocols, and MCP security.

- [x] `P05.S27` - bring agents.md generation into standard compliance; `AGENTS.md`.
- [ ] `P05.S28` - upgrade the default embedding model; `src/vaultspec_core`.
- [ ] `P05.S29` - upgrade the acp sdk dependency; `pyproject.toml`.
- [ ] `P05.S30` - apply an mcp security baseline; `src/vaultspec_core/mcp_server`.

### Phase `P06` - Test Coverage and CI

Close test coverage gaps and stand up continuous integration.

- [x] `P06.S31` - add cli command test coverage; `src/vaultspec_core/tests/cli`.
- [x] `P06.S32` - add logging configuration test coverage; `src/vaultspec_core/tests/test_logging_config.py`.
- [ ] `P06.S33` - fix rag search test timeouts; `src/vaultspec_core`.
- [x] `P06.S34` - expand metrics test coverage; `src/vaultspec_core/metrics/tests/test_metrics.py`.
- [x] `P06.S35` - add mcp config loading test coverage; `src/vaultspec_core/core/tests/test_mcps.py`.
- [x] `P06.S36` - register a benchmark test marker; `pyproject.toml`.
- [x] `P06.S37` - add a continuous integration pipeline; `.github/workflows/ci.yml`.

### Phase `P07` - Strategic Features

Add higher-leverage features inspired by the frontier agent tooling landscape.

- [ ] `P07.S38` - add an agent readiness assessment; `src/vaultspec_core`.
- [x] `P07.S39` - add event-driven hooks; `src/vaultspec_core/builtins/hooks`.
- [ ] `P07.S40` - add a constitution layer; `src/vaultspec_core`.
- [ ] `P07.S41` - register the project in the acp registry; `pyproject.toml`.
- [ ] `P07.S42` - add interactive add modes to the cli; `src/vaultspec_core/cli`.
- [x] `P07.S43` - add a fix flag to the vault audit command; `src/vaultspec_core/cli/vault_check_cmd.py`.

### Phase `P08` - Advanced Features

Pursue longer-horizon, research-grade capabilities once the foundation is solid.

- [ ] `P08.S44` - build agentic rag capability; `src/vaultspec_core`.
- [ ] `P08.S45` - build graphrag capability; `src/vaultspec_core/graph`.
- [ ] `P08.S46` - add a2a v0.3 features including grpc and security signing; `src/vaultspec_core/protocol`.
- [ ] `P08.S47` - integrate an mcp registry; `src/vaultspec_core/mcp_server`.
- [ ] `P08.S48` - build an agent evaluation framework; `src/vaultspec_core/core`.
- [ ] `P08.S49` - build a tiered policy engine; `src/vaultspec_core/core`.
- [ ] `P08.S50` - build a compliance dashboard; `src/vaultspec_core`.
- [ ] `P08.S51` - support parallel agent execution; `src/vaultspec_core/core/executor.py`.
- [ ] `P08.S52` - build a spec registry; `src/vaultspec_core/vaultcore`.
- [ ] `P08.S53` - support reverse spec generation; `src/vaultspec_core/vaultcore`.
- [ ] `P08.S54` - add token usage optimization; `src/vaultspec_core`.
- [ ] `P08.S55` - publish a documentation site; `docs`.
- [ ] `P08.S56` - write a migration guide; `src/vaultspec_core/migrations`.
