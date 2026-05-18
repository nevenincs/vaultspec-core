---
tags:
  - '#adr'
  - '#cli-spec-edit-safety'
date: '2026-05-17'
related:
  - "[[2026-05-17-cli-simplification-ux-audit]]"
  - "[[2026-05-17-cli-spec-edit-safety-research]]"
---

# `cli-spec-edit-safety` adr: `Surface editor configuration and make spec edit fail honestly` | (**status:** `accepted`)

## Problem Statement

`vaultspec-core spec rules edit` (and the sibling
`spec skills edit`, `spec agents edit`) hardcodes `zed` as the
editor binary, ignores `$EDITOR` and `$VISUAL`, prints a Python
traceback to stderr when `zed` is not installed, and exits 0.
The exit code lies; CI integrations that monitor exit codes will
report success while the edit silently failed. Finding B7 in the
audit.

The internal configuration object the traceback referenced
suggests an editor-config mechanism exists but is not surfaced.
No CLI verb queries or sets it. The verb is effectively unused
by any team whose preferred editor is not `zed`.

## Considerations

- Two orthogonal problems: the wrong default editor, and the
  honest-exit-code violation. Both need fixing; they are
  separate decisions.
- Editor selection has a standard contract (`$VISUAL` then
  `$EDITOR` then a hardcoded fallback). The fix should adopt
  the contract rather than invent a new one.
- A documented per-project editor configuration is genuinely
  useful for teams that want consistent tool choices across
  team members. The internal `editor` attribute should become
  a documented config entry.
- A new `vaultspec-core config` verb group is overdue: it would
  serve this finding and several adjacent ones (the `--dev`
  source-repo guard, the editor configuration, presumably
  others not yet uncovered).
- The fix must not make `spec * edit` newly required. The
  verb is optional today (Joan's workaround: edit the file
  directly). The fix makes the verb actually usable, but the
  direct-file-edit path remains a first-class option.

## Constraints

- Adding a new dependency on the user's environment must
  degrade gracefully. If `$EDITOR` is unset and no documented
  fallback (`vi`) is present, the verb must print a clear
  error stating exactly which environment variables it tried
  and what to set. It must exit non-zero.
- The new `vaultspec-core config` verb group introduces a new
  noun. It should land alongside this ADR rather than waiting
  for a separate decision. The shape is small; the surface
  area is contained.
- Existing automation that calls `spec * edit` (probably
  effectively none, given the unusability finding) must
  continue to work if a usable editor is configured.

## Implementation

**Editor resolution order.** When `spec * edit` is invoked, the
editor binary is resolved in this order:

1. Command-line `--editor <binary>` flag if present.
2. Project-local config: `vaultspec-core config get editor`
   reading from a documented config entry.
3. `$VISUAL` environment variable.
4. `$EDITOR` environment variable.
5. Fallback to `vi`.
6. If none of the above resolves to an executable on `$PATH`,
   the verb prints an error naming every variable it tried
   and exits non-zero.

The hardcoded `zed` choice is removed entirely.

**Exit-code honesty.** Wrap the editor invocation in an error
handler that catches subprocess failures and configuration
errors. On any failure path:

- Print a concise stderr message naming the failure.
- Exit with a non-zero status code (`2` for editor
  resolution failure, `3` for subprocess failure, `4` for
  user-cancellation if detectable).
- Never print a raw Python traceback to stderr on an expected
  failure path; the traceback is reserved for genuine
  unexpected bugs.

**`vaultspec-core config` verb group.** New top-level group:

- `vaultspec-core config get <key>` — read a configuration
  value. First key in scope: `editor`.
- `vaultspec-core config set <key> <value>` — write a
  configuration value to the documented config file.
- `vaultspec-core config unset <key>` — clear a configuration
  entry.
- `vaultspec-core config list` — enumerate all known
  configuration entries with current values.
- The config file location is documented in `--help` and
  stored under `.vaultspec/config.toml` so the
  spec-gitignore ADR's shared-by-default policy applies.

**Companion language updates.**

- Framework manual section on customising the CLI gets a
  short subsection on editor configuration with worked
  examples.
- `spec * edit --help` text is rewritten to describe the
  editor-resolution order plainly. Today's help text is
  generic and gives no hint about the resolution logic.
- Builtin rule files that describe how to customise project
  rules link to the new config verb.
- Agent personas update to know that editing project rules
  can happen either through `spec * edit` (requires a usable
  editor) or by direct file write (always works); both paths
  produce equivalent results.

**`--editor` flag on `spec * edit`.** A per-invocation override
for the editor binary. Useful for CI contexts that want to
script the edit with a non-interactive command (e.g.,
`--editor='sed -i s/foo/bar/'`). The flag's value is parsed
through `shlex.split` and invoked with `shell=False` so user
quoting controls argv splitting, not shell expansion;
spec-edit invocations never pass a string to a shell
interpreter, even when the operator's value contains shell
metacharacters. This invariant is mandatory; the implementation
must not accept the flag's value as a shell command string under
any condition.

## Rationale

The current implementation is the worst-case CLI failure mode:
silent destruction of the user's intent with a misleading exit
code. Two months ago this was probably written as "the editor
question, we will figure out the default later" with `zed` as a
placeholder. The placeholder shipped. The fix is to honour the
contract every other Unix tool already honours, while making
the configuration knob a first-class surface.

The new `vaultspec-core config` verb group is a small but
overdue surface. The same group will host adjacent
configuration concerns as they surface (editor today, possibly
hook-enablement, possibly retention defaults for archive). The
absence of any config surface is itself a finding: the
framework has internal knobs with no documented external way
to set them.

Honest exit codes are non-negotiable for any CI-touched verb.
The fix is small (wrap the subprocess invocation, translate
errors), but the discipline matters across the rest of the
CLI: any verb that silently exits 0 on failure is a B7-shape
bug waiting to be found. A separate paper-cut audit pass on
exit-code honesty is a downstream consequence of this ADR.

## Consequences

Gains. `spec * edit` becomes a usable verb for the first time.
Editor selection follows the standard contract every developer
already knows. CI hooks that rely on exit codes stop receiving
false success signals. The `vaultspec-core config` surface
becomes available for adjacent knobs.

Difficulties. The new config verb group is a new top-level
surface. It must land with thoughtful help text, a documented
schema, and a test surface that covers each entry.

Pitfalls. An aggressive editor-resolution fallback ladder is
useful; the `--editor` flag is a security surface that requires
discipline. The flag's value is parsed via `shlex.split` and
invoked with `shell=False`; the implementation must never pass
the value to a shell interpreter. Any future helper that adds
shell-style expansion (variable substitution, glob expansion,
pipe chaining) belongs in a separate explicit verb, not in
`--editor`'s execution path.

Pathways. Once `spec * edit` works and exit codes are honest,
the framework's pre-commit-hook integration surface becomes
trustworthy. Other verbs in the CLI that silently exit 0 on
failure (a paper-cut audit will find them) get fixed under
the same pattern.
