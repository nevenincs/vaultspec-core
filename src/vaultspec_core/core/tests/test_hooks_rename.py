"""Real-filesystem tests for :func:`hooks_rename`.

``hooks_rename`` is now driven through the shared ``RenameTransaction`` engine.
These tests exercise the successful move, byte-for-byte preservation on an
induced mid-apply failure, ``base_dir`` containment, and the
``ResourceExistsError`` / ``ResourceNotFoundError`` contract.  No test doubles
are used: every condition is induced through the real filesystem under a real
temporary ``.vaultspec`` tree with an active workspace context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.core import hooks_rename
from vaultspec_core.core import types as _types
from vaultspec_core.core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
    VaultSpecError,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_HOOK_BODY = "event: vault.document.created\nenabled: true\nactions: []\n"


@pytest.fixture
def hooks_dir(tmp_path: Path) -> Iterator[Path]:
    """Yield a real temp hooks dir with an active, isolated workspace context."""
    vs = tmp_path / ".vaultspec"
    hooks = vs / "rules" / "hooks"
    hooks.mkdir(parents=True)

    ctx = _types.WorkspaceContext(
        root_dir=tmp_path,
        target_dir=tmp_path,
        rules_src_dir=vs / "rules" / "rules",
        skills_src_dir=vs / "rules" / "skills",
        agents_src_dir=vs / "rules" / "agents",
        system_src_dir=vs / "rules" / "system",
        templates_dir=vs / "rules" / "templates",
        hooks_dir=hooks,
    )
    token = _types._workspace_ctx.set(ctx)
    try:
        yield hooks
    finally:
        _types._workspace_ctx.reset(token)


def _write_hook(hooks: Path, name: str, *, body: str = _HOOK_BODY) -> Path:
    path = hooks / f"{name}.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_successful_rename_moves_file_byte_for_byte(hooks_dir: Path) -> None:
    old = _write_hook(hooks_dir, "guard")
    original = old.read_bytes()

    new_path = hooks_rename("guard", "sentinel")

    assert new_path == hooks_dir / "sentinel.yaml"
    assert not old.exists()
    assert new_path.is_file()
    # A hook rename is a pure move: the content is preserved byte-for-byte.
    assert new_path.read_bytes() == original


def test_rollback_on_induced_failure_leaves_file_byte_identical(
    hooks_dir: Path,
) -> None:
    old = _write_hook(hooks_dir, "guard")
    original = old.read_bytes()

    # Rename into a subdirectory whose parent does not exist: the OS rename
    # fails inside the transaction, driving the reverse journal, and the source
    # hook must remain byte-identical with no destination created.
    with pytest.raises((VaultSpecError, OSError)):
        hooks_rename("guard", "missing-subdir/renamed-hook")

    assert old.is_file()
    assert old.read_bytes() == original
    assert not (hooks_dir / "missing-subdir").exists()


def test_containment_refuses_escaping_destination(hooks_dir: Path) -> None:
    old = _write_hook(hooks_dir, "guard")
    original = old.read_bytes()

    with pytest.raises(VaultSpecError):
        hooks_rename("guard", "../escaped")

    assert old.read_bytes() == original


def test_rename_collision_raises_resource_exists(hooks_dir: Path) -> None:
    _write_hook(hooks_dir, "guard")
    dst = _write_hook(hooks_dir, "sentinel", body="event: x\nactions: []\n")
    dst_original = dst.read_bytes()

    with pytest.raises(ResourceExistsError):
        hooks_rename("guard", "sentinel")

    # The pre-existing destination is untouched.
    assert dst.read_bytes() == dst_original


def test_rename_missing_raises_resource_not_found(hooks_dir: Path) -> None:
    with pytest.raises(ResourceNotFoundError):
        hooks_rename("ghost", "whatever")
