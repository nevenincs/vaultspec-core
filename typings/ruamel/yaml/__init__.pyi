"""Minimal local type stub for the untyped-in-practice ``ruamel.yaml`` package.

``ruamel.yaml`` ships a ``py.typed`` marker, but several of its own inline
annotations (``YAML.dump``'s ``self: Any`` receiver, its ``StreamType``
alias) resolve to ``Unknown`` inside the library itself, so basedpyright
cannot recover a sound signature from the real source. This stub covers
only the round-trip surface this codebase actually calls: constructing a
:class:`YAML` handler, configuring it, and loading/dumping through it.
"""

from collections.abc import Mapping
from typing import IO, Any

class YAMLError(Exception): ...

class YAML:
    preserve_quotes: bool
    width: int | None

    def __init__(
        self,
        *,
        typ: str | list[str] | None = ...,
        pure: bool = ...,
        output: Any = ...,
        plug_ins: Any = ...,
    ) -> None: ...
    def indent(
        self,
        *,
        mapping: int | None = ...,
        sequence: int | None = ...,
        offset: int | None = ...,
    ) -> None: ...
    def load(self, stream: str) -> Any: ...
    def dump(
        self,
        data: Mapping[Any, Any] | list[Any],
        stream: IO[str],
        *,
        transform: Any = ...,
    ) -> None: ...
