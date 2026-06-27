---
tags:
  - '#exec'
  - '#rename-convergence'
date: '2026-06-27'
modified: '2026-06-27'
step_id: 'S05'
related:
  - "[[2026-06-27-rename-convergence-plan]]"
---

# Route resource_rename through the engine with per-base_dir containment, case-safe rename, resource-domain lock, and rollback

## Scope

- `src/vaultspec_core/core/resources.py`

## Description

- Route both branches of `resource_rename` through a `RenameTransaction` bound to the resource's own `base_dir`, replacing the ad-hoc `shutil.move`-plus-unlink flow and its best-effort move-back rollback.
- Derive the shared resource-domain lock sentinel from the active workspace context's source rules dir so a rename serializes on one `.vaultspec` sentinel whether `base_dir` is the source tree or a provider mirror; fall back to a lock-free transaction when no context is active.
- Add explicit containment assertions on both endpoints before any work, asserting the skill directory endpoints (not just `SKILL.md`), so an escaping name is refused before the lock or snapshot.
- For a flat resource, snapshot the old file, rename it through the transaction, journal the destination as a created file, then write the rewritten `name:` content with the existing atomic write.
- For a skill, snapshot the old `SKILL.md`, rename the directory through the transaction, journal the new `SKILL.md` as a created file, then write the rewritten `name:` content; the reverse journal now gives the multi-step skill rename real rollback.
- Preserve the frontmatter `name:` rewrite, the flat-root de-nesting, the returned new path, and the `ResourceExistsError` / `ResourceNotFoundError` raises byte-for-byte.

## Outcome

- All three resource rename surfaces (rules, skills, agents) are now containment-guarded, case-safe, lock-serialized, and roll back byte-for-byte on a mid-apply failure, with the `spec.rules.rename`, `spec.skills.rename`, and `spec.agents.rename` JSON envelopes unchanged.
- The existing spec-rename live suite stayed green untouched, confirming the observable contract is preserved.

## Notes

- The frontmatter `name:` rewrite is emitted verbatim through the existing builder, so the envelope and golden output are stable; no line-ending tension surfaced for the spec resources in scope.
- Unlike the docs-domain lock, the resource lock sentinel's parent directory always exists, so the lock is genuinely acquired in any context-bearing flow rather than a no-op.
