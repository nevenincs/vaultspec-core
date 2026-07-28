"""Vault document kernel: models, parsing, scanning, and hydration.

Re-exports from six internal modules: :mod:`.models`
(:class:`~vaultspec_core.vaultcore.models.DocType`,
:class:`~vaultspec_core.vaultcore.models.DocumentMetadata`,
:class:`~vaultspec_core.vaultcore.models.VaultConstants`),
:mod:`.parser`
(:func:`~vaultspec_core.vaultcore.parser.parse_frontmatter`,
:func:`~vaultspec_core.vaultcore.parser.parse_vault_metadata`),
:mod:`.links`, :mod:`.scanner`, :mod:`.query`, and
:mod:`.hydration`.  Consumed by :mod:`vaultspec_core.metrics`,
:mod:`vaultspec_core.graph`, and :mod:`vaultspec_core.mcp_server`.
"""

from typing import TYPE_CHECKING

from . import query as _query
from .body_schema import BODY_SCHEMA_REGISTRY as BODY_SCHEMA_REGISTRY
from .body_schema import CURRENT_BODY_SCHEMA as CURRENT_BODY_SCHEMA
from .body_schema import BodySchema as BodySchema
from .body_schema import BodySchemaResolution as BodySchemaResolution
from .body_schema import resolve_body_schema as resolve_body_schema
from .hydration import create_vault_doc as create_vault_doc
from .hydration import get_template_path as get_template_path
from .hydration import hydrate_template as hydrate_template
from .links import extract_related_links as extract_related_links
from .links import extract_wiki_links as extract_wiki_links
from .models import DocType as DocType
from .models import DocumentMetadata as DocumentMetadata
from .models import VaultConstants as VaultConstants
from .models import normalize_date as normalize_date
from .models import parse_lenient_date as parse_lenient_date
from .models import refresh_modified_stamp as refresh_modified_stamp
from .parser import parse_frontmatter as parse_frontmatter
from .parser import parse_vault_metadata as parse_vault_metadata
from .query import VaultDocument as VaultDocument
from .query import archive_feature as archive_feature
from .query import list_documents as list_documents
from .query import list_feature_details as list_feature_details
from .query import unarchive_feature as unarchive_feature
from .scanner import get_doc_type as get_doc_type
from .scanner import list_features as list_features
from .scanner import scan_vault as scan_vault

if TYPE_CHECKING:
    from pathlib import Path

    from ..graph.api import VaultGraph
    from .query_listing import VaultStats

# ``query.get_stats`` (defined in ``query_listing``) declares an
# unparameterized ``-> dict`` return, so importing it directly always reports
# as "partially unknown" regardless of how precisely the caller is typed.
# This thin re-binding declares the signature actually returned (verified
# against the runtime behaviour documented on ``get_stats`` itself) for
# type-checking only; the ``else`` branch binds the exact same callable at
# runtime, so behaviour is unchanged. Mirrors the identical pattern in
# :mod:`vaultspec_core.graph.api` for untyped ``networkx`` entry points.
if TYPE_CHECKING:

    def get_stats(
        root_dir: Path,
        *,
        feature: str | None = None,
        doc_type: str | None = None,
        date: str | None = None,
        graph: VaultGraph | None = None,
    ) -> VaultStats: ...
else:
    get_stats = _query.get_stats
