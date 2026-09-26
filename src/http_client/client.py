"""``HttpClient`` - a direct (non-anonymized) HTTP/HTTPS client.

Ports ``http-client-java``'s ``ra.http.HTTPService`` - outbound ``sendOut``
only. That class's other half (a Jetty-based local server for hosting
Envelope-JSON APIs / SPAs / WebSockets, used e.g. by ``tor-client-java`` to
serve a Tor hidden service) has no port here: nothing in this ecosystem
outside the JVM desktop stack needs it. See ``DESIGN.md``.
"""

from __future__ import annotations

import http.client
import logging
import ssl
import threading
import time
from enum import Enum
from urllib.parse import urlsplit

from ra_common.envelope import (
    HEADER_AUTHORIZATION,
    HEADER_CONTENT_DISPOSITION,
    HEADER_CONTENT_TRANSFER_ENCODING,
    HEADER_CONTENT_TYPE,
    HEADER_USER_AGENT,
    Action,
    Envelope,
)

_LOG = logging.getLogger(__name__)

DEFAULT_REQUEST_TIMEOUT = 30.0
# Not "ra-http-client": a project-identifying default is itself a fingerprinting leak - it
# tells every destination (and any on-path observer, for plain HTTP) exactly which library,
# and by extension which project, made the request, narrowing the anonymity set to whoever
# else runs this exact software. A generic, widely-shared value instead, same principle Tor
# Browser uses (every user presents an identical, unremarkable fingerprint) - see DESIGN.md
# "Identity metadata leaks".
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"

_PASSTHROUGH_HEADERS = (
    HEADER_AUTHORIZATION,
    HEADER_CONTENT_DISPOSITION,
    HEADER_CONTENT_TYPE,
    HEADER_CONTENT_TRANSFER_ENCODING,
    HEADER_USER_AGENT,
)

_METHOD_FOR_ACTION = {
    Action.GET: "GET",
    Action.POST: "POST",
    Action.PUT: "PUT",
    Action.DELETE: "DELETE",
}

# HTTP status -> a short "why this looks like blocking" tag, ported from
# HTTPService.handleFailure's switch (403/408/410/418/451/511).
_BLOCKED_CODES = {
    403: "BLOCKED-FORBIDDEN",
    408: "BLOCKED-TIMEOUT",
    410: "BLOCKED-GONE",
    418: "BLOCKED-TEAPOT",
    451: "BLOCKED-LEGAL",
    511: "BLOCKED-AUTHN",
}


class Status(str, Enum):
    CLOSED = "Closed"
    CONNECTED = "Connected"
    DISCONNECTED = "Disconnected"
    ERROR = "Error"


class HttpClient:
    """Stateless beyond config + status - safe to reuse across requests, one
    instance per caller (mirrors ``TorClient``'s shape, not a pooled
    connection manager)."""

    def __init__(self) -> None:
        self.trust_all_certs = False
        self.proxy_host: str | None = None
        self.proxy_port: int | None = None
        self.timeout = DEFAULT_REQUEST_TIMEOUT
        self.user_agent = DEFAULT_USER_AGENT
        self._status = Status.CLOSED
        self._lock = threading.Lock()

    @classmethod
    def from_config(cls, cfg: dict[str, str]) -> "HttpClient":
        """Config keys: ``ra.http.client.trustallcerts``,
        ``ra.http.client.proxyHost``, ``ra.http.client.proxyPort``,
        ``ra.http.client.requestTimeoutSecs``, ``ra.http.client.userAgent``."""
        c = cls()
        if "ra.http.client.trustallcerts" in cfg:
            c.trust_all_certs = cfg["ra.http.client.trustallcerts"].strip().lower() == "true"
        if "ra.http.client.proxyHost" in cfg:
            c.proxy_host = cfg["ra.http.client.proxyHost"]
        if "ra.http.client.proxyPort" in cfg:
            c.proxy_port = int(cfg["ra.http.client.proxyPort"])
        if "ra.http.client.requestTimeoutSecs" in cfg:
            c.timeout = float(cfg["ra.http.client.requestTimeoutSecs"])
        if "ra.http.client.userAgent" in cfg:
            c.user_agent = cfg["ra.http.client.userAgent"]
        return c

    def status(self) -> Status:
        with self._lock:
            return self._status

    def _set_status(self, s: Status) -> None:
        with self._lock:
            self._status = s

    def start(self) -> bool:
        """Nothing to dial in advance (unlike Tor's local daemon) - marks
        ready and returns ``True``."""
        self._set_status(Status.CONNECTED)
        return True

    def stop(self) -> bool:
        self._set_status(Status.DISCONNECTED)
        return True

    def send(self, envelope: Envelope) -> bool:
        """Fetch ``envelope.url`` into ``envelope``'s content (via
        ``add_content``, so ``envelope.message`` must be a ``DocumentMessage``
        - see ``Envelope.document()``). Errors go to ``envelope.add_error_message``.

        Returns ``False`` only on a client-side failure (not started, no URL,
        bad method, connection error) - matching ``HTTPService.sendOut``, an
        HTTP error *response* (4xx/5xx) still returns ``True`` with the status
        code recorded as an error message.
        """
        if self.status() != Status.CONNECTED:
            envelope.add_error_message("HTTP client not connected")
            return False

        url = envelope.url
        if not url:
            envelope.add_error_message("Envelope.url is required")
            return False
        try:
            scheme, host, port, path = _parse_url(url)
        except ValueError as e:
            envelope.add_error_message(str(e))
            return False

        method = _METHOD_FOR_ACTION.get(envelope.action)
        if method is None:
            envelope.add_error_message("Envelope.action must be set to Get, Post, Put, or Delete")
            return False

        headers: dict[str, str] = {}
        for name in _PASSTHROUGH_HEADERS:
            value = envelope.headers.get(name)
            if value:
                headers[name] = value
        headers.setdefault(HEADER_USER_AGENT, self.user_agent)

        # Java's HTTPService default path (no ExternalRoute.sendContentOnly,
        # a Java-only concept with no port here) always bodies the *whole*
        # Envelope as JSON, not just its content - matched here unconditionally.
        body: bytes | None = None
        mp = envelope.multipart
        if mp is not None:
            headers[HEADER_CONTENT_TYPE] = f"multipart/form-data; boundary={mp.boundary}"
            body = mp.finish().encode(mp.charset or "utf-8")
        elif method in ("POST", "PUT", "DELETE"):
            headers.setdefault(HEADER_CONTENT_TYPE, "application/json")
            body = envelope.to_json().encode("utf-8")

        start = time.monotonic()
        try:
            status_code, _resp_headers, resp_body = _request(
                scheme,
                host,
                port,
                path,
                method,
                headers,
                body,
                timeout=self.timeout,
                trust_all_certs=self.trust_all_certs,
                proxy_host=self.proxy_host,
                proxy_port=self.proxy_port,
            )
        except (OSError, ssl.SSLError, http.client.HTTPException) as e:
            _LOG.warning("HTTP request to %s failed: %s", url, e)
            envelope.add_error_message(str(e))
            return False
        elapsed_ms = (time.monotonic() - start) * 1000

        if status_code >= 400:
            tag = _BLOCKED_CODES.get(status_code)
            if tag:
                _LOG.warning("HTTP %s from %s: %s (%.0fms)", status_code, url, tag, elapsed_ms)
            else:
                _LOG.warning("HTTP %s from %s (%.0fms)", status_code, url, elapsed_ms)
            envelope.add_error_message(str(status_code))

        envelope.add_content(resp_body)
        return True


