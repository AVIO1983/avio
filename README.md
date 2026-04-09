# Digital Service Business Manager (Desktop App)

Production-style Python desktop software for digital service shops using **CustomTkinter** + **SQLite**.

## Features Implemented

- Premium centered CustomTkinter UI with sidebar and icon labels.
- Login system with secure PBKDF2 password hashing.
- Authenticator-based 2FA with scannable QR code (Google/Microsoft/Authy compatible).
- Authenticator-based 2FA (TOTP compatible with Google Authenticator URI).
- Full transaction system with auto transaction IDs, duplicate detection, and auto-commission.
- Commission rules per service: fixed or percentage.
- Permanent SQLite storage with auto DB creation.
- Soft delete for transactions and services.
- Report generation (daily/monthly/custom date range).
- Export reports to PDF and Excel.
- WhatsApp Web integration (daily report + single transaction summary).
- Automatic daily backup scheduler + manual backup + full/selective restore.
- Dark/light toggle, service management, smart suggestions infrastructure, and dashboard analytics charts.

## Project Structure

```text
main.py
ui/
  app.py
  widgets.py
database/
  db_manager.py
  repositories.py
auth/
  auth_manager.py
  security.py
reports/
  report_manager.py
  exporters.py
backup/
  backup_manager.py
whatsapp/
  whatsapp_manager.py
utils/
  scheduler.py
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
python main.py
```

## Default Login

- Username: `admin`
- Password: `admin123`

## Database Schema

On first run, `business_manager.db` is created with:

- `users`
- `services`
- `commission_rules`
- `transactions`
- `backups`

See full schema in `database/db_manager.py`.

## Notes

- WhatsApp sending uses WhatsApp Web deep-link (opens browser).
- Backups are stored in `./backups/` and tracked in DB.
- Exports are written to `./exports/`.
