"""
Trust-on-first-use (TOFU) client pairing, for remote/tower mode only (see TOWER_SETUP.md).

In remote mode the Flask server runs on a separate "tower" machine, reached over a private LAN
link by the Electron client on the paralegal's laptop — see app.py's _enforce_pairing_key, which is
a complete no-op when bound to loopback (i.e. every dev/test run and local-mode use). Once the
server is actually network-exposed, this is the only thing standing between "anything that can
reach this address" and full access to every case's PHI, so it's worth being precise about what
guarantee it does and doesn't provide:

Electron generates a random key on first launch (see electron/main.js's getOrCreatePairingKey) and
attaches it to every request as the X-Chronology-Pairing-Key header, with no manual pairing step.
The server has no paired key on first boot; whichever key arrives on the very first request gets
permanently remembered (this file's job); every request after that must match exactly, or it's
rejected. This is a real guarantee for the ACTUAL deployment topology this app targets (a direct
point-to-point Ethernet cable, nothing else ever plugged into that segment) — the first device that
can possibly reach the tower over that link is, by construction, the laptop. It's a much weaker
guarantee on a shared/switched network, where "whoever gets there first" isn't necessarily trusted.

This authenticates "a device holding this key," not the laptop's hardware specifically — if the key
file were ever copied off the laptop, that copy would work too. Re-pairing (deleting
PAIRING_KEY_FILE) should only be done while the two machines are cabled together in isolation
again, same discipline as the original setup — otherwise whichever device reaches the tower next
becomes the new trusted one.
"""
from __future__ import annotations

import hmac
import threading

import db

PAIRING_KEY_FILE = db.get_app_data_dir() / "paired_client_key.token"

_lock = threading.Lock()


def check(header_value: str | None) -> bool:
    """True if `header_value` is the paired client's key — pairing it as the trusted key first if
    none exists yet (see module docstring). A missing/empty header never pairs and never matches."""
    if not header_value:
        return False
    with _lock:
        if not PAIRING_KEY_FILE.exists():
            PAIRING_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            PAIRING_KEY_FILE.write_text(header_value)
            return True
        return hmac.compare_digest(header_value, PAIRING_KEY_FILE.read_text().strip())
