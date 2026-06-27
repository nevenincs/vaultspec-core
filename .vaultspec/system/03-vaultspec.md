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

**Orient first.** In a project with no session context, run `vaultspec-core status`
before invoking any pipeline skill. Read the in-flight plans it names, then enter the
pipeline at the right phase: resume an in-flight plan via `vaultspec-execute`, or start
fresh at Research.

Ground every pipeline phase in what the project already decided and built before acting;
the always-on `vaultspec-discovery` rule defines the canonical discovery sequence.

All significant work must follow this pipeline:

| Phase        | Skill                   | Artifact              | Requires          |
| ------------ | ----------------------- | --------------------- | ----------------- |
| 1a Research  | vaultspec-research      | .vault/research/...   | -                 |
| 1b Reference | vaultspec-code-research | .vault/reference/...  | -                 |
| 2 Specify    | vaultspec-adr           | .vault/adr/...        | Research artifact |
| 3 Plan       | vaultspec-write         | .vault/plan/...       | ADR artifact      |
| 4 Execute    | vaultspec-execute       | .vault/exec/.../steps | Approved plan     |
| 5 Verify     | vaultspec-code-review   | .vault/audit/...      | Completed step(s) |

Phases 1a and 1b are parallel entry points: Research explores the problem space,
Reference grounds the work in existing source code. A feature needs at least one of the
two; complex features benefit from both.

The pipeline scales with the work. Trivial, single-file fixes with no architectural
weight may proceed directly with user approval; state explicitly that the pipeline is
being skipped and why. Everything else follows the phases above.

Plan documents structure work with the hierarchy `Epic > Wave > Phase > Step` and
declare a complexity tier (`L1`, `L2`, `L3`, or `L4`) in frontmatter. The tier
determines which structural containers exist: `L1` is Steps only; `L2` adds Phases; `L3`
adds Waves; `L4` adds an Epic frame and requires an external project-management
association declared in the Epic intent block. The leaf row at every tier is named
`Step`; the Execution Record artifact retains the name `<Step Record>` and maps
one-to-one to a Step. Full conventions live in the Markdown comment hint blocks embedded
in `.vaultspec/templates/plan.md`.

The `vaultspec-core vault plan` CLI is the canonical surface for structural manipulation
of plan documents. Writers and executors MUST use the `vaultspec-core vault plan ...`
CLI verbs (`step add/insert/move/remove/check/uncheck/toggle/edit`, `phase`/`wave`
equivalents, `epic intent`, `tier promote/demote`) for every identifier-affecting change
rather than hand-editing the markdown body. The CLI guarantees canonical-identifier
preservation, gap-no-reuse, and display-path consistency that hand edits cannot. Run
`vaultspec-core vault plan --help` for the full subcommand surface.

Supporting skills, invoked when appropriate:

| Need               | Skill                    | Purpose                                                             |
| ------------------ | ------------------------ | ------------------------------------------------------------------- |
| Curate             | vaultspec-curate         | Maintain `.vault/` links, tags, and hygiene                         |
| Documentation      | vaultspec-documentation  | Write or revise project documentation                               |
| Team coordination  | vaultspec-team           | Start coding teams for complex challenges spanning parallel workers |
| Project management | vaultspec-projectmanager | Coordinate issues, milestones, and releases outside the pipeline    |

- **Use vaultspec- skills** to interpret user intent:

| Example User Intent                 | Invoke                  |
| ----------------------------------- | ----------------------- |
| "Research X" / "Investigate"        | vaultspec-research      |
| "Decide on X" / "Create an ADR"     | vaultspec-adr           |
| "How does [codebase] implement X?"  | vaultspec-code-research |
| "Plan the implementation"           | vaultspec-write         |
| "Execute the plan" / "Build it"     | vaultspec-execute       |
| "Review the code" / "Verify"        | vaultspec-code-review   |
| "Clean up docs" / "Curate"          | vaultspec-curate        |
| "Start a new feature" (broad)       | vaultspec-research      |
| "Write documentation for {subject}" | vaultspec-documentation |

## Agents

Agent personas are defined in `.vaultspec/agents/`. Two mechanisms are available
depending on plan complexity:

- **Parallel sub-agents** for focused, managed work
- **Agent teams** for self-orchestrating complex challenges, coordinated through the
  host environment.

Each persona declares a `mode:` field in its frontmatter. The field states the persona's
declared mutation intent: `read-write` personas mutate project state, whether through
the harness file tools (Write/Edit) or through stateful commands such as `gh` and `git`;
`read-only` personas mutate nothing and return their findings as their final message for
the dispatching orchestrator to persist (scaffold via `vaultspec-core vault add`, then
body-prose edit). The declaration is intent, not a sandbox - Bash can technically write
files in either mode - so honoring it is persona discipline, not tooling enforcement.

Artifacts are persisted in `.vault/`. The user must approve plans before execution
proceeds. Code review via vaultspec-code-review is mandatory after execution.
