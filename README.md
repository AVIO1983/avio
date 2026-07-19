# PRINTER DOCTOR PRO ENTERPRISE

Single-file Python 3.9+ PySide6 desktop application for printer service centers, IT administrators, schools, offices, print shops, CSC centers, cyber cafes, and repair technicians.

## Highlights

- One-file application entry point: `main.py`.
- PySide6 glassmorphism-inspired desktop UI with sidebar navigation, cards, search, notifications, dark/light/AMOLED themes, drag-and-drop imports, and responsive scroll pages.
- SQLite database with tables for printers, drivers, error codes, diagnostics, repairs, firmware, manuals, images, service history, consumables, network devices, settings, users, parts, and update catalog.
- Offline-first operation with optional online activation for image fetching and official support pages.
- Real printer detection paths for Windows (`pywin32`/WMI), CUPS systems (`lpstat`), and TCP network discovery for printer ports 9100/631/515.
- ERROR CODE EXPERT supports large CSV knowledge-base imports without demo records.
- Auto Repair Engine executes safe platform-aware print service, queue, temp file, and app cache repair actions.
- Driver backup archive creation with manifest and Windows driver-store capture when accessible.
- Report generation to JSON, HTML, Excel/CSV, and PDF/HTML fallback.
- Rule-based local AI repair assistant and interactive diagnostic wizard.

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python main.py
```

## First Run Login

- Username: `admin`
- Password: `admin123`

Change the default password/user policy before production deployment.

## Runtime Data

The app creates a platform-specific data directory containing the SQLite database, logs, caches, driver backups, manuals, and generated reports.

## Packaging

The code is PyInstaller-friendly because the application logic is contained in `main.py` and optional integrations are dynamically loaded when installed.

```bash
pyinstaller --onefile --windowed --name "PrinterDoctorProEnterprise" main.py
```


## CHOWDARYS ONLINE SERVICES - DIGITAL DOCUMENT VAULT PRO

This repository now includes a Next.js + Supabase SaaS scaffold under `apps/document-vault-pro` for the CHOWDARYS ONLINE SERVICES Digital Document Vault Pro platform. It includes a premium glassmorphism UI, PWA manifest, security headers, protected preview component, role/status constants, document category coverage, and a Supabase PostgreSQL schema for brands, franchises, profiles, family vaults, documents, wallets, payments, subscriptions, requests, CRM, tickets, consent, devices and audit logs.

Key files:

- `apps/document-vault-pro/app/page.tsx` — premium responsive landing/dashboard experience.
- `apps/document-vault-pro/components/document-preview.tsx` — preview-only protected document surface with watermark and disabled context menu/drag.
- `apps/document-vault-pro/lib/platform.ts` — roles, statuses, categories, languages, modules and dashboard metrics.
- `supabase/document_vault_schema.sql` — Supabase database architecture with RLS policies.


## MSOS Billing Pro Enterprise

This repository includes `msos_billing_pro_enterprise.py`, an offline-first PySide6/SQLite professional billing application with customer, service, company, invoice, template designer, PDF/image export, QR/barcode, audit log and Google Drive upload queue support. See `MSOS_BILLING_PRO_README.md` for installation and operation details.
