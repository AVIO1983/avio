"""Simple license token starter for your own software.

This module signs license payloads using HMAC-SHA256.
Use this design for server-side verification or internal tooling.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


@dataclass(frozen=True)
class LicensePayload:
    subject: str
    product: str
    issued_at: int
    expires_at: int
    features: Dict[str, Any]

    def to_json_bytes(self) -> bytes:
        data = {
            "subject": self.subject,
            "product": self.product,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "features": self.features,
        }
        return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")


class LicenseManager:
    def __init__(self, secret_key: str):
        if len(secret_key) < 32:
            raise ValueError("secret_key should be at least 32 characters")
        self._secret_key = secret_key.encode("utf-8")

    @staticmethod
    def generate_secret_key() -> str:
        return secrets.token_urlsafe(48)

    def sign_license(self, payload: LicensePayload) -> str:
        message = payload.to_json_bytes()
        sig = hmac.new(self._secret_key, message, hashlib.sha256).digest()
        return f"{_b64url_encode(message)}.{_b64url_encode(sig)}"

    def verify_license(self, token: str, now: int | None = None) -> Dict[str, Any]:
        now = int(time.time()) if now is None else now

        try:
            encoded_payload, encoded_sig = token.split(".", maxsplit=1)
        except ValueError as exc:
            raise ValueError("Invalid token format") from exc

        payload_bytes = _b64url_decode(encoded_payload)
        provided_sig = _b64url_decode(encoded_sig)

        expected_sig = hmac.new(self._secret_key, payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(provided_sig, expected_sig):
            raise ValueError("Invalid signature")

        payload = json.loads(payload_bytes)
        if now > int(payload["expires_at"]):
            raise ValueError("License expired")
        return payload


def demo() -> None:
    secret = LicenseManager.generate_secret_key()
    manager = LicenseManager(secret)

    payload = LicensePayload(
        subject="customer-123",
        product="my-awesome-app",
        issued_at=int(time.time()),
        expires_at=int(time.time()) + 60 * 60 * 24 * 30,
        features={"pro": True, "max_projects": 50},
    )

    token = manager.sign_license(payload)
    verified = manager.verify_license(token)

    print("Secret key (store safely):", secret)
    print("License token:", token)
    print("Verified payload:", verified)


if __name__ == "__main__":
    demo()
