from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from database.db_manager import DatabaseManager


class BackupManager:
    def __init__(self, db: DatabaseManager, backup_dir: Path | None = None):
        self.db = db
        self.backup_dir = backup_dir or Path(__file__).resolve().parents[1] / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, backup_type: str = "auto", notes: dict | None = None) -> Path:
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"business_manager_{stamp}.db"
        shutil.copy2(self.db.db_path, backup_file)
        self.db.create_backup_record(str(backup_file), backup_type, notes)
        return backup_file

    def list_backups(self) -> list[dict]:
        return self.db.fetch_all("SELECT * FROM backups ORDER BY id DESC")

    def restore_full(self, backup_file: str) -> None:
        shutil.copy2(backup_file, self.db.db_path)

    def selective_restore_transactions(self, backup_file: str) -> int:
        import sqlite3

        backup_conn = sqlite3.connect(backup_file)
        backup_conn.row_factory = sqlite3.Row
        rows = backup_conn.execute("SELECT * FROM transactions WHERE is_deleted=0").fetchall()
        restored = 0
        for row in rows:
            exists = self.db.fetch_one("SELECT id FROM transactions WHERE transaction_id=?", (row["transaction_id"],))
            if exists:
                continue
            self.db.execute(
                """
                INSERT INTO transactions(
                    transaction_id, txn_datetime, customer_name, phone_number, service_id, description,
                    amount, commission, final_amount, payment_mode, status, duplicate_flag, deleted_at, is_deleted
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row["transaction_id"],
                    row["txn_datetime"],
                    row["customer_name"],
                    row["phone_number"],
                    row["service_id"],
                    row["description"],
                    row["amount"],
                    row["commission"],
                    row["final_amount"],
                    row["payment_mode"],
                    row["status"],
                    row["duplicate_flag"],
                    row["deleted_at"],
                    row["is_deleted"],
                ),
            )
            restored += 1
        backup_conn.close()
        return restored
