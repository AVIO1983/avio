from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


class ExportManager:
    def export_excel(self, report: dict[str, Any], output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        file = output_dir / f"report_{report['from']}_{report['to']}_{datetime.utcnow().strftime('%H%M%S')}.xlsx"

        with pd.ExcelWriter(file) as writer:
            summary_df = pd.DataFrame([
                {
                    "from": report["from"],
                    "to": report["to"],
                    "total_income": report["total_income"],
                    "total_commission": report["total_commission"],
                    "total_transactions": report["total_transactions"],
                }
            ])
            summary_df.to_excel(writer, index=False, sheet_name="Summary")
            pd.DataFrame(report["service_breakdown"]).to_excel(writer, index=False, sheet_name="Services")
            pd.DataFrame(report["payment_breakdown"]).to_excel(writer, index=False, sheet_name="Payments")
        return file

    def export_pdf(self, report: dict[str, Any], output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        file = output_dir / f"report_{report['from']}_{report['to']}_{datetime.utcnow().strftime('%H%M%S')}.pdf"
        c = canvas.Canvas(str(file), pagesize=A4)
        width, height = A4

        y = height - 40
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, y, "Digital Service Business Report")
        y -= 25
        c.setFont("Helvetica", 10)
        c.drawString(40, y, f"Period: {report['from']} to {report['to']}")
        y -= 20
        c.drawString(40, y, f"Total Income: Rs {report['total_income']:.2f}")
        y -= 15
        c.drawString(40, y, f"Total Commission: Rs {report['total_commission']:.2f}")
        y -= 15
        c.drawString(40, y, f"Total Transactions: {report['total_transactions']}")
        y -= 25

        c.setFont("Helvetica-Bold", 11)
        c.drawString(40, y, "Service Breakdown")
        y -= 18
        c.setFont("Helvetica", 9)
        for row in report["service_breakdown"][:18]:
            c.drawString(40, y, f"{row['service']}: {row['count']} txns, Rs {float(row['income'] or 0):.2f}")
            y -= 14
            if y < 60:
                c.showPage()
                y = height - 40

        c.showPage()
        c.save()
        return file
