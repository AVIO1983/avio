from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

DB_PATH = Path(__file__).resolve().parents[1] / "business_manager.db"


class DatabaseManager:
    def __init__(self, db_path: str | os.PathLike[str] | None = None) -> None:
        self.db_path = str(db_path or DB_PATH)
        self._ensure_parent()
        self._initialize_db()

    def _ensure_parent(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize_db(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    two_fa_enabled INTEGER DEFAULT 0,
                    two_fa_secret TEXT,
                    phone_number TEXT,
                    created_at TEXT NOT NULL,
                    is_deleted INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_deleted INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS commission_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_id INTEGER NOT NULL,
                    rule_type TEXT NOT NULL CHECK(rule_type IN ('fixed', 'percentage')),
                    value REAL NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_deleted INTEGER DEFAULT 0,
                    FOREIGN KEY(service_id) REFERENCES services(id)
                );

                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id TEXT UNIQUE NOT NULL,
                    txn_datetime TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    phone_number TEXT,
                    service_id INTEGER NOT NULL,
                    description TEXT,
                    amount REAL NOT NULL,
                    commission REAL NOT NULL,
                    final_amount REAL NOT NULL,
                    payment_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duplicate_flag INTEGER DEFAULT 0,
                    deleted_at TEXT,
                    is_deleted INTEGER DEFAULT 0,
                    FOREIGN KEY(service_id) REFERENCES services(id)
                );

                CREATE TABLE IF NOT EXISTS backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_file TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    backup_type TEXT NOT NULL,
                    notes TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(txn_datetime);
                CREATE INDEX IF NOT EXISTS idx_txn_service ON transactions(service_id);
                CREATE INDEX IF NOT EXISTS idx_txn_customer ON transactions(customer_name);
                """
            )
        self.seed_defaults()

    def seed_defaults(self) -> None:
        services = [
            "Aadhaar money withdrawal",
            "Aadhaar money deposit",
            "Online money transfer",
            "Aadhaar update services",
            "PAN card services",
            "Voter ID services",
            "Online applications",
            "Xerox (B/W)",
            "Color printing",
            "WhatsApp document printing",
        ]
        now = datetime.utcnow().isoformat()
        with self.connection() as conn:
            for service in services:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO services(name, description, created_at, updated_at, is_deleted)
                    VALUES(?, '', ?, ?, 0)
                    """,
                    (service, now, now),
                )

    def fetch_all(self, query: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    def fetch_one(self, query: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
            return dict(row) if row else None

    def execute(self, query: str, params: Iterable[Any] = ()) -> int:
        with self.connection() as conn:
            cur = conn.execute(query, tuple(params))
            return cur.lastrowid

    def create_backup_record(self, backup_file: str, backup_type: str, notes: dict[str, Any] | None = None) -> None:
        self.execute(
            "INSERT INTO backups(backup_file, created_at, backup_type, notes) VALUES(?, ?, ?, ?)",
            (backup_file, datetime.utcnow().isoformat(), backup_type, json.dumps(notes or {})),
        )
