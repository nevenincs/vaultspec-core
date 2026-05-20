---
name: vaultspec-archive-discipline
---

# Archive discipline: audit incoming references before retiring a feature

A working example of codification applied to a real audit finding. This rule was
promoted from the rolling CLI UX audit (finding B9) following the discipline described
in the `vaultspec-codify` rule.

## Rule

Before invoking `vaultspec-core vault feature archive <feature-tag>`, enumerate every
document outside the feature whose `related:` frontmatter points at any document inside
the feature. Decide in advance whether those incoming references should be rewritten,
acknowledged as dangling, or block the archive entirely.

## Why

The rolling CLI UX audit's B9 finding documented that
`vaultspec-core vault feature archive` today has five compounding gaps: no `--dry-run`,
no reversal verb, silent breakage of cross-feature `related:` links, an output directory
`vaultspec-core vault check structure` declares illegal, and an auto-fix path that
amputates the very relationships the verb was invoked to preserve. The team-lead brief
in the audit's Round 3 explicitly stated "the trail should stay readable; we're not
deleting anything", and the CLI did the opposite.

The sibling ADR `cli-memory-lifecycle` proposes a comprehensive fix landing in the
umbrella plan's `W02.P04.S14`. Until that ships, this rule is the operator discipline
that prevents the known failure mode.

## How

Before archive, run a discovery pass:

- `vaultspec-core vault check dangling` against the current vault to record the baseline
  (no dangling links before archive).

- Search the vault for incoming references to the feature being archived. The feature's
  index document at `.vault/index/<feature-tag>.index.md` enumerates the feature's own
  documents; you want the inverse — every document in
  `.vault/{adr,plan,research,audit,exec,reference}/` whose `related:` field references
  any of those stems.

- Classify each incoming reference: cross-feature provenance to preserve, stale link to
  drop, or external dependency that should block archive until resolved.

Then take the right action:

- **Good:** the discovery pass reports zero incoming cross-feature references. Archive
  is safe. Run `vaultspec-core vault feature archive <feature-tag>` and verify
  `vaultspec-core vault check all` stays green.

- **Good:** the discovery pass reports incoming references and you have explicitly
  rewritten or removed them before invoking the archive verb. The archive then leaves no
  dangling links.

- **Bad:** invoke `vaultspec-core vault feature archive` against a feature with
  unaudited incoming references, then attempt to "fix" the resulting dangling errors via
  `vaultspec-core vault repair`. The repair's auto-fix removes the `related:` entries,
  silently destroying the cross-feature provenance the rule was meant to preserve.

- **Bad:** invoke `vaultspec-core vault feature archive <typo>` against a tag that does
  not exist. The verb returns exit 0 with a silent no-op (also finding B9); CI cannot
  detect that nothing was archived. Validate the feature tag with
  `vaultspec-core vault feature list` before archive.

## Status

Active. Once `cli-memory-lifecycle` `W02.P04.S14` lands (the archive verb gains a
dry-run preview, a paired unarchive verb, cross-feature link rewriting, and a non-zero
exit on typo'd targets), the discovery-pass burden moves into the CLI and this rule's
body shortens to a one-line pointer at the new dry-run preview path as canonical. The
rule's intent (audit incoming references before retirement) survives the verb
improvement; only the procedure changes.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (rolling), finding B9 critical. Sibling
decision ADR `2026-05-17-cli-memory-lifecycle-adr`. Umbrella plan step `W02.P04.S14` in
`2026-05-17-cli-simplification-ux-plan`.
