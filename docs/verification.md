# Check your workspace and feature records

Choose the command for what you need to check:

| Check                                    | Command                          |
| ---------------------------------------- | -------------------------------- |
| Workspace installation and vault records | `vaultspec-core doctor`          |
| Vault records only                       | `vaultspec-core vault check all` |
| Workspace installation only              | `vaultspec-core spec doctor`     |

Run commands from your workspace root. Each command also accepts `--target DIR` to check
another workspace and `--json` for structured output.

<p id="checking-everything-at-once"></p>

## Check after installation or an upgrade

```sh
vaultspec-core doctor
```

Address the reported problems and rerun the command. To check only the installed
workspace configuration, use `vaultspec-core spec doctor`.

Some printed warnings are informational and don't affect the exit code. See the
[workspace diagnostic reference](./CLI.md#vaultspec-core-spec-doctor) for the checks and
warning rules.

<p id="checking-only-the-vault"></p>
<p id="repairing-what-can-be-repaired"></p>
<p id="what-to-run-and-when"></p>

## Check records before committing

After editing feature records, run:

```sh
vaultspec-core vault check all
```

Use the findings to locate records that need attention. For the full check inventory and
available flags, see the [vault check reference](./CLI.md#vaultspec-core-vault-check).

To apply supported corrections:

```sh
vaultspec-core vault check all --fix
```

This command modifies files. Review its changes with `git diff`, correct any remaining
problems, and rerun `vaultspec-core vault check all` before committing. Errors that
remain after `--fix` still make the command fail.

To investigate one check separately, name it explicitly. For example:

```sh
vaultspec-core vault check dangling
```

<p id="checking-the-code-boundary"></p>

## Check source references to vault documents

```sh
vaultspec-core vault check code-boundary
```

The `all` check excludes `code-boundary`. Read this command's findings directly: its
advisory warnings don't fail the command, so a successful exit doesn't mean it found no
references.

<p id="gating-a-script-or-a-pipeline"></p>
<p id="which-printed-lines-change-the-exit-code"></p>

## Use checks in automation

In continuous integration (CI), invoke `vaultspec-core vault check all` directly and use
its exit code to determine success.

| Command                 | Exit `0`                      | Exit `1`                    | Exit `2`              |
| ----------------------- | ----------------------------- | --------------------------- | --------------------- |
| `doctor`, `spec doctor` | No counted warnings or errors | Counted warnings, no errors | Errors                |
| `vault check all`       | No errors; warnings allowed   | Errors                      | Not used for findings |

Only `spec doctor` accepts `--gate-errors`. Use
`vaultspec-core spec doctor --gate-errors` when automation should accept workspace
warnings: warnings return `0`, and errors return `2`.
