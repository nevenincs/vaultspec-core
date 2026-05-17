---
tags:
  - '#plan'
  - '#cli-simplification-ux'
date: '2026-05-17'
tier: L4
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
  - '[[2026-05-17-cli-simplification-ux-research]]'
  - '[[2026-05-17-cli-memory-lifecycle-adr]]'
  - '[[2026-05-17-cli-spec-gitignore-adr]]'
  - '[[2026-05-17-cli-sync-vocabulary-adr]]'
  - '[[2026-05-17-cli-scaffolder-integrity-adr]]'
  - '[[2026-05-17-cli-plan-body-preservation-adr]]'
  - '[[2026-05-17-cli-exec-step-records-adr]]'
  - '[[2026-05-17-cli-spec-edit-safety-adr]]'
  - '[[2026-05-17-cli-rename-integrity-adr]]'
  - '[[2026-05-17-cli-spec-crud-parity-adr]]'
  - '[[2026-05-17-cli-next-step-hints-adr]]'
  - '[[2026-05-17-cli-blast-radius-gating-adr]]'
  - '[[2026-05-17-cli-json-consistency-adr]]'
  - '[[2026-05-17-cli-surface-consolidation-adr]]'
  - '[[2026-05-17-cli-paper-cuts-adr]]'
---


# `cli-simplification-ux` `CLI simplification and UX hardening epic` plan

## Epic intent

Convert the rolling CLI UX audit's fourteen finding clusters into a coherent set of architectural, code, and language changes that restore the CLI's design integrity for production use. Tracking issue: GitHub #113. Project-management association: pull request #114 on branch claude/simplify-vaultspec-cli-wHR3K. The fourteen sibling ADRs under feature tags cli-memory-lifecycle, cli-spec-gitignore, cli-sync-vocabulary, cli-scaffolder-integrity, cli-plan-body-preservation, cli-exec-step-records, cli-spec-edit-safety, cli-rename-integrity, cli-spec-crud-parity, cli-next-step-hints, cli-blast-radius-gating, cli-json-consistency, cli-surface-consolidation, and cli-paper-cuts are the decision substrate this plan executes. Timeline: rolling, with foundation waves landing before downstream waves. Teams: framework maintainers and downstream agent consumers.

## Wave `W01` - Foundation

Lay the preconditions every downstream wave depends on. The spec layer becomes team-shared, the canonical outcome vocabulary becomes the single source of truth across every sync-shaped surface, and the scaffolders stop producing values their own validators reject. No downstream wave can land while these preconditions are absent. Authorising decisions: cli-spec-gitignore, cli-sync-vocabulary, cli-scaffolder-integrity.

### Phase `W01.P01` - Reverse spec-layer gitignore

Reverse the default gitignore policy so .vaultspec/ authored content reaches teammates by default; ship the managed-block migration and the install-summary language update together.

- [ ] `W01.P01.S01` - Implement versioned migration rewriting the managed gitignore block on next upgrade with detection of operator customisation; `src/vaultspec_core/migrations/`.
- [ ] `W01.P01.S02` - Add sharing-policy summary line to install and upgrade output; `src/vaultspec_core/cli/root.py`.
- [ ] `W01.P01.S03` - Update framework manual, builtin rules, and agent personas to describe the new shared-by-default policy; `.vaultspec/`.

### Phase `W01.P02` - Define canonical outcome vocabulary

Establish the seven-word canonical outcome taxonomy (created/updated/unchanged/removed/restored/skipped/failed) and route every sync-shaped surface through a single renderer that emits text and JSON together.

- [ ] `W01.P02.S04` - Implement Outcome enum and shared rendering helper for text and JSON together; `src/vaultspec_core/cli/rendering.py`.
- [ ] `W01.P02.S05` - Route every sync-shaped CLI surface through the shared outcome renderer; `src/vaultspec_core/cli/`.
- [ ] `W01.P02.S06` - Update CLI reference, builtin rules, and agent personas to use the canonical seven-word taxonomy; `.vaultspec/`.

### Phase `W01.P03` - Enforce scaffolder integrity

Enforce the framework-wide invariant that scaffolders never emit values their validators would reject, with an emit-time linter and required flags on the verbs that today emit placeholders.

- [ ] `W01.P03.S07` - Implement emit-time validator that runs the schema check against scaffolded output before flush; `src/vaultspec_core/vaultcore/`.
- [ ] `W01.P03.S08` - Add --tier flag with default L1 to vault add plan and remove the L curly-pound placeholder from the plan template; `src/vaultspec_core/cli/vault_cmd.py`.
- [ ] `W01.P03.S09` - Require --phase-title and --phase-intent on vault plan tier promote from L1 to L2 and remove the TODO placeholder; `src/vaultspec_core/plan/commands/`.
- [ ] `W01.P03.S10` - Narrow the unhydrated-placeholder warning to skip tokens inside HTML comment regions; `src/vaultspec_core/builtins/`.

