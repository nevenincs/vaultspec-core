"""The core related-link writer on real files: resolution, idempotency, lock, cache."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest

from ...config import reset_config
from ...core.helpers import advisory_lock
from ...graph.cache import cache_path
from ..edit_engine import document_lock_target
from ..parser import parse_vault_metadata
from ..related_links import LinkError, LinkStatus, add_related_link, link_document

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

pytestmark = [pytest.mark.unit]

_SOURCE = "2026-01-02-alpha-adr"
_TARGET = "2026-01-03-beta-adr"


@pytest.fixture(autouse=True)
def _config() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _doc(root: Path, stem: str, related: tuple[str, ...] = ()) -> Path:
    path = root / ".vault" / "adr" / f"{stem}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", "tags:", "  - '#adr'", "  - '#demo'", "date: '2026-01-02'"]
    if related:
        lines += ["related:", *(f"  - '{link}'" for link in related)]
    lines += ["---", "", f"# `demo` adr: `{stem}` | (**status:** `accepted`)", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _related(path: Path) -> list[str]:
    metadata, _ = parse_vault_metadata(path.read_text(encoding="utf-8"))
    return list(metadata.related)


def test_adds_the_edge_and_drops_the_graph_cache(tmp_path: Path) -> None:
    source = _doc(tmp_path, _SOURCE)
    _doc(tmp_path, _TARGET)
    cache = cache_path(tmp_path)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("{}", encoding="utf-8")

    result = add_related_link(tmp_path, _SOURCE, f"[[{_TARGET}]]")

    assert result.status is LinkStatus.CREATED
    assert (result.src, result.dst) == (_SOURCE, _TARGET)
    assert _related(source) == [f"[[{_TARGET}]]"]
    assert not cache.exists()


def test_an_aliased_existing_edge_is_left_alone(tmp_path: Path) -> None:
    source = _doc(tmp_path, _SOURCE, related=(f"[[{_TARGET}|Beta]]",))
    _doc(tmp_path, _TARGET)
    before = source.read_bytes()

    result = add_related_link(tmp_path, f".vault/adr/{_SOURCE}.md", _TARGET)

    assert result.status is LinkStatus.UNCHANGED
    assert source.read_bytes() == before


def test_dry_run_reports_without_writing(tmp_path: Path) -> None:
    source = _doc(tmp_path, _SOURCE)
    _doc(tmp_path, _TARGET)
    before = source.read_bytes()

    result = add_related_link(tmp_path, _SOURCE, _TARGET, dry_run=True)

    assert result.status is LinkStatus.CREATED
    assert result.dry_run
    assert source.read_bytes() == before


def test_a_dangling_target_needs_force(tmp_path: Path) -> None:
    source = _doc(tmp_path, _SOURCE)

    with pytest.raises(LinkError, match="dangling"):
        add_related_link(tmp_path, _SOURCE, "2026-09-09-missing-adr")
    assert _related(source) == []

    result = add_related_link(tmp_path, _SOURCE, "2026-09-09-missing-adr", force=True)
    assert result.status is LinkStatus.CREATED
    assert _related(source) == ["[[2026-09-09-missing-adr]]"]


def test_an_unknown_source_is_refused(tmp_path: Path) -> None:
    _doc(tmp_path, _TARGET)

    with pytest.raises(LinkError, match="Cannot resolve source"):
        add_related_link(tmp_path, "2026-09-09-nothing-adr", _TARGET)


def test_the_write_waits_for_the_document_lock(tmp_path: Path) -> None:
    source = _doc(tmp_path, _SOURCE)
    lock = document_lock_target(source, tmp_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    held = threading.Event()
    release = threading.Event()
    done = threading.Event()

    def hold() -> None:
        with advisory_lock(lock):
            held.set()
            release.wait(timeout=10)

    def write() -> None:
        link_document(tmp_path, source, _TARGET)
        done.set()

    holder = threading.Thread(target=hold)
    holder.start()
    assert held.wait(timeout=10)
    writer = threading.Thread(target=write)
    writer.start()

    assert not done.wait(timeout=0.5), "the link was written while the lock was held"
    release.set()
    assert done.wait(timeout=10)
    holder.join(timeout=10)
    writer.join(timeout=10)
    assert _related(source) == [f"[[{_TARGET}]]"]
