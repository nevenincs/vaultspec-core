"""Collectors for hooks rendered into agent-runtime provider configs.

``.vaultspec/hooks/`` is authored once and rendered into each installed
provider's native hook-config file by
:func:`~vaultspec_core.core.provider_hooks.provider_hooks_sync`. Nothing
reported whether that render had happened, matched its source, or still carried
an intact ownership record, so a workspace whose hooks reached no provider
looked exactly like one whose hooks reached all of them.

This module answers three questions per provider: is the render present, does
the ownership record still describe it, and does any source file name an event
this provider cannot consume. The third is not a fault in the workspace - it is
the expected consequence of providers disagreeing about which events exist -
but it is silent otherwise, so a hook an author believes is universal can be
absent from half the fleet with nothing saying so.

All imports from ``core.*`` are deferred inside function bodies to prevent
import cycles, following the other collectors in this package.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from .signals import ProviderHookSignal

if TYPE_CHECKING:
    from pathlib import Path

    from ..enums import Tool

logger = logging.getLogger(__name__)

__all__ = [
    "HookTarget",
    "ProviderHookReport",
    "collect_provider_hook_reports",
    "worst_hook_signal",
]

# Ordering by how much a reader needs to know about it, worst first. Used to
# reduce a per-provider verdict list to the one status a summary row carries.
_SEVERITY: tuple[ProviderHookSignal, ...] = (
    ProviderHookSignal.UNREADABLE,
    ProviderHookSignal.SIDECAR_STALE,
    ProviderHookSignal.SIDECAR_MISSING,
    ProviderHookSignal.STALE,
    ProviderHookSignal.NOT_RENDERED,
    ProviderHookSignal.IN_SYNC,
    ProviderHookSignal.NO_SOURCES,
)


@dataclass(frozen=True)
class HookTarget:
    """One installed hook-capable provider and the files it renders into.

    A provider records which entries are vaultspec's in one of two ways, and
    exactly one of these fields says which:

    - ``sidecar`` names an ownership file beside the config, listing the groups
      the last sync wrote. The config itself carries no marker.
    - ``hookset`` names a group inside the config that vaultspec owns outright,
      which is both the render and the record.

    Keying off the shape rather than off the provider's identity keeps this
    collector out of the business of knowing which provider does which.
    """

    tool: Tool
    native: Path
    sidecar: Path | None = None
    hookset: str | None = None


@dataclass(frozen=True)
class ProviderHookReport:
    """The hook-render verdict for one provider."""

    tool: str
    signal: ProviderHookSignal
    native_path: str
    #: ``name (event)`` for each source hook this provider cannot consume.
    unsupported: tuple[str, ...] = field(default=())


def _read_json(path: Path) -> dict[str, Any] | None:
    """Return *path* parsed as a JSON object.

    Returns:
        The parsed object, ``{}`` when the file is absent, or ``None`` when it
        is present and could not be read as a JSON object. ``None`` is the
        check-did-not-run answer and is deliberately distinct from ``{}``.
    """
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        logger.warning("Cannot read provider hook file %s: %s", path, exc)
        return None
    if not isinstance(raw, dict):
        return None
    return cast("dict[str, Any]", raw)


def _hooks_mapping(native: dict[str, Any]) -> dict[str, Any]:
    """Return the ``hooks`` mapping of a settings-style provider file."""
    hooks = native.get("hooks")
    return cast("dict[str, Any]", hooks) if isinstance(hooks, dict) else {}


def _groups_present(rendered: dict[str, Any], live: dict[str, Any]) -> tuple[int, int]:
    """Count how many rendered groups appear in *live*.

    Returns:
        ``(present, total)`` over every group of every event in *rendered*.
    """
    present = 0
    total = 0
    for event, groups in rendered.items():
        current = live.get(event)
        current_list = cast("list[Any]", current) if isinstance(current, list) else []
        for group in cast("list[Any]", groups):
            total += 1
            if group in current_list:
                present += 1
    return present, total


def _flat_signal(
    rendered: dict[str, Any],
    live: dict[str, Any],
    recorded: dict[str, Any],
    *,
    has_sources: bool,
) -> ProviderHookSignal:
    """Verdict for a provider whose ownership lives in a sidecar file."""
    if not rendered:
        # Nothing should be rendered. A record left behind means the next sync
        # has entries to prune, which is drift rather than a settled state.
        if recorded:
            return ProviderHookSignal.STALE
        return (
            ProviderHookSignal.IN_SYNC if has_sources else ProviderHookSignal.NO_SOURCES
        )

    present, total = _groups_present(rendered, live)
    if present == 0:
        # Nothing the source renders is in the file. Whether that is "never
        # rendered" or "rendered, then the source changed" is decided by the
        # ownership record: a non-empty record proves an earlier sync wrote
        # groups that are still live, so the file is stale rather than absent,
        # and telling the operator "never rendered" would send them looking for
        # the wrong thing.
        if recorded:
            return ProviderHookSignal.STALE
        return ProviderHookSignal.NOT_RENDERED
    if present < total:
        return ProviderHookSignal.STALE
    if not recorded:
        return ProviderHookSignal.SIDECAR_MISSING
    if recorded != rendered:
        return ProviderHookSignal.SIDECAR_STALE
    return ProviderHookSignal.IN_SYNC


def _hookset_signal(
    rendered: dict[str, Any],
    native: dict[str, Any],
    hookset: str,
    *,
    has_sources: bool,
) -> ProviderHookSignal:
    """Verdict for a provider that owns a named hookset.

    The hookset is both the render and the ownership record, so there is no
    sidecar state to disagree with: it either matches what the source renders
    or it does not.
    """
    live = native.get(hookset)
    expected = rendered.get(hookset) if rendered else None

    if expected is None:
        if live is not None:
            return ProviderHookSignal.STALE
        return (
            ProviderHookSignal.IN_SYNC if has_sources else ProviderHookSignal.NO_SOURCES
        )
    if live is None:
        return ProviderHookSignal.NOT_RENDERED
    if live != expected:
        return ProviderHookSignal.STALE
    return ProviderHookSignal.IN_SYNC


def _unsupported_for(specs: list[Any], tool: Tool) -> tuple[str, ...]:
    """Return ``name (event)`` for each enabled spec *tool* cannot consume."""
    from ..provider_hooks import supported_events

    events = supported_events(tool)
    return tuple(
        f"{spec.name} ({spec.event.value})"
        for spec in specs
        if spec.enabled and spec.event not in events
    )


def collect_provider_hook_reports(
    hooks_dir: Path, targets: list[HookTarget]
) -> list[ProviderHookReport]:
    """Assess each provider's rendered hooks against ``.vaultspec/hooks/``.

    Renders the current source specs for every target the same way sync does,
    then compares the result with what the provider's config file carries and
    with the ownership record beside it. Nothing is written.

    Args:
        hooks_dir: The provider-hook source directory.
        targets: Installed hook-capable providers and their files, in the
            order sync visits them.

    Returns:
        One :class:`ProviderHookReport` per target, in the order given.
    """
    from ..provider_hooks import load_provider_hook_specs, render_hooks_payload

    specs = load_provider_hook_specs(hooks_dir)
    has_sources = bool(specs)

    reports: list[ProviderHookReport] = []
    for target in targets:
        rendered = render_hooks_payload(specs, target.tool) or {}
        native = _read_json(target.native)
        recorded = _read_json(target.sidecar) if target.sidecar else {}

        if native is None or recorded is None:
            signal = ProviderHookSignal.UNREADABLE
        elif target.hookset is not None:
            signal = _hookset_signal(
                rendered, native, target.hookset, has_sources=has_sources
            )
        else:
            signal = _flat_signal(
                rendered,
                _hooks_mapping(native),
                recorded,
                has_sources=has_sources,
            )

        reports.append(
            ProviderHookReport(
                tool=target.tool.value,
                signal=signal,
                native_path=str(target.native),
                unsupported=_unsupported_for(specs, target.tool),
            )
        )
    return reports


def worst_hook_signal(
    reports: list[ProviderHookReport],
) -> ProviderHookSignal:
    """Return the signal a summary row should carry for *reports*."""
    seen = {report.signal for report in reports}
    for signal in _SEVERITY:
        if signal in seen:
            return signal
    return ProviderHookSignal.NO_SOURCES
