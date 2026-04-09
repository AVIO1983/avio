from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from database.db_manager import DatabaseManager


class ServiceRepository:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def list_services(self) -> list[dict[str, Any]]:
        return self.db.fetch_all("SELECT * FROM services WHERE is_deleted=0 ORDER BY name")

    def add_service(self, name: str, description: str = "") -> int:
        now = datetime.utcnow().isoformat()
        return self.db.execute(
            "INSERT INTO services(name, description, created_at, updated_at, is_deleted) VALUES(?,?,?,?,0)",
            (name, description, now, now),
        )

    def soft_delete_service(self, service_id: int) -> None:
        self.db.execute("UPDATE services SET is_deleted=1, updated_at=? WHERE id=?", (datetime.utcnow().isoformat(), service_id))


class CommissionRepository:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def upsert_rule(self, service_id: int, rule_type: str, value: float) -> None:
        now = datetime.utcnow().isoformat()
        existing = self.db.fetch_one(
            "SELECT id FROM commission_rules WHERE service_id=? AND is_deleted=0 ORDER BY id DESC LIMIT 1",
            (service_id,),
        )
        if existing:
            self.db.execute(
                "UPDATE commission_rules SET rule_type=?, value=?, updated_at=? WHERE id=?",
                (rule_type, value, now, existing["id"]),
            )
        else:
            self.db.execute(
                "INSERT INTO commission_rules(service_id, rule_type, value, updated_at, is_deleted) VALUES(?,?,?,?,0)",
                (service_id, rule_type, value, now),
            )

    def get_rule_for_service(self, service_id: int) -> dict[str, Any] | None:
        return self.db.fetch_one(
            "SELECT * FROM commission_rules WHERE service_id=? AND is_deleted=0 ORDER BY id DESC LIMIT 1",
            (service_id,),
        )


class TransactionRepository:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def generate_transaction_id(self) -> str:
        return f"TXN-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    def create_transaction(self, payload: dict[str, Any]) -> int:
        return self.db.execute(
            """
            INSERT INTO transactions(
                transaction_id, txn_datetime, customer_name, phone_number, service_id, description,
                amount, commission, final_amount, payment_mode, status, duplicate_flag, is_deleted
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,0)
            """,
            (
                payload["transaction_id"],
                payload["txn_datetime"],
                payload["customer_name"],
                payload.get("phone_number", ""),
                payload["service_id"],
                payload.get("description", ""),
                payload["amount"],
                payload["commission"],
                payload["final_amount"],
                payload["payment_mode"],
                payload["status"],
                payload.get("duplicate_flag", 0),
            ),
        )

    def recent_transactions(self, limit: int = 300) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT t.*, s.name AS service_name
            FROM transactions t
            JOIN services s ON t.service_id = s.id
            WHERE t.is_deleted=0
            ORDER BY t.id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def soft_delete_transaction(self, transaction_id: str) -> None:
        self.db.execute(
            "UPDATE transactions SET is_deleted=1, deleted_at=? WHERE transaction_id=?",
            (datetime.utcnow().isoformat(), transaction_id),
        )

    def is_duplicate(self, customer_name: str, amount: float, service_id: int, minutes: int = 30) -> bool:
        query = """
            SELECT id FROM transactions
            WHERE customer_name=? AND amount=? AND service_id=?
            AND is_deleted=0
            AND datetime(txn_datetime) >= datetime('now', ?)
            LIMIT 1
        """
        window = f"-{minutes} minutes"
        return self.db.fetch_one(query, (customer_name, amount, service_id, window)) is not None

    def customer_suggestions(self, query: str) -> list[str]:
        rows = self.db.fetch_all(
            """
            SELECT DISTINCT customer_name
            FROM transactions
            WHERE is_deleted=0 AND customer_name LIKE ?
            ORDER BY customer_name
            LIMIT 5
            """,
            (f"%{query}%",),
        )
        return [r["customer_name"] for r in rows]
