// Unit tests for web/js/finance.js — run with:  node --test tests/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { monthOutlook, burnRate, loanSchedule, headsUpCandidates, historyMonths, isFixed, weekStart, iso } from '../web/js/finance.js';

const cat = (name) => ({ name });
let n = 0;
const tx = (date, amount, direction, category, merchant = 'Shop') =>
  ({ id: `t${++n}`, txn_date: date, amount, direction, merchant, categories: category ? cat(category) : null });
const d = (y, m, day) => `${y}-${String(m).padStart(2, '0')}-${String(day).padStart(2, '0')}`;

// Six full months (May–Oct 2026) + half of November. Per month: salary 4000,
// rent 1200, utilities 150, loan 300 (category Loans), groceries 20/day.
function household({ withIncome = true } = {}) {
  const rows = [];
  for (let m = 5; m <= 11; m++) {
    const days = new Date(2026, m, 0).getDate();
    const last = m === 11 ? 15 : days;
    if (withIncome) rows.push(tx(d(2026, m, 1), 4000, 'credit', 'Other', 'Employer GmbH'));
    if (m < 11 || last >= 3) rows.push(tx(d(2026, m, 3), 1200, 'debit', 'Rent / Housing', 'Vermieter'));
    rows.push(tx(d(2026, m, 5), 150, 'debit', 'Utilities', 'Stadtwerke'));
    rows.push(tx(d(2026, m, 7), 300, 'debit', 'Loans', 'Kredit Bank'));
    for (let day = 1; day <= last; day++) rows.push(tx(d(2026, m, day), 20, 'debit', 'Groceries', 'Rewe'));
  }
  return rows;
}
const today = new Date(2026, 10, 15); // Sun 15 Nov 2026

test('fixed costs are recognised by category and loan pattern', () => {
  assert.equal(isFixed(tx('2026-11-01', 1, 'debit', 'Rent / Housing'), []), true);
  assert.equal(isFixed(tx('2026-11-01', 1, 'debit', 'Groceries'), []), false);
  assert.equal(isFixed(tx('2026-11-01', 1, 'debit', 'Other', 'SANTANDER RATE 12'), [{ payment_pattern: 'santander' }]), true);
});

test('history skips a partial first month', () => {
  const rows = [tx('2026-05-20', 10, 'debit', 'Groceries'), tx('2026-06-02', 10, 'debit', 'Groceries')];
  const months = historyMonths(rows, new Date(2026, 7, 1)).map((m) => iso(m).slice(0, 7));
  assert.deepEqual(months, ['2026-06', '2026-07']);
});

test('weekly burn rate = (income − fixed − savings) × 12/52', () => {
  const r = burnRate({ txns: household(), loans: [], today, savingsPct: 20 });
  assert.equal(r.basis, 'income');
  assert.equal(r.monthsUsed, 3);
  assert.equal(r.incomeMonthly, 4000);
  assert.equal(r.fixedMonthly, 1650);           // rent + utilities + loan
  assert.equal(r.savingsMonthly, 800);
  assert.equal(r.budgetMonthly, 1550);
  assert.ok(Math.abs(r.weekly - 1550 * 12 / 52) < 1e-9);
  assert.equal(r.weekStart, '2026-11-09');      // Monday
  assert.equal(r.weekSpent, 7 * 20);            // Mon–Sun groceries only
  assert.equal(r.daysLeft, 1);                  // Sunday
});

test('a loan whose payments never appear in the ledger still counts', () => {
  const rows = household().filter((t) => t.categories?.name !== 'Loans');
  const loans = [{ balance: 5000, monthly_payment: 250, payment_pattern: 'santander' }];
  const r = burnRate({ txns: rows, loans, today, savingsPct: 20 });
  assert.equal(r.unseenLoanPayments, 250);
  assert.equal(r.fixedMonthly, 1350 + 250);
});

test('fixed + savings above income gives a deficit, not a negative budget', () => {
  const r = burnRate({ txns: household(), loans: [], today, savingsPct: 90 });
  assert.equal(r.weekly, 0);
  assert.equal(r.deficit, 1650 + 3600 - 4000);
});

