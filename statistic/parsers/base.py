"""The common source abstraction over both transcript corpora.

:class:`TranscriptSource` is the single protocol both source adapters
(``ClaudeSource`` and ``CodexSource``) implement. Each adapter owns its schema
quirks entirely - call linkage, exit-status derivation, and cost attribution -
behind this interface, so every downstream layer sees only an iterable of
:class:`~statistic.normalize.models.CallRecord`. The protocol is generic over
the adapter's session handle type, which stays opaque to callers: they obtain
session handles from :meth:`TranscriptSource.iter_sessions` and feed each back
into :meth:`TranscriptSource.iter_calls` without inspecting it.

Both methods are lazy iterators. The corpus is large and streamed line by line,
so an adapter must never materialize a whole session or the whole corpus in
memory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from collections.abc import Iterator

    from statistic.normalize.models import CallRecord

#: The adapter-specific session-handle type. Opaque to downstream callers; each
#: adapter binds it to whatever it needs to enumerate a session's calls (a file
#: path, an index entry, a small metadata object).
SessionT = TypeVar("SessionT")


class TranscriptSource(Protocol[SessionT]):
    """Stream normalized calls from one agent-CLI transcript corpus.

    Implementations discover their session files under a source-specific home
    root (always injectable, so tests can point at fixture roots), apply the
    activity-window filter on transcript timestamps rather than file mtime, and
    emit validated :class:`~statistic.normalize.models.CallRecord` instances.
    """

    def iter_sessions(self) -> Iterator[SessionT]:
        """Yield each in-window session handle in the corpus.

        Returns:
            A lazy iterator over the adapter's opaque session handles. Sessions
            whose activity falls entirely outside the window are skipped.
        """
        ...

    def iter_calls(self, session: SessionT) -> Iterator[CallRecord]:
        """Yield the normalized calls of a single session.

        Args:
            session: A session handle previously yielded by
                :meth:`iter_sessions`.

        Returns:
            A lazy iterator over the session's normalized
            :class:`~statistic.normalize.models.CallRecord` instances, in
            transcript order.
        """
        ...
