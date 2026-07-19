# MSOS Billing Pro Enterprise

`msos_billing_pro_enterprise.py` is a complete offline-first Python 3.12+ desktop billing application for Windows 10/11 and service-center billing offices. It creates its SQLite database automatically on first run, seeds a Super Admin account, sample company profile, services, invoice series and a built-in invoice template.

## Features Included

- Premium frameless PySide6 UI with rounded glass-style shell, blue/green theme, draggable window, dashboard cards, customer/service tables, invoice generation and visual template designer.
- SQLite schema for users, customers, services, companies, bill series, templates, invoices, line items, upload queue, settings and audit logs.
- Encrypted password/PIN hashes using PBKDF2-HMAC-SHA256.
- Multiple company/profile-ready data model with invoice prefix/suffix and bill number counters.
- Drag-and-drop/movable visual template designer that persists field coordinates as JSON.
- Invoice workflow: customer, service, quantity, payment mode, PDF/PNG/JPEG output, QR code, barcode and upload queue entry.
- Local folder structure: `Bills/<Company>/<Year>/<Month>/<Date>/{PDF,PNG,JPEG}`.
- Optional dependency detection prints a `pip install ...` command for missing packages without silently installing anything.
- Google Drive synchronization-ready upload queue and dependency set for OAuth/Drive integration.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python msos_billing_pro_enterprise.py
```

On Linux/macOS use `source .venv/bin/activate` instead of the Windows activation command.

## First Login Seed

The local database seeds this account for production bootstrap:

- Username: `admin`
- Password: `admin123`
- PIN: `1234`
- Role: `Super Admin`

Change these credentials before using the application with real customer data.

## Runtime Data

Runtime data is stored under the platform application data folder using the slug `msos_billing_pro_enterprise`. Generated invoices are saved both in the SQLite invoice history and on disk.

## Packaging

```bash
pyinstaller --onefile --windowed --name "MSOSBillingProEnterprise" msos_billing_pro_enterprise.py
```
