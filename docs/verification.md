# Verifying a workspace and a vault

This page covers how to check that vaultspec is installed correctly and that the
documents it manages are sound. For the workflow those documents come out of, see the
[framework manual](./framework.md); for every flag on every command, the
[CLI reference](./CLI.md).

Two separate things can be wrong. The framework can be wired into the project badly,
which is a workspace problem. The documents under `.vault/` can disagree with each
other, which is a vault problem. Different commands answer them:

| What you want to know                    | Command                                    |
| ---------------------------------------- | ------------------------------------------ |
| Are my documents valid?                  | `vaultspec-core vault check all`           |
| Is the framework installed correctly?    | `vaultspec-core spec doctor`               |
| Both, under one exit code                | `vaultspec-core doctor`                    |
| Does my source code reference the vault? | `vaultspec-core vault check code-boundary` |

All four accept `--json` and `--target DIR`.

## Checking everything at once

```
vaultspec-core doctor
```

It runs the workspace diagnosis and the vault check suite, and reports both under one
exit code. The first half reports on the installation:

```
workspace diagnosis
  framework ok .vaultspec/ present
  process registry warn 6 stale of 6 process record(s): engine-dev-mantest.json, ...
  claude ok dir: complete
  gemini ok dir: complete
  antigravity ok dir: complete
  codex ok dir: complete
  builtins ok current
  gitignore warn partial
  gitattributes ok complete
  mcp ok .mcp.json present
  migration ok all registered migrations applied
  vault content ok no generated template annotations
  precommit ok all hooks present in the config
  rename integrity ok all rules, skills, and agents names are consistent
  install mode (vaultspec-core) ok declared tool; artifacts match
  semantic search none vaultspec-rag not provisioned; core discovery and find cover document lookup without it
```

That is one workspace's report, with the stale-record filenames after the count cut
to keep the line readable. A run prints the lines that apply to the workspace it
finds, so yours may carry lines this one does not.

The second half is the vault check suite, one line per check.

### Which printed lines change the exit code

The exit codes are `0` for clean, `1` for warnings, and `2` for errors. Not every
printed line feeds that code. A line is *weighed* if it can raise the exit code, and the
diagnosis prints several that never do:

| Printed line                        | Weighed                       |
| ----------------------------------- | ----------------------------- |
| `framework`                         | Yes                           |
| `gitignore`                         | Yes                           |
| `gitattributes`                     | Yes                           |
| `builtins`                          | Yes                           |
| `migration`                         | Yes                           |
| `precommit`                         | Yes                           |
| `rename integrity`                  | Yes                           |
| `vault content`                     | Yes                           |
| `install mode`                      | Yes, per declared package     |
| A provider (`claude`, `codex`, ...) | Yes, except the `mixed` state |
| `mcp`                               | No                            |
| `process registry`                  | No                            |
| `mcp seeds`                         | No                            |

So a run can print `warn` and still exit `0`:

```
  process registry warn 6 stale of 6 process record(s)
  claude warn dir: mixed
```

Both of those are unweighed. `mixed` means the provider directory holds extra files
vaultspec does not own, which is benign and deliberately excluded so it cannot block a
commit through the bundled hook. A provider directory that is missing, empty, or partial
is weighed and does raise the code.

If you gate on this command, the word `warn` in its output does not mean it failed. Read
the exit code.

`vaultspec-core spec doctor` computes its exit code the same way over the workspace half
alone. It also accepts `--gate-errors`, which folds the warning exit to `0` so only
errors fail, while still printing every warning. That flag is for the pre-commit gate,
where warning-level provider lag is an expected steady state. `vaultspec-core doctor`
does not accept it.

## Checking only the vault

```
vaultspec-core vault check all
```

Nineteen checks run. The `--fix` column says whether a failure can be repaired
automatically:

| Check                      | Catches                                                | `--fix` |
| -------------------------- | ------------------------------------------------------ | ------- |
| `structure`                | Directory layout and filenames                         | Yes     |
| `frontmatter`              | Fields invalid for the document's type                 | Yes     |
| `body-sections`            | A section the template requires, missing or empty      | No      |
| `markdown`                 | Markdown hygiene violations                            | Yes     |
| `encoding`                 | Documents that are not valid text                      | No      |
| `placeholders`             | Unreplaced `{...}` template tokens                     | No      |
| `annotations`              | Template comment blocks that should have been stripped | Yes     |
| `links`                    | Wiki-links that break the convention                   | Yes     |
| `dangling`                 | `related:` entries naming a document that is absent    | Yes     |
| `body-links`               | Links in body prose, where they are forbidden          | Yes     |
| `orphans`                  | Documents nothing links to                             | No      |
| `references`               | Missing cross-references between related documents     | Yes     |
| `schema`                   | An ADR with no research, or a plan with no ADR         | Yes     |
| `adr-status`               | A status outside the allowed set                       | Yes     |
| `exec-mapping`             | An execution record naming no live Step                | No      |
| `features`                 | A feature missing a document type or its index         | No      |
| `modified-stamp`           | A body edited without restamping                       | Yes     |
| `rename-integrity`         | A document's name disagreeing with its filename        | Yes     |
| `feature-rename-integrity` | An exec folder disagreeing with its feature tag        | No      |

Run one by name when you already know which failure you are chasing:

```
vaultspec-core vault check dangling
```

## Checking the code boundary

`vault check all` runs nineteen of the twenty checks. The twentieth, `code-boundary`,
scans your source files rather than your vault, looking for source that references the
development corpus. Vault documents cite code by locator; code never cites the vault.
Scanning a source tree costs more than reading a vault, so it is opt-in:

```
vaultspec-core vault check code-boundary
```

An exit-`0` `vault check all` says nothing about the boundary. If it matters to you, run
and gate on this one separately.

## Repairing what can be repaired

```
vaultspec-core vault check all --fix
```

Everything marked `Yes` in the table above is repaired in place. What cannot be repaired
is reported and left alone, because guessing at a fix for a broken cross-reference
produces a document that passes the check while still pointing at the wrong target.

`--fix` does not force a pass. A run that repairs two problems and leaves three
unfixable ones still exits `1`.

## Gating a script or a pipeline

Add `--json` and read the envelope's `status` key. The envelope carries four keys:

```json
{
  "schema": "vaultspec.vault.check.all.v1",
  "status": "unchanged",
  "data": { "checks": [] },
  "hints": { "text": "Your vault is clean. Proceed to commit your changes" }
}
```

`status` uses the sync vocabulary rather than a boolean. A clean run reports
`unchanged`, a run that repaired something reports `updated`, and a run with findings
left reports `failed`. Test for the failure value rather than for a success value, so a
new status does not read as a pass:

```bash
vaultspec-core vault check all --json | jq -e '.status != "failed"'
```

The exit code carries the same verdict and is simpler to gate on: `0` clean, `1`
findings. Diagnostic logging stays on stderr, so stdout is the envelope and nothing
else.

Each entry under `data.checks` carries its own `check_name`, `diagnostics`,
`fixed_count`, and `supports_fix`, so a report can name which check failed rather than
only that something did.

## What to run, and when

Run `vaultspec-core vault check all --fix` before you commit. It repairs the mechanical
problems and names the rest.

Run `vaultspec-core doctor` after installing or upgrading, and when something behaves in
a way the documentation does not explain. Most of what it catches is workspace drift.

Gate continuous integration on `vaultspec-core vault check all`. Prefer it over the
diagnosis: the workspace diagnosis fails on machine state, such as a missing hook or an
unapplied migration, which a pull request cannot fix.
