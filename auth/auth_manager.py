from __future__ import annotations

from datetime import datetime

from auth.security import build_otpauth_uri, generate_totp_secret, hash_password, verify_password, verify_totp
from database.db_manager import DatabaseManager


class AuthManager:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self._ensure_default_admin()

    def _ensure_default_admin(self) -> None:
        user = self.db.fetch_one("SELECT id FROM users WHERE username='admin' AND is_deleted=0")
        if user:
            return
        password_hash, salt = hash_password("admin123")
        self.db.execute(
            """
            INSERT INTO users(username, password_hash, salt, created_at, is_deleted)
            VALUES(?,?,?,?,0)
            """,
            ("admin", password_hash, salt, datetime.utcnow().isoformat()),
        )

    def login(self, username: str, password: str) -> dict | None:
        user = self.db.fetch_one("SELECT * FROM users WHERE username=? AND is_deleted=0", (username,))
        if not user or not verify_password(password, user["password_hash"], user["salt"]):
            return None
        return user

    def verify_2fa(self, user: dict, otp: str) -> bool:
        if not user.get("two_fa_enabled"):
            return True
        secret = user.get("two_fa_secret")
        return bool(secret and verify_totp(secret, otp))

    def toggle_2fa(self, user_id: int, enable: bool) -> dict | None:
    def toggle_2fa(self, user_id: int, enable: bool) -> str | None:
        if not enable:
            self.db.execute("UPDATE users SET two_fa_enabled=0, two_fa_secret=NULL WHERE id=?", (user_id,))
            return None
        secret = generate_totp_secret()
        self.db.execute("UPDATE users SET two_fa_enabled=1, two_fa_secret=? WHERE id=?", (secret, user_id))
        user = self.db.fetch_one("SELECT username FROM users WHERE id=?", (user_id,))
        uri = build_otpauth_uri(user["username"], secret)
        return {"secret": secret, "uri": uri, "username": user["username"]}
        return build_otpauth_uri(user["username"], secret)

    def update_phone(self, user_id: int, phone_number: str) -> None:
        self.db.execute("UPDATE users SET phone_number=? WHERE id=?", (phone_number, user_id))
