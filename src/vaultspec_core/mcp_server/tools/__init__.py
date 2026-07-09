"""First-class MCP tool handlers, grouped by domain.

Each module registers a slice of the nine-tool surface onto a shared
``FastMCP`` instance.  :mod:`documents` owns document discovery and mutation
(``find`` / ``create`` / ``edit``), :mod:`orientation` owns read-only
orientation and health checking (``status`` / ``check``), and :mod:`plan`
owns plan progress and step authoring (``plan_progress`` / ``plan_edit``);
the gateway tools land in a later phase.  All handlers route every mutation
through the shared ``vaultcore`` / ``plan`` cores and author no creation,
edit, orientation, or plan-structure logic here.
"""

from __future__ import annotations

__all__ = [
    "register_document_tools",
    "register_orientation_tools",
    "register_plan_tools",
]

from .documents import register_document_tools
from .orientation import register_orientation_tools
from .plan import register_plan_tools
