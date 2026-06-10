---
tags:
  - '#plan'
  - '#firmware-wording-review'
date: '2026-06-09'
tier: L2
related:
  - '[[2026-06-09-firmware-wording-review-adr]]'
  - '[[2026-06-09-firmware-wording-review-research]]'
---

# `firmware-wording-review` `firmware reconciliation` plan

Reconcile all 98 findings of the 2026-06-09 firmware wording review to closure by implementing decisions D1 through D16 of the accepted ADR across the markdown firmware.

## Description

The firmware wording review surfaced 98 raw findings across the 46 markdown firmware files under `src/vaultspec_core/builtins/`: three critical contradictions (the phantom `vaultspec-write-plan` skill name, three competing Verify-artifact addresses, unfulfillable persistence mandates on read-only personas), a band of sharp inconsistencies (hand-authoring instructions the CLI rule forbids, discipline rules stale against the 0.1.26 CLI, a lagging bundled CLI reference, orphaned firmware members, an incoherent executor trio, template placeholder leaks), and a long tail of style and typo defects. The accepted ADR records sixteen decisions, one per finding theme; this plan maps every concrete finding item to exactly one Step, and every Step action names the decision it implements so findings trace from research theme through ADR decision to Step.

All edits land in the canonical source tree under `src/vaultspec_core/builtins/` and propagate via sync and upgrade in Phase P09; the deployed mirror under `.vaultspec/rules/` is never edited directly. The feature is documentation-only by intent: the two rename-class decisions (the `tier: MEDIUM` frontmatter enum and the `ref-audit.md` template filename) are gated by explicit code-binding check Steps (P05.S34, P06.S49), and any Python work those checks surface is logged as a follow-up issue in P09 rather than executed inside this plan. The plan-editing discipline rule is shortened only after the live prose-preservation confirmation in P02.S13 passes.

Agent assignment: `vaultspec-standard-executor` executes the bulk prose, reference, template, and sweep Steps (P01, P03, P04, P06, P07, P08); `vaultspec-high-executor` executes the discipline-rule shortening and code-binding check Steps (P02, P05.S34, P06.S49) and the persona-contract Steps in P05; `vaultspec-code-reviewer` gates the P09 close-out before the feature is declared complete.

## Steps

### Phase `P01` - critical decision propagation

Land the three behavior-affecting decisions (D1 plan-skill name, D2 verify-artifact address, D12 team-dispatch wording) so every later phase edits against a coherent baseline.

