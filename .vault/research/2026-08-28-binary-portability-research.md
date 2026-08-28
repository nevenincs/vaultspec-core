---
tags:
  - '#research'
  - '#binary-portability'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:29285b4b12b8c14ccea1e3ca394c26271d4aa61899883eeea00a65cfe1e99689'
related: []
---

# `binary-portability` research: `what the standalone binaries actually promise on each platform`

The release publishes eight binaries across four target triples and calls them
standalone. Measured against the platforms the project's own install
documentation names, three of the four targets do not hold that promise: the
Linux binary cannot load at all on any currently-supported enterprise or LTS
distribution, and no binary on any platform runs without network access on
first launch. None of this is caught before publishing, because no release
artifact is ever executed by the pipeline that produces it.

The common cause is that the binaries' platform contract is inherited from
whatever the build machines happen to be, rather than declared and asserted.
What the ADR must settle is what that contract is, and where it is enforced.

## Findings

### The Linux binary cannot load on Debian 12, Ubuntu 22.04, or RHEL 9

The published `vaultspec-core-x86_64-unknown-linux-gnu` from
`vaultspec-core-v0.1.60` fails in the dynamic loader, before `main`, on every
distribution tested:

| image                  | glibc | result                           |
| ---------------------- | ----- | -------------------------------- |
| `debian:bookworm-slim` | 2.36  | `version 'GLIBC_2.39' not found` |
| `ubuntu:22.04`         | 2.35  | `version 'GLIBC_2.39' not found` |
| `almalinux:9`          | 2.34  | `version 'GLIBC_2.39' not found` |

The floor comes from exactly two symbols, both referenced weakly, both from the
Rust standard library's pidfd-aware process spawn path:

```
$ objdump -T vaultspec-core-x86_64-unknown-linux-gnu | grep GLIBC_2.39
w DF *UND* (GLIBC_2.39) pidfd_spawnp
w DF *UND* (GLIBC_2.39) pidfd_getpid
```

Every other symbol in the binary resolves at `GLIBC_2.34` or below, and the
only shared objects it needs are `libc.so.6`, `libm.so.6` and `libgcc_s.so.1`.
Weak binding does not help: the loader's version check reads the
`.gnu.version_r` entry rather than the symbol binding, so a missing version
definition is fatal regardless.

The binding constraint among the platforms named above is RHEL 9 and its
rebuilds at `GLIBC_2.34`; a floor at or below that covers all three.

### The floor is inherited from the build runner, not chosen

Neither `.github/workflows/binaries.yml` nor `dev/binaries/build_pyapp.py`
pins a glibc floor, a container, or a sysroot for the Linux target. The Linux
build runner is a WSL Ubuntu host reporting `ldd (Ubuntu GLIBC 2.43) 2.43`, and
the binary inherits that. The floor therefore moves on its own whenever the
runner is upgraded, which is why the regression arrived without a code change
and without a failing job.

`x86_64-unknown-linux-gnu` is the only target where the host's system libraries
leak into the artifact this way; the macOS and Windows targets pin their
platform floor through the SDK and the CRT respectively.

### Building in an old-glibc container removes the floor without losing the code path

A probe exercising `std::process::Command` - the path that pulls the pidfd
symbols - was compiled with stable Rust 1.98.0 inside
`quay.io/pypa/manylinux_2_28_x86_64`, whose glibc is 2.28. The two pidfd
symbols are still referenced, and the highest version the binary requires is
`GLIBC_2.28`:

```
GLIBC_2.2.5  GLIBC_2.3  GLIBC_2.3.4  GLIBC_2.9  GLIBC_2.14
GLIBC_2.15   GLIBC_2.16 GLIBC_2.18   GLIBC_2.28
```

This is the mechanism the fix depends on: when the link-time libc does not
define `pidfd_spawnp`, the reference stays an unversioned undefined weak
symbol, no `.gnu.version_r` entry is emitted for it, and the runtime lookup
still succeeds on a newer host. The pidfd fast path is therefore kept where the
target has it, rather than compiled out.

`manylinux_2_28` is one available baseline and not the only one; any image
whose glibc is at or below the intended floor behaves the same way. What it
demonstrates is that pinning the floor costs nothing at runtime.

### No binary is standalone on first run

`build_pyapp.py:113` sets `PYAPP_DISTRIBUTION_EMBED=1`, which embeds the
CPython runtime, but the project itself is configured by name and version
(`PYAPP_PROJECT_NAME`, `PYAPP_PROJECT_VERSION`), so PyApp resolves
`vaultspec-core==<version>` from PyPI into a per-user data directory on first
launch. The binary carries an interpreter but not the code it runs.

The consequence is that every target is offline-hostile on first run, and that
a release is not usable until the PyPI publish has landed - an ordering
dependency the binaries workflow does not express. `pyapp@0.29.0` exposes
`PYAPP_PROJECT_PATH`, which embeds a local wheel instead, and is the mechanism
that would make the artifacts match the claim.

### Nothing executes a release artifact before it is published

The build matrix compiles four targets and uploads them; no job runs any of
them. The macOS x86_64 binary is additionally cross-built on the Apple Silicon
runner (`binaries.yml`, `macos-x86_64` matrix entry) and so is executed on no
machine at any point, including by a human.

A single execution of each artifact on a machine matching its target would have
caught the glibc regression, and an execution in a network-isolated environment
would have caught the bootstrap dependency. The cross-built Intel macOS binary
is the one case where the build fleet cannot self-verify, because no Intel
macOS host is registered.

### Signing and notarization are absent on both signed platforms

The Windows binaries carry no Authenticode signature and the macOS binaries are
ad-hoc signed rather than notarized, so Gatekeeper rejects a browser-downloaded
macOS binary outright and SmartScreen warns on the Windows one. Neither is a
portability defect in the loader sense, but both are part of the same question:
what a published binary is required to satisfy before it is allowed to become a
release asset. They are recorded here so the ADR can decide whether the
enforcement point it establishes covers them, and are not otherwise
investigated.

### What was not investigated

Whether the full PyApp build - as opposed to the probe above - succeeds inside
the same container; it needs `cargo` and `uv`, neither of which the image
carries by default. Whether embedding
the project wheel changes the artifact size enough to matter - the Linux binary
is currently 37 MB and the wheel is small, but this was not measured. Whether
the `linux-arm64` runner already registered to the repository should carry an
`aarch64-unknown-linux-gnu` target, which is a matrix-coverage question rather
than a portability one. No macOS host was reachable for direct inspection, so
every macOS claim here is drawn from the published artifacts and the workflow
definition rather than from a run.

## Sources

- `.github/workflows/binaries.yml`
- `dev/binaries/build_pyapp.py:108`
- `dev/binaries/build_pyapp.py:113`
- `vaultspec-core-v0.1.60` release assets
- `pyapp@0.29.0`
- https://ofek.dev/pyapp/latest/config/project/
- https://github.com/pypa/manylinux
