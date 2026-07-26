-- Self-transfer exclusion + excluded flag on transactions.
-- Money moving between the household's own accounts is stored (audit trail)
-- but excluded from every total the app shows.

alter table transactions add column if not exists excluded boolean not null default false;

-- Names of the household's own account holders, as they appear as bank
-- counterparties. bank-sync marks matching transactions excluded.
create table if not exists transfer_names (
  id           uuid primary key default gen_random_uuid(),
  household_id uuid not null references households (id) on delete cascade,
  name         text not null,               -- matched with ilike '%name%'
  created_at   timestamptz not null default now(),
  unique (household_id, name)
);

alter table transfer_names enable row level security;
create policy transfer_names_all on transfer_names
  for all using (is_household_member(household_id))
  with check (is_household_member(household_id));
