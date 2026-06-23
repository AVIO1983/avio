-- CHOWDARYS ONLINE SERVICES - DIGITAL DOCUMENT VAULT PRO
-- Supabase PostgreSQL architecture: multi-tenant brands, RBAC, vault storage, payments, CRM, tickets, consent, QR and AI metadata.

create extension if not exists pgcrypto;
create extension if not exists citext;

create type app_role as enum ('MASTER_SUPER_ADMIN','SUPER_ADMIN','ADMIN','OPERATOR','USER');
create type lifecycle_status as enum ('Pending','Active','Rejected','Suspended','On Hold');
create type document_status as enum ('Pending','Approved','Rejected','On Hold');
create type request_status as enum ('Pending','In Review','Uploaded','Completed','Rejected');
create type ticket_status as enum ('Open','In Progress','Waiting','Resolved','Closed');
create type payment_status as enum ('Pending','Success','Failed','Refunded');

create table brands (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  domain text unique,
  logo_url text,
  theme jsonb not null default '{"navy":"#07162f","royal":"#246BFE","emerald":"#10B981"}',
  default_language text not null default 'English',
  created_at timestamptz not null default now()
);

create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  brand_id uuid not null references brands(id),
  role app_role not null default 'USER',
  status lifecycle_status not null default 'Pending',
  login_mode text not null default 'Google + Username',
  full_name text not null,
  mobile text,
  email citext,
  address text,
  district text,
  state text,
  country text default 'India',
  customer_id text unique,
  qr_code text,
  profile_photo_url text,
  notes text,
  consent_status boolean not null default false,
  created_at timestamptz not null default now()
);

create table franchises (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references brands(id),
  parent_id uuid references franchises(id),
  admin_id uuid references profiles(id),
  name text not null,
  platform_share numeric(5,2) not null default 0,
  franchise_share numeric(5,2) not null default 0,
  operator_share numeric(5,2) not null default 0,
  created_at timestamptz not null default now()
);

create table family_members (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references brands(id),
  profile_id uuid not null references profiles(id) on delete cascade,
  relation text not null,
  full_name text not null,
  date_of_birth date,
  created_at timestamptz not null default now()
);

create table document_categories (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references brands(id),
  name text not null,
  download_price numeric(12,2) not null default 0,
  retention_days integer,
  created_at timestamptz not null default now(),
  unique (brand_id, name)
);

create table documents (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references brands(id),
  owner_id uuid not null references profiles(id),
  family_member_id uuid references family_members(id),
  category_id uuid not null references document_categories(id),
  name text not null,
  status document_status not null default 'Pending',
  storage_bucket text not null default 'encrypted-documents',
  encrypted_path text not null,
  preview_path text,
  checksum text not null,
  version integer not null default 1,
  expires_on date,
  verification_id text unique not null default encode(gen_random_bytes(12), 'hex'),
  ocr_text text,
  ai_metadata jsonb not null default '{}',
  approved_by uuid references profiles(id),
  approved_at timestamptz,
  created_at timestamptz not null default now()
);

create table wallets (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references brands(id),
  profile_id uuid not null references profiles(id),
  balance numeric(12,2) not null default 0,
  unique (brand_id, profile_id)
);

create table payments (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references brands(id),
  profile_id uuid not null references profiles(id),
  document_id uuid references documents(id),
  provider text not null,
  amount numeric(12,2) not null,
  status payment_status not null default 'Pending',
  provider_reference text,
  created_at timestamptz not null default now()
);

create table wallet_ledger (
  id uuid primary key default gen_random_uuid(),
  wallet_id uuid not null references wallets(id),
  payment_id uuid references payments(id),
  entry_type text not null,
  amount numeric(12,2) not null,
  balance_after numeric(12,2) not null,
  created_at timestamptz not null default now()
);

create table subscriptions (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references brands(id),
  profile_id uuid not null references profiles(id),
  plan_name text not null check (plan_name in ('Basic','Premium','Family','Lifetime')),
  download_limit text not null check (download_limit in ('One Download','Three Downloads','Five Downloads','Unlimited')),
  valid_until date,
  created_at timestamptz not null default now()
);

create table document_requests (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references brands(id),
  profile_id uuid not null references profiles(id),
  category_id uuid references document_categories(id),
  status request_status not null default 'Pending',
  notes text,
  assigned_to uuid references profiles(id),
  created_at timestamptz not null default now()
);

create table service_requests (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references brands(id),
  profile_id uuid not null references profiles(id),
  service_type text not null,
  status request_status not null default 'Pending',
  workflow jsonb not null default '[]',
  created_at timestamptz not null default now()
);

create table tickets (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references brands(id),
  profile_id uuid not null references profiles(id),
  category text not null,
  status ticket_status not null default 'Open',
  subject text not null,
  description text,
  assigned_to uuid references profiles(id),
  created_at timestamptz not null default now()
);

create table crm_events (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references brands(id),
  profile_id uuid not null references profiles(id),
  event_type text not null,
  tags text[] default '{}',
  notes text,
  follow_up_at timestamptz,
  created_by uuid references profiles(id),
  created_at timestamptz not null default now()
);

create table consent_records (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references brands(id),
  profile_id uuid not null references profiles(id),
  consent_version text not null,
  accepted_policies text[] not null,
  ip_address inet,
  browser text,
  device_fingerprint text,
  accepted_at timestamptz not null default now()
);

create table device_sessions (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid not null references brands(id),
  profile_id uuid not null references profiles(id),
  device_fingerprint text not null,
  ip_address inet,
  browser text,
  trusted boolean not null default false,
  blocked boolean not null default false,
  last_seen_at timestamptz not null default now()
);

create table audit_logs (
  id uuid primary key default gen_random_uuid(),
  brand_id uuid references brands(id),
  actor_id uuid references profiles(id),
  action text not null,
  entity_table text,
  entity_id uuid,
  metadata jsonb not null default '{}',
  ip_address inet,
  created_at timestamptz not null default now()
);

alter table profiles enable row level security;
alter table documents enable row level security;
alter table family_members enable row level security;
alter table payments enable row level security;
alter table tickets enable row level security;
alter table consent_records enable row level security;

create or replace function current_profile_role() returns app_role language sql stable as $$
  select role from profiles where id = auth.uid()
$$;

create policy "admins manage profiles" on profiles for all using (current_profile_role() in ('MASTER_SUPER_ADMIN','SUPER_ADMIN','ADMIN'));
create policy "users read own profile" on profiles for select using (id = auth.uid());
create policy "admins manage documents" on documents for all using (current_profile_role() in ('MASTER_SUPER_ADMIN','SUPER_ADMIN','ADMIN','OPERATOR'));
create policy "users read approved own documents" on documents for select using (owner_id = auth.uid() and status = 'Approved');
create policy "users manage own tickets" on tickets for all using (profile_id = auth.uid());
create policy "admins manage tickets" on tickets for all using (current_profile_role() in ('MASTER_SUPER_ADMIN','SUPER_ADMIN','ADMIN','OPERATOR'));

insert into brands(name, domain) values ('CHOWDARYS ONLINE SERVICES', 'vault.chowdarysonline.example') on conflict do nothing;
