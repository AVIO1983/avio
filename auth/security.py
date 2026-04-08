from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or base64.b64encode(os.urandom(16)).decode("utf-8")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return base64.b64encode(digest).decode("utf-8"), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    calculated, _ = hash_password(password, salt)
    return hmac.compare_digest(calculated, stored_hash)


def generate_totp_secret() -> str:
    return base64.b32encode(os.urandom(10)).decode("utf-8").replace("=", "")


def _hotp(secret: str, counter: int, digits: int = 6) -> str:
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8), casefold=True)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = (struct.unpack(">I", h[offset : offset + 4])[0] & 0x7FFFFFFF) % (10**digits)
    return str(code).zfill(digits)


def verify_totp(secret: str, otp: str, interval: int = 30, window: int = 1) -> bool:
    counter = int(time.time()) // interval
    for delta in range(-window, window + 1):
        if _hotp(secret, counter + delta) == otp:
            return True
    return False


def build_otpauth_uri(username: str, secret: str, issuer: str = "DigitalServiceManager") -> str:
    return f"otpauth://totp/{issuer}:{username}?secret={secret}&issuer={issuer}"
