---
tags:
  - '#research'
  - '#test-provisioning-economics'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:2c5f71066ca6790aac51afef2977081cb8456dbcf9cb73a7040a49965686172c'
related: []
---

# `test-provisioning-economics` research: `Where the broad lane spends its time`

## Summary

The `broad` test lane is dominated by fixture setup, not by test bodies, and the
setup cost is dominated by a single syscall. Provisioning a test workspace costs
4-40 seconds depending on machine load, and 61% of that is `os.fsync`. 391 tests
pay it, for a durability property none of them asserts.

Everything below was measured on 2026-09-08 against `main` at `b5c7f256`, on a
24-logical-CPU Windows 11 workstation. The machine was concurrently running this
repository's own self-hosted CI runner, so absolute wall times are pessimistic;
the ratios and the profile shares are not affected by that.

## Findings

### Fixture setup is the suite

A full `broad` run (`pytest src/vaultspec_core -m "not repo and not benchmark and not claude" -n 12`) completed 4410 tests in 67m36s. The `pytest-durations`
fixture table for that run:

| fixture                            | total    | count | median | max   |
| ---------------------------------- | -------- | ----- | ------ | ----- |
| `tests/cli::synthetic_project`     | 3h59m53s | 391   | 19.5s  | 4m57s |
| `mcp_server/tests::vault_root`     | 53m31s   | 78    | 25.2s  | 5m31s |
| `test_adoption.py::fresh_clone`    | 20m10s   | 16    | 50.6s  | 5m30s |
| `test_executor.py::workspace`      | 16m29s   | 9     | 54.7s  | 6m05s |
| `test_tool_surface.py::vault_root` | 15m18s   | 7     | 2m21s  | 5m34s |
| `test_gateway.py::vault_root`      | 14m35s   | 16    | 24.7s  | 4m29s |
| `test_edit_engine.py::vault_root`  | 11m47s   | 22    | 20.8s  | 2m52s |
| grand total, all fixtures          | 6h46m42s | 7564  | 0.01s  | 6m05s |

Of the 25 slowest entries pytest reported, the large majority are `setup` rather
than `call`, at 200-365 seconds each. Test bodies are a small fraction of the
total.

The single fixture `synthetic_project` accounts for 59% of all fixture time.

### The fixtures rebuild an identical tree per test

`src/vaultspec_core/tests/cli/conftest.py:41` declares `synthetic_project` at
function scope. Each request runs `build_synthetic_vault(dest, n_docs=24, seed=42)` followed by `install_run(path=dest, provider="all", upgrade=False, dry_run=False, force=True)`.

Both halves are deterministic: the corpus is seeded, and the install is a
function of the bundled builtins plus that corpus. The 391 resulting trees are
byte-identical at the moment the fixture yields. Each contains 245 files.

The same shape recurs in other packages under other names:
`src/vaultspec_core/mcp_server/tests/conftest.py:33` (`vault_root`, via
`WorkspaceFactory(root).install()`), `test_adoption.py::fresh_clone`,
`test_executor.py::workspace`, `test_preflight.py::installed_workspace`.

Across the collected `broad` lane, 406 tests request `synthetic_project` and 173
request `factory`; `WorkspaceFactory.install()` is called 299 times in test
bodies.

### `os.fsync` is 61% of an install

`cProfile` over three consecutive `install_run(provider="all")` calls:

```
768985 function calls in 13.196 seconds

ncalls  tottime  cumtime  filename:lineno(function)
     3    0.000   12.953  core/provision.py:683(install_run)
   426    0.011   10.812  core/helpers.py:637(atomic_write_bytes)
   426    8.043    8.043  {built-in method nt.fsync}
   468    1.490    1.490  {built-in method nt.open}
   687    0.878    0.880  {built-in method nt.mkdir}
   426    0.798    0.799  {built-in method nt.replace}
```

`nt.fsync` is 8.043s of 13.196s. One call per file written, 426 per install.

### Removing the fsync is worth 13x, and removes the variance

Interleaved A/B, alternating strategies within one process so machine drift
affects both arms equally, six samples each:

```
install (fsync on)           : median 40.10s  [40.2, 72.0, 50.8, 18.0, 40.0, 15.9]
install (fsync off)          : median  3.08s  [11.4, 10.9,  2.5,  2.1,  3.6,  2.1]
copytree of prebuilt template: median  2.13s  [ 3.5,  6.4,  1.9,  2.4,  1.3,  0.9]
```

The median ratio is 13x for fsync suppression and 19x for cloning a prebuilt
tree. The spread matters more than the median: with fsync on, the slowest sample
is 4.5x the fastest, because `fsync` serialises at the device and therefore
competes with every other writer on the volume rather than scaling with CPU.

Uncontended, the same install measures ~4.3s, of which ~2.7s is fsync - the same
61% share.

### No test asserts the durability property

`os.fsync` appears exactly once in the source tree, at
`src/vaultspec_core/core/helpers.py:681`, inside `atomic_write_bytes`.

The atomicity of that helper does not depend on it: atomicity comes from `O_EXCL`
temp creation (`helpers.py:505`) plus `os.replace` (`helpers.py:587`). The
`fsync` buys durability across power loss.

No test asserts that property, and the suite says so in its own words at
`src/vaultspec_core/core/tests/test_manifest_exclusive_atomicity.py:14`: the
durability half of the change, fsync ordering under power loss, is not tested.

No ADR mentions `fsync`. Ten ADRs name `atomic_write` or `atomic_write_bytes` as
the shared write path without stating what it guarantees.

### Parallelism alone does not fix an fsync-bound suite

`pytest-xdist>=3.8.0` is declared at `pyproject.toml:106` and no lane passes
`-n`; every target in `dev/toolchain.py:505-608` is single-process.

Running the lane at `-n 12` on 24 logical CPUs did not produce a 12x
improvement. The fixture setup medians in that run, 19.5s for
`synthetic_project`, are several times the uncontended single-process cost of
~4.3s, which is the signature of workers queueing on the device rather than
scaling. Ordering follows: the durability boundary has to move before
parallelism pays.

## Sources

- `pytest --durations` and `pytest-durations` fixture tables from a full `broad`
  run at `-n 12`, 2026-09-08.
- `cProfile` over `install_run(provider="all")`, three iterations after a warm-up.
- Interleaved A/B harness alternating fsync-on, fsync-off and `shutil.copytree`,
  six samples per arm, one process.
- `src/vaultspec_core/tests/cli/conftest.py:41`
- `src/vaultspec_core/mcp_server/tests/conftest.py:33`
- `src/vaultspec_core/core/helpers.py:637`, `:681`, `:505`, `:587`
- `src/vaultspec_core/core/tests/test_manifest_exclusive_atomicity.py:14`
- `pyproject.toml:106`, `dev/toolchain.py:505-608`