test('without income data the burn rate falls back to 90% of a past week', () => {
  const r = burnRate({ txns: household({ withIncome: false }), loans: [], today });
  assert.equal(r.basis, 'history');
  assert.ok(Math.abs(r.weekly - 20 * 7 * 0.9) < 1e-9);
});

test('month outlook: pace, projection and above-normal days', () => {
  const rows = household();
  rows.push(tx('2026-11-10', 300, 'debit', 'Shopping', 'MediaMarkt'));
  const o = monthOutlook({ txns: rows, loans: [], monthStart: new Date(2026, 10, 1), today });
  assert.equal(o.isCurrent, true);
  assert.equal(o.lastDay, 15);
  assert.equal(o.historyMonthCount, 6);
  assert.ok(Math.abs(o.avgDay - 20) < 1e-9);    // fixed costs are not day-to-day spending
  assert.equal(o.actualCum, 15 * 20 + 300);
  assert.equal(o.projected, 600 + 20 * 15);
  assert.equal(o.typicalToday, 300);
  assert.deepEqual(o.aboveDays.map((x) => x.date), ['2026-11-10']);
  assert.equal(o.aboveDays[0].topMerchant, 'MediaMarkt');
  assert.equal(o.days[15].cum, null);           // no actual data after today
});

test('a lumpy weekly shop is not an above-normal day; a real spike is', () => {
  const rows = [];
  for (let m = 5; m <= 11; m++) {
    const last = m === 11 ? 15 : new Date(2026, m, 0).getDate();
    for (let day = 1; day <= last; day += 3) rows.push(tx(d(2026, m, day), 60, 'debit', 'Groceries', 'Rewe'));
  }
  rows.push(tx('2026-11-11', 240, 'debit', 'Shopping', 'Zalando'));
  const o = monthOutlook({ txns: rows, loans: [], monthStart: new Date(2026, 10, 1), today });
  assert.ok(o.avgDay > 19 && o.avgDay < 21);   // 60 every third day
  assert.equal(o.threshold, 60);                // the top-10% day, not 2 × 20
  assert.deepEqual(o.aboveDays.map((x) => x.date), ['2026-11-11']);
});

test('past month outlook has no projection', () => {
  const o = monthOutlook({ txns: household(), loans: [], monthStart: new Date(2026, 9, 1), today });
  assert.equal(o.isCurrent, false);
  assert.equal(o.projected, null);
  assert.equal(o.lastDay, 31);
  assert.equal(o.actualCum, 31 * 20);
});

test('loan schedule: annuity, zero rate, and a payment below the interest', () => {
  const a = loanSchedule({ balance: 10000, interest_rate: 6, monthly_payment: 200, original_amount: 20000 }, today);
  assert.equal(a.monthsLeft, 58);
  assert.ok(a.interestLeft > 1500 && a.interestLeft < 1560, `interest ${a.interestLeft}`);
  assert.equal(a.paidPct, 50);
  assert.equal(a.payoffDate, '2031-09');
  const z = loanSchedule({ balance: 1200, interest_rate: 0, monthly_payment: 100 }, today);
  assert.equal(z.monthsLeft, 12);
  assert.equal(z.interestLeft, 0);
  assert.equal(loanSchedule({ balance: 10000, interest_rate: 12, monthly_payment: 90 }, today).neverPaysOff, true);
});

test('heads-up flags big discretionary buys, never groceries, fixed or reviewed ones', () => {
  const rows = household();
  const tv = tx('2026-11-12', 450, 'debit', 'Shopping', 'MediaMarkt');
  const big = tx('2026-11-11', 400, 'debit', 'Groceries', 'Rewe');
  const done = tx('2026-11-13', 380, 'debit', 'Entertainment', 'Eventim');
  rows.push(tv, big, done);
  const c = headsUpCandidates({ txns: rows, loans: [], reviewedIds: new Set([done.id]), today });
  assert.deepEqual(c.map((x) => x.txn.id), [tv.id]);
  assert.equal(c[0].reason, 'Bigger than 90% of your purchases');
});

test('weekStart is Monday', () => {
  assert.equal(iso(weekStart(new Date(2026, 10, 15))), '2026-11-09');
  assert.equal(iso(weekStart(new Date(2026, 10, 9))), '2026-11-09');
});
