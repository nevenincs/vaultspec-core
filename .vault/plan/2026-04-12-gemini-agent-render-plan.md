---
tags:
  - '#plan'
  - '#gemini-agent-render'
date: '2026-04-12'
modified: '2026-07-31'
body_hash: 'sha256:ac69db75279a7f9364fe16d92583dcf58b4bcb09e57e89978ed171917522cc56'
tier: L2
related:
  - '[[2026-04-12-gemini-agent-render-research]]'
  - '[[2026-04-12-gemini-agent-render-adr]]'
---

# gemini-agent-render plan

### Phase `P01` - Phase 1 implementation

Land the per-provider agent renderer factory so Gemini CLI loads every managed agent without validation errors.

- [x] `P01.S01` - introduce the per-provider agent renderer factory with Claude and Gemini tool-mapping renderers; `src/vaultspec_core/core/agents.py`.
- [x] `P01.S02` - thread render warnings through agents_sync alongside parse warnings; `src/vaultspec_core/core/agents.py`.
- [x] `P01.S03` - add renderer dispatch, coverage and tool-mapping tests with no mocks or skips; `src/vaultspec_core/tests/cli/test_agents_render.py`.
- [x] `P01.S04` - run lint, format and type-check gates over the renderer and its tests; `src/vaultspec_core/core/agents.py`.
- [x] `P01.S05` - commit, push, and refresh the pull request body with the latest commit list and test counts; `src/vaultspec_core/core/agents.py`.

### Phase `P02` - Phase 2 verification

Verify the renderer against the ADR with a formal code review and close out the phase summary.

- [x] `P02.S06` - run a high-tier code review of the diff against the ADR; `.vault/exec/2026-04-12-gemini-agent-render/2026-04-12-gemini-agent-render-phase1-review-exec.md`.
- [x] `P02.S07` - write the phase summary referencing each step record and the review; `.vault/exec/2026-04-12-gemini-agent-render/2026-04-12-gemini-agent-render-phase1-summary-exec.md`.
