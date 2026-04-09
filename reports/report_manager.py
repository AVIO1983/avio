from __future__ import annotations

from datetime import date
from typing import Any

from database.db_manager import DatabaseManager


class ReportManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def summary(self, from_date: date, to_date: date) -> dict[str, Any]:
        params = (from_date.isoformat(), to_date.isoformat())
        totals = self.db.fetch_one(
            """
            SELECT
                COALESCE(SUM(final_amount),0) AS total_income,
                COALESCE(SUM(commission),0) AS total_commission,
                COUNT(*) AS total_transactions
            FROM transactions
            WHERE is_deleted=0
            AND date(txn_datetime) BETWEEN date(?) AND date(?)
            """,
            params,
        ) or {}

        service_breakdown = self.db.fetch_all(
            """
            SELECT s.name AS service, COUNT(*) AS count, SUM(t.final_amount) AS income
            FROM transactions t
            JOIN services s ON t.service_id=s.id
            WHERE t.is_deleted=0 AND date(t.txn_datetime) BETWEEN date(?) AND date(?)
            GROUP BY s.name
            ORDER BY income DESC
            """,
            params,
        )

        payment_breakdown = self.db.fetch_all(
            """
            SELECT payment_mode, COUNT(*) AS count, SUM(final_amount) AS amount
            FROM transactions
            WHERE is_deleted=0 AND date(txn_datetime) BETWEEN date(?) AND date(?)
            GROUP BY payment_mode
            ORDER BY amount DESC
            """,
            params,
        )
        return {
            **totals,
            "service_breakdown": service_breakdown,
            "payment_breakdown": payment_breakdown,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        }

    def dashboard_metrics(self) -> dict[str, Any]:
        today = self.db.fetch_one(
            """
            SELECT COALESCE(SUM(final_amount),0) AS today_income,
                   COUNT(*) AS today_transactions
            FROM transactions WHERE is_deleted=0 AND date(txn_datetime)=date('now')
            """
        ) or {}
        service_earnings = self.db.fetch_all(
            """
            SELECT s.name, COALESCE(SUM(t.final_amount),0) AS total
            FROM services s LEFT JOIN transactions t ON s.id=t.service_id AND t.is_deleted=0
            WHERE s.is_deleted=0
            GROUP BY s.id, s.name
            ORDER BY total DESC
            LIMIT 5
            """
        )
        return {**today, "top_services": service_earnings}
