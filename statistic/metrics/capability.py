"""The declared-capability denominator parsed from the CLI reference.

The dead-surface and invocation-miss metrics measure observed usage against a
closed ground-truth set: every verb path the CLI actually declares, and the
flags it declares for each. That ground truth is machine-generated between the
``vaultspec:generated`` markers in ``.vaultspec/reference/cli.md`` and changes
whenever the CLI surface changes, so it is parsed live at analysis time rather
than hand-copied - a copied table would rot the moment the surface moved.

:func:`parse_capability_inventory` reads the command-inventory marker block and
returns a :class:`CapabilityInventory`: the set of valid verb paths (e.g.
``("vault", "check", "links")``) plus, where the reference declares them, the
valid flags per verb path. Flag validation is deliberately *advisory* - an
observed flag absent from the inventory is a candidate miss, never silently
dropped, because the generated reference may lag the installed binary.

The path to the reference is always injected as a parameter. The module-level
:func:`default_reference_path` derives a repo-relative default from this file's
own location, so nothing hardcodes an absolute path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: Fence around the machine-generated command inventory in the CLI reference.
_MARKER_BEGIN = "vaultspec:generated:begin command-inventory"
_MARKER_END = "vaultspec:generated:end command-inventory"

#: The CLI executable name that prefixes every verb path in the inventory.
_EXECUTABLE = "vaultspec-core"

#: Matches the first inline code span in a bullet, which carries the full
#: ``vaultspec-core <verb path>`` invocation.
_COMMAND_SPAN = re.compile(r"`" + re.escape(_EXECUTABLE) + r"\s+([^`]+)`")

#: Matches a flag token wrapped in backticks anywhere in a bullet's prose, e.g.
#: ``--fix``, ``--force``, or the short form ``-f``.
_FLAG_TOKEN = re.compile(r"`(-{1,2}[A-Za-z][\w-]*)`")


def default_reference_path() -> Path:
    """Return the repo-relative path to the bundled CLI reference.

    The path is derived from this module's own location - ``statistic`` sits at
    the repository root - so it carries no absolute prefix or username. Callers
    may pass their own path to :func:`parse_capability_inventory` instead.

    Returns:
        The path to ``.vaultspec/reference/cli.md`` under the repository root.
    """
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / ".vaultspec" / "reference" / "cli.md"


@dataclass(frozen=True)
class CapabilityInventory:
    """The declared verb-path and per-verb flag denominator.

    Attributes:
        verb_paths: Every declared verb path as a tuple of segments, e.g.
            ``("vault", "check", "links")``. This is the closed denominator the
            dead-surface metric measures observed usage against.
        flags: The declared flags for each verb path, keyed by the same tuple.
            A verb path with no declared flags maps to an empty frozenset. The
            mapping is advisory: absence of an observed flag here marks a
            candidate miss, not a hard rejection.
    """

    verb_paths: frozenset[tuple[str, ...]]
    flags: dict[tuple[str, ...], frozenset[str]]

    def declares_verb_path(self, verb_path: tuple[str, ...]) -> bool:
        """Report whether the inventory declares *verb_path*.

        Args:
            verb_path: A verb path as a tuple of segments, e.g.
                ``("vault", "list")``.

        Returns:
            ``True`` when the verb path is part of the declared surface,
            ``False`` otherwise (a candidate dead or undeclared surface).
        """
        return verb_path in self.verb_paths

    def declares_flag(self, verb_path: tuple[str, ...], flag: str) -> bool:
        """Report whether *flag* is declared for *verb_path*.

        This is the advisory membership query behind miss detection: a ``False``
        result marks *flag* as a candidate miss for the verb path, never a
        silent drop, since the generated reference may lag the installed binary.

        Args:
            verb_path: The verb path the flag was observed under.
            flag: The canonical flag token, e.g. ``--feature`` or ``-f``.

        Returns:
            ``True`` when the reference declares *flag* for *verb_path*,
            ``False`` otherwise (including when the verb path itself is
            undeclared).
        """
        return flag in self.flags.get(verb_path, frozenset())

    def declared_flags(self, verb_path: tuple[str, ...]) -> frozenset[str]:
        """Return the declared flag set for *verb_path*.

        Args:
            verb_path: The verb path to look up.

        Returns:
            The declared flags for the verb path, or an empty frozenset when
            the verb path is undeclared or declares no flags.
        """
        return self.flags.get(verb_path, frozenset())


def _iter_inventory_bullets(lines: list[str]) -> list[str]:
    """Reassemble the wrapped bullet lines inside the marker block.

    The reference wraps long bullets across indented continuation lines. This
    joins each ``- ``-prefixed bullet with its continuations into one logical
    line, and ignores everything outside the ``vaultspec:generated`` markers.

    Args:
        lines: The reference file split into physical lines.

    Returns:
        One reassembled string per inventory bullet, in document order.
    """
    inside = False
    bullets: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            bullets.append(" ".join(part.strip() for part in current))
            current.clear()

    for line in lines:
        if _MARKER_BEGIN in line:
            inside = True
            continue
        if _MARKER_END in line:
            flush()
            inside = False
            continue
        if not inside:
            continue
        stripped = line.lstrip()
        if stripped.startswith("- "):
            flush()
            current.append(stripped[2:])
        elif current and stripped:
            current.append(stripped)
        elif not stripped:
            flush()
    flush()
    return bullets


def parse_capability_inventory(
    reference_path: Path | None = None,
) -> CapabilityInventory:
    """Parse the declared-capability denominator from the CLI reference.

    Reads the command-inventory block between the ``vaultspec:generated``
    markers, extracts each ``vaultspec-core <verb path>`` invocation, and
    collects the flags the reference declares inline for it. Bullets outside the
    markers are ignored entirely.

    Args:
        reference_path: The path to the CLI reference file. When ``None``, the
            repo-relative :func:`default_reference_path` is used. This is always
            a parameter so tests can point at a redacted fixture and no absolute
            path is ever hardcoded.

    Returns:
        The :class:`CapabilityInventory` denominator of verb paths and their
        declared flags.

    Raises:
        ValueError: When the reference contains no ``vaultspec:generated``
            command-inventory marker block, which would silently empty the
            denominator; the marker-format contract is surfaced loudly instead.
    """
    path = reference_path if reference_path is not None else default_reference_path()
    text = path.read_text(encoding="utf-8")
    if _MARKER_BEGIN not in text or _MARKER_END not in text:
        msg = (
            f"no vaultspec:generated command-inventory markers found in {path}; "
            "the capability denominator cannot be parsed"
        )
        raise ValueError(msg)

    verb_paths: set[tuple[str, ...]] = set()
    flags: dict[tuple[str, ...], frozenset[str]] = {}

    for bullet in _iter_inventory_bullets(text.splitlines()):
        command_match = _COMMAND_SPAN.search(bullet)
        if command_match is None:
            continue
        verb_path = tuple(command_match.group(1).split())
        if not verb_path:
            continue
        verb_paths.add(verb_path)
        declared = frozenset(_FLAG_TOKEN.findall(bullet))
        flags[verb_path] = flags.get(verb_path, frozenset()) | declared

    return CapabilityInventory(verb_paths=frozenset(verb_paths), flags=flags)
