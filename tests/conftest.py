"""Shared fixtures for the pymetalink test suite.

The console tests download files through the HTTP and FTP clients in
``metalink.download``.  Instead of relying on external mirrors, these fixtures
spin up loopback servers that serve a small deterministic payload.
"""

import hashlib
import http.server
import threading

import pytest

# The payload is generated deterministically so its checksums can be baked
# into the ``.meta4`` fixtures under ``tests/``.
PAYLOAD_SIZE = 32768
PIECE_SIZE = 8192


def payload_bytes():
    """Return the deterministic payload shared by the test fixtures."""
    return b"".join(
        hashlib.sha256(str(i).encode()).digest() for i in range(PAYLOAD_SIZE // 32)
    )


@pytest.fixture(scope="session")
def payload():
    """The payload bytes together with their checksums."""
    data = payload_bytes()
    return {
        "data": data,
        "size": len(data),
        "md5": hashlib.md5(data).hexdigest(),
        "sha1": hashlib.sha1(data).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "pieces": [
            hashlib.sha1(data[i : i + PIECE_SIZE]).hexdigest()
            for i in range(0, len(data), PIECE_SIZE)
        ],
    }


@pytest.fixture(scope="session")
def payload_dir(tmp_path_factory, payload):
    """A directory containing ``payload.bin`` for the local servers to serve."""
    directory = tmp_path_factory.mktemp("payload")
    (directory / "payload.bin").write_bytes(payload["data"])
    return directory


class PayloadRequestHandler(http.server.BaseHTTPRequestHandler):
    """Serve the payload for any path, with Range and redirect support."""

    protocol_version = "HTTP/1.1"
    payload = b""

    def log_message(self, *args):
        pass

    def _respond(self, status, body, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Accept-Ranges", "bytes")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        self._respond(200, self.payload)

    def do_GET(self):
        if "/redirect/" in self.path:
            name = self.path.rstrip("/").rsplit("/", 1)[-1]
            host, port = self.server.server_address[:2]
            self._respond(
                302,
                b"",
                {"Location": "http://%s:%s/%s" % (host, port, name)},
            )
            return

        body = self.payload
        range_header = self.headers.get("Range")
        if range_header:
            start_text, _, end_text = range_header.partition("=")[2].partition("-")
            start = int(start_text)
            end = int(end_text) if end_text else len(body) - 1
            end = min(end, len(body) - 1)
            chunk = body[start : end + 1]
            self._respond(
                206,
                chunk,
                {"Content-Range": "bytes %d-%d/%d" % (start, end, len(body))},
            )
        else:
            self._respond(200, body)


@pytest.fixture(scope="session")
def http_server(payload):
    """A loopback HTTP server that serves the payload."""
    handler = type(
        "TestPayloadHandler", (PayloadRequestHandler,), {"payload": payload["data"]}
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="session")
def ftp_server(payload_dir):
    """A loopback FTP server with anonymous read access to the payload."""
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer

    authorizer = DummyAuthorizer()
    authorizer.add_anonymous(str(payload_dir), perm="elr")

    class LocalFTPHandler(FTPHandler):
        pass

    LocalFTPHandler.authorizer = authorizer

    server = FTPServer(("127.0.0.1", 0), LocalFTPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.close_all()
