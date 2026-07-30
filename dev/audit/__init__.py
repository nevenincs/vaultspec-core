"""The supply-chain audit gate.

The ``audit deps`` verb is the one audit target that gates, and it runs the
module here rather than a bare ``uv audit`` because the triage decision - which
published advisories against this locked set are already accounted for - is
code with its own test coverage, not a flag.

Nothing in :mod:`vaultspec_core` imports this package and the published wheel
does not ship it. The package marker exists so the gate is importable under its
real dotted name (``dev.audit.dependency_audit``), which is what lets the
cohabiting :mod:`dev.audit.tests` package exercise it directly.

Modules:
    :mod:`dev.audit.dependency_audit`: The ``uv audit`` supply-chain gate.
"""

from __future__ import annotations
