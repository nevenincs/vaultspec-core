"""The product identity every release channel renders from.

A channel manifest repeats the same handful of facts - the distribution name,
the binaries it places, the release tag scheme, the licence - in four
different syntaxes. Declaring them once here is what lets one generator serve
every product in the family, and what keeps a Scoop manifest and a Homebrew
formula cut from the same release from disagreeing about what the product is.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Rust target triples the delivery matrix builds, mapped to the channel that
#: consumes each one. A triple absent here is not deliverable: it may exist as
#: a release asset, but no package manager will point at it.
WINDOWS_X86_64 = "x86_64-pc-windows-msvc"
MACOS_ARM64 = "aarch64-apple-darwin"
MACOS_X86_64 = "x86_64-apple-darwin"
LINUX_X86_64 = "x86_64-unknown-linux-gnu"
LINUX_ARM64 = "aarch64-unknown-linux-gnu"

#: The triples Scoop serves. Scoop is Windows-only by construction.
SCOOP_TARGETS = (WINDOWS_X86_64,)

#: The triples Homebrew serves. Homebrew runs on macOS and on Linux, so a
#: formula covers both - which is why the absence of a Linux ARM64 build is a
#: delivery gap and not merely a missing convenience: Homebrew on Linux ARM64
#: is a supported platform this product cannot currently be installed on.
HOMEBREW_TARGETS = (MACOS_ARM64, MACOS_X86_64, LINUX_X86_64, LINUX_ARM64)


@dataclass(frozen=True)
class Executable:
    """One console entry point carried by a target release bundle."""

    #: The name the binary is installed as, and the stem of its release asset.
    name: str
    #: Short description used where a channel labels the individual command.
    summary: str


@dataclass(frozen=True)
class Product:
    """One deliverable product and the identity its channels repeat."""

    #: PyPI distribution name; also the manifest and formula file stem.
    name: str
    #: Ruby class name for the Homebrew formula, e.g. ``VaultspecCore``.
    formula_class: str
    description: str
    homepage: str
    license: str
    #: Release tags are ``<tag_prefix><version>``.
    tag_prefix: str
    #: The executables carried by each target bundle, in installation order.
    executables: tuple[Executable, ...]
    #: Channel-specific caveats surfaced to whoever installs from a manifest.
    notes: tuple[str, ...] = ()
    #: The triples this product can actually RUN on. Distinct from what a
    #: package manager serves: Homebrew runs on macOS, but a CUDA-only
    #: product cannot, and offering an install there ships a binary that
    #: raises at startup. Empty means "every target the channel serves".
    supported_targets: tuple[str, ...] = ()
    #: Human-readable identity used by release metadata.
    display_name: str = ""
    #: Human-readable publisher identity used by release metadata.
    publisher: str = ""
    #: Copyright string used by release metadata.
    legal_copyright: str = ""

    def serves(self, target: str) -> bool:
        """Return whether this product may be offered on ``target``."""
        return not self.supported_targets or target in self.supported_targets

    def version_from_tag(self, tag: str) -> str:
        """Return the version a release tag names.

        Accepts the canonical ``<prefix><version>`` tag and the bare ``v``
        and unprefixed forms a maintainer may pass when reproducing a
        release locally.
        """
        for prefix in (self.tag_prefix, "v"):
            if tag.startswith(prefix):
                return tag[len(prefix) :]
        return tag

    def tag_for(self, version: str) -> str:
        """Return the release tag that publishes ``version``."""
        return f"{self.tag_prefix}{version}"

    def asset_name(self, executable: Executable, target: str) -> str:
        """Return the private staging filename for one binary on one target.

        This target-qualified name disambiguates matrix outputs before the
        bundle boundary. Public consumers use :meth:`bundle_name` instead.
        """
        return raw_asset_name(executable.name, target)

    def executable_name(self, executable: Executable, target: str) -> str:
        """Return the stable name of *executable* inside a target bundle."""
        return executable_filename(executable.name, target)

    def bundle_name(self, version: str, target: str) -> str:
        """Return the public archive filename for one product target."""
        return f"{self.name}-v{version}-{target}{archive_suffix(target)}"

    def release_base_url(self, version: str) -> str:
        """Return the immutable download base for one release."""
        return f"{self.homepage}/releases/download/{self.tag_for(version)}"


def is_windows_target(target: str) -> bool:
    """Return whether *target* is the Windows MSVC release target."""
    return target.endswith("windows-msvc")


def executable_filename(name: str, target: str) -> str:
    """Return the stable extracted filename for a binary name and target."""
    return f"{name}{'.exe' if is_windows_target(target) else ''}"


def raw_asset_name(name: str, target: str) -> str:
    """Return the target-qualified staging filename for one executable."""
    return f"{name}-{target}{'.exe' if is_windows_target(target) else ''}"


def archive_suffix(target: str) -> str:
    """Return the archive suffix used for a target platform."""
    return ".zip" if is_windows_target(target) else ".tar.gz"


VAULTSPEC_CORE = Product(
    name="vaultspec-core",
    formula_class="VaultspecCore",
    description="Decision-driven harness for coding agents, and humans.",
    homepage="https://github.com/nevenincs/vaultspec-core",
    license="MIT",
    tag_prefix="vaultspec-core-v",
    executables=(
        Executable(name="vaultspec-core", summary="the vaultspec-core CLI"),
        Executable(name="vaultspec-mcp", summary="the vaultspec MCP server"),
    ),
    # vaultspec-core is pure Python, and every target the channels serve has a
    # prepared distribution carrying the native dependencies it needs, so
    # supported_targets is left at its default.
    notes=(
        "Installs vaultspec-core and vaultspec-mcp.",
        "Each binary carries its own Python, Vaultspec and every dependency, "
        "so no launch needs a network.",
        "Upgrade through this channel: the binaries do not update themselves.",
        "Verify with: vaultspec-core --version",
    ),
    display_name="Vaultspec Core",
    publisher="Gergely Wootsch",
    legal_copyright="Copyright (c) Gergely Wootsch",
)

#: Every product this checkout generates channel manifests for, keyed by name.
PRODUCTS = {VAULTSPEC_CORE.name: VAULTSPEC_CORE}
