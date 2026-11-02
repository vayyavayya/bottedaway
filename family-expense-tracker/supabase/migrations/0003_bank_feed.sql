-- Bank feed: connections to Enable Banking + dedup support on transactions.

-- One row per authorized bank consent (per person, per bank).
create table if not exists bank_connections (
  id             uuid primary key default gen_random_uuid(),
  household_id   uuid not null references households (id) on delete cascade,
  label          text not null,              -- e.g. 'Ajit — Commerzbank'
  aspsp_name     text not null,              -- Enable Banking ASPSP name
  aspsp_country  text not null default 'DE',
  state_token    text not null,              -- nonce carried through the auth redirect
  session_id     text,                       -- EB session id once authorized
  accounts       jsonb,                      -- EB account uids + metadata
  status         text not null default 'pending'
                   check (status in ('pending', 'active', 'expired', 'revoked')),
  valid_until    timestamptz,                -- consent expiry (PSD2 ~90-180 days)
  last_synced_at timestamptz,
  created_at     timestamptz not null default now()
);

alter table bank_connections enable row level security;

-- Household members may see their connections (status surfacing in the app later).
create policy bank_connections_select on bank_connections
  for select using (is_household_member(household_id));
-- No insert/update/delete policies: only the service role (edge functions) writes.

-- Transactions: external reference for idempotent bank syncs.
alter table transactions add column if not exists external_ref text;
create unique index if not exists idx_transactions_external_ref
  on transactions (household_id, external_ref);

-- Allow 'bank_feed' as a transaction source.
do $$
declare c text;
begin
  select conname into c from pg_constraint
   where conrelid = 'transactions'::regclass and contype = 'c'
     and pg_get_constraintdef(oid) like '%source%';
  if c is not null then
    execute format('alter table transactions drop constraint %I', c);
  end if;
  alter table transactions add constraint transactions_source_check
    check (source in ('receipt', 'bank_statement', 'utility_bill', 'manual', 'bank_feed'));
end $$;
