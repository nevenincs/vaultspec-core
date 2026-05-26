---
name: vaultspec-dry-run-discipline
---

# Dry-run discipline: preview destructive verbs before applying

Third worked example of codification. Promoted from the rolling CLI UX audit's findings
S4, S14, and the gating dimension of B9.

## Rule

Before invoking any vaultspec CLI verb that writes or removes state, run the same verb
with `--dry-run` first when the flag is available, and read the previewed change list
carefully. Apply the real run only after the preview matches your intent.

## Why

The rolling CLI UX audit's findings S4, S14, and B9 documented that destructive verbs
across the CLI are gated asymmetrically: `install` writes about seventy files into the
workspace with no flag, `uninstall` requires `--force`,
`vaultspec-core install --upgrade` ships without a preview, and
`vaultspec-core vault feature archive` has no `--dry-run`, no reversal, and silently
breaks cross-feature links. The blast radius of a wrong-directory invocation today is
large and the recovery story is manual.

The sibling ADR `cli-blast-radius-gating` proposes universal `--dry-run` discipline
landing in the umbrella plan's `W04.P11`. Until that ships, the operator is the
discipline. This rule records the operator's contract.

## How

The general pattern, for any destructive verb:

1. Form the intended invocation (verb plus arguments plus flags).
1. Add `--dry-run` to it and run.
1. Read the preview output. Confirm the affected files / records match your intent.
1. If the preview is empty or absent, escalate: an empty preview on a verb that should
   produce side effects is a finding worth logging, not a green light.
1. Re-run the original invocation without `--dry-run` only when the preview is
   satisfactory.

Worked examples (every command below works against today's CLI; verified against
`vaultspec-core --version` 0.1.19):

- **Good:** `vaultspec-core install --dry-run` against an empty directory, read the file
  list, confirm provider selection, then run `vaultspec-core install`.

- **Good:**
  `vaultspec-core vault add plan --feature my-feature --title "..." --tier L1 --related <stem> --dry-run`
  to preview the scaffolded path, frontmatter, and tier value. The `--tier` flag
  (defaults to L1; accepted values L1..L4) ensures the scaffolded document parses on the
  next vault command and is the canonical way to set the plan's tier at creation time.

- **Bad:** `vaultspec-core install` in a busy repository without a preview. About
  seventy files appear, `.gitignore` is rewritten, `CLAUDE.md` is created. If the
  directory was wrong, the cleanup is `vaultspec-core uninstall --force` -- and
  uninstall has its own gaps.

- **Bad:** `vaultspec-core vault feature archive <typo>` against a tag that does not
  exist. The verb returns exit 0 with a silent no-op (see also the
  `vaultspec-archive-discipline` rule). The dry-run does not exist for this verb today,
  so the only safe path is to validate the tag with `vaultspec-core vault feature list`
  before invocation.

- **Bad:** trusting `vaultspec-core install --upgrade --dry-run`'s output today (which
  is empty per finding S14). Treat the empty preview as a warning, not as confirmation.
  Until the gap closes (umbrella plan `W04.P11.S39`), the operator must inspect the
  workspace by hand for what the upgrade would overwrite.

## Status

Active. Once `cli-blast-radius-gating` `W04.P11` lands (universal `--dry-run`
discipline, shared code paths between preview and apply, preservation summary lines on
every destructive verb), the rule's body shortens to a one-line affirmation that
`--dry-run` is the canonical preview path on every verb. The rule's intent (preview
before apply) survives the framework improvement; it becomes structurally enforced
rather than operator-enforced.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (rolling), findings S4 (round 1), S14
(round 3a), and the gating dimension of B9 (round 3b). Sibling decision ADR
`2026-05-17-cli-blast-radius-gating-adr`. Umbrella plan steps `W04.P11.S39`, `S40`,
`S41`, `S42` in `2026-05-17-cli-simplification-ux-plan`.
