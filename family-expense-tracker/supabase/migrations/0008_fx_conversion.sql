-- Foreign-currency support: amounts are normalized to EUR (ECB reference rates
-- via frankfurter.app) by bank-sync; the original amount and currency are kept.

alter table transactions add column if not exists original_amount numeric(12, 2);
alter table transactions add column if not exists original_currency text;
