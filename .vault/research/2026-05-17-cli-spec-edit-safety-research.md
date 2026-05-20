---
tags:
  - '#research'
  - '#cli-spec-edit-safety'
date: '2026-05-17'
related:
  - '[[2026-05-17-cli-simplification-ux-audit]]'
---

# `cli-spec-edit-safety` research: `spec * edit silently fails: hardcoded editor and exit-0-on-traceback`

Synthesis note for finding B7. Captures the evidence behind the
sibling ADR.

## Findings

### `spec rules edit` hardcodes `zed`, ignores `$EDITOR`

Joan's round-3a finding [43]. The command attempts to launch `zed`
as the editor binary regardless of the user's shell environment.
On any system without `zed` installed (which is most systems —
`zed` is a niche editor), the binary cannot be invoked and the
verb emits a Python traceback to stderr. The standard Unix
contract for editor selection (`$VISUAL`, then `$EDITOR`, then
documented fallbacks like `vi`) is not consulted.

The traceback includes a reference to an internal configuration
object's `editor` attribute, suggesting an editor-configuration
mechanism exists internally. No CLI verb surfaces it. There is no
`vaultspec-core config get editor`, no `--editor` flag on `spec * edit`, no documented environment variable.

### The exit code lies

The traceback prints to stderr; the verb exits 0. A pre-commit
hook or CI step that depends on `spec * edit`'s exit code to
detect failure will report success while the edit silently did
nothing. This is the worst category of CLI bug: a destructive-
intent operation that reports success when it failed.

### The whole edit surface is optional today

Joan's workaround: write directly to
`.vaultspec/rules/<group>/<filename>.md` with a text editor of
the user's choice. The CLI's `spec * show` and `spec * sync` are
file readers; they do not require the edit step to round-trip
through the CLI. The entire `spec * edit` verb tree is therefore
de facto unused: every project that has a working editor that
is not `zed` does the edit outside the CLI.

### Sister verbs `rules edit`, `skills edit`, `agents edit`

All three route through the same handler. The same bug exists
on all three. A fix at the dispatch layer fixes all three at
once.

### Why this is the highest-severity finding on the spec subtree

Joan's round-3a survey produced two blocker-grade findings on
the spec subtree: B7 (silent edit failure) and B8 (rename
frontmatter desync). B7 is worse because failure is invisible.
CI integrations that call `spec rules edit` in batch will
appear to succeed indefinitely while changing nothing. B8 is
detectable (the user can see name disagreement); B7 is not
unless the user opens the file afterwards and notices the lack
of changes.

## Constraints identified

- The framework cannot ship a default editor that exists on
  every developer's system. The standard Unix contract
  (`$VISUAL` then `$EDITOR` then a documented fallback) is the
  shape that works.
- A documented per-project editor configuration is useful for
  teams that pin specific editor configurations. The internal
  `editor` attribute the traceback exposed should become a
  documented configuration file entry.
- Exit codes are a contract with CI. Any verb that fails must
  exit non-zero. The dispatch layer must catch traceback paths
  and translate them into a clean exit status with a useful
  stderr message.

## Recommendation

Honour standard editor environment variables. Add a `--editor`
flag on `spec * edit`. Surface the editor configuration through
a new `vaultspec-core config` verb group. Make exit codes
honest: any traceback path exits non-zero. Full design in the
sibling ADR.
