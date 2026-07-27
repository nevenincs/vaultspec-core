"""Real-filesystem tests for explicit atomic vault document archiving."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from vaultspec_core.config import reset_config
from vaultspec_core.vaultcore.batch_archive import (
    ArchiveDocumentsError,
    RestoreDocumentsError,
    archive_documents,
    restore_documents,
)

pytestmark = [pytest.mark.unit]


def _document(
    *, related: tuple[str, ...] = (), body: bytes = b"Evidence: caf\xc3\xa9\n"
) -> bytes:
    related_lines = b"".join(f"  - '[[{stem}]]'\n".encode() for stem in related)
    return (
        b"---\ntags:\n  - '#research'\n  - '#feat'\nrelated:\n"
        + related_lines
        + b"---\n\n"
        + body
    )


def _write(root: Path, relative: str, *, related: tuple[str, ...] = ()) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_document(related=related))
    return path


def test_archives_explicit_documents_to_their_vault_relative_destinations(
    tmp_path: Path,
) -> None:
    first = _write(tmp_path, ".vault/research/first.md")
    second = _write(tmp_path, ".vault/plan/nested/second.md")
    first_bytes = first.read_bytes()
    second_bytes = second.read_bytes()

    result = archive_documents(
        tmp_path,
        (Path(".vault/research/first.md"), ".vault/plan/nested/second.md"),
    )

    assert result.status == "updated"
    assert result.archived_count == 2
    assert result.paths == (
        Path(".vault/_archive/research/first.md"),
        Path(".vault/_archive/plan/nested/second.md"),
    )
    assert not first.exists()
    assert not second.exists()
    assert (tmp_path / result.paths[0]).read_bytes() == first_bytes
    assert (tmp_path / result.paths[1]).read_bytes() == second_bytes


def test_preflight_rejects_any_collision_without_moving_another_document(
    tmp_path: Path,
) -> None:
    first = _write(tmp_path, ".vault/research/first.md")
    second = _write(tmp_path, ".vault/plan/second.md")
    destination = tmp_path / ".vault/_archive/plan/second.md"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"existing historical evidence")

    with pytest.raises(ArchiveDocumentsError, match="destination already exists"):
        archive_documents(
            tmp_path,
            (".vault/research/first.md", ".vault/plan/second.md"),
        )

    assert first.is_file()
    assert second.is_file()
    assert destination.read_bytes() == b"existing historical evidence"


def test_rolls_back_an_earlier_real_move_when_a_later_file_is_locked(
    tmp_path: Path,
) -> None:
    first = _write(tmp_path, ".vault/research/first.md")
    locked = _write(tmp_path, ".vault/plan/locked.md")
    first_bytes = first.read_bytes()

    if os.name == "nt":
        with (
            locked.open("rb"),
            pytest.raises(ArchiveDocumentsError, match="Archive move failed"),
        ):
            archive_documents(
                tmp_path,
                (".vault/research/first.md", ".vault/plan/locked.md"),
            )
    else:
        original_mode = stat.S_IMODE(locked.parent.stat().st_mode)
        locked.parent.chmod(stat.S_IREAD | stat.S_IEXEC)
        try:
            with pytest.raises(ArchiveDocumentsError, match="Archive move failed"):
                archive_documents(
                    tmp_path,
                    (".vault/research/first.md", ".vault/plan/locked.md"),
                )
        finally:
            locked.parent.chmod(original_mode)

    assert first.read_bytes() == first_bytes
    assert locked.is_file()
    assert not (tmp_path / ".vault/_archive/research/first.md").exists()
    assert not (tmp_path / ".vault/_archive/plan/locked.md").exists()


@pytest.mark.parametrize(
    "paths, message",
    [
        ((), "at least one"),
        ((".vault/research/only.md", ".vault/research/only.md"), "Duplicate"),
        ((".vault/_archive/research/old.md",), "outside _archive"),
        (("outside.md",), "must be under"),
        ((".vault/research/../research/only.md",), "confined"),
    ],
)
def test_preflight_rejects_unsafe_explicit_path_sets(
    tmp_path: Path, paths: tuple[str, ...], message: str
) -> None:
    source = _write(tmp_path, ".vault/research/only.md")

    with pytest.raises(ArchiveDocumentsError, match=message):
        archive_documents(tmp_path, paths)

    assert source.is_file()


def test_dry_run_reports_cross_links_without_changing_bytes(tmp_path: Path) -> None:
    source = _write(tmp_path, ".vault/research/source.md")
    referer = _write(
        tmp_path,
        ".vault/plan/consumer.md",
        related=("source",),
    )
    before = source.read_bytes()

    result = archive_documents(tmp_path, (".vault/research/source.md",), dry_run=True)

    assert result.status == "unchanged"
    assert result.dry_run is True
    assert result.cross_link_paths == (Path(".vault/plan/consumer.md"),)
    assert source.read_bytes() == before
    assert referer.is_file()
    assert result.to_dict() == {
        "status": "unchanged",
        "archived_count": 1,
        "paths": [".vault/_archive/research/source.md"],
        "cross_link_paths": [".vault/plan/consumer.md"],
        "dry_run": True,
    }


def test_preflight_refuses_a_symlinked_source_without_touching_the_target(
    tmp_path: Path,
) -> None:
    target = _write(tmp_path, ".vault/research/target.md")
    link = tmp_path / ".vault/research/link.md"
    try:
        os.symlink(target, link)
    except OSError as exc:
        pytest.fail(f"test host must support a local symlink: {exc}")

    with pytest.raises(ArchiveDocumentsError, match="symlink"):
        archive_documents(tmp_path, (".vault/research/link.md",))

    assert target.is_file()
    assert link.is_symlink()


def test_preflight_refuses_a_non_regular_markdown_path(tmp_path: Path) -> None:
    directory = tmp_path / ".vault/research/not-a-document.md"
    directory.mkdir(parents=True)

    with pytest.raises(ArchiveDocumentsError, match="not a regular file"):
        archive_documents(tmp_path, (".vault/research/not-a-document.md",))

    assert directory.is_dir()


def test_refuses_a_configured_vault_reached_through_a_symlinked_parent(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    external = tmp_path / "external"
    document = _write(external / "vault", "research/secret.md")
    project.mkdir()
    try:
        os.symlink(external, project / "linked", target_is_directory=True)
    except OSError as exc:
        pytest.fail(f"test host must support a local directory symlink: {exc}")

    previous = os.environ.get("VAULTSPEC_DOCS_DIR")
    os.environ["VAULTSPEC_DOCS_DIR"] = "linked/vault"
    reset_config()
    try:
        with pytest.raises(ArchiveDocumentsError, match="escapes the project root"):
            archive_documents(project, ("linked/vault/research/secret.md",))
    finally:
        if previous is None:
            os.environ.pop("VAULTSPEC_DOCS_DIR", None)
        else:
            os.environ["VAULTSPEC_DOCS_DIR"] = previous
        reset_config()

    assert document.is_file()


def test_restores_explicit_archived_documents_to_exact_vault_destinations(
    tmp_path: Path,
) -> None:
    first = _write(tmp_path, ".vault/_archive/research/first.md")
    second = _write(tmp_path, ".vault/_archive/plan/nested/second.md")
    first_bytes = first.read_bytes()
    second_bytes = second.read_bytes()

    result = restore_documents(
        tmp_path,
        (
            ".vault/_archive/research/first.md",
            Path(".vault/_archive/plan/nested/second.md"),
        ),
    )

    assert result.status == "updated"
    assert result.restored_count == 2
    assert result.paths == (
        Path(".vault/research/first.md"),
        Path(".vault/plan/nested/second.md"),
    )
    assert not first.exists()
    assert not second.exists()
    assert (tmp_path / result.paths[0]).read_bytes() == first_bytes
    assert (tmp_path / result.paths[1]).read_bytes() == second_bytes


def test_restore_preflight_rejects_collision_without_moving_another_document(
    tmp_path: Path,
) -> None:
    first = _write(tmp_path, ".vault/_archive/research/first.md")
    second = _write(tmp_path, ".vault/_archive/plan/second.md")
    destination = _write(tmp_path, ".vault/plan/second.md")
    destination_bytes = destination.read_bytes()

    with pytest.raises(RestoreDocumentsError, match="destination already exists"):
        restore_documents(
            tmp_path,
            (".vault/_archive/research/first.md", ".vault/_archive/plan/second.md"),
        )

    assert first.is_file()
    assert second.is_file()
    assert destination.read_bytes() == destination_bytes


def test_restore_rolls_back_an_earlier_real_move_when_a_later_file_is_locked(
    tmp_path: Path,
) -> None:
    first = _write(tmp_path, ".vault/_archive/research/first.md")
    locked = _write(tmp_path, ".vault/_archive/plan/locked.md")
    first_bytes = first.read_bytes()

    if os.name == "nt":
        with (
            locked.open("rb"),
            pytest.raises(RestoreDocumentsError, match="Restore move failed"),
        ):
            restore_documents(
                tmp_path,
                (".vault/_archive/research/first.md", ".vault/_archive/plan/locked.md"),
            )
    else:
        original_mode = stat.S_IMODE(locked.parent.stat().st_mode)
        locked.parent.chmod(stat.S_IREAD | stat.S_IEXEC)
        try:
            with pytest.raises(RestoreDocumentsError, match="Restore move failed"):
                restore_documents(
                    tmp_path,
                    (
                        ".vault/_archive/research/first.md",
                        ".vault/_archive/plan/locked.md",
                    ),
                )
        finally:
            locked.parent.chmod(original_mode)

    assert first.read_bytes() == first_bytes
    assert locked.is_file()
    assert not (tmp_path / ".vault/research/first.md").exists()
    assert not (tmp_path / ".vault/plan/locked.md").exists()


@pytest.mark.parametrize(
    "paths, message",
    [
        ((), "at least one"),
        ((".vault/_archive/research/only.md",) * 2, "Duplicate"),
        ((".vault/research/only.md",), "under _archive"),
        (("outside.md",), "must be under"),
        ((".vault/_archive/research/../research/only.md",), "confined"),
    ],
)
def test_restore_preflight_rejects_unsafe_explicit_path_sets(
    tmp_path: Path, paths: tuple[str, ...], message: str
) -> None:
    source = _write(tmp_path, ".vault/_archive/research/only.md")

    with pytest.raises(RestoreDocumentsError, match=message):
        restore_documents(tmp_path, paths)

    assert source.is_file()


def test_restore_dry_run_reports_cross_links_without_changing_bytes(
    tmp_path: Path,
) -> None:
    source = _write(tmp_path, ".vault/_archive/research/source.md")
    referer = _write(tmp_path, ".vault/plan/consumer.md", related=("source",))
    before = source.read_bytes()

    result = restore_documents(
        tmp_path, (".vault/_archive/research/source.md",), dry_run=True
    )

    assert result.status == "unchanged"
    assert result.dry_run is True
    assert result.cross_link_paths == (Path(".vault/plan/consumer.md"),)
    assert source.read_bytes() == before
    assert referer.is_file()
    assert result.to_dict() == {
        "status": "unchanged",
        "restored_count": 1,
        "paths": [".vault/research/source.md"],
        "deduplicated_count": 0,
        "deduplicated_paths": [],
        "cross_link_paths": [".vault/plan/consumer.md"],
        "dry_run": True,
    }


def test_restore_preflight_refuses_a_symlinked_source_and_destination_parent(
    tmp_path: Path,
) -> None:
    target = _write(tmp_path, ".vault/_archive/research/target.md")
    link = tmp_path / ".vault/_archive/research/link.md"
    try:
        os.symlink(target, link)
    except OSError as exc:
        pytest.fail(f"test host must support a local symlink: {exc}")

    with pytest.raises(RestoreDocumentsError, match="symlink"):
        restore_documents(tmp_path, (".vault/_archive/research/link.md",))

    assert target.is_file()
    assert link.is_symlink()


def test_restore_preflight_refuses_a_destination_parent_symlink(
    tmp_path: Path,
) -> None:
    source = _write(tmp_path, ".vault/_archive/research/source.md")
    external = tmp_path / "external"
    external.mkdir()
    destination_parent = tmp_path / ".vault/research"
    try:
        os.symlink(external, destination_parent, target_is_directory=True)
    except OSError as exc:
        pytest.fail(f"test host must support a local directory symlink: {exc}")

    with pytest.raises(RestoreDocumentsError, match="escapes vault"):
        restore_documents(tmp_path, (".vault/_archive/research/source.md",))

    assert source.is_file()
    assert not (external / "source.md").exists()


def test_restore_deduplicates_an_identical_live_destination_only_when_opted_in(
    tmp_path: Path,
) -> None:
    archived = _write(tmp_path, ".vault/_archive/index/duplicate.md")
    destination = tmp_path / ".vault/index/duplicate.md"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(archived.read_bytes())

    result = restore_documents(
        tmp_path,
        (".vault/_archive/index/duplicate.md",),
        deduplicate_identical=True,
    )

    assert result.status == "updated"
    assert result.restored_count == 0
    assert result.deduplicated_count == 1
    assert result.paths == ()
    assert result.deduplicated_paths == (Path(".vault/_archive/index/duplicate.md"),)
    assert not archived.exists()
    assert destination.is_file()
    assert result.to_dict()["deduplicated_paths"] == [
        ".vault/_archive/index/duplicate.md"
    ]


def test_restore_deduplication_refuses_a_nonidentical_destination(
    tmp_path: Path,
) -> None:
    archived = _write(tmp_path, ".vault/_archive/index/duplicate.md")
    destination = tmp_path / ".vault/index/duplicate.md"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"different evidence\n")

    with pytest.raises(RestoreDocumentsError, match="not byte-identical"):
        restore_documents(
            tmp_path,
            (".vault/_archive/index/duplicate.md",),
            deduplicate_identical=True,
        )

    assert archived.is_file()
    assert destination.read_bytes() == b"different evidence\n"


def test_restore_rollback_reinstates_a_deduplicated_source_after_later_failure(
    tmp_path: Path,
) -> None:
    duplicate = _write(tmp_path, ".vault/_archive/index/duplicate.md")
    duplicate_bytes = duplicate.read_bytes()
    live_duplicate = tmp_path / ".vault/index/duplicate.md"
    live_duplicate.parent.mkdir(parents=True)
    live_duplicate.write_bytes(duplicate_bytes)
    locked = _write(tmp_path, ".vault/_archive/plan/locked.md")

    if os.name == "nt":
        with (
            locked.open("rb"),
            pytest.raises(RestoreDocumentsError, match="Restore move failed"),
        ):
            restore_documents(
                tmp_path,
                (
                    ".vault/_archive/index/duplicate.md",
                    ".vault/_archive/plan/locked.md",
                ),
                deduplicate_identical=True,
            )
    else:
        original_mode = stat.S_IMODE(locked.parent.stat().st_mode)
        locked.parent.chmod(stat.S_IREAD | stat.S_IEXEC)
        try:
            with pytest.raises(RestoreDocumentsError, match="Restore move failed"):
                restore_documents(
                    tmp_path,
                    (
                        ".vault/_archive/index/duplicate.md",
                        ".vault/_archive/plan/locked.md",
                    ),
                    deduplicate_identical=True,
                )
        finally:
            locked.parent.chmod(original_mode)

    assert duplicate.read_bytes() == duplicate_bytes
    assert live_duplicate.read_bytes() == duplicate_bytes
    assert locked.is_file()
    assert not (tmp_path / ".vault/plan/locked.md").exists()
