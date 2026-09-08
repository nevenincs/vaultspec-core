"""Worktree initialization: the one command a fresh checkout needs.

``just init`` makes the current worktree usable from a bare checkout, and is
the single command any tool - a human, a git hook, an agent, the worktree
provisioner - calls after creating one. It never asks a question, never needs
an argument, and is always safe to run again.

This package is the implementation behind that recipe, and it is subject to
three constraints the rest of ``dev/`` is not:

It runs BEFORE the virtual environment exists.
    So it is invoked on an ephemeral interpreter
    (``uv run --no-project --python <pin> -- python -m dev.init``) and imports
    only the standard library plus :mod:`dev.exit_codes`, which is itself
    stdlib-only. It must never import :mod:`dev.toolchain`, :mod:`dev.runner`,
    or anything reached through ``uv run --no-sync python -m dev``: those
    presume the environment this package is responsible for creating.

It is the same command in every repository.
    Every module here except :mod:`dev.init.plan` is byte-identical across
    ``vaultspec-core``, ``vaultspec-rag``, ``vaultspec-dashboard``,
    ``vaultspec-a2a`` and ``cadrumo``. :mod:`dev.init.plan` is the one file
    that states what THIS repository's bootstrap actually is, declaratively, as
    data. A repository's initialization differs in its steps, never in its
    contract.

Its failures are read by machines.
    A provisioner needs to tell "your workstation is missing Node" apart from
    "the lockfile is broken" apart from "an editor is holding the venv open",
    without parsing prose. Hence the exit codes in :mod:`dev.exit_codes` and
    the JSON report every run writes.

Modules:
    :mod:`dev.init.contract`: Phases, step and result records, the NDJSON
        event stream, and the report schema.
    :mod:`dev.init.process`: Subprocess execution, output capture, and the
        classification of a failure into a contract exit code.
    :mod:`dev.init.probe`: Host-tool discovery and version comparison.
    :mod:`dev.init.stamp`: Input digests and the idempotence stamp that makes
        a second run a sub-second no-op.
    :mod:`dev.init.plan`: THIS repository's phases. The only file that differs.
"""

from __future__ import annotations

__all__ = ["__doc__"]
