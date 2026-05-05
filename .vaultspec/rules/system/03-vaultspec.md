---
order: 3
---

# Vaultspec Framework

- You're operating within `vaultspec`: a spec-driven development framework.

- You **must translate user requests into structured workflows** using the provided
  vaultpsec-\* skills and agent personas.

- **MUST read before starting a new pipeline phase** relevant `.vault/` documents.
  Check for any previous audit or adr overlap. All authored records live in
  `.vault/` under `adr/`, `audit/`, `exec/`, `plan/`, `reference/`, and
  `research/`. Auto-generated feature indexes live in `.vault/index/` and
  are managed by `vault feature index`; do not author them by hand.

All significant work must follow this pipeline:

| Phase       | Skill                    | Artifact               | Requires          |
| ----------- | ------------------------ | ---------------------- | ----------------- |
| 1 Research  | vaultspec-research       | .vault/research/...    | -                 |
| 1 Reference | vaultspec-code-reference | .vault/reference/...   | -                 |
| 2 Specify   | vaultspec-adr            | .vault/adr/...         | Research artifact |
| 3 Plan      | vaultspec-write-plan     | .vault/plan/...        | ADR artifact      |
| 4 Execute   | vaultspec-execute        | .vault/exec/.../steps  | Approved plan     |
| 5 Verify    | vaultspec-code-review    | .vault/exec/.../review | Completed step(s) |

Plan documents structure work with the hierarchy
`Epic > Wave > Phase > Step` and declare a complexity tier
(`L1`, `L2`, `L3`, or `L4`) in frontmatter. The tier determines
which structural containers exist: `L1` is Steps only; `L2`
adds Phases; `L3` adds Waves; `L4` adds an Epic frame and
requires an external project-management association declared
in the Epic intent block. The leaf row at every tier is named
`Step`; the execution-log artefact retains the name
`<Step Record>` and maps one-to-one to a Step. Full conventions
live in the plan-hardening convention ADR and in the markdown-
comment hint blocks embedded in `.vaultspec/rules/templates/plan.md`.

The `vault plan` CLI (vaultspec-core) is the canonical surface
for structural manipulation of plan documents. Writers and
executors MUST use the CLI verbs (`step add/insert/move/remove/ check/uncheck/toggle/edit`, `phase`/`wave` equivalents, `epic intent`, `tier promote/demote`) for every identifier-affecting
change rather than hand-editing the markdown body. The CLI
guarantees canonical-identifier preservation, gap-no-reuse, and
display-path consistency that hand edits cannot. See the CLI
ADR (`2026-05-06-plan-hardening-adr`) for the subcommand
contract.

Supporting skills, invoke when appropriate:

| Curate | vaultspec-curate | Maintain .vault/ hygiene - links, tags |
| Documentation | vaultspec-documentation | Write project documentation |

- **Utilize vaultspec- skills** to interpret user intent:

| Example User Intent                 | Invoke                   |
| ----------------------------------- | ------------------------ |
| "Research X" / "Investigate"        | vaultspec-research       |
| "Decide on X" / "Create an ADR"     | vaultspec-adr            |
| "How does [codebase] implement X?"  | vaultspec-code-reference |
| "Plan the implementation"           | vaultspec-write-plan     |
| "Execute the plan" / "Build it"     | vaultspec-execute        |
| "Review the code" / "Verify"        | vaultspec-code-review    |
| "Clean up docs" / "Curate"          | vaultspec-curate         |
| "Start a new feature" (broad)       | vaultspec-research       |
| "Write documentation for {subject}" | vaultspec-documentation  |

## Agents

Agent personas are defined in `.vaultspec/rules/agents/`. Two mechanisms are
available depending on plan complexity:

- **Parallel sub-agents** for focused, managed work
- **Agent teams** for self-orchestrating complex challanges using the team dispatch
  tools.

Artifacts are persisted in `.vault/`.
The user must approve plans before execution proceeds. Code review via
vaultspec-code-review is mandatory after execution.

<!-- end conventions -->