def _parse_url(url: str) -> tuple[str, str, int, str]:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError(f"unsupported scheme {parts.scheme!r} (only http/https)")
    if not parts.hostname:
        raise ValueError("URL has no host")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    return parts.scheme, parts.hostname, port, path


_MAX_REDIRECTS = 5


def _request(
    scheme: str,
    host: str,
    port: int,
    path: str,
    method: str,
    headers: dict[str, str],
    body: bytes | None,
    *,
    timeout: float,
    trust_all_certs: bool,
    proxy_host: str | None,
    proxy_port: int | None,
) -> tuple[int, list[tuple[str, str]], bytes]:
    """Follows 3xx ``Location`` redirects (same method + body each hop, up to
    ``_MAX_REDIRECTS``) - matches ``HTTPService``'s OkHttp clients, which are
    all built with ``followRedirects(true)``/``followSslRedirects(true)``."""
    for _ in range(_MAX_REDIRECTS):
        status, resp_headers, resp_body = _request_once(
            scheme, host, port, path, method, headers, body,
            timeout=timeout, trust_all_certs=trust_all_certs,
            proxy_host=proxy_host, proxy_port=proxy_port,
        )
        if status not in (301, 302, 303, 307, 308):
            return status, resp_headers, resp_body
        location = next((v for k, v in resp_headers if k.lower() == "location"), None)
        if not location:
            return status, resp_headers, resp_body
        scheme, host, port, path = _parse_url(_resolve_location(scheme, host, port, location))
    return status, resp_headers, resp_body


def _resolve_location(scheme: str, host: str, port: int, location: str) -> str:
    if location.startswith("http://") or location.startswith("https://"):
        return location
    default_port = {"http": 80, "https": 443}[scheme]
    authority = host if port == default_port else f"{host}:{port}"
    if location.startswith("/"):
        return f"{scheme}://{authority}{location}"
    return f"{scheme}://{authority}/{location}"


def _request_once(
    scheme: str,
    host: str,
    port: int,
    path: str,
    method: str,
    headers: dict[str, str],
    body: bytes | None,
    *,
    timeout: float,
    trust_all_certs: bool,
    proxy_host: str | None,
    proxy_port: int | None,
) -> tuple[int, list[tuple[str, str]], bytes]:
    ssl_context: ssl.SSLContext | None = None
    if scheme == "https":
        ssl_context = ssl._create_unverified_context() if trust_all_certs else ssl.create_default_context()

    conn: http.client.HTTPConnection
    request_path = path
    if proxy_host:
        if scheme == "https":
            conn = http.client.HTTPSConnection(proxy_host, proxy_port, timeout=timeout, context=ssl_context)
            conn.set_tunnel(host, port)
        else:
            conn = http.client.HTTPConnection(proxy_host, proxy_port, timeout=timeout)
            # a plain HTTP proxy expects an absolute-form request target
            request_path = f"http://{host}:{port}{path}"
    elif scheme == "https":
        conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ssl_context)
    else:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)

    try:
        conn.request(method, request_path, body=body, headers=headers)
        resp = conn.getresponse()
        resp_body = resp.read()
        return resp.status, resp.getheaders(), resp_body
    finally:
        conn.close()
