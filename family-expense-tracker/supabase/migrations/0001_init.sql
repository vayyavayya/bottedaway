-- Family Expense Tracker — core schema
-- Run this in the Supabase SQL editor (or via `supabase db push`).
-- Everything is scoped to a "household" so you and your partner share one private
-- dataset, and Row Level Security guarantees nobody outside the household can read it.

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
create extension if not exists pgcrypto;      -- gen_random_uuid(), gen_random_bytes()

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

create table if not exists households (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  invite_code text not null unique,
  created_by  uuid not null references auth.users (id) on delete cascade,
  created_at  timestamptz not null default now()
);

create table if not exists household_members (
  household_id uuid not null references households (id) on delete cascade,
  user_id      uuid not null references auth.users (id) on delete cascade,
  role         text not null default 'member' check (role in ('owner', 'member')),
  display_name text,
  joined_at    timestamptz not null default now(),
  primary key (household_id, user_id)
);

create table if not exists categories (
  id           uuid primary key default gen_random_uuid(),
  household_id uuid not null references households (id) on delete cascade,
  name         text not null,
  icon         text default '🛒',
  color        text default '#0f766e',
  sort_order   int  default 100,
  created_at   timestamptz not null default now(),
  unique (household_id, name)
);

-- Any uploaded file: a bill photo, a bank statement PDF, a utility bill.
create table if not exists documents (
  id                uuid primary key default gen_random_uuid(),
  household_id      uuid not null references households (id) on delete cascade,
  uploaded_by       uuid not null references auth.users (id) on delete cascade,
  doc_type          text not null default 'receipt'
                       check (doc_type in ('receipt', 'bank_statement', 'utility_bill', 'other')),
  original_filename text,
  mime_type         text,
  storage_path      text,          -- original image/pdf in the `documents` bucket
  pdf_path          text,          -- generated PDF copy (for photos)
  status            text not null default 'uploaded'
                       check (status in ('uploaded', 'processing', 'analyzed', 'failed')),
  error_message     text,
  created_at        timestamptz not null default now()
);

-- Structured header for a single receipt / bill.
create table if not exists receipts (
  id           uuid primary key default gen_random_uuid(),
  document_id  uuid not null references documents (id) on delete cascade,
  household_id uuid not null references households (id) on delete cascade,
  merchant     text,
  purchased_at date,
  currency     text default 'USD',
  subtotal     numeric(12, 2),
  tax          numeric(12, 2),
  total        numeric(12, 2),
  category_id  uuid references categories (id) on delete set null,
  notes        text,
  raw_analysis jsonb,          -- full model output, for auditing / re-processing
  created_by   uuid not null references auth.users (id) on delete cascade,
  created_at   timestamptz not null default now()
);

create table if not exists line_items (
  id          uuid primary key default gen_random_uuid(),
  receipt_id  uuid not null references receipts (id) on delete cascade,
  description text,
  quantity    numeric(12, 3),
  unit_price  numeric(12, 2),
  amount      numeric(12, 2),
  category_id uuid references categories (id) on delete set null,
  position    int default 0
);

-- Unified ledger that powers all the insights. A receipt contributes one row
-- (its total); a bank statement contributes one row per line; a utility bill one row.
create table if not exists transactions (
  id           uuid primary key default gen_random_uuid(),
  household_id uuid not null references households (id) on delete cascade,
  document_id  uuid references documents (id) on delete set null,
  receipt_id   uuid references receipts (id) on delete cascade,
  txn_date     date not null,
  merchant     text,
  description  text,
  amount       numeric(12, 2) not null,   -- always positive
  direction    text not null default 'debit' check (direction in ('debit', 'credit')),
  currency     text default 'USD',
  category_id  uuid references categories (id) on delete set null,
  source       text not null default 'receipt'
                  check (source in ('receipt', 'bank_statement', 'utility_bill', 'manual')),
  created_by   uuid references auth.users (id) on delete set null,
  created_at   timestamptz not null default now()
);

create index if not exists idx_documents_household   on documents (household_id, created_at desc);
create index if not exists idx_receipts_household     on receipts (household_id, purchased_at desc);
create index if not exists idx_line_items_receipt     on line_items (receipt_id);
create index if not exists idx_transactions_household on transactions (household_id, txn_date desc);
create index if not exists idx_transactions_category  on transactions (household_id, category_id);
create index if not exists idx_members_user           on household_members (user_id);

-- ---------------------------------------------------------------------------
-- Membership helper (SECURITY DEFINER to avoid recursive RLS on household_members)
-- ---------------------------------------------------------------------------
create or replace function is_household_member(hid uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from household_members
    where household_id = hid and user_id = auth.uid()
  );
