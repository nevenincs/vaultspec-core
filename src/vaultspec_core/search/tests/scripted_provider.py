"""A real local HTTP server that answers like the Jev endpoint, from a script.

The transport tests exercise the client against real sockets, real HTTP/1.1
keep-alive and real timeouts. Only the provider's decisions are scripted: each
request receives the next scripted reply, and the last reply repeats once the
script runs out. A search sends many requests concurrently, in no fixed order,
so a server may instead be given a responder that derives each reply from the
request it answers. The server records every request it receives and the peak
number it handled at once.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any, Self, override

if TYPE_CHECKING:
    from collections.abc import Callable
    from socketserver import BaseServer
    from types import TracebackType

__all__ = ["Received", "Reply", "ScriptedProvider"]


@dataclass(frozen=True)
class Reply:
    """One scripted provider reply.

    Attributes:
        status: The HTTP status.
        body: The raw body.
        content_type: The ``Content-Type`` header.
        headers: Extra headers, such as ``retry-after``.
        delay: Seconds to wait before replying.
        drop: Close the connection without replying at all.
    """

    status: int = 200
    body: bytes = b""
    content_type: str = "application/json"
    headers: tuple[tuple[str, str], ...] = ()
    delay: float = 0.0
    drop: bool = False

    @classmethod
    def json(
        cls,
        payload: object,
        status: int = 200,
        *,
        headers: tuple[tuple[str, str], ...] = (),
        delay: float = 0.0,
    ) -> Reply:
        """A JSON reply."""
        body = json.dumps(payload).encode("utf-8")
        return cls(status=status, body=body, headers=headers, delay=delay)

    @classmethod
    def html(cls, status: int, text: str) -> Reply:
        """An HTML reply, the shape an edge firewall answers with."""
        return cls(status=status, body=text.encode("utf-8"), content_type="text/html")


@dataclass(frozen=True)
class Received:
    """One request as the server received it.

    Attributes:
        headers: Request headers, keyed as the client sent them.
        body: The raw request body.
        client: The client's ``(host, port)``; one port per connection.
    """

    headers: dict[str, str]
    body: bytes
    client: tuple[str, int]

    def payload(self) -> dict[str, Any]:
        """The request body parsed as JSON."""
        return json.loads(self.body)


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        provider = _provider_of(self.server)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        host, port = self.client_address[:2]
        reply = provider.take(
            Received(dict(self.headers.items()), body, (str(host), int(port)))
        )
        provider.enter()
        try:
            if reply.delay:
                time.sleep(reply.delay)
            if reply.drop:
                self.close_connection = True
                return
            self.send_response(reply.status)
            self.send_header("Content-Type", reply.content_type)
            self.send_header("Content-Length", str(len(reply.body)))
            for name, value in reply.headers:
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(reply.body)
        finally:
            provider.leave()

    @override
    def log_message(self, format: str, *args: Any) -> None:
        """Keep the request log out of the test output."""


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, provider: ScriptedProvider) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.provider = provider

    @override
    def handle_error(self, request: Any, client_address: Any) -> None:
        """A client that gave up mid-reply is expected here; stay quiet."""


def _provider_of(server: BaseServer) -> ScriptedProvider:
    assert isinstance(server, _Server)
    return server.provider


class ScriptedProvider:
    """Serve scripted replies on ``127.0.0.1`` for the life of a ``with`` block.

    Args:
        replies: Replies served in order, the last one repeating.
        responder: Derives each reply from the request instead; used when
            no script is given.
    """

    def __init__(
        self, *replies: Reply, responder: Callable[[Received], Reply] | None = None
    ) -> None:
        if not replies and responder is None:
            raise ValueError("a script needs at least one reply or a responder")
        self._script = list(replies)
        self._responder = responder
        self._lock = threading.Lock()
        self._in_flight = 0
        self.received: list[Received] = []
        self.peak = 0
        self._server = _Server(self)
        # A short poll interval keeps shutdown, and so each test, fast.
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.02},
            daemon=True,
        )

    @property
    def endpoint(self) -> str:
        """The URL to hand the client."""
        host, port = self._server.server_address[:2]
        return f"http://{host!s}:{port}/v1/systemone"

    def take(self, received: Received) -> Reply:
        """Record *received* and return the reply scripted for it."""
        responder = self._responder
        with self._lock:
            self.received.append(received)
            if responder is None or self._script:
                if len(self._script) > 1:
                    return self._script.pop(0)
                return self._script[0]
        return responder(received)

    def enter(self) -> None:
        with self._lock:
            self._in_flight += 1
            self.peak = max(self.peak, self._in_flight)

    def leave(self) -> None:
        with self._lock:
            self._in_flight -= 1

    def __enter__(self) -> Self:
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