- [x] `P01.S01` - replace the phantom vaultspec-write-plan skill name with vaultspec-write in the pipeline table at line 25 and the intent table at line 68 (D1); `src/vaultspec_core/builtins/system/03-vaultspec.md`.
- [x] `P01.S02` - replace the phantom vaultspec-write-plan skill name with vaultspec-write in the skill catalog at line 35 (D1); `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.
- [x] `P01.S03` - replace the phantom vaultspec-write-plan skill name with vaultspec-write in the pipeline cross-reference at line 24 (D1); `src/vaultspec_core/builtins/skills/vaultspec-code-research/SKILL.md`.
- [x] `P01.S04` - correct the Verify-phase artifact cell from the exec review path to the canonical audit address .vault/audit/yyyy-mm-dd-feature-audit.md (D2); `src/vaultspec_core/builtins/system/03-vaultspec.md`.
- [x] `P01.S05` - document the optional narrative-infix audit filename yyyy-mm-dd-feature-topic-audit.md as the disambiguator for features with multiple audits (D2); `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.
- [x] `P01.S06` - add the missing Audit node to the Documentation Hierarchy so the ADR and Plan depends-on-audits links resolve (D2); `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.
- [x] `P01.S07` - retire the undocumented code-review-audit double suffix at lines 28 and 48 in favor of the canonical audit address with optional narrative infix (D2); `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md`.
- [x] `P01.S08` - retire the undocumented code-review-audit double suffix at line 87 in favor of the canonical audit address with optional narrative infix (D2); `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md`.
- [x] `P01.S09` - confirm the hardcoded audit directory tag stands and the template remains the review-flavored audit body living under .vault/audit/ (D2); `src/vaultspec_core/builtins/templates/code-review.md`.
- [x] `P01.S10` - replace the asserted team dispatch tools infrastructure claim at line 82 with hedged coordinated-through-the-host-environment wording (D12); `src/vaultspec_core/builtins/system/03-vaultspec.md`.

### Phase `P02` - discipline rule refresh

Shorten the three audit-derived discipline rules per their own Status clauses now that the 0.1.26 CLI has closed the gaps they guarded (D5).

- [x] `P02.S11` - shorten the rule per its own Status clause now that archive dry-run, the paired unarchive verb, and exit-1 on nonexistent tags have landed, replacing the version anchor with a dated verification note (D5); `src/vaultspec_core/builtins/rules/vaultspec-archive-discipline.builtin.md`.
- [x] `P02.S12` - shorten the rule per its own Status clause, dropping the stale 0.1.19 claims, the empty-upgrade-preview example, and the silent-no-op claim, replacing the version anchor with a dated verification note (D5); `src/vaultspec_core/builtins/rules/vaultspec-dry-run-discipline.builtin.md`.
- [x] `P02.S13` - live-confirm plan body-prose preservation by running structural plan verbs against a scratch plan document carrying authored prose sections (D5); `src/vaultspec_core/builtins/rules/vaultspec-plan-editing-discipline.builtin.md`.
- [x] `P02.S14` - shorten the rule per its own Status clause only after the live prose-preservation confirmation passes, replacing the ordering procedure with a pointer at the preserved-prose behavior (D5); `src/vaultspec_core/builtins/rules/vaultspec-plan-editing-discipline.builtin.md`.

### Phase `P03` - bundled CLI reference update

Hand-update the machine-facing CLI reference to the live 0.1.26 surface so sibling rules stop depending on undocumented flags (D6).

- [x] `P03.S15` - add the missing vault add flags --tier, --step, --all-steps, and --no-hints to the vault add section (D6); `src/vaultspec_core/builtins/reference/cli.md`.
- [x] `P03.S16` - document vault feature archive --dry-run and --no-hints and add a vault feature unarchive prose section (D6); `src/vaultspec_core/builtins/reference/cli.md`.
- [x] `P03.S17` - append rename-integrity to the vault check prose checker list (D6); `src/vaultspec_core/builtins/reference/cli.md`.
- [x] `P03.S18` - add the plan-verb --phase, --wave, --dry-run, and --canonicalise flags to the plan subcommand sections (D6); `src/vaultspec_core/builtins/reference/cli.md`.
- [x] `P03.S19` - add a sync output-vocabulary section matching the verified description in the CLI rule (D6); `src/vaultspec_core/builtins/reference/cli.md`.

### Phase `P04` - skills authoring path

Rewrite every artifact-producing skill around the vault add scaffold-then-edit-prose path and reconcile the CLI rule's internal contradiction (D4).

- [x] `P04.S20` - rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4); `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`.
- [x] `P04.S21` - rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4); `src/vaultspec_core/builtins/skills/vaultspec-research/SKILL.md`.
- [x] `P04.S22` - rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4); `src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md`.
- [x] `P04.S23` - rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4); `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md`.
- [x] `P04.S24` - rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4); `src/vaultspec_core/builtins/skills/vaultspec-code-research/SKILL.md`.
- [x] `P04.S25` - rewrite the persistence steps to scaffold via vaultspec-core vault add then edit body prose, removing the hand-authored frontmatter instruction (D4); `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`.
- [x] `P04.S26` - qualify the absolute hand-writing Mandate at line 14 to match the Allowed-manual-edits section it currently contradicts (D4); `src/vaultspec_core/builtins/rules/vaultspec-cli.builtin.md`.

### Phase `P05` - persona contracts

Reconcile persona persistence mandates, the executor trio, ADR authorship, and the curate contract so each persona's declared mode matches its body (D3, D9, D10, D11).

- [x] `P05.S27` - reword the persistence mandate to return findings to the dispatching orchestrator, which persists via vault add scaffold plus body-prose edit, keeping the persona read-only (D3); `src/vaultspec_core/builtins/agents/vaultspec-code-reviewer.md`.
- [x] `P05.S28` - reword the persistence mandate to return findings to the dispatching orchestrator, which persists via vault add scaffold plus body-prose edit, keeping the persona read-only (D3); `src/vaultspec_core/builtins/agents/vaultspec-adr-researcher.md`.
- [x] `P05.S29` - reword the persistence mandate to return findings to the dispatching orchestrator, which persists via vault add scaffold plus body-prose edit, keeping the persona read-only (D3); `src/vaultspec_core/builtins/agents/vaultspec-reference-auditor.md`.
- [x] `P05.S30` - document once in the agents section the mode field semantics: declared file-mutation intent via harness tools, with the Bash caveat acknowledged (D3); `src/vaultspec_core/builtins/system/03-vaultspec.md`.
- [x] `P05.S31` - note the Bash-only mutation path via gh and git as deliberate for this read-write persona without Write or Edit tools (D3); `src/vaultspec_core/builtins/agents/vaultspec-project-coordinator.md`.
- [x] `P05.S32` - rewrite the verbatim high-tier mission statement at lines 10-12 into a tier-appropriate mission of simplicity, pattern-following, and minimal blast radius (D9); `src/vaultspec_core/builtins/agents/vaultspec-low-executor.md`.
- [x] `P05.S33` - add the mandatory Critical Requirement code-review section that the standard and high executors carry (D9); `src/vaultspec_core/builtins/agents/vaultspec-low-executor.md`.
- [x] `P05.S34` - run the code-binding check for tier MEDIUM frontmatter consumption in Python loaders and tests before any enum value change (D9); `src/vaultspec_core`.
- [x] `P05.S35` - rename the medium-tier description wording to standard and move the frontmatter tier MEDIUM to STANDARD if the code-binding check clears (D9); `src/vaultspec_core/builtins/agents/vaultspec-standard-executor.md`.
- [x] `P05.S36` - move the frontmatter tier MEDIUM to STANDARD if the code-binding check clears (D9); `src/vaultspec_core/builtins/agents/vaultspec-codifier.md`.
- [x] `P05.S37` - move the frontmatter tier MEDIUM to STANDARD if the code-binding check clears (D9); `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`.
- [x] `P05.S38` - move the frontmatter tier MEDIUM to STANDARD if the code-binding check clears (D9); `src/vaultspec_core/builtins/agents/vaultspec-reference-auditor.md`.
- [x] `P05.S39` - move the frontmatter tier MEDIUM to STANDARD if the code-binding check clears (D9); `src/vaultspec_core/builtins/agents/vaultspec-project-coordinator.md`.
- [x] `P05.S40` - move the frontmatter tier MEDIUM to STANDARD if the code-binding check clears (D9); `src/vaultspec_core/builtins/agents/vaultspec-researcher.md`.
- [x] `P05.S41` - add the low executor to the Step routing table so low-tier Steps gain a routing target (D9); `src/vaultspec_core/builtins/agents/vaultspec-writer.md`.
- [x] `P05.S42` - align the Documentation section to the trio-parallel form referencing the exec-step.md template (D9); `src/vaultspec_core/builtins/agents/vaultspec-low-executor.md`.
- [x] `P05.S43` - align the Documentation section to the trio-parallel form referencing the exec-step.md template (D9); `src/vaultspec_core/builtins/agents/vaultspec-standard-executor.md`.
- [x] `P05.S44` - align the Documentation section to the trio-parallel form referencing the exec-step.md template (D9); `src/vaultspec_core/builtins/agents/vaultspec-high-executor.md`.
- [x] `P05.S45` - transfer ADR authorship to this persona by amending the context-enhancer-only restriction to match its own formalizes-decisions description (D10); `src/vaultspec_core/builtins/agents/vaultspec-adr-researcher.md`.
- [x] `P05.S46` - swap the named drafting persona from vaultspec-writer to vaultspec-adr-researcher, leaving the writer mandate plan-only (D10); `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`.
- [x] `P05.S47` - reconcile the curator contract to the persona delegate model: orchestrate fixes through loaded personas rather than editing in-place (D11); `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`.
- [x] `P05.S48` - add the audit-report persistence obligation that the curate skill already promises (D11); `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`.

### Phase `P06` - orphan wiring

Wire the orphaned template, personas, and skills into the catalogs and unify the reference doc-type noun (D7, D8).

- [x] `P06.S49` - run the code-binding check for the ref-audit.md template filename across Python loaders, provider sync mappings, and tests (D7); `src/vaultspec_core`.
- [x] `P06.S50` - rename the template file to reference.md if the code-binding check shows the name unbound or trivially remappable, otherwise keep the filename and unify prose only (D7); `src/vaultspec_core/builtins/templates/ref-audit.md`.
- [x] `P06.S51` - unify the reference noun across the hierarchy node, the pipeline phase wording, and the directory-table description (D7); `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.
- [x] `P06.S52` - add the template mandate, the standard frontmatter-and-tagging mandate, and an explicit pointer to the vaultspec-reference-auditor persona (D8); `src/vaultspec_core/builtins/skills/vaultspec-code-research/SKILL.md`.
- [x] `P06.S53` - name the vaultspec-researcher persona as the generic persona for multi-researcher coordination (D8); `src/vaultspec_core/builtins/skills/vaultspec-research/SKILL.md`.
- [x] `P06.S54` - add vaultspec-team and vaultspec-projectmanager to the supporting-skills table (D8); `src/vaultspec_core/builtins/system/03-vaultspec.md`.
- [x] `P06.S55` - add vaultspec-team, vaultspec-projectmanager, vaultspec-code-review, and vaultspec-curate to the skill catalog, closing the catalog gaps (D8); `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.
- [x] `P06.S56` - replace the body-text Related lines instruction in the snapshot template with frontmatter related guidance (D8); `src/vaultspec_core/builtins/agents/vaultspec-reference-auditor.md`.
- [x] `P06.S57` - remove the mention of the retired safety auditors persona (D8); `src/vaultspec_core/builtins/agents/vaultspec-reference-auditor.md`.

### Phase `P07` - template sweep

Fix every template placeholder leak against the documented placeholder conventions and document the machine-filled placeholder class (D14).

- [x] `P07.S58` - replace the unquoted angle-bracket tier placeholder with a quoted curly-brace placeholder (D14); `src/vaultspec_core/builtins/templates/plan.md`.
- [x] `P07.S59` - drop the stale phase segment from the H1 heading, a fossil of the one-plan-per-phase model (D14); `src/vaultspec_core/builtins/templates/plan.md`.
- [x] `P07.S60` - update the plan heading example to the phase-less H1 form (D14); `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.
- [x] `P07.S61` - retier the wave-assuming verification hint at line 173 so it holds at every tier (D14); `src/vaultspec_core/builtins/templates/plan.md`.
- [x] `P07.S62` - lowercase the Title Case H1 to match the all-lowercase heading convention every sibling follows (D14); `src/vaultspec_core/builtins/templates/code-review.md`.
- [x] `P07.S63` - move the uppercase TOPIC, LEVEL, Summary, and DESCRIPTION placeholders into comments using convention-compliant names (D14); `src/vaultspec_core/builtins/templates/code-review.md`.
- [x] `P07.S64` - annotate the heading, scope_block, step_id, and plan_stem placeholders as machine-filled (D14); `src/vaultspec_core/builtins/templates/exec-step.md`.
- [x] `P07.S65` - move the instructional boilerplate and the file1 and file2 placeholders inside comment blocks so sanitize strips them (D14); `src/vaultspec_core/builtins/templates/exec-summary.md`.
- [x] `P07.S66` - seed the related field instead of the empty list that violates the always-populate hint the template itself states (D14); `src/vaultspec_core/builtins/templates/audit.md`.
- [x] `P07.S67` - add proposed to the status enum and note the status convention in the frontmatter hint (D14); `src/vaultspec_core/builtins/templates/adr.md`.
- [x] `P07.S68` - document the generated frontmatter field the template declares (D14); `src/vaultspec_core/builtins/templates/index.md`.
- [x] `P07.S69` - document the machine-filled placeholder class (heading, step_id, plan_stem, scope_block, document_list) as a named class in the placeholder conventions (D14); `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.
- [x] `P07.S70` - align the documented date-quoting example with the quoted form the templates use (D14); `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.
- [x] `P07.S71` - lowercase the uppercase YYYY-MM-DD in the hint block and reword the garbled DO-NOT-add-frontmatter-fields-outside-the-frontmatter hint (D14); `src/vaultspec_core/builtins/templates/adr.md`.
- [x] `P07.S72` - lowercase the uppercase YYYY-MM-DD in the hint block and reword the garbled DO-NOT-add-frontmatter-fields-outside-the-frontmatter hint (D14); `src/vaultspec_core/builtins/templates/audit.md`.
- [x] `P07.S73` - lowercase the uppercase YYYY-MM-DD in the hint block and reword the garbled DO-NOT-add-frontmatter-fields-outside-the-frontmatter hint (D14); `src/vaultspec_core/builtins/templates/code-review.md`.
- [x] `P07.S74` - lowercase the uppercase YYYY-MM-DD in the hint block and reword the garbled DO-NOT-add-frontmatter-fields-outside-the-frontmatter hint (D14); `src/vaultspec_core/builtins/templates/exec-step.md`.
- [x] `P07.S75` - lowercase the uppercase YYYY-MM-DD in the hint block and reword the garbled DO-NOT-add-frontmatter-fields-outside-the-frontmatter hint (D14); `src/vaultspec_core/builtins/templates/exec-summary.md`.
- [x] `P07.S76` - lowercase the uppercase YYYY-MM-DD in the hint block and reword the garbled DO-NOT-add-frontmatter-fields-outside-the-frontmatter hint (D14); `src/vaultspec_core/builtins/templates/plan.md`.
- [x] `P07.S77` - lowercase the uppercase YYYY-MM-DD in the hint block and reword the garbled DO-NOT-add-frontmatter-fields-outside-the-frontmatter hint (D14); `src/vaultspec_core/builtins/templates/ref-audit.md`.
- [x] `P07.S78` - lowercase the uppercase YYYY-MM-DD in the hint block and reword the garbled DO-NOT-add-frontmatter-fields-outside-the-frontmatter hint (D14); `src/vaultspec_core/builtins/templates/research.md`.

