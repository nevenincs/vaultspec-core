"""Smoke instruments run against built distribution artifacts.

:mod:`dev.smoke.smoke_check` is not a pytest module and is never collected: it
is executed as a script by ``.github/workflows/publish.yml`` against an
installed wheel and an installed sdist, in an isolated environment that has
this repository's source tree on disk but NOT on ``sys.path``. It therefore
imports nothing from ``dev`` - this package exists to give the instrument a
named home beside the rest of the development tooling, not to be imported by
it.
"""

from __future__ import annotations
