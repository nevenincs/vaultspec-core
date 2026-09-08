# The exit-code contract

A command's exit code is its contract with CI and with the developer. This
document is the canonical statement of that contract. It is identical in
`vaultspec-core`, `vaultspec-rag`, `vaultspec-dashboard`, `vaultspec-a2a` and
`cadrumo`, and the numbers it names live in `dev/exit_codes.py`, which is the
machine-readable form of this page. `dev/guards/test_exit_code_contract.py`
enforces both.

## The governing distinction

A tool that RAN and found something is not the same event as a tool that FAILED
TO RUN. The first is a measurement; the second is the absence of one. Any
mechanism that maps both onto the same status is lying, and the shape it
usually takes is `some-scanner ; exit 0`: a literal `exit 0` maps *every*
non-zero status onto success, so a scanner that was never installed, whose
config no longer parses, or that segfaulted halfway through reports exactly
like a clean run — and keeps reporting it, silently, for as long as nobody
looks.

Advisory intent is legitimate. The mechanism must be structural: the target
declares `advisory=True`, and the runner suppresses only the statuses that mean
"findings" (`FINDINGS_CODES`, which is `{1}` for every scanner in this fleet).
Anything else propagates as `ADVISORY_BROKEN` (7).

## Verb classes, keyed to CONSEQUENCE

| Verb class | Gates?                          | 0 means                            | Non-zero means                                                                            |
| ---------- | ------------------------------- | ---------------------------------- | ----------------------------------------------------------------------------------------- |
| `check-*`  | yes                             | read-only inspection found nothing | a finding, or the checker could not run                                                   |
| `fix-*`    | on failure only                 | the repair pass completed          | the repair pass failed; `5` under `VAULTSPEC_FIX_STRICT` when it had to change something  |
| `test-*`   | yes                             | tests ran and passed               | a failure, or `8` when nothing ran                                                        |
| `audit-*`  | **no**, except dependency audit | the scan completed                 | `7` when the scanner could not run; for the dependency audit, `1` on a published advisory |
| `build-*`  | yes                             | artefacts produced                 | the build failed                                                                          |
| `health-*` | never                           | always; the output is the product  | —                                                                                         |

`check` is read-only and `fix` mutates: that is the whole of the difference
between them, and it is why `fix` may not be used as a gate. A `fix` that
exited non-zero because it changed a file would make every clean local
development loop red.

### The `audit` collision, resolved

`vaultspec-dashboard` treated `audit-*` as gating; `vaultspec-core`,
`vaultspec-rag` and `cadrumo` treated it as advisory-exit-0. Same verb,
opposite meaning. The resolution is not to move recipes but to state the rule
the fleet already half-followed:

> **`audit` is advisory, except the DEPENDENCY audit, which gates.**

A published advisory against a version this repository has pinned is a verdict
about a specific artefact, and the remedy is mechanical: change the pin. A
duplication, dead-code, complexity or shadowing scan yields a lead to confirm
by hand. Dashboard's `audit` verb is *entirely* supply-chain — python, rust and
node dependency trees — so it gates in full and never collided; it was
undocumented, not wrong. Its `node-tooling` target audits build tooling that
never reaches a user, and is advisory.

Lane L8 owns the dependency gate's implementation. It gates with `FAILED` (1)
and must fail CLOSED: `uv audit` is a preview feature that has historically
exited 0 while printing advisories, so the verdict is derived from the printed
summary AND the exit code, never from the exit code alone.

## The numbers

| Code | Name                     | Meaning                                                                                       |
| ---- | ------------------------ | --------------------------------------------------------------------------------------------- |
| 0    | `OK`                     | ran; nothing that gates                                                                       |
| 1    | `FAILED`                 | ran; reported a gating result                                                                 |
| 2    | `INIT_HOST_TOOL_MISSING` | `just init`: a required host tool is absent (L6)                                              |
| 3    | `INIT_STALE`             | `just init`: environment stale relative to its inputs (L6)                                    |
| 4    | `INIT_STEP_FAILED`       | `just init`: one bootstrap step failed (L6)                                                   |
| 5    | `DRIFT`                  | managed content differs from its generated form (L6; also `fix` under `VAULTSPEC_FIX_STRICT`) |
| 6    | `INIT_LOCKED`            | `just init`: the environment is held open by another process (L6)                             |
| 7    | `ADVISORY_BROKEN`        | an advisory target's tool failed to RUN                                                       |
| 8    | `NOTHING_SELECTED`       | nothing ran: empty selection, or every test skipped                                           |
| 127  | `TOOL_MISSING`           | required tool absent, no fallback                                                             |

2–6 are L6's `just init` codes, adopted unchanged. Outside `init`, an absent
executable found at dispatch time is `127` — the shell's own
command-not-found status, legible without a lookup table. `init` keeps `2`
because its report distinguishes *which* host tool, and callers of `init`
already read that report.

## Aggregators: one rule

`check-all`, `fix-all`, `audit-all`, `test-all` and `build-all` **run every
step and report, and exit with the first non-zero status they saw.** They do
not stop at the first failure.

`cadrumo` previously had four rules in one justfile — `check-all` ran
everything, `fix-all` was fail-fast `just` dependencies, `audit-all` always
exited 0, `test-all` iterated fifteen lanes continue-on-failure — which made
"what does `-all` mean here" unanswerable without reading the body.

Run-all is the rule because an aggregate's purpose is a complete picture per
invocation. Fail-fast costs one CI round-trip per defect and hides the
correlation between them; the developer who ran `check-all` wanted the list.
Individual targets remain fail-fast: within one target the later steps usually
presuppose the earlier ones.

The consequence for construction: an `-all` aggregate is a target inside `dev/`
with `keep_going=True`, composing the others by reference. It is **not** a
`just` dependency chain, because `just` dependencies are unconditionally
fail-fast and cannot express this rule.

## Partial and skipped work

A run that proved nothing must not read as a run that proved everything.

- A test lane that collected no tests exits `8` (`NOTHING_SELECTED`). The
  runner maps pytest's own status `5` onto it.
- A lane legitimately permitted to be empty sets
  `VAULTSPEC_ALLOW_EMPTY_SELECTION=1`, which is a declaration in the toolchain
  table, not a flag typed at a prompt.
- A hardware-gated lane whose tests all skip — `rag`'s GPU tiers on a host with
  no CUDA — is the case this rule exists for. pytest exits 0 for an all-skipped
  run, so `-ra` (lane L3) makes the skips visible in the log, and a lane that
  can skip *wholesale* is declared advisory rather than gating, so it cannot
  contribute a green verdict it did not earn.
- An optional tool that is simply absent is reported and skipped by
  `ToolOrSkip`, which only an advisory target may use. A gate that silently
  passes when its tool is missing is not a gate — it resolves to `127`.

## Where the contract lives

- `dev/exit_codes.py` — the constants and the two mapping functions.
- `dev/runner.py` / `dev/__main__.py` — the single place advisory suppression
  and selection mapping are applied.
- `dev/guards/test_exit_code_contract.py` — the guard. It asserts the mapping
  functions behave as written and that no justfile recipe re-implements a
  swallow (`; exit 0`, a trailing bare `exit 0`, `|| true`,
  `continue-on-error` inside a recipe body).

`dev/guards/` is why `vaultspec-core` and `vaultspec-dashboard` held their
shape while the other three drifted. The guard is the durable part of this
contract; the prose is only its explanation.
