---
tags:
  - '#plan'
  - '#pytest-e2e'
date: '2026-02-21'
modified: '2026-07-31'
body_hash: 'sha256:6e3ab3004fa02e3cf4747769fec833d7f327a3e1e3e78c27e4d694df2464afa8'
tier: L2
related:
  - '[[2026-02-21-pytest-e2e-observability-adr]]'
  - '[[2026-02-21-pytest-e2e-observability-research]]'
---

# `pytest-e2e` `impl` plan

### Phase `P01` - Infrastructure

Add live logging, timeout, and reporting config to pytest, then install the observability plugin dependencies

- [x] `P01.S01` - add log_cli, log_file, and timeout configuration to the pytest ini options; `pyproject.toml`.
- [ ] `P01.S02` - register the flaky marker and add pytest-rerunfailures and pytest-harvest as new test dependencies; `pyproject.toml`.
- [x] `P01.S03` - install the reportlog and durations test dependencies; `pyproject.toml`.

### Phase `P02` - Test instrumentation

Add retry markers, results_bag metrics capture, and live logging to the real-LLM end-to-end test classes

- [ ] `P02.S04` - add retry markers to the real-LLM end-to-end test classes; `pyproject.toml`.
- [ ] `P02.S05` - add results_bag metrics capture to the end-to-end tests; `pyproject.toml`.
- [ ] `P02.S06` - add logging around each llm call site in the end-to-end test files; `pyproject.toml`.

### Phase `P03` - Housekeeping and verification

Update .gitignore for new log and report artifacts, then verify the fast suite and plugin loading are unaffected

- [x] `P03.S07` - add test-debug.log and test-events.jsonl entries to .gitignore; `.gitignore`.
- [ ] `P03.S08` - verify fast tests still pass with the new pytest config; `pyproject.toml`.
- [x] `P03.S09` - verify the new pytest plugins load without conflicts; `pyproject.toml`.
