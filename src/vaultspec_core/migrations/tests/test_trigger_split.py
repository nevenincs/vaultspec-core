"""Tests for the ``trigger_split`` registry entry.

Exercises :func:`vaultspec_core.migrations.m_0_2_4_trigger_split.migrate`
against real on-disk ``.vaultspec/hooks/`` fixtures. The migration relocates
lifecycle trigger files into ``.vaultspec/triggers/`` and leaves provider hooks
and unclassifiable files where their author put them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.migrations import MigrationError
from vaultspec_core.migrations.m_0_2_4_trigger_split import migrate

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]


def _hook(root: Path, name: str, body: str) -> Path:
    path = root / ".vaultspec" / "hooks" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _spec(event: str) -> str:
    return f"name: h\nevent: {event}\nactions:\n  - type: shell\n    command: echo x\n"


def _names(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.iterdir())


def test_absent_hooks_directory_is_a_noop(tmp_path: Path) -> None:
    result = migrate(tmp_path)

    assert result.counts == {"moved": 0, "left": 0}
    assert not (tmp_path / ".vaultspec" / "triggers").exists()


def test_lifecycle_trigger_moves_and_provider_hook_stays(tmp_path: Path) -> None:
    _hook(tmp_path, "on-sync.yaml", _spec("config.synced"))
    _hook(tmp_path, "guard.yaml", _spec("pre_tool_use"))

    result = migrate(tmp_path)

    assert result.counts["moved"] == 1
    assert _names(tmp_path / ".vaultspec" / "hooks") == ["guard.yaml"]
    assert _names(tmp_path / ".vaultspec" / "triggers") == ["on-sync.yaml"]


def test_moved_file_keeps_its_contents(tmp_path: Path) -> None:
    body = _spec("config.synced")
    _hook(tmp_path, "on-sync.yaml", body)

    migrate(tmp_path)

    moved = tmp_path / ".vaultspec" / "triggers" / "on-sync.yaml"
    assert moved.read_text(encoding="utf-8") == body


def test_retired_lifecycle_events_still_move(tmp_path: Path) -> None:
    """Events retired in this release are lifecycle files by origin.

    Leaving them in ``hooks/`` would strand them in front of a loader with no
    opinion about them; moving them puts them where the trigger loader reports
    them as unsupported.
    """
    _hook(tmp_path, "on-create.yaml", _spec("vault.document.created"))
    _hook(tmp_path, "on-audit.yml", _spec("audit.completed"))

    result = migrate(tmp_path)

    assert result.counts["moved"] == 2
    assert _names(tmp_path / ".vaultspec" / "hooks") == []
    assert _names(tmp_path / ".vaultspec" / "triggers") == [
        "on-audit.yml",
        "on-create.yaml",
    ]


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(_spec("typo.event"), id="unknown-event"),
        pytest.param("name: h\nactions: []\n", id="no-event"),
        pytest.param("event: [not, a, string]\n", id="non-string-event"),
        pytest.param("::: not yaml :::\n", id="unparseable"),
        pytest.param("- a list, not a mapping\n", id="not-a-mapping"),
    ],
)
def test_unclassifiable_file_is_left_in_place(tmp_path: Path, body: str) -> None:
    _hook(tmp_path, "mystery.yaml", body)

    result = migrate(tmp_path)

    assert result.counts == {"moved": 0, "left": 1}
    assert _names(tmp_path / ".vaultspec" / "hooks") == ["mystery.yaml"]
    assert not (tmp_path / ".vaultspec" / "triggers").exists()


def test_name_collision_aborts_before_moving_anything(tmp_path: Path) -> None:
    _hook(tmp_path, "first.yaml", _spec("config.synced"))
    _hook(tmp_path, "clash.yaml", _spec("config.synced"))
    existing = tmp_path / ".vaultspec" / "triggers" / "clash.yaml"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("name: prior\n", encoding="utf-8")

    with pytest.raises(MigrationError, match="already exists"):
        migrate(tmp_path)

    assert _names(tmp_path / ".vaultspec" / "hooks") == ["clash.yaml", "first.yaml"]
    assert existing.read_text(encoding="utf-8") == "name: prior\n"


def test_summary_tells_the_operator_to_re_approve(tmp_path: Path) -> None:
    """Consent is keyed by directory, so a moved trigger loses its grant."""
    _hook(tmp_path, "on-sync.yaml", _spec("config.synced"))

    result = migrate(tmp_path)

    assert "spec triggers trust" in result.summary


def test_provider_hooks_only_leaves_the_directory_untouched(tmp_path: Path) -> None:
    _hook(tmp_path, "guard.yaml", _spec("session_start"))

    result = migrate(tmp_path)

    assert result.counts == {"moved": 0, "left": 0}
    assert _names(tmp_path / ".vaultspec" / "hooks") == ["guard.yaml"]
    assert not (tmp_path / ".vaultspec" / "triggers").exists()