## Wave `W02` - Memory architecture

Introduce the missing memory-lifecycle verbs and the atomicity invariant every metadata-rewriting verb must honour. Codify, supersede, and retire become first-class CLI operations with typed frontmatter relationship fields. Rename becomes atomic across filename and frontmatter. The editor surface becomes honest, with standard environment-variable resolution and exit-code integrity. Authorising decisions: cli-memory-lifecycle, cli-rename-integrity, cli-spec-edit-safety.

### Phase `W02.P04` - Memory-lifecycle verbs

Introduce codify, supersede, and retire as first-class lifecycle verbs with typed frontmatter relationship fields and an archive verb that preserves cross-feature provenance.

- [ ] `W02.P04.S11` - Land frontmatter schema additions (supersedes, superseded_by, derived_from, promoted_to, archived) with a versioned migration; `src/vaultspec_core/migrations/`.
- [ ] `W02.P04.S12` - Implement vault rule promote --from --as as the codify verb; `src/vaultspec_core/cli/`.
- [ ] `W02.P04.S13` - Implement vault adr supersede with frontmatter rewrites on both old and new documents; `src/vaultspec_core/cli/vault_cmd.py`.
- [ ] `W02.P04.S14` - Fix vault feature archive end to end: dry-run, unarchive verb, cross-feature link rewriting, structure-check allowlist, dangling-check archive resolver; `src/vaultspec_core/cli/vault_cmd.py`.
- [ ] `W02.P04.S15` - Update ADR template, pipeline rules, and agent personas to teach the codify lifecycle phase; `.vaultspec/`.

### Phase `W02.P05` - Atomic rename invariant

Make rename rewrite filename and frontmatter atomically across every metadata-rewriting verb, with a new vault check that surfaces pre-existing inconsistencies.

- [ ] `W02.P05.S16` - Implement atomic rename rewriting filename and frontmatter together across spec rules, skills, and agents; `src/vaultspec_core/cli/spec_cmd.py`.
- [ ] `W02.P05.S17` - Add vault check rename-integrity with --fix and --fix-frontmatter-wins modes; `src/vaultspec_core/vaultcore/checks/`.
- [ ] `W02.P05.S18` - Update help text, manual, and agent personas to describe atomic rename behaviour; `.vaultspec/`.

### Phase `W02.P06` - Spec edit safety

Resolve editor selection through the standard environment-variable contract, introduce the vaultspec-core config surface, and make every exit code honest.

- [ ] `W02.P06.S19` - Add vaultspec-core config verb group with get, set, unset, list against .vaultspec/config.toml; `src/vaultspec_core/cli/`.
- [ ] `W02.P06.S20` - Implement editor resolution order (flag, config, VISUAL, EDITOR, vi, fail) in spec edit; `src/vaultspec_core/cli/spec_cmd.py`.
- [ ] `W02.P06.S21` - Wrap the editor subprocess invocation translating failures into honest non-zero exit codes; `src/vaultspec_core/cli/spec_cmd.py`.
- [ ] `W02.P06.S22` - Update CLI reference and builtin rules to describe editor-resolution order and config surface; `.vaultspec/`.

## Wave `W03` - Pipeline integrity

Make the pipeline's daily-use verbs safe. Plan-editing operations preserve author prose through unknown-block round-tripping. The execute phase gains its missing per-Step authoring surface so the framework's own rules become followable. Authorising decisions: cli-plan-body-preservation, cli-exec-step-records.

### Phase `W03.P07` - Plan-body preservation

Preserve author prose across every plan-editing verb through unknown-block round-tripping in the parser/serialiser, plus universal dry-run on the plan-editing surface.

- [ ] `W03.P07.S23` - Extend the plan parser to capture unknown-but-positioned blocks with verbatim source and anchor positions; `src/vaultspec_core/plan/`.
- [ ] `W03.P07.S24` - Update the plan serialiser to round-trip unknown blocks verbatim in their original position; `src/vaultspec_core/plan/`.
- [ ] `W03.P07.S25` - Add --dry-run to every plan-editing verb emitting a unified diff against the current file; `src/vaultspec_core/cli/plan_cmd.py`.
- [ ] `W03.P07.S26` - Add --canonicalise flag and update help, plan template, and agent personas to describe preservation; `src/vaultspec_core/cli/plan_cmd.py`.

### Phase `W03.P08` - Step-aware exec records

Make vault add exec Step-aware so per-Step execution records become CLI-authorable, closing the framework's own rules-versus-CLI disagreement on the execute phase.

