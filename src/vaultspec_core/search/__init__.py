"""Hosted vault search: ranked records with verbatim excerpts.

Search runs on the TypeSafe Jev model when a hosted-search credential is
configured, and reports ``not_configured`` otherwise. Every outcome that did
not rank names the search to run instead: a vaultspec-rag vault search when
the workspace provisions rag, core's listing verbs and grep when it does not.
It never calls vaultspec-rag.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._capability import DiscoveryCapability as DiscoveryCapability
from ._capability import discovery_capability as discovery_capability
from ._capability import discovery_fields as discovery_fields
from ._capability import hosted_search_config as hosted_search_config
from ._corpus import SEARCHABLE_TYPES as SEARCHABLE_TYPES
from ._filters import SEARCHABLE_TYPE_NAMES as SEARCHABLE_TYPE_NAMES
from ._lexical import tokenize as tokenize
from ._models import DEFAULT_RESULTS as DEFAULT_RESULTS
from ._models import EXCERPT_BYTES as EXCERPT_BYTES
from ._models import MAX_QUERY_CHARS as MAX_QUERY_CHARS
from ._models import MAX_RESULTS as MAX_RESULTS
from ._models import SUPPORTING_BYTES as SUPPORTING_BYTES
from ._models import Excerpt as Excerpt
from ._models import InvalidQueryError as InvalidQueryError
from ._models import NextStep as NextStep
from ._models import NextStepKind as NextStepKind
from ._models import SearchHit as SearchHit
from ._models import SearchOutcome as SearchOutcome
from ._models import SearchStatus as SearchStatus
from ._models import SearchUsage as SearchUsage
from ._models import SearchVerdict as SearchVerdict
from ._models import UnavailableReason as UnavailableReason
from ._models import UnsearchableTypeError as UnsearchableTypeError
from ._questions import PREMISE_CONFLICT_THRESHOLD as PREMISE_CONFLICT_THRESHOLD
from ._remediation import remediation as remediation
from ._wire import SCORE_PLACES as SCORE_PLACES
from ._wire import hit_fields as hit_fields
from ._wire import outcome_fields as outcome_fields

__all__ = [
    "DEFAULT_RESULTS",
    "EXCERPT_BYTES",
    "MAX_QUERY_CHARS",
    "MAX_RESULTS",
    "PREMISE_CONFLICT_THRESHOLD",
    "SCORE_PLACES",
    "SEARCHABLE_TYPES",
    "SEARCHABLE_TYPE_NAMES",
    "SUPPORTING_BYTES",
    "DiscoveryCapability",
    "Excerpt",
    "InvalidQueryError",
    "NextStep",
    "NextStepKind",
    "SearchHit",
    "SearchOutcome",
    "SearchStatus",
    "SearchUsage",
    "SearchVerdict",
    "UnavailableReason",
    "UnsearchableTypeError",
    "discovery_capability",
    "discovery_fields",
    "hit_fields",
    "hosted_search_config",
    "outcome_fields",
    "remediation",
    "search_vault",
    "tokenize",
]

if TYPE_CHECKING:
    from ._service import search_vault as search_vault


def __getattr__(name: str) -> object:
    # The service pulls in the HTTPS transport (ssl, http.client). Every CLI
    # start imports this package for its constants, so the transport loads
    # only when a search actually runs.
    if name == "search_vault":
        from ._service import search_vault

        return search_vault
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
