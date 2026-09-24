"""First-class MCP tool handlers, grouped by domain.

Each module registers a slice of the twelve-tool surface onto a shared
``MCPServer`` instance. :mod:`documents` owns document discovery and mutation
(``find`` / ``create`` / ``edit``), :mod:`exec` owns the execution ledger
(``log``), :mod:`orientation` owns read-only orientation and health checking
(``status`` / ``check``), :mod:`plan` owns plan progress and step authoring
(``plan_progress`` / ``plan_edit``), :mod:`search` owns hosted vault search
(``search``), :mod:`crossref` owns ADR cross-referencing
(``crossref``), and :mod:`gateway` owns the stateless long-tail gateway
(``discover`` / ``invoke``). All handlers route every mutation
through the shared
``vaultcore`` / ``plan`` cores or, for the long tail, subprocess the installed
binary; no creation, edit, orientation, or plan-structure logic is authored
here.
"""

from __future__ import annotations

__all__ = [
    "register_crossref_tools",
    "register_document_tools",
    "register_exec_tools",
    "register_gateway_tools",
    "register_orientation_tools",
    "register_plan_tools",
    "register_search_tools",
]

from .crossref import register_crossref_tools
from .documents import register_document_tools
from .exec import register_exec_tools
from .gateway import register_gateway_tools
from .orientation import register_orientation_tools
from .plan import register_plan_tools
from .search import register_search_tools
