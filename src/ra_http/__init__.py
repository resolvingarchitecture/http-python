"""http-client - a direct (non-anonymized) HTTP/HTTPS client for 1M5, in Python.

A Python port of ``http-client-java``'s outbound ``sendOut`` path
(``ra.http.HTTPService``) - see ``DESIGN.md`` for what was left out and why.
"""

from ra_common.envelope import Envelope

from .client import DEFAULT_REQUEST_TIMEOUT, DEFAULT_USER_AGENT, HttpClient, Status

__all__ = [
    "HttpClient",
    "Status",
    "Envelope",
    "DEFAULT_REQUEST_TIMEOUT",
    "DEFAULT_USER_AGENT",
]

__version__ = "0.1.0"
