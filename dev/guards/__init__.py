"""Repository-wide contract guards.

Every other tree in this repository puts its tests beside the thing they
exercise: :mod:`dev.audit`, :mod:`dev.binaries`, :mod:`dev.health`,
:mod:`dev.statistics` and ``docs/_render`` each carry a cohabiting ``tests``
package, and the library's suites sit inside ``src/vaultspec_core``. These
guards have no such module to sit beside, because their SUBJECT is the
repository's own committed configuration - the CI workflows, the ``justfile``,
the verb registry, ``pyproject.toml``, the installed ``.vaultspec/templates``,
and the hand-written stubs in ``typings/``. There is no importable unit to
cohabit with, so they cohabit with the harness that runs them instead, and the
test modules sit directly in this package rather than behind an empty
instrument shell that exists only to hold a ``tests`` directory.

Each module resolves whatever repository paths it needs from its own location
or from the ``repo_root``/``pyproject`` fixtures in ``dev/conftest.py``. There
is deliberately no shared constants module: a guard that imports its notion of
the repository layout from a sibling test package makes the layout a
test-suite-owned fact rather than a fact of the checkout, which is precisely
the coupling that emptying the repository root was meant to remove.
"""

from __future__ import annotations
