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
"""

from __future__ import annotations

import os
from typing import Any

__all__ = ["json_format_kwargs", "pretty_enabled"]

#: Compact separators: no space after ``,`` or ``:``. ``json.dumps`` defaults
#: to ``", "`` and ``": "``, which adds two bytes per field on top of the
#: indentation itself.
_COMPACT: dict[str, Any] = {"separators": (",", ":")}

#: Indented form, for a human reading a payload directly.
_PRETTY: dict[str, Any] = {"indent": 2}

#: Environment variable that restores indentation.
_PRETTY_ENV = "VAULTSPEC_JSON_PRETTY"

_FALSEY = frozenset({"", "0", "false", "no", "off"})


def pretty_enabled() -> bool:
    """Report whether indented JSON was explicitly requested.

    Read per call rather than cached at import so a test or a shell can
    toggle it without reloading the module.

    Returns:
        ``True`` when the environment opts into indentation.
    """
    return os.environ.get(_PRETTY_ENV, "").strip().lower() not in _FALSEY


def json_format_kwargs() -> dict[str, Any]:
    """Return the ``json.dumps`` formatting keywords for this channel.

    Returns:
        Compact separators by default; indentation when opted in.
    """
    return dict(_PRETTY) if pretty_enabled() else dict(_COMPACT)


#: Spread into every CLI ``json.dumps`` call as
#: ``json.dumps(payload, **json_format_kwargs())``. It is a function call
#: rather than a module-level mapping on purpose: ``**`` unpacking of a
#: ``dict`` subclass reads the underlying storage directly and bypasses any
#: ``keys``/``__getitem__`` override, so a lazily-resolving mapping expands to
#: nothing and silently restores the default separators. That failure is
#: invisible - the payload still shrinks, because the indent is gone - which
#: is exactly the kind of quiet regression this module exists to prevent.
