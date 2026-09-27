"""Guards for reading the latest release's payload before anything is downloaded.

Each case is a payload that must not become a recorded surface: a release that
is not this product's, one GitHub should never have called latest, and a wheel
set that does not name exactly one distribution. Recording any of them would
put a version in the references that no user installed.
"""

from __future__ import annotations

import pytest

from dev.packaging.products import VAULTSPEC_CORE
from dev.packaging.published_surface import (
    PublishedSurfaceError,
    parse_latest_release,
    repository,
)

pytestmark = pytest.mark.unit

WHEEL = "vaultspec_core-0.2.6-py3-none-any.whl"


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "tag_name": "vaultspec-core-v0.2.6",
        "draft": False,
        "prerelease": False,
        "assets": [
            {"name": WHEEL},
            {"name": "vaultspec_core-0.2.6.tar.gz"},
            {"name": "SHA256SUMS"},
        ],
    }
    payload.update(overrides)
    return payload


def test_a_published_release_names_its_version_and_its_one_wheel() -> None:
    """The tag's version and the wheel asset are what the recording reads."""
    release = parse_latest_release(_payload(), VAULTSPEC_CORE)

    assert release.tag == "vaultspec-core-v0.2.6"
    assert release.version == "0.2.6"
    assert release.wheel == WHEEL


@pytest.mark.parametrize("flag", ["draft", "prerelease"])
def test_a_draft_or_prerelease_is_refused(flag: str) -> None:
    """Neither is published, whatever endpoint returned it."""
    with pytest.raises(PublishedSurfaceError, match="draft or a prerelease"):
        parse_latest_release(_payload(**{flag: True}), VAULTSPEC_CORE)


def test_another_product_s_tag_is_refused() -> None:
    """A tag outside the product's scheme is not this product's release."""
    with pytest.raises(PublishedSurfaceError, match="not a vaultspec-core release"):
        parse_latest_release(_payload(tag_name="vaultspec-rag-v0.4.11"), VAULTSPEC_CORE)


@pytest.mark.parametrize(
    "assets",
    [
        [{"name": "vaultspec_core-0.2.6.tar.gz"}],
        [{"name": WHEEL}, {"name": "vaultspec_core-0.2.6-py3-none-win_amd64.whl"}],
    ],
    ids=["no-wheel", "two-wheels"],
)
def test_a_release_without_exactly_one_wheel_is_refused(
    assets: list[dict[str, str]],
) -> None:
    """The surface is read from one distribution; none or two is ambiguous."""
    with pytest.raises(PublishedSurfaceError, match="exactly one"):
        parse_latest_release(_payload(assets=assets), VAULTSPEC_CORE)


@pytest.mark.parametrize("name", [f"../{WHEEL}", f"dist\\{WHEEL}"])
def test_a_wheel_name_carrying_a_path_is_refused(name: str) -> None:
    """The asset name becomes a URL segment and a file name, never a path."""
    with pytest.raises(PublishedSurfaceError, match="with a path"):
        parse_latest_release(_payload(assets=[{"name": name}]), VAULTSPEC_CORE)


def test_the_repository_is_derived_from_the_product_homepage() -> None:
    """One declaration of where the product is released, reused here."""
    assert repository(VAULTSPEC_CORE) == "nevenincs/vaultspec-core"
