from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from PIL import Image
from tkcalendar import DateEntry
from tkinter import messagebox

from auth.auth_manager import AuthManager
from auth.security import build_totp_qr_png_bytes
from backup.backup_manager import BackupManager
from database.db_manager import DatabaseManager
from database.repositories import CommissionRepository, ServiceRepository, TransactionRepository
from reports.exporters import ExportManager
from reports.report_manager import ReportManager
from ui.widgets import CenteredTable
from utils.scheduler import DailyTaskScheduler
from whatsapp.whatsapp_manager import WhatsAppManager


class LoginFrame(ctk.CTkFrame):
    def __init__(self, master, auth: AuthManager, on_login):
        super().__init__(master)
        self.auth = auth
        self.on_login = on_login

        container = ctk.CTkFrame(self, corner_radius=16)
        container.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(container, text="Digital Service Manager", font=ctk.CTkFont(size=24, weight="bold")).pack(padx=30, pady=(20, 12))
        self.username = ctk.CTkEntry(container, placeholder_text="Username", width=280)
        self.username.pack(pady=8)
        self.password = ctk.CTkEntry(container, placeholder_text="Password", show="*", width=280)
        self.password.pack(pady=8)
        self.otp = ctk.CTkEntry(container, placeholder_text="2FA OTP (if enabled)", width=280)
        self.otp.pack(pady=8)

        ctk.CTkButton(container, text="Login", width=280, command=self.do_login).pack(pady=(12, 20))
        ctk.CTkLabel(container, text="Default: admin / admin123", text_color="gray").pack(pady=(0, 20))

    def do_login(self):
        user = self.auth.login(self.username.get().strip(), self.password.get().strip())
        if not user:
            messagebox.showerror("Login", "Invalid credentials")
            return
        if user.get("two_fa_enabled"):
            if not self.auth.verify_2fa(user, self.otp.get().strip()):
                messagebox.showerror("2FA", "Invalid OTP")
                return
        self.on_login(user)


