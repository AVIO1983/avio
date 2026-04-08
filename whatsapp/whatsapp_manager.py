from __future__ import annotations

import urllib.parse
import webbrowser
from datetime import datetime


class WhatsAppManager:
    def send_message_web(self, phone_number: str, message: str) -> str:
        encoded = urllib.parse.quote(message)
        url = f"https://web.whatsapp.com/send?phone={phone_number}&text={encoded}"
        webbrowser.open(url)
        return url

    @staticmethod
    def format_transaction_message(transaction: dict) -> str:
        return (
            f"Transaction Summary\n"
            f"ID: {transaction.get('transaction_id')}\n"
            f"Customer: {transaction.get('customer_name')}\n"
            f"Service: {transaction.get('service_name')}\n"
            f"Amount: Rs {float(transaction.get('final_amount', 0)):.2f}\n"
            f"Date: {transaction.get('txn_datetime')}"
        )

    @staticmethod
    def format_daily_report(report: dict) -> str:
        now = datetime.now().strftime("%d-%m-%Y")
        return (
            f"Daily Report ({now})\n"
            f"Period: {report['from']} to {report['to']}\n"
            f"Income: Rs {float(report['total_income']):.2f}\n"
            f"Commission: Rs {float(report['total_commission']):.2f}\n"
            f"Transactions: {report['total_transactions']}"
        )
