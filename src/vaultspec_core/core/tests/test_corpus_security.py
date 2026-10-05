"""Corpus consumers reject redirected files at discovery and at read time."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import get_config, reset_config
from vaultspec_core.core.corpus_io import UnsafeDocumentError, is_corpus_path
from vaultspec_core.core.document_io import read_document_bytes, read_document_text
from vaultspec_core.crossref._corpus import _read, load_adrs
from vaultspec_core.graph import VaultGraph
from vaultspec_core.graph.cache import fingerprint_vault, hash_file, validate
from vaultspec_core.search._corpus import load_records, read_version
from vaultspec_core.vaultcore.checks._base import iter_document_texts
from vaultspec_core.vaultcore.query_listing import list_documents, scan_all
from vaultspec_core.vaultcore.scanner import list_features, scan_vault

if TYPE_CHECKING:
    from collections.abc import Generator

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _config() -> Generator[None]:
    reset_config()
    yield
    reset_config()


def _write(path: Path, feature: str = "local") -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (
        f"---\ntags: ['#adr', '#{feature}']\ndate: '2026-01-01'\nrelated: []\n---\n"
        f"# {feature}\n\n## Decision\n\nEvidence: café 世界.\n"
    ).encode()
    path.write_bytes(raw)
    return raw


@pytest.mark.parametrize("target_kind", ["outside", "inside", "dangling"])
def test_corpus_consumers_exclude_markdown_file_links(
    tmp_path: Path, target_kind: str
) -> None:
    root = tmp_path / "project"
    safe = root / ".vault/adr/safe.md"
    safe_bytes = _write(safe)
    target = tmp_path / "victim.txt"
    if target_kind == "inside":
        target = root / ".vault/adr/target.txt"
    if target_kind != "dangling":
        _write(target, "private-secret")
    link = safe.with_name("leak.md")
    link.symlink_to(target)

    assert list(scan_vault(root)) == [safe]
    assert list_features(root) == {"local"}
    assert [doc.path for doc in scan_all(root)] == [safe]
    assert list(iter_document_texts(root)) == [(safe, safe_bytes.decode(), False)]
    assert set(VaultGraph(root).raw_texts) == {safe}
    assert set(VaultGraph(root).raw_texts) == {safe}
    assert [record.path for record in load_records(root)] == [safe]
    assert [record.stem for record in load_adrs(root)] == ["safe"]
    assert _read(link, root) is None


@pytest.mark.parametrize("link_kind", ["symlink", "junction"])
def test_corpus_consumers_prune_redirected_directories(
    tmp_path: Path, link_kind: str
) -> None:
    if link_kind == "junction" and os.name != "nt":
        pytest.skip("junctions are Windows-only")
    root = tmp_path / "project"
    safe = root / ".vault/research/safe.md"
    _write(safe)
    outside = tmp_path / "outside"
    _write(outside / "victim.md", "private-secret")
    link = root / ".vault/adr"
    if link_kind == "junction":
        subprocess.run(
            ["cmd", "/d", "/c", "mklink", "/J", str(link), str(outside)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        assert link.is_junction()
    else:
        link.symlink_to(outside, target_is_directory=True)

    assert list(scan_vault(root)) == [safe]
    assert load_adrs(root) == []
    assert not is_corpus_path(link / "victim.md", root)
    with pytest.raises(UnsafeDocumentError):
        read_document_bytes(link / "victim.md", root_dir=root)


def test_search_revalidates_a_record_replaced_after_listing(tmp_path: Path) -> None:
    root = tmp_path / "project"
    path = root / ".vault/adr/safe.md"
    _write(path)
    (record,) = load_records(root)
    outside = tmp_path / "victim.txt"
    _write(outside, "private-secret")
    path.unlink()
    path.symlink_to(outside)

    assert read_version(record) is None


@pytest.mark.parametrize("seed_through_alias", [False, True])
def test_cached_corpus_paths_follow_the_current_workspace_alias(
    tmp_path: Path, seed_through_alias: bool
) -> None:
    root = tmp_path / "project"
    path = root / ".vault/adr/safe.md"
    raw = _write(path)
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    seed, target = (alias, root) if seed_through_alias else (root, alias)
    VaultGraph(seed)
    expected = target / ".vault/adr/safe.md"

    (record,) = load_records(target)
    assert record.path == expected
    version = read_version(record)
    assert version is not None
    assert version.blocks
    assert read_document_bytes(record.path, root_dir=target) == raw
    (doc,) = list_documents(target)
    assert doc.path == expected


@pytest.mark.parametrize("replacement", ["file", "parent"])
def test_reader_rejects_replacement_between_validation_and_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replacement: str
) -> None:
    root = tmp_path / "project"
    path = root / ".vault/adr/safe.md"
    _write(path)
    outside = tmp_path / "outside"
    _write(outside / path.name, "private-secret")
    original_open = os.open
    intercepted = False
    descriptors: list[int] = []

    def swap_before_open(
        file: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal intercepted
        if Path(file) == path and not intercepted:
            intercepted = True
            if replacement == "file":
                path.unlink()
                path.symlink_to(outside / path.name)
            else:
                path.parent.rename(path.parent.with_name("original-adr"))
                path.parent.symlink_to(outside, target_is_directory=True)
        descriptor = original_open(file, flags, mode, dir_fd=dir_fd)
        descriptors.append(descriptor)
        return descriptor

    monkeypatch.setattr(os, "open", swap_before_open)
    with pytest.raises(OSError):
        read_document_bytes(path, root_dir=root)
    assert intercepted
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_cache_rejects_paths_replaced_after_discovery(tmp_path: Path) -> None:
    root = tmp_path / "project"
    path = root / ".vault/adr/safe.md"
    raw = _write(path)
    manifest = fingerprint_vault([path], root)
    assert validate(manifest, [path], root, cache_mtime_ns=None, deep=True)
    assert hash_file(path, root_dir=root)
    outside = tmp_path / "victim.txt"
    outside.write_bytes(raw)
    path.unlink()
    path.symlink_to(outside)

    assert fingerprint_vault([path], root) == {}
    assert not validate(manifest, [path], root, cache_mtime_ns=2**63)
    with pytest.raises(UnsafeDocumentError):
        hash_file(path, root_dir=root)


def test_reader_rejects_nonregular_files_and_outside_candidates(tmp_path: Path) -> None:
    root = tmp_path / "project"
    path = root / ".vault/adr/directory.md"
    path.mkdir(parents=True)
    outside = root / ".vault-other/victim.md"
    _write(outside)
    for candidate in (path, outside):
        with pytest.raises(UnsafeDocumentError):
            read_document_bytes(candidate, root_dir=root)


def test_explicit_external_docs_root_remains_usable_and_rejects_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    docs = tmp_path / "external-vault"
    safe = docs / "adr/safe.md"
    raw = _write(safe)
    outside = tmp_path / "victim.txt"
    _write(outside, "private-secret")
    safe.with_name("leak.md").symlink_to(outside)
    monkeypatch.setenv("VAULTSPEC_DOCS_DIR", str(docs))

    assert list(scan_vault(root)) == [safe]
    assert [doc.path for doc in scan_all(root)] == [safe]
    assert read_document_bytes(safe, root_dir=root) == raw
    with pytest.raises(UnsafeDocumentError):
        read_document_bytes(safe.with_name("leak.md"), root_dir=root)


def test_reader_preserves_bytes_and_newlines_with_custom_docs_and_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "project"
    path = root / "nested/docs/adr/safe.md"
    raw = _write(path).replace(b"\n", b"\r\n")
    path.write_bytes(raw)
    monkeypatch.setenv("VAULTSPEC_DOCS_DIR", "nested/docs")
    assert get_config(root=root).docs_dir == "nested/docs"
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    alias_path = alias / "nested/docs/adr/safe.md"

    assert list(scan_vault(alias)) == [alias_path]
    assert read_document_bytes(alias_path, root_dir=alias) == raw
    assert read_document_text(alias_path, root_dir=alias) == raw.decode().replace(
        "\r\n", "\n"
    )
    assert [record.path for record in load_records(alias)] == [alias_path]
    assert [record.stem for record in load_adrs(alias)] == ["safe"]
