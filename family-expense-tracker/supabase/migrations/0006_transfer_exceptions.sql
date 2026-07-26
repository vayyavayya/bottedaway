-- Transfer exceptions: patterns that override self-transfer detection.
-- A row with is_exception = true means "if this matches, the transaction is
-- real money in/out, never a hidden internal move" (e.g. crypto exchange
-- payouts arriving under the account holder's own name).

alter table transfer_names add column if not exists is_exception boolean not null default false;
