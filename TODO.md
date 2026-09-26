# TODO

- [x] **Identity metadata leak, fixed 2026-09-26**: `DEFAULT_USER_AGENT` was
      the project-identifying literal `"ra-http-client"` - see DESIGN.md
      "Identity metadata leaks". Now generic.
- [ ] **Real SOCKS5 support, required before any Tor use** - not just a
      missing feature. Reuse in `tor-client-python`: swap
      `tor_client.http.fetch_via_socks` (GET-only, HTTP-only) for
      `HttpClient` configured with `proxy_host`/`proxy_port` pointed at the
      SOCKS layer - needs `http.client` proxy support to speak SOCKS5
      (currently only a plain CONNECT/HTTP proxy is implemented; see
      `client.py`'s `_request`). Once added, verify (don't assume) that the
      destination hostname is sent as a SOCKS5 domain-name request, not
      resolved via local DNS first - `http-cpp`'s
      `ConnectThroughSocks5` is the reference for what "done right" looks
      like; `bitcoin-client-java`'s bitcoinj DNS-seed bug (fixed
      2026-09-25) is what "done wrong" costs.
- [ ] `sendContentOnly`-equivalent body path once `ra_common`'s route module
      grows an `ExternalRoute` analogue (see `DESIGN.md`).
- [ ] Typed blocked-response report once `ra_common.network` grows a
      `NetworkConnectionReport` equivalent (see `DESIGN.md`).
- [ ] Connection reuse/pooling across calls (each `send()` opens and closes
      a fresh connection today).
- [ ] Resolve `Envelope.url` from an `ExternalRoute` destination `NetworkPeer`
      when `url` is unset, mirroring `HTTPService.sendOut`'s fallback -
      deferred with the `ExternalRoute` item above.
