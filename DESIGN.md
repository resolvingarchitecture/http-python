# Design

## Scope: client only

`http-client-java`'s `ra.http.HTTPService` is two things bolted together:
an outbound `sendOut` (an HTTP/HTTPS client), and a Jetty-based inbound
server (`launch()`, `EnvelopeHandler`, `SPAHandler`, `EnvelopeWebSocket`,
`EnvelopeJSONDataHandler`) for hosting Envelope-JSON APIs, SPAs, and
WebSockets. `tor-client-java` extends `HTTPService` specifically to reuse
that server half for Tor hidden-service hosting.

No other language port needs the server half: `tor-client-python` (and the
other non-JVM `tor-client-*` / `i2p-*` ports) are local-daemon/local-router
clients only, with no hidden-service hosting responsibility. So this port
covers `sendOut` only. If a Python HTTP server is ever needed here, it's a
separate module, not bolted onto this client.

## No `NetworkService` base class

`ra_common.network` (Python) is deliberately minimal - just `Network`,
`NetworkStatus`, `NetworkPeer` - with a note that "the full network service
layer is deferred to a later phase." There is no Python equivalent of
`ra.common.network.NetworkService` to extend, unlike Java. `HttpClient`
instead follows the shape `tor_client.TorClient` already established for
this gap: a plain class with `from_config`/`status`/`start`/`stop`/`send`,
no shared base type. When `ra_common` grows a real network-service
abstraction, both clients should be revisited together.

## `Envelope.url`/`.action`/`.headers`, not `.headers["url"]`

`tor_client.TorClient.send` reads `envelope.headers.get("url")` - a
pre-existing quirk from when `tor-client-python` was written against a
narrower `Envelope`. `ra_common.envelope.Envelope` has had proper `.url`
and `.action` (`Action.GET/POST/PUT/DELETE`) fields since before this port
was started, so `HttpClient.send` uses those directly, matching
`HTTPService.sendOut`'s `e.getURL()` / `e.getAction()`. Not backported into
`TorClient` - out of scope here.

## Body: always the whole Envelope as JSON (no `sendContentOnly`)

Java's default `sendOut` body is `e.toJSON()` (the whole Envelope) unless
the caller's `ExternalRoute.getSendContentOnly()` is set, in which case it's
just `e.getContent()`. `ExternalRoute` is a Java-only routing concept with
no port here, so `sendContentOnly` isn't either - `HttpClient.send` always
bodies the whole Envelope as JSON for POST/PUT/DELETE (unless a `Multipart`
is set). A future `sendContentOnly`-equivalent, if `ra_common`'s route
module grows one, is a small, additive change to `send()`.

## No `NetworkConnectionReport`

`HTTPService.handleFailure` builds a typed `NetworkConnectionReport` for
403/408/410/418/451/511 responses and posts it to the router's connection
tracking. `ra_common` (Python) has no such type yet (only `Network` /
`NetworkStatus` / `NetworkPeer` - see above), so blocked-response detection
here is logged and recorded as an `Envelope` error message only. Upgrade
this once `ra_common` gets a report type worth building one against.

## TLS: stdlib `ssl`, no third-party dependency

`ssl.create_default_context()` (real verification) or
`ssl._create_unverified_context()` (test-only, `trust_all_certs`) via
`http.client.HTTPSConnection`. No `httpx`/`requests` dependency - matches
this codebase's dependency-light default (see `1m5-core-java/TODO.md`'s
"no protobuf/gRPC" note on the same theme) and keeps this a peer of
`tor_client.http`'s stdlib-only approach, just with a real TLS layer instead
of the documented gap that module left open.