- [ ] `W03.P08.S27` - Add required --step flag to vault add exec with derived path and frontmatter from the parent plan; `src/vaultspec_core/cli/vault_cmd.py`.
- [ ] `W03.P08.S28` - Add --all-steps bulk form: idempotent enumeration over plan Steps with --force override; `src/vaultspec_core/cli/vault_cmd.py`.
- [ ] `W03.P08.S29` - Remove step_id and display-path placeholders from the exec template and route through scaffolder-integrity invariant; `src/vaultspec_core/builtins/`.
- [ ] `W03.P08.S30` - Surface the exec-missing hint from vault plan status and update rules and agent personas; `src/vaultspec_core/cli/plan_cmd.py`.

## Wave `W04` - Surface and parity

Resolve the structural cleanup the earlier waves enable. Spec noun groups adopt a uniform CRUD template. Duplicate command surfaces consolidate around one canonical pick each. Destructive operations gate consistently across the entire CLI through universal --dry-run and a documented force discipline. Authorising decisions: cli-spec-crud-parity, cli-surface-consolidation, cli-blast-radius-gating.

### Phase `W04.P09` - Uniform spec CRUD shape

Apply a uniform CRUD template to every collection-shaped spec noun group, promote hooks to first-class CRUD, add status to every group, unify the body-content flag.

- [ ] `W04.P09.S31` - Define the canonical CRUD shape and apply it to spec rules, spec skills, and spec agents (list, show, add, edit, rename, remove, restore, sync, status); `src/vaultspec_core/cli/spec_cmd.py`.
- [ ] `W04.P09.S32` - Promote spec hooks to first-class CRUD with add, edit, rename, remove, restore, sync, status; `src/vaultspec_core/cli/spec_cmd.py`.
- [ ] `W04.P09.S33` - Implement status verb on every collection-shaped spec noun group with consistent semantics; `src/vaultspec_core/cli/spec_cmd.py`.
- [ ] `W04.P09.S34` - Unify the body-content flag to --body across add verbs and deprecate --content and --description as aliases; `src/vaultspec_core/cli/spec_cmd.py`.

### Phase `W04.P10` - Surface consolidation

Pick one canonical surface per duplicated operation, deprecate the alternative with redirect messaging, and ship a deprecated-usage scanner.

- [ ] `W04.P10.S35` - Reframe top-level sync as a fanout helper invoking each spec sync per noun group in sequence; `src/vaultspec_core/cli/root.py`.
- [ ] `W04.P10.S36` - Deprecate vault sanitize annotations with a redirect message pointing at vault check annotations --fix; `src/vaultspec_core/cli/vault_cmd.py`.
- [ ] `W04.P10.S37` - Reconcile spec sync argument shapes to accept the provider positional consistent with top-level sync; `src/vaultspec_core/cli/spec_cmd.py`.
- [ ] `W04.P10.S38` - Add vault check deprecated-usage scanning hook configs, agent personas, rule files, and templates for legacy invocations; `src/vaultspec_core/vaultcore/checks/`.

### Phase `W04.P11` - Blast-radius gating discipline

Apply a framework-wide gating discipline across every destructive verb with universal dry-run, gated destructive sub-paths, and preservation-summary lines.

- [ ] `W04.P11.S39` - Implement universal --dry-run across every state-changing verb with shared code paths for preview and apply; `src/vaultspec_core/cli/`.
- [ ] `W04.P11.S40` - Add --force requirement on destructive sub-paths within additive verbs such as install --upgrade; `src/vaultspec_core/cli/root.py`.
- [ ] `W04.P11.S41` - Add preservation-summary line to install --upgrade and vault feature archive success output; `src/vaultspec_core/cli/`.
- [ ] `W04.P11.S42` - Add interactive confirmation gate for TTY contexts on destructive verbs invoked without --force; `src/vaultspec_core/cli/`.

## Wave `W05` - Contract and discovery

Finalise the consumer-facing contract. Machine-readable output adopts a uniform envelope with top-level status and schema versioning. Every successful pipeline verb volunteers the natural next command in its output. The residual paper-cut tail closes under a documented contribution discipline and the new top-level workspace-readiness gate. Authorising decisions: cli-json-consistency, cli-next-step-hints, cli-paper-cuts.

### Phase `W05.P12` - Uniform JSON envelope

Adopt a uniform top-level envelope (status, schema, data, hints) across every machine-readable output, with documented schema versioning for forward compatibility.

- [ ] `W05.P12.S43` - Define the uniform JSON envelope schema (status, schema, data, hints) in the rendering helper; `src/vaultspec_core/cli/rendering.py`.
- [ ] `W05.P12.S44` - Wire the envelope through every --json-emitting verb without removing existing payload fields; `src/vaultspec_core/cli/`.
- [ ] `W05.P12.S45` - Document the schema registry and version contract in the CLI reference; `.vaultspec/CLI.md`.

