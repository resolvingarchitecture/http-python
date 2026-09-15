# Changelog

## 0.1.0

- Initial HTTP/HTTPS client: `HttpClient` (`from_config`, `start`/`stop`/`send`),
  GET/POST/PUT/DELETE, HTTP and HTTPS (stdlib `ssl`), optional proxy,
  trust-all-certs test escape hatch, 403/408/410/418/451/511 blocked-response
  logging.
- Depends on `ra-common` for `Envelope`.
- Client only - no server/SPA/WebSocket hosting (see `DESIGN.md`).
