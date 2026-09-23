"""Hosted vault search: ranked records with verbatim excerpts.

Search runs on the TypeSafe Jev model when a hosted-search credential is
configured, and reports ``not_configured`` otherwise, so the caller can route
to the agent-level fallback. It never calls vaultspec-rag.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._corpus import SEARCHABLE_TYPES as SEARCHABLE_TYPES
from ._credential import CREDENTIAL_VARIABLE as CREDENTIAL_VARIABLE
from ._credential import hosted_search_config as hosted_search_config
from ._lexical import tokenize as tokenize
from ._models import DEFAULT_RESULTS as DEFAULT_RESULTS
from ._models import EXCERPT_CHARS as EXCERPT_CHARS
from ._models import MAX_QUERY_CHARS as MAX_QUERY_CHARS
from ._models import MAX_RESULTS as MAX_RESULTS
from ._models import SUPPORTING_CHARS as SUPPORTING_CHARS
from ._models import CredentialSource as CredentialSource
from ._models import Excerpt as Excerpt
from ._models import HostedSearchConfig as HostedSearchConfig
from ._models import SearchHit as SearchHit
from ._models import SearchOutcome as SearchOutcome
from ._models import SearchStatus as SearchStatus
from ._models import SearchUsage as SearchUsage
from ._models import UnavailableReason as UnavailableReason
from ._questions import PREMISE_CONFLICT_THRESHOLD as PREMISE_CONFLICT_THRESHOLD
from ._remediation import remediation as remediation

__all__ = [
    "CREDENTIAL_VARIABLE",
    "DEFAULT_RESULTS",
    "EXCERPT_CHARS",
    "MAX_QUERY_CHARS",
    "MAX_RESULTS",
    "PREMISE_CONFLICT_THRESHOLD",
    "SEARCHABLE_TYPES",
    "SUPPORTING_CHARS",
    "CredentialSource",
    "Excerpt",
    "HostedSearchConfig",
    "SearchHit",
    "SearchOutcome",
    "SearchStatus",
    "SearchUsage",
    "UnavailableReason",
    "hosted_search_config",
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
