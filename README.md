# Python license key starter (for your own software)

This repo contains a minimal Python license system example.

## What it does

- Creates signed license tokens using **HMAC-SHA256**.
- Stores customer/product/feature data in token payload.
- Verifies signature and expiration date.

## Quick start

```bash
python license_system.py
```

## Integration notes

- Keep the HMAC secret key on trusted systems only.
- If verification is done client-side, a shared secret can be extracted.
- For stronger offline client verification, switch to asymmetric signing (e.g., Ed25519/RSA with public-key verification).
