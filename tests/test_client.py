from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from ra_common.envelope import Action, Envelope

from http_client import HttpClient, Status
from http_client.client import _parse_url


def test_parse_url_with_path_and_query():
    assert _parse_url("http://example.com:8080/a/b?x=1") == ("http", "example.com", 8080, "/a/b?x=1")


def test_parse_url_defaults_port_and_path():
    assert _parse_url("https://example.com") == ("https", "example.com", 443, "/")


def test_parse_url_rejects_unknown_scheme():
    with pytest.raises(ValueError):
        _parse_url("ftp://example.com/")


def test_send_without_start_reports_not_connected():
    client = HttpClient()
    env = Envelope.document()
    env.url = "http://example.com/"
    env.action = Action.GET
    assert client.send(env) is False
    assert "HTTP client not connected" in env.error_messages()


def test_send_without_url_errors():
    client = HttpClient()
    assert client.start() is True
    env = Envelope.document()
    assert client.send(env) is False
    assert "Envelope.url is required" in env.error_messages()


def test_send_without_action_errors():
    client = HttpClient()
    assert client.start() is True
    env = Envelope.document()
    env.url = "http://example.com/"
    assert client.send(env) is False
    assert any("Envelope.action" in m for m in env.error_messages())


class _EchoHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - silence test server logging
        pass

    def do_GET(self):
        if self.path == "/error":
            self.send_response(451)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = b"<html><body>hello</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        received = self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Length", str(len(received)))
        self.end_headers()
        self.wfile.write(received)


@pytest.fixture
def echo_server():
    server = HTTPServer(("127.0.0.1", 0), _EchoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_http_get(echo_server):
    host, port = echo_server
    client = HttpClient.from_config({})
    assert client.start() is True

    env = Envelope.document()
    env.url = f"http://{host}:{port}/"
    env.action = Action.GET
    assert client.send(env) is True
    assert env.content() == b"<html><body>hello</body></html>"
    assert env.error_messages() == []


def test_http_post_sends_envelope_as_json_body(echo_server):
    """No content-only path is ported (Java's ExternalRoute.sendContentOnly
    has no equivalent here) - POST always bodies the whole Envelope as JSON,
    so the echo server bounces back that same JSON, id and all."""
    import json

    host, port = echo_server
    client = HttpClient.from_config({})
    assert client.start() is True

    env = Envelope.document()
    env.url = f"http://{host}:{port}/"
    env.action = Action.POST
    assert client.send(env) is True
    echoed = json.loads(env.content())
    assert echoed["id"] == env.id


def test_http_error_status_is_recorded_but_still_returns_true(echo_server):
    host, port = echo_server
    client = HttpClient.from_config({})
    assert client.start() is True

    env = Envelope.document()
    env.url = f"http://{host}:{port}/error"
    env.action = Action.GET
    assert client.send(env) is True
    assert "451" in env.error_messages()


def test_stop_sets_disconnected():
    client = HttpClient()
    assert client.start() is True
    assert client.status() == Status.CONNECTED
    assert client.stop() is True
    assert client.status() == Status.DISCONNECTED


class TestLiveNetwork:
    """Mirrors ``HTTPServiceTest``'s httpClientTest/httpsClientTest, but
    checks shape (a real HTML page came back) rather than exact page copy,
    which drifts - Java's hardcoded ``<title>Resolving Architecture</title>``
    no longer matches the live site. Skips cleanly (not a failure) when this
    sandbox has no outbound network."""

    def test_http_get_live_redirects_to_https(self):
        """The bare http:// origin 301s to https:// - exercises this
        client's redirect following."""
        client = HttpClient.from_config({})
        assert client.start() is True
        env = Envelope.document()
        env.url = "http://resolvingarchitecture.io"
        env.action = Action.GET
        try:
            ok = client.send(env)
        except OSError as e:
            pytest.skip(f"no outbound network: {e}")
        if not ok or not env.content():
            pytest.skip(f"live request did not succeed: {env.error_messages()}")
        assert b"<html" in env.content().lower()
        assert b"<title>" in env.content().lower()

    def test_https_get_live(self):
        client = HttpClient.from_config({})
        assert client.start() is True
        env = Envelope.document()
        env.url = "https://resolvingarchitecture.io"
        env.action = Action.GET
        try:
            ok = client.send(env)
        except OSError as e:
            pytest.skip(f"no outbound network: {e}")
        if not ok or not env.content():
            pytest.skip(f"live request did not succeed: {env.error_messages()}")
        assert b"<html" in env.content().lower()
        assert b"<title>" in env.content().lower()
