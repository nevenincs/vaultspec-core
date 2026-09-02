# Verifying a workspace and a vault

This page covers how to check that vaultspec is installed correctly and that the
documents it manages are sound. For the workflow those documents come out of, see the
[framework manual](./framework.md); for every flag on every command, the
[CLI reference](./CLI.md).

Two questions come up, and they have different answers. *Is the framework wired into
this project properly?* is a workspace question. *Do the documents in `.vault/` hold
together?* is a vault question. One command answers both.

## The single command

```
vaultspec-core doctor
```

It runs the workspace diagnosis and the full vault check suite, and reports both under
one exit code. Reach for it when you want a yes-or-no answer about the whole project.

The first half reports on the installation itself:

```
workspace diagnosis
  framework ok .vaultspec/ present
  claude ok dir: complete
  builtins ok current
  gitignore ok complete
  mcp ok .mcp.json present
  migration ok all registered migrations applied
  precommit ok all hooks present
  install mode (vaultspec-core) ok declared dependency; artifacts match
```

The second half is the vault check suite, one line per check.

### A printed warning does not always change the exit code

The exit codes are `0` for clean, `1` for warnings, and `2` for errors. That covers the
checks the diagnosis weighs, and the diagnosis prints some lines it does not weigh. A
workspace with stale process records and an out-of-date package seed reports both as
warnings and still exits `0`:

```
  process registry warn 6 stale of 6 process record(s)
  mcp seeds warn stale package seed definition(s)
```

This matters if you are gating on the command rather than reading it. Do not infer
failure from the presence of the word `warn` in the output; read the exit code, or read
`status` under `--json`.

The conditions that do raise the code are the framework layout, the provider
directories, the builtins, `.gitignore` and `.gitattributes`, migrations, the pre-commit
hooks, rename integrity, vault content, and an install-mode or version-floor mismatch on
any declared package.

Three lines are printed and not weighed: the process registry, stale package seeds, and
the tool-server configuration. The last is worth knowing about - a diagnosis can report
on `.mcp.json` and still exit `0`.

The same applies to `vaultspec-core spec doctor`, which computes its code the same way
over the workspace half alone.

## Checking only the vault

```
vaultspec-core vault check all
```

Nineteen checks run, and each prints its own line. What they prove, grouped by the kind
of damage they catch:

**The document is well formed.** `structure` checks directory layout and filenames.
`frontmatter` validates fields against the schema for the document's type.
`body-sections` confirms the sections a template requires are present. `markdown`
applies hygiene rules and can repair them. `encoding` surfaces documents that are not
valid text.

**Nothing is left half-authored.** `placeholders` finds unreplaced `{...}` tokens.
`annotations` finds template comment blocks that were meant to be stripped.

**The graph holds together.** `links` checks wiki-links follow the convention.
`dangling` finds `related:` entries pointing at documents that do not exist.
`body-links` finds links in body prose, where they are forbidden. `orphans` finds
documents nothing links to. `references` finds missing cross-references.

**The lifecycle is coherent.** `schema` enforces that an ADR references research and a
plan references an ADR. `adr-status` validates status against the allowed set.
`exec-mapping` checks each execution record maps to a live Step in its parent plan.
`features` checks feature-tag completeness.

**Nothing has drifted since it was written.** `modified-stamp` reconciles the recency
stamp against the body hash, which is how an unstamped hand edit becomes visible.
`rename-integrity` and `feature-rename-integrity` catch names that disagree with their
filenames or their folders.

Run one check by name when you already know which half you are investigating:

```
vaultspec-core vault check dangling
```

### The check that `all` does not run

There are twenty checks; `all` runs nineteen. The exception is `code-boundary`, which
scans your source files rather than your vault, looking for references to the
development corpus - vault documents cite code by locator, and code never cites the
vault. Scanning a source tree costs more than reading a vault, so it is opt-in and runs
only when you name it:

```
vaultspec-core vault check code-boundary
```

A green `vault check all` says nothing about the boundary. If it matters to you, run
this one separately and gate on it separately.

## Repairing what can be repaired

```
vaultspec-core vault check all --fix
```

Anything mechanical is repaired in place: markdown hygiene, frontmatter reconciliation,
stripped template annotations, refreshed stamps. What cannot be repaired mechanically is
reported and left alone, because guessing at a fix for a broken cross-reference produces
a document that passes and lies.

## Gating a script or a pipeline

Add `--json` and read one field:

```
vaultspec-core vault check all --json
```

The envelope carries `schema`, `status`, `data`, and `hints`. The single question *did
this run pass* is answered by `status` alone, so a gate reduces to inspecting that one
key. Diagnostic logging stays on stderr, so stdout is the envelope and nothing else.

Use `--target DIR` to check a project other than the current directory.

## What to run, and when

Run `vaultspec-core vault check all --fix` before you commit. It is fast, it repairs the
mechanical problems, and it names the rest.

Run `vaultspec-core doctor` after installing, after upgrading, and when something
behaves in a way the documentation does not explain. Most of what it catches is a
workspace that drifted rather than a vault that broke.

Gate continuous integration on `vaultspec-core vault check all --json` and the `status`
field. Gate on the vault check rather than on the diagnosis: the vault is what your
commits change, and the workspace diagnosis reports conditions that are true of a
machine rather than of a change.
