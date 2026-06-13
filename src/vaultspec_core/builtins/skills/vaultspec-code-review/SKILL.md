---
name: vaultspec-code-review
description: Run a formal code review for safety, intent, and quality. Use to verify completed work before marking it done.
---

# Code review skill (vaultspec-code-review)

When to use this skill:

- **Mandatory:** At the end of every `vaultspec-execute` cycle, before marking a feature
  as "Done", and before publishing a PR.
- After major feature implementation work.
- When you need a second pair of eyes on a specific module or PR.
- **Safety Check:** When you suspect a safety violation (e.g., `unsafe` usage) or
  testing framework issue in complex projects.

## Workflow

- **Announce at start:** "I'm using the `vaultspec-code-review` skill to audit the
  implementation."

- Identify relevant docs, the plan (`.vault/plan/...`), ADR and research documents

- Identify files modified

- Scaffold the audit document with `vaultspec-core vault add audit --feature {feature}`;
  the CLI owns the filename and frontmatter. Log discovered issues to its body as
  triaged `LOW`->`CRITICAL` task entries.

- Use a `vaultspec-code-reviewer` agent persona, or other code-review specialists.

- Use parallel subagents to comprehensively comb through codebase.

- Instruct agents to always read grounding docs, ADRs, and plans.

- Instruct agents to log findings as triaged issue entries into the single shared
  scaffolded audit document's body.

- Code review is not a code fixer skill - do NOT modify the codebase.

## Important

- **Template:** You MUST read and use the template at
  `.vaultspec/rules/templates/code-review.md`; its embedded hint blocks govern the body
  structure.

- **Location:** the scaffold creates `.vault/audit/yyyy-mm-dd-{feature}-audit.md`; never
  hand-write the filename or frontmatter. When the feature already carries an audit,
  disambiguate with the optional narrative infix:
  `yyyy-mm-dd-{feature}-{topic}-audit.md`.

- **Tags:** the scaffold tags the audit document with `#audit` and `#{feature}`; verify
  via `vaultspec-core vault check all` rather than hand-editing.

- Issues must be continuously appended to the audit document as a rolling log of open
  tasks.