$$;

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------
alter table households        enable row level security;
alter table household_members enable row level security;
alter table categories        enable row level security;
alter table documents         enable row level security;
alter table receipts          enable row level security;
alter table line_items        enable row level security;
alter table transactions      enable row level security;

-- households
create policy households_select on households
  for select using (is_household_member(id));
create policy households_insert on households
  for insert with check (created_by = auth.uid());
create policy households_update on households
  for update using (is_household_member(id));

-- household_members: you can see rows of households you belong to; you may add
-- only yourself (owner-add-partner happens via the join_household RPC).
create policy members_select on household_members
  for select using (is_household_member(household_id));
create policy members_insert_self on household_members
  for insert with check (user_id = auth.uid());
create policy members_update_self on household_members
  for update using (user_id = auth.uid());
create policy members_delete_self on household_members
  for delete using (user_id = auth.uid());

-- categories
create policy categories_all on categories
  for all using (is_household_member(household_id))
  with check (is_household_member(household_id));

-- documents
create policy documents_all on documents
  for all using (is_household_member(household_id))
  with check (is_household_member(household_id));

-- receipts
create policy receipts_all on receipts
  for all using (is_household_member(household_id))
  with check (is_household_member(household_id));

-- line_items (scoped through their receipt)
create policy line_items_all on line_items
  for all using (
    exists (select 1 from receipts r
            where r.id = line_items.receipt_id and is_household_member(r.household_id))
  )
  with check (
    exists (select 1 from receipts r
            where r.id = line_items.receipt_id and is_household_member(r.household_id))
  );

-- transactions
create policy transactions_all on transactions
  for all using (is_household_member(household_id))
  with check (is_household_member(household_id));

-- ---------------------------------------------------------------------------
-- RPC: create a household (seeds membership + default categories + invite code)
-- ---------------------------------------------------------------------------
create or replace function create_household(p_name text, p_display_name text default null)
returns households
language plpgsql
security definer
set search_path = public
as $$
declare
  h households;
  code text;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;

  code := upper(encode(gen_random_bytes(4), 'hex'));  -- 8-char invite code

  insert into households (name, invite_code, created_by)
  values (coalesce(nullif(trim(p_name), ''), 'Our Household'), code, auth.uid())
  returning * into h;

  insert into household_members (household_id, user_id, role, display_name)
  values (h.id, auth.uid(), 'owner', p_display_name);

  insert into categories (household_id, name, icon, color, sort_order) values
    (h.id, 'Groceries',      '🛒', '#16a34a', 10),
    (h.id, 'Dining Out',     '🍽️', '#f97316', 20),
    (h.id, 'Transport',      '🚗', '#0ea5e9', 30),
    (h.id, 'Utilities',      '💡', '#eab308', 40),
    (h.id, 'Rent / Housing', '🏠', '#8b5cf6', 50),
    (h.id, 'Health',         '💊', '#ef4444', 60),
    (h.id, 'Shopping',       '🛍️', '#ec4899', 70),
    (h.id, 'Entertainment',  '🎬', '#14b8a6', 80),
    (h.id, 'Kids',           '🧸', '#f59e0b', 90),
    (h.id, 'Other',          '📦', '#64748b', 999);

  return h;
end;
$$;

-- ---------------------------------------------------------------------------
-- RPC: join an existing household by invite code
-- ---------------------------------------------------------------------------
create or replace function join_household(p_code text, p_display_name text default null)
returns households
language plpgsql
security definer
set search_path = public
as $$
declare
  h households;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;

  select * into h from households
  where invite_code = upper(trim(p_code));

  if h.id is null then
    raise exception 'invalid invite code';
  end if;

  insert into household_members (household_id, user_id, role, display_name)
  values (h.id, auth.uid(), 'member', p_display_name)
  on conflict (household_id, user_id) do nothing;

  return h;
end;
$$;

-- ---------------------------------------------------------------------------
-- Monthly insights view (per household / month / category)
-- ---------------------------------------------------------------------------
create or replace view v_monthly_category_spend
  with (security_invoker = true) as
  select
    t.household_id,
    date_trunc('month', t.txn_date)::date as month,
    t.category_id,
    c.name  as category_name,
    c.icon  as category_icon,
    c.color as category_color,
    sum(case when t.direction = 'debit'  then t.amount else 0 end) as spent,
    sum(case when t.direction = 'credit' then t.amount else 0 end) as received,
    count(*) as txn_count
  from transactions t
  left join categories c on c.id = t.category_id
  group by 1, 2, 3, 4, 5, 6;
