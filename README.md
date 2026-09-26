# http (Python)

A direct (non-anonymized) HTTP/HTTPS client for **1M5**.

A Python port of [`http-java`](https://github.com/resolvingarchitecture/http-java)'s
outbound path (`ra.http.HTTPService.sendOut`). That class's other half - a
Jetty-based local server for hosting Envelope-JSON APIs / SPAs / WebSockets,
used e.g. by `tor-client-java` to serve a Tor hidden service - has no port
here; see `DESIGN.md`.

## Use

```python
from ra_common.envelope import Action, Envelope
from ra_http import HttpClient

client = HttpClient.from_config({})
client.start()                                 # nothing to dial in advance - always True

env = Envelope.document()
env.url = "https://example.com/"
env.action = Action.GET
client.send(env)                                # response body -> env.content(), errors -> env.error_messages()
```

### Config keys

| key | default | meaning |
|-----|---------|---------|
| `ra.http.client.trustallcerts` | `false` | skip TLS certificate verification (test-only) |
| `ra.http.client.proxyHost` / `proxyPort` | unset | HTTP CONNECT / plain-HTTP proxy |
| `ra.http.client.requestTimeoutSecs` | `30` | per-request timeout |
| `ra.http.client.userAgent` | a generic, widely-shared browser value | default `User-Agent`, overridden by an `Envelope` header |

## Build

```
python3.13 -m venv .venv
.venv/bin/pip install -e ../../common/ra-common-python
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```

## Identity metadata leaks

Checked and fixed (2026-09-26), the same class of bug found and fixed in
`http-java`'s OkHttp-based client: `DEFAULT_USER_AGENT` used to be
the literal string `"ra-http-client"` - itself a fingerprinting leak (it
identifies exactly which project made the request, an even smaller
anonymity set than a generic library name). Now a generic, widely-shared
browser value instead - same principle Tor Browser uses (every user
presents an identical, unremarkable fingerprint). See `DESIGN.md` "Identity
metadata leaks" for the full requirement, including one still-open check:
this client's proxy support is plain HTTP CONNECT, not SOCKS5, so it cannot
yet correctly reach a SOCKS5-only relay like `tor-client-java`'s
`TorSocksRelay` at all (a functional gap, not a metadata leak, but one that
must be closed before this client is trusted to route anything over Tor).

## Status

GET/POST/PUT/DELETE over HTTP and HTTPS (stdlib `ssl`, no third-party TLS
dependency), an optional CONNECT/plain-HTTP proxy (so `tor-client-python`
could reuse this instead of its own hand-rolled `http.py` - not wired up
yet), a trust-all-certs test escape hatch, and 403/408/410/418/451/511
blocked-response tagging (logged, not returned as a typed report - see
`DESIGN.md`). No multipart file upload beyond passing an already-built
`Multipart` through; no connection pooling/keep-alive reuse across calls.
See `TODO.md`.
