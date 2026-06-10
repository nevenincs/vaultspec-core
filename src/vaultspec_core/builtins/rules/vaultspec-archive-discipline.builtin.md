---
name: vaultspec-archive-discipline
---

# Archive discipline: audit incoming references before retiring a feature

A working example of codification applied to a real audit finding. This rule was
promoted from the rolling CLI UX audit (finding B9) following the discipline described
in the `vaultspec-codify` rule.

## Rule

Before invoking `vaultspec-core vault feature archive <feature-tag>`, run the same verb
with `--dry-run` as the canonical discovery pass and audit the preview for incoming
references: documents outside the feature whose `related:` frontmatter points at
documents inside it. Decide whether each incoming reference should be rewritten,
acknowledged as dangling, or block the archive entirely before applying the real run.

## Why

The rolling CLI UX audit's B9 finding documented compounding gaps in the archive verb:
no preview, no reversal verb, silent breakage of cross-feature `related:` links, and a
destructive auto-fix path. The CLI has since closed the verb-level gaps: the archive
verb carries `--dry-run`, a paired `vaultspec-core vault feature unarchive` verb
restores a mistaken archive, and archiving a nonexistent tag exits 1 with an error
(re-verified against the live CLI on 2026-06-10, `vaultspec-core --version` 0.1.26).
What the CLI cannot decide is whether an incoming cross-feature reference is provenance
to preserve, a stale link to drop, or a dependency that should block retirement. That
judgment is this rule.

## How

- Run `vaultspec-core vault feature archive <feature-tag> --dry-run` and read the
  previewed changes; classify every incoming reference before the real run.
- After the real run, verify `vaultspec-core vault check all` stays green. If the
  archive was a mistake, `vaultspec-core vault feature unarchive <feature-tag>` reverses
  it.

## Status

Active. The CLI improvements this rule anticipated (`cli-memory-lifecycle`
`W02.P04.S14`) have landed: `--dry-run` is the canonical discovery pass, `unarchive` is
the reversal verb, and typo'd tags fail loudly. The rule's intent (audit incoming
references before retirement) survives the verb improvement; the discovery procedure now
lives in the CLI preview.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (rolling), finding B9 critical. Sibling
decision ADR `2026-05-17-cli-memory-lifecycle-adr`. Umbrella plan step `W02.P04.S14` in
`2026-05-17-cli-simplification-ux-plan`.
