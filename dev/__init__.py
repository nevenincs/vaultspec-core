"""Platform-agnostic backend for the repository's ``justfile`` harness.

The ``justfile`` declares *what* each development verb is; this package
implements *how* it runs. Every recipe body is therefore a single portable
command - ``uv run --no-sync python -m dev <verb> <target>`` - with no shell
branching, no ``sh``-versus-PowerShell dialect, and no platform-specific
script backing it.

The split matters because the alternative drifts. Encoding the toolchain in
shell means writing every non-trivial recipe twice, once per dialect, and the
two copies diverge the moment one is edited. Here the branching that genuinely
exists - a tool being present or falling back to its Docker image, a chain
stopping at its first failure, an advisory scan reporting without gating -
lives in one place, in :mod:`dev.runner`, and is exercised identically on
every platform.

This package imports only the standard library. It is the entry point a fresh
clone reaches before any dependency is installed, so a third-party import here
would make the harness unable to bootstrap the environment it needs.

Modules:
    :mod:`dev.runner`: Process execution, tool resolution, Docker fallback.
    :mod:`dev.toolchain`: The declarative verb and target registry.
"""

from __future__ import annotations
