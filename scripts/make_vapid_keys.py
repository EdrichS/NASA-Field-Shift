"""Create the Web Push (VAPID) key pair for browser alerts and write it to .env.push
(gitignored; the backend loads it after .env). Prints only the public key.

Usage: make vapid        (refuses to overwrite existing keys; pass --force to replace them,
                          which unsubscribes every browser that already opted in)
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

OUT = Path(__file__).resolve().parents[1] / ".env.push"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main() -> int:
    if OUT.exists() and "--force" not in sys.argv:
        print(f"{OUT.name} already exists; keeping the current keys (use --force to replace).")
        return 0
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_numbers().private_value.to_bytes(32, "big")
    public = key.public_key().public_bytes(serialization.Encoding.X962,
                                           serialization.PublicFormat.UncompressedPoint)
    OUT.write_text(
        "# Web Push (VAPID) keys for SowSmart browser alerts. Made by scripts/make_vapid_keys.py.\n"
        f"VAPID_PUBLIC_KEY={b64url(public)}\n"
        f"VAPID_PRIVATE_KEY={b64url(private)}\n"
        "VAPID_SUBJECT=mailto:noreply@sowsmart.invalid\n"
    )
    OUT.chmod(0o600)
    print(f"Wrote {OUT.name}. Public key: {b64url(public)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
