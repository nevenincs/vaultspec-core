---
tags:
  - '#plan'
  - '#pre-existing-tests'
date: '2026-05-01'
modified: '2026-06-13'
related:
  - '[[2026-05-01-pre-existing-tests-adr]]'
  - '[[2026-05-01-pre-existing-tests-research]]'
---

# `pre-existing-tests` plan: pre-existing test failures (#98, #99)

Tight, two-task plan to repair the two pre-existing test failures recorded
in #98 and #99.

## Proposed Changes

Apply the fix paths chosen in the ADR. One commit per task so the PR is
independently reviewable per issue.

## Tasks

- Task 1: Fix #98
  - Delete `tests/test_mcp_config.py`. Confirm `tests/test_mcps.py`
    coverage is unchanged. No replacement file.
- Task 2: Fix #99
  - In `src/vaultspec_core/tests/cli/test_agents_render.py`, swap
    `TestGeminiCliLoadsRenderedAgents._invoke_gemini` argv to
    `[gemini_bin, "--skip-trust", "skills", "list"]` and remove the now
    unused `_PROBE_PROMPT` constant.
  - Update class docstring to reflect the new probe surface.
- Task 3: Quality gates and audit sweep
  - Run pytest twice in succession; confirm zero failures both times.
  - `ty check`, `ruff check`, `ruff format --check`, `vault check all`,
    `spec doctor` all clean.
  - Grep for skips, xfails, similar source-repo path assertions; surface
    findings in PR body. Do not fix unrelated issues here.

## Parallelization

Tasks 1 and 2 are independent and could run in parallel; sequential
execution keeps commit history clean and avoids cross-test interference.

## Verification

Mission success means:

- `uv run --no-sync pytest` produces zero failures on the source repo.
- The gemini probe (when selected via `@pytest.mark.gemini`) actually
  catches a deliberately broken agent. Verified empirically against
  gemini 0.40.0-preview.4 before code changes.
- No skips, mocks, patches, stubs, fakes are introduced.
- The two consecutive clean pytest runs prove stability rather than a
  flaky pass.

Caveats: the gemini-marked test is opt-in and requires the gemini binary;
its actual run-time validation depends on the maintainer running it with
the marker. The canary inside the test (broken agent must show up in
errors) is the in-process guard that prevents future probe rot from
silently passing.
