"""The single-variable dotenv reader over real files."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vaultspec_core.config import read_dotenv_value

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit]

NAME = "VAULTSPEC_EXAMPLE_TOKEN"


def _dotenv(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"{NAME}=plain\n", "plain"),
        (f"export {NAME}=exported\n", "exported"),
        (f"  {NAME} = spaced  \n", "spaced"),
        (f'{NAME}="double quoted"\n', "double quoted"),
        (f"{NAME}='single quoted'\n", "single quoted"),
        (f'{NAME}="keeps # and = inside"  # comment\n', "keeps # and = inside"),
        (f"{NAME}=value # trailing comment\n", "value"),
        (f"{NAME}=hash#inside\n", "hash#inside"),
        (f"{NAME}=$HOME/literal\n", "$HOME/literal"),
        (f"# {NAME}=commented\n\n{NAME}=live\n", "live"),
        (f"{NAME}=first\n{NAME}=second\n", "second"),
        (f"OTHER=1\n{NAME}_SUFFIX=near\n{NAME}=exact\n", "exact"),
    ],
    ids=[
        "plain",
        "export",
        "spaces",
        "double quotes",
        "single quotes",
        "quoted hash",
        "trailing comment",
        "hash inside word",
        "no interpolation",
        "commented line skipped",
        "last assignment wins",
        "exact name only",
    ],
)
def test_reads_the_named_value(tmp_path: Path, text: str, expected: str) -> None:
    assert read_dotenv_value(_dotenv(tmp_path, text), NAME) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "OTHER=1\n",
        f"# {NAME}=commented\n",
        f"{NAME}=\n",
        f"{NAME}=   \n",
        f'{NAME}=""\n',
        f'{NAME}="unterminated\nrest"\n',
        f"{NAME}\n",
        f"{NAME}_SUFFIX=near\n",
    ],
    ids=[
        "empty file",
        "other variable",
        "commented",
        "empty value",
        "whitespace value",
        "empty quotes",
        "multiline quote",
        "no assignment",
        "longer name",
    ],
)
def test_absent_blank_or_malformed_is_none(tmp_path: Path, text: str) -> None:
    assert read_dotenv_value(_dotenv(tmp_path, text), NAME) is None


def test_byte_order_mark_is_tolerated(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_bytes(f"{NAME}=bom\n".encode("utf-8-sig"))

    assert read_dotenv_value(path, NAME) == "bom"


def test_missing_file_is_none(tmp_path: Path) -> None:
    assert read_dotenv_value(tmp_path / ".env", NAME) is None


def test_directory_is_none(tmp_path: Path) -> None:
    assert read_dotenv_value(tmp_path, NAME) is None


def test_undecodable_file_is_none(tmp_path: Path) -> None:
    path = tmp_path / ".env"
    path.write_bytes(b"\xff\xfe\xfa" + f"{NAME}=value\n".encode())

    assert read_dotenv_value(path, NAME) is None
