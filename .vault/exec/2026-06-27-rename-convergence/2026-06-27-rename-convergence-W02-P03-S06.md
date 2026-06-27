---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S06'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Add real-filesystem resource_rename tests (rules/skills/agents, rollback, preserved envelopes)

## Scope

- `src/vaultspec_core/core/tests/test_resource_rename.py`

## Description

- Add a real-filesystem test module with a fixture that builds a temporary `.vaultspec` source tree and sets an isolated workspace context that is reset on teardown, with no test doubles.
- Cover the flat rename: a rule rename rewrites the frontmatter `name:`, removes the old file, and materializes the new file; an agent rename rewrites its name too.
- Cover the skill rename: the directory is moved, `SKILL.md` has its `name:` rewritten, and an extra resource file in the skill dir rides the rename intact.
- Cover the contract raises: `ResourceExistsError` on a flat and a skill destination collision, `ResourceNotFoundError` on a missing source, a missing skill directory, and a skill directory missing its `SKILL.md`.
- Cover rollback by planting a directory at the atomic-write temp path so the post-rename content write fails after the rename has landed, then assert the resource tree is byte-identical for both the flat and the multi-step skill case.
- Cover containment by asserting a destination and a source name that escape `base_dir` are both refused and leave the tree byte-identical.

## Outcome

- Closes the standing coverage gap: `resource_rename` had no dedicated tests; it now has seventeen real-filesystem assertions spanning all three resource kinds, both rollback paths, and containment.
- The collision, not-found, and containment cases assert byte-identical trees, proving no partial mutation escapes on the refusal paths.

## Notes

- The induced mid-apply failure mirrors the atomic-write temp-name formula and self-checks: if the write scheme changed, the planted obstacle would miss and the expected raise would not fire, so the test fails loudly rather than silently passing.
- The rollback assertions scope their byte-identity comparison to the resource subtree, so the acquired resource lock file (which lives one level up under the framework dir) does not perturb the comparison.
