"""The record-type filter every search surface accepts.

A surface passes the caller's type names through unchanged; the search
package decides which are searchable and refuses the rest with one message,
so the CLI and the MCP tool cannot disagree about what a filter means.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ._corpus import SEARCHABLE_TYPES
from ._models import UnsearchableTypeError

if TYPE_CHECKING:
    from collections.abc import Collection

    from ..vaultcore.models import DocType

__all__ = ["SEARCHABLE_TYPE_NAMES", "record_types"]

#: The searchable record types, in the order help, errors and next steps list
#: them.
SEARCHABLE_TYPE_NAMES: Final = ", ".join(sorted(SEARCHABLE_TYPES))


def record_types(names: Collection[str] | None) -> frozenset[DocType] | None:
    """Resolve a record-type filter to the types search ranks.

    Args:
        names: The requested type names (a :class:`DocType` is one), or
            ``None``. No names is no filter.

    Returns:
        The selected record types, or ``None`` to search every searchable
        type.

    Raises:
        UnsearchableTypeError: If a name is not a searchable record type.
    """
    if not names:
        return None
    by_name = {doc_type.value: doc_type for doc_type in SEARCHABLE_TYPES}
    refused = sorted({str(name) for name in names} - by_name.keys())
    if refused:
        msg = (
            f"search does not rank {', '.join(refused)} records; "
            f"choose from {SEARCHABLE_TYPE_NAMES}"
        )
        raise UnsearchableTypeError(msg)
    return frozenset(by_name[str(name)] for name in names)