class DashboardFrame(ctk.CTkFrame):
    def __init__(self, master, db: DatabaseManager, user: dict):
        super().__init__(master)
        self.db = db
        self.user = user
        self.service_repo = ServiceRepository(db)
        self.commission_repo = CommissionRepository(db)
        self.txn_repo = TransactionRepository(db)
        self.reports = ReportManager(db)
        self.exporter = ExportManager()
        self.backup = BackupManager(db)
        self.whatsapp = WhatsAppManager()

        self.scheduler = DailyTaskScheduler(callback=lambda: self.backup.create_backup("auto"))
        self.scheduler.start()

        self.pack(fill="both", expand=True)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self.show_page("dashboard")

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        ctk.CTkLabel(self.sidebar, text="⚙ Business Suite", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20, 10))

        buttons = [
            ("🏠 Dashboard", "dashboard"),
            ("💸 Transactions", "transactions"),
            ("🧮 Commission", "commission"),
            ("📊 Reports", "reports"),
            ("💾 Backup", "backup"),
            ("💬 WhatsApp", "whatsapp"),
            ("🔐 Settings", "settings"),
        ]
        for text, key in buttons:
            ctk.CTkButton(self.sidebar, text=text, width=180, command=lambda k=key: self.show_page(k)).pack(pady=6)
        self.appearance = ctk.CTkSwitch(self.sidebar, text="Dark mode", command=self._toggle_theme)
        self.appearance.select()
        self.appearance.pack(pady=16)

    def _toggle_theme(self):
        ctk.set_appearance_mode("dark" if self.appearance.get() else "light")

    def _build_main(self):
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.pages = {k: ctk.CTkFrame(self.main) for k in ["dashboard", "transactions", "commission", "reports", "backup", "whatsapp", "settings"]}
        for p in self.pages.values():
            p.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._build_dashboard_page()
        self._build_transactions_page()
        self._build_commission_page()
        self._build_reports_page()
        self._build_backup_page()
        self._build_whatsapp_page()
        self._build_settings_page()

    def show_page(self, key: str):
        self.pages[key].tkraise()
        if key == "dashboard":
            self.refresh_dashboard()
        if key == "transactions":
            self.refresh_transactions()

    def _card(self, parent, title: str, var: ctk.StringVar, color: str):
        card = ctk.CTkFrame(parent, corner_radius=14, fg_color=color)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(12, 4))
        ctk.CTkLabel(card, textvariable=var, font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(2, 12))
        return card

    def _build_dashboard_page(self):
        page = self.pages["dashboard"]
        ctk.CTkLabel(page, text="Dashboard", font=ctk.CTkFont(size=26, weight="bold")).pack(pady=12)

        row = ctk.CTkFrame(page, fg_color="transparent")
        row.pack(fill="x", padx=14)
        for i in range(4):
            row.grid_columnconfigure(i, weight=1)

        self.today_income_var = ctk.StringVar(value="0")
        self.today_txn_var = ctk.StringVar(value="0")
        self.total_txn_var = ctk.StringVar(value="0")
        self.top_service_var = ctk.StringVar(value="-")

        cards = [
            ("Today Income", self.today_income_var, "#1f6aa5"),
            ("Today Txns", self.today_txn_var, "#2d8a45"),
            ("Total Txns", self.total_txn_var, "#865cbf"),
            ("Top Service", self.top_service_var, "#bb6d1a"),
        ]
        for i, (t, v, c) in enumerate(cards):
            self._card(row, t, v, c).grid(row=0, column=i, padx=8, pady=6, sticky="ew")

        chart_wrap = ctk.CTkFrame(page)
        chart_wrap.pack(fill="both", expand=True, padx=14, pady=10)
        self.chart_frame = chart_wrap

    def refresh_dashboard(self):
        metrics = self.reports.dashboard_metrics()
        self.today_income_var.set(f"Rs {float(metrics.get('today_income', 0)):.2f}")
        self.today_txn_var.set(str(metrics.get("today_transactions", 0)))
        all_txn = len(self.txn_repo.recent_transactions(5000))
        self.total_txn_var.set(str(all_txn))
        top_services = metrics.get("top_services", [])
        self.top_service_var.set(top_services[0]["name"] if top_services else "-")
        self._render_charts(top_services)

    def _render_charts(self, top_services):
        for child in self.chart_frame.winfo_children():
            child.destroy()
        fig = Figure(figsize=(8, 3.4), dpi=100)
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)

        txns = self.txn_repo.recent_transactions(300)
        by_day = {}
        for t in txns:
            d = t["txn_datetime"][:10]
            by_day[d] = by_day.get(d, 0) + float(t["final_amount"])
        days = sorted(by_day.keys())[-7:]
        vals = [by_day[d] for d in days]
        ax1.plot(days, vals, marker="o")
        ax1.set_title("Daily Income")
        ax1.tick_params(axis="x", rotation=45)

        labels = [x["name"] for x in top_services[:5]] or ["No data"]
        sizes = [float(x["total"]) for x in top_services[:5]] or [1]
        ax2.pie(sizes, labels=labels, autopct="%1.0f%%")
        ax2.set_title("Service Distribution")

        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _build_transactions_page(self):
        page = self.pages["transactions"]
        ctk.CTkLabel(page, text="Transaction Management", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=8)
        form = ctk.CTkFrame(page)
        form.pack(fill="x", padx=10)

        self.customer_name = ctk.CTkEntry(form, placeholder_text="Customer Name")
        self.phone = ctk.CTkEntry(form, placeholder_text="Phone")
        services = self.service_repo.list_services()
        self.service_map = {s["name"]: s["id"] for s in services}
        self.service_option = ctk.CTkOptionMenu(form, values=list(self.service_map.keys()))
        self.desc = ctk.CTkEntry(form, placeholder_text="Description")
        self.amount = ctk.CTkEntry(form, placeholder_text="Amount")
        self.payment = ctk.CTkOptionMenu(form, values=["Cash", "UPI", "PhonePe", "Bank"])
        self.status = ctk.CTkOptionMenu(form, values=["Success", "Pending", "Failed"])

        widgets = [self.customer_name, self.phone, self.service_option, self.desc, self.amount, self.payment, self.status]
        for i, w in enumerate(widgets):
            w.grid(row=i // 4, column=i % 4, padx=8, pady=8, sticky="ew")
        for i in range(4):
            form.grid_columnconfigure(i, weight=1)

        ctk.CTkButton(form, text="Add Transaction", command=self.add_transaction).grid(row=2, column=0, columnspan=2, pady=8, sticky="ew")
        ctk.CTkButton(form, text="Delete Selected by ID", command=self.delete_transaction_prompt).grid(row=2, column=2, columnspan=2, pady=8, sticky="ew")

        self.table = CenteredTable(
            page,
            columns=["transaction_id", "txn_datetime", "customer_name", "service_name", "final_amount", "payment_mode", "status"],
            width=900,
            height=350,
        )
        self.table.pack(fill="both", expand=True, padx=10, pady=10)

    def _compute_commission(self, service_id: int, amount: float) -> float:
        rule = self.commission_repo.get_rule_for_service(service_id)
        if not rule:
            return 0.0
        if rule["rule_type"] == "fixed":
            return float(rule["value"])
        return amount * float(rule["value"]) / 100

    def add_transaction(self):
        try:
            amount = float(self.amount.get().strip())
        except ValueError:
            messagebox.showerror("Validation", "Amount must be numeric")
            return

        name = self.customer_name.get().strip()
        if not name:
            messagebox.showerror("Validation", "Customer name required")
            return

        service_id = self.service_map[self.service_option.get()]
        commission = self._compute_commission(service_id, amount)
        duplicate = self.txn_repo.is_duplicate(name, amount, service_id)
        payload = {
            "transaction_id": self.txn_repo.generate_transaction_id(),
            "txn_datetime": datetime.utcnow().isoformat(timespec="seconds"),
            "customer_name": name,
            "phone_number": self.phone.get().strip(),
            "service_id": service_id,
            "description": self.desc.get().strip(),
            "amount": amount,
            "commission": commission,
            "final_amount": amount + commission,
            "payment_mode": self.payment.get(),
            "status": self.status.get(),
            "duplicate_flag": int(duplicate),
        }
        self.txn_repo.create_transaction(payload)
        messagebox.showinfo("Saved", "Transaction added" + (" (duplicate flagged)" if duplicate else ""))
        self.refresh_transactions()

    def refresh_transactions(self):
        txns = self.txn_repo.recent_transactions()
        self.table.set_rows(txns)

    def delete_transaction_prompt(self):
        popup = ctk.CTkInputDialog(text="Enter Transaction ID to soft delete:", title="Soft Delete")
        txn_id = popup.get_input()
        if txn_id:
            self.txn_repo.soft_delete_transaction(txn_id.strip())
            self.refresh_transactions()

    def _build_commission_page(self):
        page = self.pages["commission"]
        ctk.CTkLabel(page, text="Commission Rules", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=10)
        wrap = ctk.CTkFrame(page)
        wrap.place(relx=0.5, rely=0.28, anchor="center")

        self.rule_service = ctk.CTkOptionMenu(wrap, values=list(self.service_map.keys()))
        self.rule_service.grid(row=0, column=0, padx=8, pady=8)
        self.rule_type = ctk.CTkOptionMenu(wrap, values=["fixed", "percentage"])
        self.rule_type.grid(row=0, column=1, padx=8, pady=8)
        self.rule_value = ctk.CTkEntry(wrap, placeholder_text="Value")
        self.rule_value.grid(row=0, column=2, padx=8, pady=8)
        ctk.CTkButton(wrap, text="Save Rule", command=self.save_commission_rule).grid(row=0, column=3, padx=8, pady=8)

    def save_commission_rule(self):
        try:
            value = float(self.rule_value.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Invalid value")
            return
        sid = self.service_map[self.rule_service.get()]
        self.commission_repo.upsert_rule(sid, self.rule_type.get(), value)
        messagebox.showinfo("Saved", "Commission rule updated")

    def _build_reports_page(self):
        page = self.pages["reports"]
        ctk.CTkLabel(page, text="Reports", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=10)
        top = ctk.CTkFrame(page)
        top.pack(pady=8)

        self.from_date = DateEntry(top, width=13)
        self.to_date = DateEntry(top, width=13)
        self.from_date.grid(row=0, column=0, padx=10)
        self.to_date.grid(row=0, column=1, padx=10)
        ctk.CTkButton(top, text="Generate", command=self.generate_report).grid(row=0, column=2, padx=10)
        ctk.CTkButton(top, text="Export PDF", command=self.export_pdf).grid(row=0, column=3, padx=10)
        ctk.CTkButton(top, text="Export Excel", command=self.export_excel).grid(row=0, column=4, padx=10)

        self.report_box = ctk.CTkTextbox(page, height=360)
        self.report_box.pack(fill="both", expand=True, padx=14, pady=10)
        self.last_report = None

    def generate_report(self):
        f = datetime.strptime(self.from_date.get(), "%m/%d/%y").date()
        t = datetime.strptime(self.to_date.get(), "%m/%d/%y").date()
        rep = self.reports.summary(f, t)
        self.last_report = rep
        text = [
            f"Report Period: {rep['from']} to {rep['to']}",
            f"Total Income: Rs {rep['total_income']:.2f}",
            f"Total Commission: Rs {rep['total_commission']:.2f}",
            f"Transactions: {rep['total_transactions']}",
            "\nService-wise breakdown:",
        ]
        for row in rep["service_breakdown"]:
            text.append(f"- {row['service']}: {row['count']} txns, Rs {float(row['income'] or 0):.2f}")
        text.append("\nPayment-wise breakdown:")
        for row in rep["payment_breakdown"]:
            text.append(f"- {row['payment_mode']}: {row['count']} txns, Rs {float(row['amount'] or 0):.2f}")
        self.report_box.delete("1.0", "end")
        self.report_box.insert("end", "\n".join(text))

    def export_pdf(self):
        if not self.last_report:
            self.generate_report()
        out = self.exporter.export_pdf(self.last_report, Path("exports"))
        messagebox.showinfo("Export", f"PDF exported: {out}")

    def export_excel(self):
        if not self.last_report:
            self.generate_report()
        out = self.exporter.export_excel(self.last_report, Path("exports"))
        messagebox.showinfo("Export", f"Excel exported: {out}")

    def _build_backup_page(self):
        page = self.pages["backup"]
        ctk.CTkLabel(page, text="Backup & Restore", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=10)
        top = ctk.CTkFrame(page)
        top.pack(pady=10)
        ctk.CTkButton(top, text="Create Backup Now", command=self.create_backup_now).grid(row=0, column=0, padx=8)
        ctk.CTkButton(top, text="Full Restore", command=self.full_restore).grid(row=0, column=1, padx=8)
        ctk.CTkButton(top, text="Selective Restore Txns", command=self.selective_restore).grid(row=0, column=2, padx=8)

        self.backup_list = ctk.CTkTextbox(page, height=380)
        self.backup_list.pack(fill="both", expand=True, padx=12, pady=8)
        self.refresh_backup_list()

    def create_backup_now(self):
        f = self.backup.create_backup("manual")
        messagebox.showinfo("Backup", f"Created {f}")
        self.refresh_backup_list()

    def refresh_backup_list(self):
        rows = self.backup.list_backups()
        self.backup_list.delete("1.0", "end")
        for r in rows:
            self.backup_list.insert("end", f"{r['id']}. {r['created_at']} | {r['backup_type']} | {r['backup_file']}\n")

    def full_restore(self):
        id_ = ctk.CTkInputDialog(text="Backup ID for full restore:", title="Restore").get_input()
        if not id_:
            return
        row = self.db.fetch_one("SELECT backup_file FROM backups WHERE id=?", (int(id_),))
        if not row:
            return
        self.backup.restore_full(row["backup_file"])
        messagebox.showinfo("Restore", "Full restore complete. Please restart app.")

    def selective_restore(self):
        id_ = ctk.CTkInputDialog(text="Backup ID for selective restore:", title="Selective Restore").get_input()
        if not id_:
            return
        row = self.db.fetch_one("SELECT backup_file FROM backups WHERE id=?", (int(id_),))
        if not row:
            return
        count = self.backup.selective_restore_transactions(row["backup_file"])
        messagebox.showinfo("Restore", f"Restored {count} transactions")
        self.refresh_transactions()

    def _build_whatsapp_page(self):
        page = self.pages["whatsapp"]
        ctk.CTkLabel(page, text="WhatsApp Communication", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=8)

        frm = ctk.CTkFrame(page)
        frm.place(relx=0.5, rely=0.25, anchor="center")
        self.wa_number = ctk.CTkEntry(frm, placeholder_text="Phone with country code (e.g. 9198xxxx)", width=320)
        self.wa_number.grid(row=0, column=0, columnspan=2, padx=8, pady=8)
        ctk.CTkButton(frm, text="Save My Number", command=self.save_whatsapp_number).grid(row=1, column=0, padx=8, pady=8)
        ctk.CTkButton(frm, text="Send Daily Report", command=self.send_daily_report).grid(row=1, column=1, padx=8, pady=8)
        ctk.CTkButton(frm, text="Send Transaction by ID", command=self.send_txn_by_id).grid(row=2, column=0, columnspan=2, padx=8, pady=8, sticky="ew")

    def save_whatsapp_number(self):
        self.db.execute("UPDATE users SET phone_number=? WHERE id=?", (self.wa_number.get().strip(), self.user["id"]))
        messagebox.showinfo("Saved", "WhatsApp number saved")

    def send_daily_report(self):
        phone = self.wa_number.get().strip() or self.user.get("phone_number")
        if not phone:
            messagebox.showerror("Error", "Register phone number first")
            return
        rep = self.reports.summary(date.today(), date.today())
        msg = self.whatsapp.format_daily_report(rep)
        url = self.whatsapp.send_message_web(phone, msg)
        messagebox.showinfo("WhatsApp", f"Opened WhatsApp Web:\n{url}")

    def send_txn_by_id(self):
        txid = ctk.CTkInputDialog(text="Transaction ID:", title="Send Transaction").get_input()
        if not txid:
            return
        txn = self.db.fetch_one(
            """
            SELECT t.*, s.name AS service_name FROM transactions t
            JOIN services s ON s.id=t.service_id
            WHERE t.transaction_id=?
            """,
            (txid.strip(),),
        )
        if not txn:
            messagebox.showerror("Not found", "Transaction not found")
            return
        phone = self.wa_number.get().strip() or self.user.get("phone_number")
        msg = self.whatsapp.format_transaction_message(txn)
        self.whatsapp.send_message_web(phone, msg)

    def _build_settings_page(self):
        page = self.pages["settings"]
        ctk.CTkLabel(page, text="Security & Service Settings", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=10)

        security = ctk.CTkFrame(page)
        security.pack(pady=8)
        self.enable_2fa = ctk.CTkSwitch(security, text="Enable Authenticator 2FA")
        self.enable_2fa.grid(row=0, column=0, padx=8, pady=10)
        ctk.CTkButton(security, text="Apply 2FA", command=self.apply_2fa).grid(row=0, column=1, padx=8)

        service_box = ctk.CTkFrame(page)
        service_box.pack(pady=20)
        self.service_name_entry = ctk.CTkEntry(service_box, placeholder_text="New service name", width=260)
        self.service_name_entry.grid(row=0, column=0, padx=8, pady=8)
        ctk.CTkButton(service_box, text="Add Service", command=self.add_service).grid(row=0, column=1, padx=8)

    def apply_2fa(self):
        result = AuthManager(self.db).toggle_2fa(self.user["id"], bool(self.enable_2fa.get()))
        if result:
            self.show_2fa_qr_modal(result)
        else:
            messagebox.showinfo("2FA", "Disabled")

    def show_2fa_qr_modal(self, result: dict):
        import io

        qr_bytes = build_totp_qr_png_bytes(result["username"], result["secret"])
        image = Image.open(io.BytesIO(qr_bytes))

        modal = ctk.CTkToplevel(self)
        modal.title("Scan Authenticator QR")
        modal.geometry("420x520")
        modal.grab_set()

        ctk.CTkLabel(
            modal,
            text="Scan with Google / Microsoft / Any TOTP Authenticator",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(16, 10))
        ctk_img = ctk.CTkImage(light_image=image, dark_image=image, size=(280, 280))
        img_lbl = ctk.CTkLabel(modal, text="", image=ctk_img)
        img_lbl.image = ctk_img
        img_lbl.pack(pady=8)

        ctk.CTkLabel(modal, text="Manual setup secret:").pack(pady=(8, 4))
        secret_entry = ctk.CTkEntry(modal, width=320)
        secret_entry.insert(0, result["secret"])
        secret_entry.configure(state="readonly")
        secret_entry.pack(pady=(0, 10))

        uri_box = ctk.CTkTextbox(modal, width=360, height=80)
        uri_box.insert("1.0", result["uri"])
        uri_box.configure(state="disabled")
        uri_box.pack(pady=8)

        ctk.CTkLabel(
            modal,
            text="Use generated 6-digit OTP during login.",
            text_color="gray",
        ).pack(pady=(6, 12))

    def add_service(self):
        name = self.service_name_entry.get().strip()
        if not name:
            return
        self.service_repo.add_service(name)
        self.service_map = {s["name"]: s["id"] for s in self.service_repo.list_services()}
        for opt in [self.service_option, self.rule_service]:
            opt.configure(values=list(self.service_map.keys()))
        messagebox.showinfo("Service", "Added")


class BusinessApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("Digital Service Business Manager")
        self.geometry("1460x860")

        self.db = DatabaseManager()
        self.auth = AuthManager(self.db)

        self.login_frame = LoginFrame(self, self.auth, self.on_login)
        self.login_frame.pack(fill="both", expand=True)

    def on_login(self, user: dict):
        self.login_frame.destroy()
        DashboardFrame(self, self.db, user)
