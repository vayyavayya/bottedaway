-- Refund netting: a charge and its refund (same counterparty, same amount,
-- opposite directions, within 3 days) cancel out — both get excluded so
-- neither Spent nor Money In is inflated by round-trips.

create or replace function net_refund_pairs(hid uuid)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare
  d record;
  cid uuid;
  n int := 0;
begin
  for d in
    select id, merchant, amount, txn_date from transactions
    where household_id = hid and source = 'bank_feed' and direction = 'debit'
      and not excluded and nullif(trim(coalesce(merchant, '')), '') is not null
    order by txn_date
  loop
    select t.id into cid from transactions t
    where t.household_id = hid and t.source = 'bank_feed' and t.direction = 'credit'
      and not t.excluded and lower(t.merchant) = lower(d.merchant)
      and abs(t.amount - d.amount) < 0.005
      and abs(t.txn_date - d.txn_date) <= 3
    limit 1;
    if cid is not null then
      update transactions set excluded = true where id in (d.id, cid);
      n := n + 2;
    end if;
  end loop;
  return n;
end
$$;
