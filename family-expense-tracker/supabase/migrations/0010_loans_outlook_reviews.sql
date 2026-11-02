-- Loans, savings target and purchase reviews.
--
-- loans            what the household owes; drives the loans wheel on Home and counts
--                  as a fixed cost in the recommended weekly burn rate.
-- savings target   share of monthly income set aside before the burn rate is computed.
-- purchase_reviews the "worth a second look?" heads-up: the member says what was
--                  bought and why, Claude answers. Members can only skip an item; the
--                  verdict and feedback are written by the purchase-review function.

create table if not exists loans (
  id               uuid primary key default gen_random_uuid(),
  household_id     uuid not null references households (id) on delete cascade,
  name             text not null check (char_length(name) between 1 and 80),
  lender           text,
  kind             text not null default 'other'
                     check (kind in ('mortgage', 'car', 'personal', 'credit_card', 'student', 'family', 'other')),
  original_amount  numeric(12, 2) check (original_amount is null or original_amount >= 0),
  balance          numeric(12, 2) not null check (balance >= 0),
  interest_rate    numeric(6, 3) not null default 0 check (interest_rate between 0 and 100),  -- annual %
  monthly_payment  numeric(12, 2) check (monthly_payment is null or monthly_payment >= 0),
  start_date       date,
  end_date         date,
  payment_day      int check (payment_day between 1 and 31),
  payment_pattern  text,          -- matched (case-insensitive substring) against bank transactions
  notes            text,
  created_by       uuid references auth.users (id) on delete set null,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index if not exists idx_loans_household on loans (household_id);

alter table loans enable row level security;

create policy loans_all on loans
  for all using (is_household_member(household_id))
  with check (is_household_member(household_id));

alter table households
  add column if not exists savings_target_pct numeric(5, 2) not null default 20
    check (savings_target_pct between 0 and 90);

create table if not exists purchase_reviews (
  id             uuid primary key default gen_random_uuid(),
  household_id   uuid not null references households (id) on delete cascade,
  transaction_id uuid not null unique references transactions (id) on delete cascade,
  user_id        uuid references auth.users (id) on delete set null,
  status         text not null check (status in ('dismissed', 'reviewed')),
  what           text check (what is null or char_length(what) <= 500),
  why            text check (why is null or char_length(why) <= 1000),
  verdict        text check (verdict in ('necessary', 'nice_to_have', 'unnecessary')),
  headline       text,
  feedback       text,
  tip            text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index if not exists idx_purchase_reviews_household on purchase_reviews (household_id, created_at desc);

alter table purchase_reviews enable row level security;

create policy purchase_reviews_select on purchase_reviews
  for select using (is_household_member(household_id));

-- Members may only skip ("not now") an item; Claude's verdict comes from the function.
create policy purchase_reviews_dismiss on purchase_reviews
  for insert with check (
    is_household_member(household_id)
    and user_id = auth.uid()
    and status = 'dismissed'
    and verdict is null and feedback is null and headline is null and tip is null
  );

create or replace function touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists loans_touch on loans;
create trigger loans_touch before update on loans
  for each row execute function touch_updated_at();

drop trigger if exists purchase_reviews_touch on purchase_reviews;
create trigger purchase_reviews_touch before update on purchase_reviews
  for each row execute function touch_updated_at();
