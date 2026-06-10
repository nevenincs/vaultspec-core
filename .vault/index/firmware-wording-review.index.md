---
generated: true
tags:
  - '#index'
  - '#firmware-wording-review'
date: '2026-06-10'
related:
  - '[[2026-06-09-firmware-wording-review-P01-S01]]'
  - '[[2026-06-09-firmware-wording-review-P01-S02]]'
  - '[[2026-06-09-firmware-wording-review-P01-S03]]'
  - '[[2026-06-09-firmware-wording-review-P01-S04]]'
  - '[[2026-06-09-firmware-wording-review-P01-S05]]'
  - '[[2026-06-09-firmware-wording-review-P01-S06]]'
  - '[[2026-06-09-firmware-wording-review-P01-S07]]'
  - '[[2026-06-09-firmware-wording-review-P01-S08]]'
  - '[[2026-06-09-firmware-wording-review-P01-S09]]'
  - '[[2026-06-09-firmware-wording-review-P01-S10]]'
  - '[[2026-06-09-firmware-wording-review-P01-summary]]'
  - '[[2026-06-09-firmware-wording-review-P02-S11]]'
  - '[[2026-06-09-firmware-wording-review-P02-S12]]'
  - '[[2026-06-09-firmware-wording-review-P02-S13]]'
  - '[[2026-06-09-firmware-wording-review-P02-S14]]'
  - '[[2026-06-09-firmware-wording-review-P02-summary]]'
  - '[[2026-06-09-firmware-wording-review-P03-S15]]'
  - '[[2026-06-09-firmware-wording-review-P03-S16]]'
  - '[[2026-06-09-firmware-wording-review-P03-S17]]'
  - '[[2026-06-09-firmware-wording-review-P03-S18]]'
  - '[[2026-06-09-firmware-wording-review-P03-S19]]'
  - '[[2026-06-09-firmware-wording-review-P03-summary]]'
  - '[[2026-06-09-firmware-wording-review-P04-S20]]'
  - '[[2026-06-09-firmware-wording-review-P04-S21]]'
  - '[[2026-06-09-firmware-wording-review-P04-S22]]'
  - '[[2026-06-09-firmware-wording-review-P04-S23]]'
  - '[[2026-06-09-firmware-wording-review-P04-S24]]'
  - '[[2026-06-09-firmware-wording-review-P04-S25]]'
  - '[[2026-06-09-firmware-wording-review-P04-S26]]'
  - '[[2026-06-09-firmware-wording-review-P04-summary]]'
  - '[[2026-06-09-firmware-wording-review-P05-S27]]'
  - '[[2026-06-09-firmware-wording-review-P05-S28]]'
  - '[[2026-06-09-firmware-wording-review-P05-S29]]'
  - '[[2026-06-09-firmware-wording-review-P05-S30]]'
  - '[[2026-06-09-firmware-wording-review-P05-S31]]'
  - '[[2026-06-09-firmware-wording-review-P05-S32]]'
  - '[[2026-06-09-firmware-wording-review-P05-S33]]'
  - '[[2026-06-09-firmware-wording-review-P05-S34]]'
  - '[[2026-06-09-firmware-wording-review-P05-S35]]'
  - '[[2026-06-09-firmware-wording-review-P05-S36]]'
  - '[[2026-06-09-firmware-wording-review-adr]]'
  - '[[2026-06-09-firmware-wording-review-plan]]'
  - '[[2026-06-09-firmware-wording-review-research]]'
---

# `firmware-wording-review` feature index

Auto-generated index of all documents tagged with `#firmware-wording-review`.

## Documents

### adr

- `2026-06-09-firmware-wording-review-adr` - `firmware-wording-review` adr: `firmware reconciliation decisions` | (**status:** `accepted`)

### exec

