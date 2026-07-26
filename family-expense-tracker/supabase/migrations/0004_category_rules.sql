-- Category rules: user corrections that stick. The bank-sync function applies
-- these (case-insensitive substring match on merchant/description) before
-- asking the AI, so recurring merchants always land in the same category.

create table if not exists category_rules (
  id           uuid primary key default gen_random_uuid(),
  household_id uuid not null references households (id) on delete cascade,
  pattern      text not null,                 -- matched with ilike '%pattern%'
  category_id  uuid not null references categories (id) on delete cascade,
  created_at   timestamptz not null default now(),
  unique (household_id, pattern)
);

alter table category_rules enable row level security;

create policy category_rules_all on category_rules
  for all using (is_household_member(household_id))
  with check (is_household_member(household_id));