### Phase `P08` - style and typo sweep

Apply the single style pass (spelling locale, dash convention, label form, announce lines, tag examples) and correct every typo in the research inventory; unify the codify trio (D13, D15).

- [x] `P08.S79` - fix the fundations and considere-null-and-void typos and supply the missing conjunction at line 20 (D15); `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`.
- [x] `P08.S80` - fix the agent personaa typo (D15); `src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md`.
- [x] `P08.S81` - fix the continously typo and repair the garbled rolling-log-of-task-queue phrase (D15); `src/vaultspec_core/builtins/skills/vaultspec-code-review/SKILL.md`.
- [x] `P08.S82` - repair the grammatically broken description fragment (D15); `src/vaultspec_core/builtins/skills/vaultspec-research/SKILL.md`.
- [x] `P08.S83` - fix the constrainst, condense-but-clear, and descision typos (D15); `src/vaultspec_core/builtins/templates/adr.md`.
- [x] `P08.S84` - fix the Succint, twice-occurring failiures, and Scafolds typos and the stray punctuation (D15); `src/vaultspec_core/builtins/templates/exec-step.md`.
- [x] `P08.S85` - fix the Use-Concise-and-Direct label fragment, the i.e.-where-e.g.-is-meant misuse, and the bullet punctuation drift (D15); `src/vaultspec_core/builtins/system/02-operations.md`.
- [x] `P08.S86` - normalize the three bold-label conventions to the single Label-colon-sentence mandate form (D15); `src/vaultspec_core/builtins/system/01-core.md`.
- [x] `P08.S87` - replace the project-bondedness neologism with project-bound, repair the verb-less back-pointer sentence, and order the tool list (D15); `src/vaultspec_core/builtins/agents/vaultspec-codifier.md`.
- [x] `P08.S88` - replace the British spellings serialiser, behaviour, and centre with American forms (D15); `src/vaultspec_core/builtins/rules/vaultspec-plan-editing-discipline.builtin.md`.
- [x] `P08.S89` - replace the British spellings with American forms (D15); `src/vaultspec_core/builtins/rules/vaultspec-codify.builtin.md`.
- [x] `P08.S90` - replace the British spellings with American forms (D15); `src/vaultspec_core/builtins/skills/vaultspec-codify/SKILL.md`.
- [x] `P08.S91` - replace the British spellings with American forms (D15); `src/vaultspec_core/builtins/agents/vaultspec-codifier.md`.
- [x] `P08.S92` - replace em dashes with spaced hyphens (D15); `src/vaultspec_core/builtins/reference/cli.md`.
- [x] `P08.S93` - replace em dashes with spaced hyphens (D15); `src/vaultspec_core/builtins/rules/vaultspec-archive-discipline.builtin.md`.
- [x] `P08.S94` - replace em dashes with spaced hyphens (D15); `src/vaultspec_core/builtins/rules/vaultspec-codify.builtin.md`.
- [x] `P08.S95` - replace em dashes with spaced hyphens (D15); `src/vaultspec_core/builtins/rules/vaultspec-plan-editing-discipline.builtin.md`.
- [x] `P08.S96` - add the canonical announce line the skill lacks (D15); `src/vaultspec_core/builtins/skills/vaultspec-execute/SKILL.md`.
- [x] `P08.S97` - add the canonical announce line the skill lacks (D15); `src/vaultspec_core/builtins/skills/vaultspec-team/SKILL.md`.
- [x] `P08.S98` - normalize the divergent announce line to the canonical form (D15); `src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md`.
- [x] `P08.S99` - replace the literal hash-feature tag example with the hash-curly-feature convention placeholder (D15); `src/vaultspec_core/builtins/skills/vaultspec-adr/SKILL.md`.
- [x] `P08.S100` - replace the literal hash-feature tag example with the hash-curly-feature convention placeholder (D15); `src/vaultspec_core/builtins/skills/vaultspec-research/SKILL.md`.
- [x] `P08.S101` - replace the literal hash-feature tag example with the hash-curly-feature convention placeholder (D15); `src/vaultspec_core/builtins/skills/vaultspec-write/SKILL.md`.
- [x] `P08.S102` - replace the literal hash-feature tag example with the hash-curly-feature convention placeholder (D15); `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`.
- [x] `P08.S103` - replace the literal hash-feature tag example with the hash-curly-feature convention placeholder (D15); `src/vaultspec_core/builtins/skills/vaultspec-execute/SKILL.md`.
- [ ] `P08.S104` - drop the fragile Second-worked-example ordinal (D15); `src/vaultspec_core/builtins/rules/vaultspec-plan-editing-discipline.builtin.md`.
- [ ] `P08.S105` - drop the fragile Third-worked-example ordinal (D15); `src/vaultspec_core/builtins/rules/vaultspec-dry-run-discipline.builtin.md`.
- [ ] `P08.S106` - convert the numbered procedural lists to bullets per the operations fragment mandate (D15); `src/vaultspec_core/builtins/rules/vaultspec-dry-run-discipline.builtin.md`.
- [ ] `P08.S107` - convert the numbered procedural lists to bullets per the operations fragment mandate (D15); `src/vaultspec_core/builtins/rules/vaultspec-plan-editing-discipline.builtin.md`.
- [ ] `P08.S108` - remove the orphan end-conventions comment marker at line 88 (D15); `src/vaultspec_core/builtins/system/03-vaultspec.md`.
- [ ] `P08.S109` - fix the doubled the-dot-vault-vault phrasing (D15); `src/vaultspec_core/builtins/skills/vaultspec-curate/SKILL.md`.
- [ ] `P08.S110` - fix the doubled the-dot-vault-vault phrasing in the description (D15); `src/vaultspec_core/builtins/agents/vaultspec-docs-curator.md`.
- [ ] `P08.S111` - replace the host-specific read_file tool id with provider-neutral wording (D15); `src/vaultspec_core/builtins/agents/vaultspec-writer.md`.
- [ ] `P08.S112` - unify the Execution Records versus Execution Logs naming for the one artifact (D15); `src/vaultspec_core/builtins/rules/vaultspec.builtin.md`.
- [ ] `P08.S113` - align the execution-log artifact phrasing with the canonical Execution Records noun (D15); `src/vaultspec_core/builtins/system/03-vaultspec.md`.
- [ ] `P08.S114` - unify the supersession procedure on a Status section naming the successor followed by spec rules remove, and add the no-first-encounter execution-cycle guard the persona and skill already state (D13); `src/vaultspec_core/builtins/rules/vaultspec-codify.builtin.md`.
- [ ] `P08.S115` - align the supersession mechanics with the unified Status-section procedure (D13); `src/vaultspec_core/builtins/skills/vaultspec-codify/SKILL.md`.
- [ ] `P08.S116` - align the supersession mechanics with the unified Status-section procedure (D13); `src/vaultspec_core/builtins/agents/vaultspec-codifier.md`.
- [ ] `P08.S117` - add the shared persona frontmatter schema the eleven top-level personas carry (D15); `src/vaultspec_core/builtins/skills/vaultspec-documentation/agents/wireframe-agent.md`.
- [ ] `P08.S118` - add the shared persona frontmatter schema the eleven top-level personas carry (D15); `src/vaultspec_core/builtins/skills/vaultspec-documentation/agents/editorial-reviewer.md`.
- [ ] `P08.S119` - remove the duplicated mandatory-read instruction and convert square-bracket placeholders to the curly-brace convention (D15); `src/vaultspec_core/builtins/skills/vaultspec-documentation/agents/wireframe-agent.md`.
- [ ] `P08.S120` - reword the Start-with-Phase instruction so it holds at L1 where only Steps exist (D15); `src/vaultspec_core/builtins/skills/vaultspec-execute/SKILL.md`.

