---
order: 3
---

# Vaultspec Framework

- You're operating within `vaultspec`: a spec-driven development framework.

- You **must translate user requests into structured workflows** using the provided
  vaultspec-\* skills and agent personas.

- **MUST read before starting a new pipeline phase** relevant `.vault/` documents. Check
  for any previous audit or adr overlap. All authored records live in `.vault/` under
  `adr/`, `audit/`, `exec/`, `plan/`, `reference/`, and `research/`. Auto-generated
  feature indexes live in `.vault/index/` and are managed by
  `vaultspec-core vault feature index`; do not author them by hand.

All significant work must follow this pipeline:

| Phase       | Skill                   | Artifact                   | Requires                                        |
| ----------- | ----------------------- | -------------------------- | ----------------------------------------------- |
| 1 Research  | vaultspec-research      | .vault/research/...        | -                                               |
| 1 Reference | vaultspec-code-research | .vault/reference/...       | -                                               |
| 2 Specify   | vaultspec-adr           | .vault/adr/...             | Research artifact                               |
| 3 Plan      | vaultspec-write-plan    | .vault/plan/...            | ADR artifact                                    |
| 4 Execute   | vaultspec-execute       | .vault/exec/.../steps      | Approved plan                                   |
| 5 Verify    | vaultspec-code-review   | .vault/exec/.../review     | Completed step(s)                               |
| 6 Codify    | vaultspec-codify        | .vaultspec/rules/rules/... | Review surfacing a durable cross-session lesson |

Phase 6 (Codify) is **discretionary**: most features end at Verify. Only when a Verify
pass surfaces a lesson that satisfies the three durability criteria (cross-session,
constraint-shaped, project-bound) does the work continue into Codify. The
`vaultspec-codify` rule defines the criteria and the body template; the
`vaultspec-codifier` agent persona enacts the discipline. A rule authored under Phase 6
binds future agents across sessions, clones, and CI runs.

Plan documents structure work with the hierarchy `Epic > Wave > Phase > Step` and
declare a complexity tier (`L1`, `L2`, `L3`, or `L4`) in frontmatter. The tier
determines which structural containers exist: `L1` is Steps only; `L2` adds Phases; `L3`
adds Waves; `L4` adds an Epic frame and requires an external project-management
association declared in the Epic intent block. The leaf row at every tier is named
`Step`; the execution-log artifact retains the name `<Step Record>` and maps one-to-one
to a Step. Full conventions live in the plan-hardening convention ADR and in the
Markdown comment hint blocks embedded in `.vaultspec/rules/templates/plan.md`.

The `vaultspec-core vault plan` CLI is the canonical surface for structural manipulation
of plan documents. Writers and executors MUST use the `vaultspec-core vault plan ...`
CLI verbs (`step add/insert/move/remove/check/uncheck/toggle/edit`, `phase`/`wave`
equivalents, `epic intent`, `tier promote/demote`) for every identifier-affecting change
rather than hand-editing the markdown body. The CLI guarantees canonical-identifier
preservation, gap-no-reuse, and display-path consistency that hand edits cannot. See the
CLI ADR (`2026-05-06-plan-hardening-adr`) for the subcommand contract.

Supporting skills, invoked when appropriate:

| Need          | Skill                   | Purpose                                     |
| ------------- | ----------------------- | ------------------------------------------- |
| Curate        | vaultspec-curate        | Maintain `.vault/` links, tags, and hygiene |
| Documentation | vaultspec-documentation | Write or revise project documentation       |

- **Use vaultspec- skills** to interpret user intent:

| Example User Intent                 | Invoke                  |
| ----------------------------------- | ----------------------- |
| "Research X" / "Investigate"        | vaultspec-research      |
| "Decide on X" / "Create an ADR"     | vaultspec-adr           |
| "How does [codebase] implement X?"  | vaultspec-code-research |
| "Plan the implementation"           | vaultspec-write-plan    |
| "Execute the plan" / "Build it"     | vaultspec-execute       |
| "Review the code" / "Verify"        | vaultspec-code-review   |
| "Codify X" / "Promote X to a rule"  | vaultspec-codify        |
| "Clean up docs" / "Curate"          | vaultspec-curate        |
| "Start a new feature" (broad)       | vaultspec-research      |
| "Write documentation for {subject}" | vaultspec-documentation |

## Agents

Agent personas are defined in `.vaultspec/rules/agents/`. Two mechanisms are available
depending on plan complexity:

- **Parallel sub-agents** for focused, managed work
- **Agent teams** for self-orchestrating complex challenges using the team dispatch
  tools.

Artifacts are persisted in `.vault/`. The user must approve plans before execution
proceeds. Code review via vaultspec-code-review is mandatory after execution.

<!-- end conventions -->
