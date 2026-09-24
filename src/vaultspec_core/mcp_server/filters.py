"""Record filters shared by every tool that selects vault records.

``find`` and ``search`` narrow the vault by the same three facts - a feature
tag, an exact date, and a set of record types - and a caller should read one
meaning for each wherever it appears. Declaring them once here keeps the two
tools from drifting: a filter documented or validated differently on each
surface would make the same argument select different records.

Each alias carries its parameter description, so the meaning reaches the
input schema from this one place; a tool docstring's ``Args:`` never reaches
the model. The record-type filter is typed by
:class:`~vaultspec_core.vaultcore.models.DocType` itself, so the accepted
values are the vault's own type list, listed in the schema, and an unknown
type is refused by schema validation rather than silently matching nothing.
Search ranks fewer types than the vault holds, so its filter lists the search
package's own set: a type every search refuses is not one to offer.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..search import SEARCHABLE_TYPES
from ..vaultcore.models import DocType
from .envelope import LeanEnum

__all__ = ["DateFilter", "FeatureFilter", "SearchTypeFilter", "TypeFilter"]

#: A feature tag, without the leading ``#``.
FeatureFilter = Annotated[str | None, Field(description="Feature tag, no '#'.")]

#: An exact frontmatter date.
DateFilter = Annotated[str | None, Field(description="Exact date, YYYY-MM-DD.")]

#: The record types to keep. The enum's values are the whole contract, so its
#: docstring stays off the wire.
TypeFilter = list[Annotated[DocType, LeanEnum()]] | None

#: The record types a search may keep: the searchable ones alone.
SearchTypeFilter = list[Annotated[DocType, LeanEnum(SEARCHABLE_TYPES)]] | None