### Phase `P09` - propagation and verification

Propagate source edits to the deployed mirror, close out health checks and tests, and log follow-up issues for deferred items (D16).

- [ ] `P09.S121` - run vaultspec-core sync to propagate the source edits to every provider surface (D16); `src/vaultspec_core/builtins`.
- [ ] `P09.S122` - run vaultspec-core install --upgrade to clear the three-file reflow drift in the deployed mirror (D16); `.vaultspec/rules`.
- [ ] `P09.S123` - run vault check all and spec doctor and confirm both report green (D16); `.vault`.
- [ ] `P09.S124` - run the full test suite via uv run --no-sync pytest and the prek hooks on modified files, confirming green (D16); `tests`.
- [ ] `P09.S125` - log a follow-up issue for automated regeneration of the bundled CLI reference from the live Typer surface (D16); `src/vaultspec_core/builtins/reference/cli.md`.
- [ ] `P09.S126` - log follow-up issues for any Python work surfaced by the tier-enum and template-filename code-binding checks (D16); `src/vaultspec_core`.

## Parallelization

- Phase P01 carries hard ordering before every later Phase: it lands the naming and address decisions all subsequent edits assume.
- Phases P02 and P03 are mutually independent and may run in parallel with each other and with the P04 to P06 sequence once P01 closes.
- Phases P04, P05, and P06 share skill and persona files (`skills/vaultspec-adr/SKILL.md`, `skills/vaultspec-code-research/SKILL.md`, `skills/vaultspec-curate/SKILL.md`, `agents/vaultspec-docs-curator.md`, `agents/vaultspec-reference-auditor.md` among others) and execute sequentially relative to each other.
- Phases P07 and P08 run after P01 through P06 so the sweeps do not race the substantive rewrites of the same files; P07 and P08 share template files and run sequentially relative to each other.
- Phase P09 is strictly last: propagation, health checks, tests, and follow-up logging close the feature.
- Within a Phase, Steps that target distinct files may be dispatched to parallel executor agents; Steps that target the same file execute in row order. The code-binding check Steps gate their dependents: P05.S34 precedes P05.S35 through P05.S40, P06.S49 precedes P06.S50, and P02.S13 precedes P02.S14.

