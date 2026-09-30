---
stack: [steamos, decky, python, linux, tls]
kind: gotcha
last_verified: 2026-09-13
---

# A Decky Loader plugin's Python trusted no certificates on a Fedora-based image: every HTTPS call died

**One-liner:** Decky Loader runs plugin backends on its own PyInstaller-built Python, whose TLS trust store resolves to `/usr/lib/ssl`. That path exists on Debian- and Arch-style systems (including SteamOS) but is **absent on Fedora-based images** (ArmadaOS, Bazzite and similar). There, every HTTPS request from the plugin failed certificate verification. Fix: load a system CA bundle **additively** from a list of known locations, falling back to `certifi`, and log which one loaded.

*Playmoir's Decky plugin (S-5), 2026-09-13, verified on an AYN Odin 3 running ArmadaOS with a completed sign-in afterwards. Inert on SteamOS by design. SteamOS itself (the target platform) was not the failing case.*

## The fix (Playmoir's `platforms/decky/backend/http.py`)

Measured on the device first, not inferred: `/usr/lib/ssl` was absent, an empty context reproduced the exact `CERTIFICATE_VERIFY_FAILED`, and loading the bundle below put 121 CAs in the store and made the same request return 200.

```python
_CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",  # Debian, Arch/SteamOS, + Fedora's compat symlink
    "/etc/pki/tls/certs/ca-bundle.crt",    # Fedora/RHEL native
    "/etc/ssl/cert.pem",                   # BSD-style layouts
)

def _tls_context() -> ssl.SSLContext:      # built once and cached
    context = ssl.create_default_context()
    for bundle in _CA_BUNDLES:
        if not os.path.exists(bundle):
            continue
        try:
            context.load_verify_locations(cafile=bundle)   # ADDITIVE to the default store
            logger.info("[http] CA bundle loaded from %s", bundle)
            break
        except OSError:
            continue
    else:
        try:
            import certifi                  # decky-loader vendors it: a real last resort
            context.load_verify_locations(cafile=certifi.where())
        except Exception:
            logger.warning("[http] no CA bundle found; HTTPS calls may fail to verify")
    return context
```

Use that context for every request the backend makes. Two rules from the source:

- **Additive, always.** On a real Steam Deck, where the default store already resolves, this costs one file read and changes nothing about what's trusted.
- **Don't gate it on `cert_store_stats()`.** OpenSSL loads a hashed `capath` lazily, so a perfectly healthy Fedora context still reports `x509_ca == 0`. The system Python on the same device reports 0 CAs and connects fine. A prior-art plugin gated on exactly that stat.
- **Never fall back to an unverified context.** A plugin that silently stops checking certificates to "fix" a connection is worse than one that fails loudly.

## Other traps from the same hardware pass (recorded, not all resolved)

- `~/homebrew/plugins/` is `root:root 755` on both ArmadaOS and a stock Steam Deck, so a deploy script running as the normal user can't install. The general path needs `sudo`.
- On the Steam **beta** client, every Decky menu page rendered blank grey on a Deck; switching to Stable and reinstalling Decky cleared it (unverified whether the beta OS branch is the cause).

## Related

- `first-build-on-a-second-os.md`: other things that only break on the second platform.
