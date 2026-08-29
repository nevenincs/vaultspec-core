---
tags:
  - '#research'
  - '#offline-binaries'
date: '2026-08-29'
modified: '2026-08-29'
body_schema: 'body-v2'
body_hash: 'sha256:7fe323f43aa8886017b42c7890bf85032b8d5000b53f2c35a27ef19b6c8b214a'
related: []
---

# `offline-binaries` research: `what a standalone binary must contain to start without a network`

The release calls its binaries standalone and they are not: each one downloads
on first launch and fails without a network. The obvious remedy - embed the
project wheel - does not fix it, and the reason it does not is the whole point
of this note. What follows establishes what the binary would actually have to
carry, and what building that costs on a fleet where one target is cross-built.

## Findings

### Embedding the wheel removes one download, not the network

`build_pyapp.py` configures the project by identifier - `PYAPP_PROJECT_NAME`
plus `PYAPP_PROJECT_VERSION` - so PyApp resolves `vaultspec-core==<version>`
from PyPI into a per-user data directory on first launch.

`PYAPP_PROJECT_PATH` replaces that identifier with an embedded wheel. It is
tempting to read this as the fix, and it is not: PyApp's own documentation
frames all three project options as *installation sources*, and says none of
them "occur when disabled". Embedding the wheel changes what is installed, not
whether an install happens.

The install still resolves the dependency closure. `vaultspec-core` declares
twelve runtime dependencies, and the ones that matter here are
`pydantic`, `rustworkx` and `PyYAML` - all carrying compiled extensions. So a
binary built this way stops fetching the project and still fetches its
dependencies. The 122 MB first-run download shrinks; offline still fails.

### The switch that actually turns installation off

`PYAPP_SKIP_INSTALL` is the option the problem calls for, and it is only
meaningful alongside distribution embedding. PyApp states the combination
plainly: it "allows for entirely predefined distributions and thus no network
calls at runtime if used in conjunction with distribution embedding".

Distribution embedding has two forms. `PYAPP_DISTRIBUTION_EMBED` - already set
here - bakes in the stock python-build-standalone archive, which contains an
interpreter and nothing else. `PYAPP_DISTRIBUTION_PATH` points at a *local*
archive instead and implicitly embeds it; the archive is expected to look like
a stock distribution, an interpreter ready for use.

So the offline binary needs a distribution archive that is the stock one plus
the application and its dependency closure already installed into it. That
artifact does not exist today and nothing in the release builds it.

### The prepared distribution is per-target, and one target has no host

Because `pydantic`, `rustworkx` and `PyYAML` ship native code, the prepared
archive is platform-specific even though `vaultspec-core` itself is pure
Python. One archive cannot serve the matrix; each build leg needs its own,
containing wheels built for that leg's platform and interpreter.

Four of the five legs can prepare their own natively. The fifth cannot:
`macos-x86_64` is cross-built on the Apple Silicon runner because no Intel
macOS host is registered, so it cannot execute an Intel interpreter to install
into. Installing for a foreign platform is possible without executing it -
resolving with an explicit platform tag and binary-only wheels unpacks the
right artifacts - but that path is materially different from the other four
and is the one most likely to produce a subtly wrong archive.

`PYAPP_FULL_ISOLATION` is adjacent: it gives each installation a full copy of
the distribution rather than a virtual environment layered over a shared one.
It was not investigated in depth, but a predefined distribution and a venv
built on top of it are in tension, so it likely belongs in the same decision.

### It reorders the release

Today the binaries are built from an already-published PyPI version: the tag is
published first, then `binaries.yml` is dispatched for that tag. A prepared
distribution has to contain the wheel, so the wheel must exist before the
binaries build. That inverts the current order and removes the release's
dependency on PyPI propagation - which is a gain, but a structural change to
the publish pipeline rather than a build flag.

### The pre-publish execution gate depends on this

A smoke run of each artifact before publishing proves little while the artifact
still needs the network to start: on a runner with connectivity it would pass
by downloading, which is precisely the behaviour under question, and it cannot
distinguish "works" from "successfully fetched". Once installation is skipped,
the same run becomes meaningful - it exercises the bytes that ship.

That makes the ordering between the two one-way: the execution gate is worth
little before the offline work and nearly free after it.

### What was not investigated

Artifact size. The Linux binary is 37 MB today with an embedded interpreter and
no application; adding the application and its dependency closure will grow it,
and by how much was not measured. Whether `python-build-standalone` archives
can be re-packed in place, or whether the prepared archive must be assembled
from an unpacked copy, was not established. Whether `PYAPP_ALLOW_UPDATES` is
wanted once `update` stops being available under skipped installation was not
considered. No macOS host was reachable, so every claim about the two Darwin
legs is drawn from the workflow definition rather than from a run.

## Sources

- `dev/binaries/build_pyapp.py`
- `.github/workflows/binaries.yml`
- `pyproject.toml`
- `pyapp@0.29.0`
- https://ofek.dev/pyapp/latest/config/project/
- https://ofek.dev/pyapp/latest/config/installation/
- https://ofek.dev/pyapp/latest/config/distribution/
