# CHOWDARYS ONLINE SERVICES - DIGITAL DOCUMENT VAULT PRO

Enterprise SaaS scaffold for a secure cloud-based Digital Document Vault, Family Locker, Customer Portal, CRM, Franchise Management System, White Label SaaS Platform, Payment Platform and Customer Service Center.

## Included production architecture

- **Frontend:** Next.js App Router, TypeScript, Tailwind CSS, premium glassmorphism landing/dashboard surface, PWA manifest and security headers.
- **Backend:** Supabase Auth, PostgreSQL, Row Level Security, Supabase Storage private buckets and signed URL access.
- **Security:** RBAC roles, user approval statuses, private encrypted file paths, device/session tracking, audit logs and consent records.
- **Vault:** Unlimited document categories, family members, status workflows, OCR text, AI metadata, verification IDs and preview-only UX.
- **Payments:** UPI provider references, wallet ledger, subscription plans, download limits and per-category pricing.
- **Operations:** Document requests, service requests, CRM events, support tickets, franchise revenue shares and white-label brand records.

## Local development

```bash
cd apps/document-vault-pro
npm install
npm run dev
```

## Supabase setup

1. Create a Supabase project.
2. Run `supabase/document_vault_schema.sql` from the repository root in the SQL editor.
3. Create private storage buckets named `encrypted-documents` and `document-previews`.
4. Configure Google OAuth, optional phone OTP, MFA and email templates in Supabase Auth.
5. Add environment variables in `.env.local`:

```bash
NEXT_PUBLIC_SUPABASE_URL="https://your-project.supabase.co"
NEXT_PUBLIC_SUPABASE_ANON_KEY="your-anon-key"
SUPABASE_SERVICE_ROLE_KEY="server-only-service-role-key"
```

## Preview security model

The UI blocks context-menu and drag actions for previews and displays a permanent watermark. Production download enforcement must remain server-side: only issue signed temporary URLs after RBAC, consent, device, approval, payment or subscription checks pass.