- `2026-06-09-firmware-wording-review-P01-S01` - replace the phantom vaultspec-write-plan skill name with vaultspec-write in the pipeline table at line 25 and the intent table at line 68 (D1)
- `2026-06-09-firmware-wording-review-P01-S02` - replace the phantom vaultspec-write-plan skill name with vaultspec-write in the skill catalog at line 35 (D1)
- `2026-06-09-firmware-wording-review-P01-S03` - replace the phantom vaultspec-write-plan skill name with vaultspec-write in the pipeline cross-reference at line 24 (D1)
- `2026-06-09-firmware-wording-review-P01-S04` - correct the Verify-phase artifact cell from the exec review path to the canonical audit address .vault/audit/yyyy-mm-dd-feature-audit.md (D2)
- `2026-06-09-firmware-wording-review-P01-S05` - document the optional narrative-infix audit filename yyyy-mm-dd-feature-topic-audit.md as the disambiguator for features with multiple audits (D2)
- `2026-06-09-firmware-wording-review-P01-S06` - add the missing Audit node to the Documentation Hierarchy so the ADR and Plan depends-on-audits links resolve (D2)
- `2026-06-09-firmware-wording-review-P01-S07` - retire the undocumented code-review-audit double suffix at lines 28 and 48 in favor of the canonical audit address with optional narrative infix (D2)
- `2026-06-09-firmware-wording-review-P01-S08` - retire the undocumented code-review-audit double suffix at line 87 in favor of the canonical audit address with optional narrative infix (D2)
- `2026-06-09-firmware-wording-review-P01-S09` - confirm the hardcoded audit directory tag stands and the template remains the review-flavored audit body living under .vault/audit/ (D2)
- `2026-06-09-firmware-wording-review-P01-S10` - replace the asserted team dispatch tools infrastructure claim at line 82 with hedged coordinated-through-the-host-environment wording (D12)
- `2026-06-09-firmware-wording-review-P01-summary` - `firmware-wording-review` `P01` summary
- `2026-06-09-firmware-wording-review-P02-S11` - shorten the rule per its own Status clause now that archive dry-run, the paired unarchive verb, and exit-1 on nonexistent tags have landed, replacing the version anchor with a dated verification note (D5)
- `2026-06-09-firmware-wording-review-P02-S12` - shorten the rule per its own Status clause, dropping the stale 0.1.19 claims, the empty-upgrade-preview example, and the silent-no-op claim, replacing the version anchor with a dated verification note (D5)
- `2026-06-09-firmware-wording-review-P02-S13` - live-confirm plan body-prose preservation by running structural plan verbs against a scratch plan document carrying authored prose sections (D5)
- `2026-06-09-firmware-wording-review-P02-S14` - shorten the rule per its own Status clause only after the live prose-preservation confirmation passes, replacing the ordering procedure with a pointer at the preserved-prose behavior (D5)
- `2026-06-09-firmware-wording-review-P02-summary` - `firmware-wording-review` `P02` summary
- `2026-06-09-firmware-wording-review-P03-S15` - add the missing vault add flags --tier, --step, --all-steps, and --no-hints to the vault add section (D6)
- `2026-06-09-firmware-wording-review-P03-S16` - document vault feature archive --dry-run and --no-hints and add a vault feature unarchive prose section (D6)
- `2026-06-09-firmware-wording-review-P03-S17` - append rename-integrity to the vault check prose checker list (D6)
- `2026-06-09-firmware-wording-review-P03-S18` - add the plan-verb --phase, --wave, --dry-run, and --canonicalise flags to the plan subcommand sections (D6)
- `2026-06-09-firmware-wording-review-P03-S19` - add a sync output-vocabulary section matching the verified description in the CLI rule (D6)
- `2026-06-09-firmware-wording-review-P03-summary` - `firmware-wording-review` `P03` summary
- `2026-06-09-firmware-wording-review-P04-S20` - rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4)
- `2026-06-09-firmware-wording-review-P04-S21` - rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4)
- `2026-06-09-firmware-wording-review-P04-S22` - rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4)
- `2026-06-09-firmware-wording-review-P04-S23` - rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4)
- `2026-06-09-firmware-wording-review-P04-S24` - rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4)
- `2026-06-09-firmware-wording-review-P04-S25` - rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4)
- `2026-06-09-firmware-wording-review-P04-S26` - qualify the absolute hand-writing mandate at line 14 to match the allowed-manual-edits section it currently contradicts (D4)
- `2026-06-09-firmware-wording-review-P04-summary` - `firmware-wording-review` `P04` summary
- `2026-06-09-firmware-wording-review-P05-S27` - reword the persistence mandate to return findings to the dispatching orchestrator, which persists via vault add scaffold plus body-prose edit, keeping the persona read-only (D3)
- `2026-06-09-firmware-wording-review-P05-S28` - reword the persistence mandate to return findings to the dispatching orchestrator, which persists via vault add scaffold plus body-prose edit, keeping the persona read-only (D3)
- `2026-06-09-firmware-wording-review-P05-S29` - reword the persistence mandate to return findings to the dispatching orchestrator, which persists via vault add scaffold plus body-prose edit, keeping the persona read-only (D3)
- `2026-06-09-firmware-wording-review-P05-S30` - document once in the agents section the mode field semantics: declared file-mutation intent via harness tools, with the Bash caveat acknowledged (D3)
- `2026-06-09-firmware-wording-review-P05-S31` - note the Bash-only mutation path via gh and git as deliberate for this read-write persona without Write or Edit tools (D3)
- `2026-06-09-firmware-wording-review-P05-S32` - rewrite the verbatim high-tier mission statement at lines 10-12 into a tier-appropriate mission of simplicity, pattern-following, and minimal blast radius (D9)
- `2026-06-09-firmware-wording-review-P05-S33` - add the mandatory Critical Requirement code-review section that the standard and high executors carry (D9)
- `2026-06-09-firmware-wording-review-P05-S34` - run the code-binding check for tier MEDIUM frontmatter consumption in Python loaders and tests before any enum value change (D9)
- `2026-06-09-firmware-wording-review-P05-S35` - rename the medium-tier description wording to standard and move the frontmatter tier MEDIUM to STANDARD if the code-binding check clears (D9)
- `2026-06-09-firmware-wording-review-P05-S36` - move the frontmatter tier MEDIUM to STANDARD if the code-binding check clears (D9)

### plan

- `2026-06-09-firmware-wording-review-plan` - `firmware-wording-review` `firmware reconciliation` plan

### research

- `2026-06-09-firmware-wording-review-research` - `firmware-wording-review` research: `md firmware wording and consistency review`
