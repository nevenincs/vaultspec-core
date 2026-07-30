"""The composed code-health measurement report.

The distinction against the top level of :mod:`dev` is deliberate. The modules
directly under ``dev/`` are the *harness*: they declare which command each
``justfile`` verb runs and execute it, and they import only the standard
library so dispatch behaves identically on every platform. Each sub-package
beside them is an *instrument* a verb invokes when the measurement is too large
to express as a command line, and is free to depend on whatever it measures
with.

Nothing here ships. ``[tool.hatch.build.targets.wheel]`` packages only
``src/vaultspec_core``, so this tree exists for the repository's own
maintenance and is imported by its cohabiting tests rather than by the package.

Modules:
    :mod:`dev.health.health_report`: The composed code-health measurement
        report, driven by the ``health`` verb.
"""

from __future__ import annotations
