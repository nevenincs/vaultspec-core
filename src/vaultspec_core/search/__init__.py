"""Hosted vault search: ranked records with verbatim excerpts.

Search runs on the TypeSafe Jev model when a hosted-search credential is
configured, and reports ``not_configured`` otherwise, so the caller can route
to the agent-level fallback. It never calls vaultspec-rag.
"""

from __future__ import annotations

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
from ._remediation import remediation as remediation
from ._service import search_vault as search_vault

__all__ = [
    "DEFAULT_RESULTS",
    "EXCERPT_CHARS",
    "MAX_QUERY_CHARS",
    "MAX_RESULTS",
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
