"""
Offline license verification. Companion to scripts/license_tool.py (that's the tool that MINTS
tokens with a private key you hold outside this repo; this module only ever VERIFIES a token
against the matching PUBLIC key, which is not sensitive and is committed alongside this file).

A license token is `<base64url payload>.<base64url signature>`, where payload is a canonical-JSON
dict {customer, tier, issued_at, expires_at} and signature is an Ed25519 signature over the payload
bytes. Verifying needs no network call — the whole point, since this app runs disconnected from
the internet (see PRODUCT_DEFINITION.md/TOWER_SETUP.md).

The token itself lives OUTSIDE this repo, in the same per-OS app-data directory db.py already uses
for durable case storage (get_app_data_dir()) — it's deployment-specific data, not source code.
"""
from __future__ import annotations

import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

import db


def _resource_path(*relative_parts: str) -> Path:
    """Same PyInstaller frozen/dev-mode resolution as app.py's helper of the same name — kept as
    its own small copy here rather than importing from app.py, to avoid a needless cross-module
    coupling for three lines. See scripts/build_backend.py for how license_public_key.pem is added
    as a PyInstaller data file at the bundle root, matching the frozen branch below."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS).joinpath(*relative_parts)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.joinpath(*relative_parts)


PUBLIC_KEY_PATH = _resource_path("license_public_key.pem")
LICENSE_FILE = db.get_app_data_dir() / "license.token"
# Tracks the latest timestamp this app has ever actually observed, specifically to catch the
# system clock being rolled backward to make an expired token look current again. Not meant to
# stop a determined attacker (there isn't one here — this gates a business relationship with one
# firm, not adversarial DRM), just to stop the license silently outliving its real expiration.
CLOCK_STATE_FILE = db.get_app_data_dir() / "license_clock_state.json"
CLOCK_ROLLBACK_TOLERANCE = timedelta(hours=6)  # small allowance for normal NTP/timezone drift


TIER_LABELS = {"3month": "3-Month", "12month": "12-Month", "lifetime": "Lifetime"}


class InvalidLicense(Exception):
    """Raised with a short, user-facing reason — shown as-is on the /license page."""


def _b64u_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def _load_public_key() -> Ed25519PublicKey:
    if not PUBLIC_KEY_PATH.exists():
        raise InvalidLicense("This build is missing its license public key — reinstall the app.")
    return serialization.load_pem_public_key(PUBLIC_KEY_PATH.read_bytes())


def _check_clock_rollback(now: datetime) -> None:
    """Refuses a license (regardless of its own expires_at) if the system clock is now noticeably
    earlier than the latest time this app has already seen — otherwise winding the clock back
    would make an expired token look valid again. Otherwise records `now` as the new high-water
    mark. Fails open (does nothing) if the state file is unreadable/corrupt — a lost anti-rollback
    guard is a much smaller problem than the app refusing to start over a corrupted local file."""
    last_seen = None
    try:
        if CLOCK_STATE_FILE.exists():
            last_seen = datetime.fromisoformat(json.loads(CLOCK_STATE_FILE.read_text())["last_seen_at"])
    except Exception:
        last_seen = None

    if last_seen is not None and now < last_seen - CLOCK_ROLLBACK_TOLERANCE:
        raise InvalidLicense(
            "This machine's clock appears to have moved backward since this app last ran — "
            "please correct the system date/time."
        )

    if last_seen is None or now > last_seen:
        try:
            CLOCK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            CLOCK_STATE_FILE.write_text(json.dumps({"last_seen_at": now.isoformat()}))
        except Exception:
            pass  # best-effort — see docstring


def decode_and_verify(token: str, *, _now: datetime | None = None) -> dict:
    """Verifies a token's signature and expiration. Raises InvalidLicense with a short reason on
    any failure; returns the decoded payload dict on success. `_now` is only for tests."""
    now = _now or datetime.now(timezone.utc)

    try:
        payload_b64, sig_b64 = token.strip().split(".")
        payload_bytes = _b64u_decode(payload_b64)
        signature = _b64u_decode(sig_b64)
    except Exception:
        raise InvalidLicense("This license key is malformed.")

    public_key = _load_public_key()
    try:
        public_key.verify(signature, payload_bytes)
    except InvalidSignature:
        raise InvalidLicense("This license key's signature doesn't check out — it may be corrupted or fake.")

    try:
        payload = json.loads(payload_bytes)
    except Exception:
        raise InvalidLicense("This license key is malformed.")

    expires_at = payload.get("expires_at")
    if expires_at:
        if now > datetime.fromisoformat(expires_at):
            raise InvalidLicense(f"This license expired on {expires_at[:10]}.")

    _check_clock_rollback(now)
    return payload


def get_current_license() -> dict:
    """Returns {"valid": bool, "payload": dict | None, "reason": str | None} for whatever token is
    currently installed (see LICENSE_FILE) — read fresh every call rather than cached, since a
    single Ed25519 verify is well under a millisecond and this app has one local user, not
    meaningful request volume to optimize for."""
    if not LICENSE_FILE.exists():
        return {"valid": False, "payload": None, "reason": "No license key has been entered yet."}
    token = LICENSE_FILE.read_text().strip()
    try:
        payload = decode_and_verify(token)
        return {"valid": True, "payload": payload, "reason": None}
    except InvalidLicense as e:
        return {"valid": False, "payload": None, "reason": str(e)}


def install_license(token: str) -> dict:
    """Validates `token` and, only if valid, saves it as the active license. Raises InvalidLicense
    (propagated to the caller/route) without touching LICENSE_FILE if it doesn't check out."""
    payload = decode_and_verify(token)
    LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
    LICENSE_FILE.write_text(token.strip())
    return payload


def _format_date(dt: datetime) -> str:
    """"Jul 25, 2027" — deliberately not using strftime's day-of-month no-leading-zero flag
    (%-d on macOS/Linux, %#d on Windows) since this needs to render identically on the Windows
    tower this app actually ships to (see TOWER_SETUP.md)."""
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


def get_license_display_info() -> dict:
    """Precomputed, template-ready license status for the small badge shown on every page (top
    right — see _license_badge.html) — date formatting and days-remaining/percent-elapsed math
    belongs here, not scattered across Jinja template logic."""
    status = get_current_license()
    if not status["valid"]:
        return {"valid": False}

    payload = status["payload"]
    tier = payload["tier"]
    info = {
        "valid": True,
        "customer": payload["customer"],
        "tier": tier,
        "tier_label": TIER_LABELS.get(tier, tier),
        "expires_display": None,
        "days_remaining": None,
        "percent_elapsed": None,
    }

    expires_at = payload.get("expires_at")
    if expires_at:
        issued = datetime.fromisoformat(payload["issued_at"])
        expires = datetime.fromisoformat(expires_at)
        now = datetime.now(timezone.utc)
        info["expires_display"] = _format_date(expires)
        info["days_remaining"] = max(0, (expires - now).days)
        total_seconds = (expires - issued).total_seconds()
        elapsed_seconds = (now - issued).total_seconds()
        info["percent_elapsed"] = (
            max(0, min(100, round(elapsed_seconds / total_seconds * 100))) if total_seconds > 0 else 100
        )

    return info
