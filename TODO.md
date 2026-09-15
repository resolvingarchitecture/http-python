# TODO

- [ ] Reuse in `tor-client-python`: swap `tor_client.http.fetch_via_socks`
      (GET-only, HTTP-only) for `HttpClient` configured with
      `proxy_host`/`proxy_port` pointed at the SOCKS layer - needs
      `http.client` proxy support to speak SOCKS5 (currently only a plain
      CONNECT/HTTP proxy is implemented; see `client.py`'s `_request`).
- [ ] `sendContentOnly`-equivalent body path once `ra_common`'s route module
      grows an `ExternalRoute` analogue (see `DESIGN.md`).
- [ ] Typed blocked-response report once `ra_common.network` grows a
      `NetworkConnectionReport` equivalent (see `DESIGN.md`).
- [ ] Connection reuse/pooling across calls (each `send()` opens and closes
      a fresh connection today).
- [ ] Resolve `Envelope.url` from an `ExternalRoute` destination `NetworkPeer`
      when `url` is unset, mirroring `HTTPService.sendOut`'s fallback -
      deferred with the `ExternalRoute` item above.
