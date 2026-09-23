"""ADR cross-referencing: the decisions an ADR should link, judged within fixed bounds.

A source ADR is judged against every other ADR of the vault in three stages:
a code-only rank over the whole corpus, one Choice stage over a fixed pool,
and a pair judgment over a fixed cut. The stages run on TypeSafe Jev under
the hosted-search credential, transport and consent; without a key nothing is
sent and the outcome is ``not_configured``. Every run's cost has a ceiling
that does not depend on the size of the vault.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._models import Bounds as Bounds
from ._models import CorpusTooLargeError as CorpusTooLargeError
from ._models import CrossrefOutcome as CrossrefOutcome
from ._models import CrossrefStatus as CrossrefStatus
from ._models import CrossrefUsage as CrossrefUsage
from ._models import InvalidSourceError as InvalidSourceError
from ._models import SweepOutcome as SweepOutcome
from ._models import Verdict as Verdict
from ._models import VerdictKind as VerdictKind
from ._questions import DEFAULT_SOURCES as DEFAULT_SOURCES
from ._questions import MAX_SOURCES as MAX_SOURCES
from ._wire import REPLY_VERDICTS as REPLY_VERDICTS
from ._wire import outcome_fields as outcome_fields
from ._wire import remediation as remediation
from ._wire import sweep_fields as sweep_fields

__all__ = [
    "DEFAULT_SOURCES",
    "MAX_SOURCES",
    "REPLY_VERDICTS",
    "Bounds",
    "CorpusTooLargeError",
    "CrossrefOutcome",
    "CrossrefStatus",
    "CrossrefUsage",
    "InvalidSourceError",
    "SweepOutcome",
    "Verdict",
    "VerdictKind",
    "crossref_adr",
    "crossref_sweep",
    "outcome_fields",
    "remediation",
    "sweep_fields",
]

if TYPE_CHECKING:
    from ._service import crossref_adr as crossref_adr
    from ._service import crossref_sweep as crossref_sweep


def __getattr__(name: str) -> object:
    # The service pulls in the HTTPS transport; surfaces import this package
    # for its constants at start-up, so the transport loads only on a run.
    if name in ("crossref_adr", "crossref_sweep"):
        from . import _service

        return getattr(_service, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