## Verification

- Every Step row in every Phase is closed (`- [x]`) and `vaultspec-core vault plan check` reports no violations on this plan document.
- A search for the phantom skill name vaultspec-write-plan across `src/vaultspec_core/builtins/` returns zero matches (D1).
- Exactly one Verify-artifact address (the canonical audit path with optional narrative infix) appears across the five surfaces the research enumerated, and the Documentation Hierarchy carries an Audit node (D2).
- No persona body mandates persisting a file it lacks the tools to write; the three read-only personas return findings to the dispatching orchestrator (D3).
- Every artifact-producing skill scaffolds via the vault add verb; no skill instructs hand-written frontmatter (D4).
- The three discipline rules contain no claims contradicted by the live 0.1.26 CLI, and each carries a dated verification note in place of a version pin (D5).
- `src/vaultspec_core/builtins/reference/cli.md` documents every flag the sibling rules reference (D6).
- No firmware member is orphaned: the code-research skill names its template and persona, the researcher persona and the team and projectmanager skills appear in the catalogs (D7, D8).
- The executor trio reads coherently: tier-appropriate low-executor mission, mandatory code review on all three, one middle-tier name, a routing target for every tier (D9).
- A grep across `src/vaultspec_core/builtins/` finds no em dash, no British spelling from the research inventory, no literal hash-feature tag example, and none of the inventoried typos (D14, D15).
- `vaultspec-core sync` and `vaultspec-core install --upgrade` complete with no failed items; a subsequent `install --upgrade --dry-run` previews zero pending updates (D16).
- `vaultspec-core vault check all` and `vaultspec-core spec doctor` exit green; the full test suite via `uv run --no-sync pytest` and the prek hooks on modified files pass (D16).
- Follow-up issues exist for the automated CLI-reference regeneration and for any Python work the code-binding checks surfaced (D16).
- `vaultspec-code-reviewer` signs off the completed change set before the feature is declared closed.
