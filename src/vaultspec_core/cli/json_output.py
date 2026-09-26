"""The one place that decides how CLI JSON is formatted on the wire.

Every ``--json`` emission in the CLI used to pass ``indent=2``. Two-space
indentation is a courtesy to a human reading a terminal, but ``--json`` is
the machine surface: it is what an agent pipes, and what the MCP gateway
forwards verbatim into a model context window. Nothing on that path is
helped by alignment, and the cost is not marginal.

Measured against a 10,476-document vault before this module existed:

=========================  ============  ============  ============
command                    pretty        compact       whitespace
=========================  ============  ============  ============
``vault list``                5,934,666     4,719,450         20.5%
``vault check all``             653,418       490,741         24.9%
``status``                      259,451       168,375         35.1%
``vault feature list``          199,579       111,381         44.2%
``vault stats``                     384           259         32.6%
=========================  ============  ============  ============

The share rises with nesting depth, so the payloads that can least afford
the tax pay the most of it - ``vault feature list`` spends 44% of itself on
whitespace. Across the 53 emission sites this was a flat surcharge on the
entire machine surface, invisible in review because each site looked like a
reasonable local choice.

Formatting is a property of the *channel*, not of any one command, so it
lives here rather than at each call site. Setting ``VAULTSPEC_JSON_PRETTY``
to a truthy value restores indentation for a human debugging a payload by
hand; nothing in the agent path sets it.

The implementation lives in :mod:`vaultspec_core.envelope`, which an
importing package can use without paying for the CLI command tree; this
module re-exports the same functions so no call site under
:mod:`vaultspec_core.cli` needs to change.
"""

from __future__ import annotations

from vaultspec_core.envelope import (
    error_format_kwargs as error_format_kwargs,
)
from vaultspec_core.envelope import (
    json_format_kwargs as json_format_kwargs,
)
from vaultspec_core.envelope import (
    pretty_enabled as pretty_enabled,
)

__all__ = ["error_format_kwargs", "json_format_kwargs", "pretty_enabled"]
