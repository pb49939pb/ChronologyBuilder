#!/usr/bin/env python3
"""
Dev-only tool for minting LawFirmAgent license tokens. NOT imported by the app itself — this is
something you run by hand on your own machine, never shipped/packaged with the app.

Design: a license token is a small signed statement — {customer, tier, issued_at, expires_at} —
signed with an Ed25519 private key you hold. The app (webapp/license.py) only ever needs the
PUBLIC key (committed to the repo, not a secret) to verify a token offline, with no network call
and no per-customer list to keep in sync. Minting a new token, renewing, or extending a customer
just means running `issue` again with this same private key — no app rebuild needed.

The private key is the one piece of real secret material here and is deliberately kept OUTSIDE
this repo entirely (default: ~/.lawfirmagent_keys/), so it structurally cannot end up in a GitHub
push no matter what git commands run inside the repo. See generate-keypair's docstring below.

Usage:
    python scripts/license_tool.py generate-keypair
    python scripts/license_tool.py issue --tier 12month --customer "Acme Law Firm"
    python scripts/license_tool.py issue --tier lifetime --customer "Acme Law Firm"
    python scripts/license_tool.py verify "<token>"
"""
import argparse
import base64
import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

DEFAULT_KEY_DIR = Path.home() / ".lawfirmagent_keys"
DEFAULT_PRIVATE_KEY_PATH = DEFAULT_KEY_DIR / "license_signing_key.pem"
REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_KEY_REPO_PATH = REPO_ROOT / "webapp" / "license_public_key.pem"

TIER_DURATIONS = {
    "3month": timedelta(days=90),
    "12month": timedelta(days=365),
    "lifetime": None,  # no expiration
}


def _b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64u_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def cmd_generate_keypair(args):
    """Generates a new Ed25519 signing keypair. The PRIVATE key goes to ~/.lawfirmagent_keys/ (or
    --key-path), well outside this repo's directory tree — the only thing that ever gets committed
    is the PUBLIC key at webapp/license_public_key.pem, which is not sensitive (a public key can't
    be used to mint new valid licenses, only to verify ones signed by the matching private key)."""
    key_path = Path(args.key_path) if args.key_path else DEFAULT_PRIVATE_KEY_PATH
    if key_path.exists() and not args.force:
        print(f"A private key already exists at {key_path} — refusing to overwrite it "
              f"(this would invalidate every license token already issued). Pass --force if you "
              f"really mean to replace it.", file=sys.stderr)
        return 1
    if str(REPO_ROOT) in str(key_path.resolve()):
        print(f"Refusing to write the private key inside the repo ({REPO_ROOT}) — it must never "
              f"be committed. Use --key-path to point somewhere outside the repo.", file=sys.stderr)
        return 1

    private_key = Ed25519PrivateKey.generate()
    key_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    key_path.write_bytes(private_bytes)
    key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600 — owner read/write only

    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    PUBLIC_KEY_REPO_PATH.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_KEY_REPO_PATH.write_bytes(public_bytes)

    print(f"Private signing key written to: {key_path}  (0600 permissions, keep this safe —")
    print(f"                                            it is the ONLY thing that can mint valid licenses)")
    print(f"Public key written to:          {PUBLIC_KEY_REPO_PATH}  (safe to commit to git)")
    return 0


def cmd_issue(args):
    key_path = Path(args.key_path) if args.key_path else DEFAULT_PRIVATE_KEY_PATH
    if not key_path.exists():
        print(f"No private key found at {key_path} — run generate-keypair first.", file=sys.stderr)
        return 1
    private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        print(f"{key_path} is not an Ed25519 private key.", file=sys.stderr)
        return 1

    issued_at = datetime.now(timezone.utc)
    duration = TIER_DURATIONS[args.tier]
    expires_at = (issued_at + duration) if duration else None

    payload = {
        "customer": args.customer,
        "tier": args.tier,
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
    }
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = private_key.sign(payload_bytes)
    token = f"{_b64u_encode(payload_bytes)}.{_b64u_encode(signature)}"

    print(f"Tier:       {args.tier}")
    print(f"Customer:   {args.customer}")
    print(f"Issued:     {issued_at.date().isoformat()}")
    print(f"Expires:    {expires_at.date().isoformat() if expires_at else 'never (lifetime)'}")
    print()
    print("License token (paste this into the app's /license page):")
    print(token)
    return 0


def cmd_verify(args):
    """Sanity-checks a token against the PUBLIC key, exactly like the app itself does — useful to
    confirm a token you just issued (or one a customer reports trouble with) is actually valid,
    without needing to open the app."""
    if not PUBLIC_KEY_REPO_PATH.exists():
        print(f"No public key found at {PUBLIC_KEY_REPO_PATH} — run generate-keypair first.", file=sys.stderr)
        return 1
    public_key = serialization.load_pem_public_key(PUBLIC_KEY_REPO_PATH.read_bytes())
    if not isinstance(public_key, Ed25519PublicKey):
        print(f"{PUBLIC_KEY_REPO_PATH} is not an Ed25519 public key.", file=sys.stderr)
        return 1

    try:
        payload_b64, sig_b64 = args.token.strip().split(".")
        payload_bytes = _b64u_decode(payload_b64)
        signature = _b64u_decode(sig_b64)
        public_key.verify(signature, payload_bytes)
        payload = json.loads(payload_bytes)
    except Exception as e:
        print(f"INVALID — {e}")
        return 1

    print("Signature: VALID")
    print(json.dumps(payload, indent=2))
    expires_at = payload.get("expires_at")
    if expires_at:
        expired = datetime.now(timezone.utc) > datetime.fromisoformat(expires_at)
        print(f"Expired:   {expired}")
    else:
        print("Expired:   never (lifetime)")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate-keypair", help="Create the signing keypair (do this once, ever).")
    p_gen.add_argument("--key-path", help=f"Where to write the private key (default: {DEFAULT_PRIVATE_KEY_PATH})")
    p_gen.add_argument("--force", action="store_true", help="Overwrite an existing private key.")
    p_gen.set_defaults(func=cmd_generate_keypair)

    p_issue = sub.add_parser("issue", help="Mint a new license token.")
    p_issue.add_argument("--tier", required=True, choices=sorted(TIER_DURATIONS))
    p_issue.add_argument("--customer", required=True, help="Firm/customer name, embedded in the token for your own records.")
    p_issue.add_argument("--key-path", help=f"Private key to sign with (default: {DEFAULT_PRIVATE_KEY_PATH})")
    p_issue.set_defaults(func=cmd_issue)

    p_verify = sub.add_parser("verify", help="Check a token's signature/expiration without opening the app.")
    p_verify.add_argument("token")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
