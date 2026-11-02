-- In-app feedback inbox. Household members send bugs, ideas and data corrections
-- from the app; the feedback worker (Claude, run via scripts/hearthctl.py — see
-- FEEDBACK_LOOP.md) picks them up, acts on them, and writes a reply back that the
-- app shows next to each item.
--
-- Clients may only create items and read their household's items. Status and the
-- reply are written by the worker through the service role / Management API, so a
-- member can never mark their own feedback as shipped.

create table if not exists feedback (
  id              uuid primary key default gen_random_uuid(),
  household_id    uuid not null references households (id) on delete cascade,
  user_id         uuid not null references auth.users (id) on delete cascade,
  author_name     text,
  kind            text not null default 'idea'
                    check (kind in ('bug', 'idea', 'data', 'other')),
  message         text not null check (char_length(message) between 3 and 4000),
  context         jsonb not null default '{}'::jsonb,   -- screen, month, device; no financial data
  status          text not null default 'new'
                    check (status in ('new', 'in_progress', 'needs_info', 'shipped', 'declined')),
  resolution_note text,                                  -- the worker's reply, shown in the app
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index if not exists idx_feedback_household on feedback (household_id, created_at desc);
create index if not exists idx_feedback_status    on feedback (status, created_at);

alter table feedback enable row level security;

create policy feedback_select on feedback
  for select using (is_household_member(household_id));

create policy feedback_insert on feedback
  for insert with check (
    is_household_member(household_id)
    and user_id = auth.uid()
    and status = 'new'
    and resolution_note is null
  );

create or replace function touch_feedback_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists feedback_touch on feedback;
create trigger feedback_touch before update on feedback
  for each row execute function touch_feedback_updated_at();