### Phase `W05.P13` - Next-step hints

Make every successful pipeline verb volunteer the natural next command in its output, surfacing vault repair and the codify phase from the verbs whose follow-on points at them.

- [ ] `W05.P13.S46` - Implement the static next-step lookup table mapping verb plus outcome to suggested follow-on command; `src/vaultspec_core/cli/rendering.py`.
- [ ] `W05.P13.S47` - Wire hint emission into every successful pipeline verb output across text and JSON paths; `src/vaultspec_core/cli/`.
- [ ] `W05.P13.S48` - Document the VAULTSPEC_NO_HINTS environment variable and --no-hints flag suppression contract; `.vaultspec/CLI.md`.

### Phase `W05.P14` - Paper-cut sweep and doctor verb

Sweep the residual paper-cut tail under a documented contribution discipline and add the top-level vaultspec-core doctor verb as the single workspace-readiness gate.

- [ ] `W05.P14.S49` - Apply the discipline-checklist sweep: hide --dev, fix vault graph usage line, drop vault feature list trailing token, disambiguate migrations status, widen spec hooks list column, fix spec system show phantom target; `src/vaultspec_core/cli/`.
- [ ] `W05.P14.S50` - Add top-level vaultspec-core doctor verb composing vault check all and spec doctor under a single exit code; `src/vaultspec_core/cli/root.py`.
- [ ] `W05.P14.S51` - Document the contribution discipline checklist gating every new CLI verb at merge time; `CONTRIBUTING.md`.
- [ ] `W05.P14.S52` - Add post-merge audit check enforcing the discipline checklist on every newly introduced verb; `src/vaultspec_core/vaultcore/checks/`.

## Parallelization

Waves are sequenced. `W01` Foundation must land before any other wave; the canonical outcome vocabulary (P02), the gitignore policy (P01), and the scaffolder-integrity invariant (P03) are referenced by every downstream phase. `W02` Memory architecture and `W03` Pipeline integrity may begin once `W01` is closed; `W03` does not depend on `W02` except through the scaffolder-integrity invariant from P03, so the two waves admit limited parallelism if separate contributors take them. `W04` Surface and parity depends on `W02` and `W03` landing first; the spec CRUD template inherits from P05 atomic rename and P06 editor safety, and surface consolidation depends on P02 vocabulary. `W05` Contract and discovery is the consumer-facing finalisation and lands last; P12 JSON envelope and P13 next-step hints share the renderer modified by P02 so they cannot be parallelised against each other, and P14 paper-cut sweep depends on every prior phase and is the closing pass.

Within a single phase, Steps are not independent. P01 S01 (migration) must land before S02 (summary line) which must land before S03 (manual update). P04 S11 (schema additions) must land before S12, S13, and S14 (verbs that depend on the new fields). Each phase's intent paragraph names the dependency direction.

Documentation Steps (those scoped at `.vaultspec/` or the framework manual) trail their corresponding code Steps within a phase; the documentation reflects the as-shipped surface.

## Verification

Mission success criteria are verifiable per Step, per phase, per wave, and at the epic level.

Per Step: the Step is closed when its scope file change is committed and the relevant pre-commit hooks pass. Steps whose scope is documentation pass `pymarkdown` and `mdformat-check`. Steps whose scope is Python source pass `ruff check` and `ty` type-checking.

Per phase: the phase is closed when every Step is closed and the phase's authorising ADR Consequences section is verifiable on the changed surface. Each phase ships a regression test that exercises the change against the failure mode the audit documented (B1 reproduces fixable, S10 vocabulary becomes consistent across surveyed surfaces, B7 silent-edit-failure no longer exits 0, and so on per phase).

Per wave: the wave is closed when every phase is closed and `vaultspec-core vault check all` plus `vaultspec-core spec doctor` both exit zero on a sample project that has run through the wave's end state. From `W05` onwards the new top-level `vaultspec-core doctor` verb (introduced in P14.S50) is the single readiness check.

At epic completion: the project-management association (pull request #114) reports the epic complete. The rolling audit document gains a final Resolution section that closes each finding cluster with a back-pointer to the phase that delivered it. The fourteen sibling ADRs have their status updated from `accepted` to `accepted (delivered)` through the supersession-aware status workflow introduced in P04.S13.

A regression-audit pass: a fresh-eyes agent with no source-code access (the audit methodology of this plan) is briefed to onboard onto a vaultspec-managed project, run a feature end to end through the pipeline including the new codify phase, archive a feature, and report friction. The pass is successful when the new agent's friction log does not reproduce any blocker-grade finding from this audit (B1, B2, B3, B5, B6, B7, B8, B9).
