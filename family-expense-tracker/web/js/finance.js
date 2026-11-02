// Pure finance math for Hearth's Home screen — no DOM, no network, so it can be
// unit-tested (tests/finance.test.mjs). Dates are local 'YYYY-MM-DD' strings;
// transactions are the non-excluded rows from store.getTransactions*.
//
// Spending is split into
//   fixed    — rent/housing, utilities, insurance, taxes, loans (by category name),
//              plus anything matching a loan's payment pattern;
//   variable — everything else: the day-to-day spending the outlook and the
//              weekly burn rate are about.

export const FIXED_CATEGORY = /rent|housing|miete|wohnen|utilit|strom|energie|insurance|versicher|tax|steuer|loan|kredit|darlehen|tilgung|mortgage/i;
const LOAN_CATEGORY = /loan|kredit|darlehen|tilgung|mortgage/i;
const EXEMPT_CATEGORY = /health|medic|pharm|apothek|grocer|lebensmittel|kids|kinder|child|transport/i;

// ---------------------------------------------------------------- dates
export function iso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
export function parseDay(s) { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); }
export function monthKey(s) { return s.slice(0, 7); }
export function daysInMonth(year, monthIndex) { return new Date(year, monthIndex + 1, 0).getDate(); }
function addMonths(d, n) { return new Date(d.getFullYear(), d.getMonth() + n, 1); }
export function weekStart(d) { // Monday
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  x.setDate(x.getDate() - ((x.getDay() + 6) % 7));
  return x;
}

// ---------------------------------------------------------------- classification
function catName(t) { return t.categories?.name || ''; }

export function matchesLoan(t, loans) {
  const text = `${t.merchant || ''} ${t.description || ''}`.toLowerCase();
  return (loans || []).some((l) => l.payment_pattern && text.includes(l.payment_pattern.trim().toLowerCase()));
}

export function isFixed(t, loans) {
  return FIXED_CATEGORY.test(catName(t)) || matchesLoan(t, loans);
}

const sum = (arr) => arr.reduce((s, x) => s + Number(x || 0), 0);
const mean = (arr) => (arr.length ? sum(arr) / arr.length : 0);
function quantile(sorted, q) {
  if (!sorted.length) return 0;
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos), hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

// ---------------------------------------------------------------- history
// The complete months before `monthStart` that have usable data. The first month
// with data is skipped when it starts after the 5th (a partial first month would
// understate the typical spend).
export function historyMonths(txns, monthStart, maxMonths = 6) {
  const firstDate = txns.reduce((min, t) => (min && min < t.txn_date ? min : t.txn_date), null);
  if (!firstDate) return [];
  const months = [];
  for (let i = 1; i <= maxMonths; i++) {
    const m = addMonths(monthStart, -i);
    const key = iso(m).slice(0, 7);
    if (key < monthKey(firstDate)) break;
    if (key === monthKey(firstDate) && Number(firstDate.slice(8, 10)) > 5) break;
    months.push(m);
  }
  return months.reverse();
}

function monthRows(txns, m) {
  const key = iso(m).slice(0, 7);
  return txns.filter((t) => monthKey(t.txn_date) === key);
}

// ---------------------------------------------------------------- month outlook
// Cumulative day-to-day spending for the month vs. the household's typical curve,
// a projection to month end (current month only), and the days that ran above
// a normal day (top 10% of past spending days).
export function monthOutlook({ txns, loans = [], monthStart, today }) {
  const y = monthStart.getFullYear(), mi = monthStart.getMonth();
  const dim = daysInMonth(y, mi);
  const variable = txns.filter((t) => t.direction === 'debit' && !isFixed(t, loans));
  const hist = historyMonths(txns, monthStart);

  // Typical cumulative curve and average day from history.
  const perMonthCum = hist.map((m) => {
    const d = daysInMonth(m.getFullYear(), m.getMonth());
    const daily = new Array(d).fill(0);
    for (const t of monthRows(variable, m)) daily[Number(t.txn_date.slice(8, 10)) - 1] += Number(t.amount);
    const cum = []; daily.reduce((s, v, i) => (cum[i] = s + v), 0);
    return { cum, daily, days: d, total: cum[d - 1] || 0 };
  });
  const typicalCum = [];
  for (let day = 1; day <= dim; day++) {
    typicalCum.push(perMonthCum.length ? mean(perMonthCum.map((p) => p.cum[Math.min(day, p.days) - 1])) : null);
  }
  const avgDay = perMonthCum.length ? mean(perMonthCum.map((p) => p.total / p.days)) : 0;
  // "Above normal" = a top-10% spending day by the household's own history (and at
  // least 1.5× an average day). Spending is lumpy — a weekly shop is not an outlier.
  const spendDays = perMonthCum.flatMap((p) => p.daily.filter((v) => v > 0)).sort((a, b) => a - b);
  const threshold = avgDay <= 0 ? null
    : spendDays.length >= 10 ? Math.max(quantile(spendDays, 0.9), avgDay * 1.5)
    : avgDay * 2;

  // This month.
  const key = iso(monthStart).slice(0, 7);
  const todayKey = iso(today).slice(0, 7);
  const isCurrent = key === todayKey;
  const lastDay = isCurrent ? today.getDate() : (key < todayKey ? dim : 0);
  const rows = monthRows(variable, monthStart);
  const daily = new Array(dim).fill(0);
  const byDay = new Map();
  for (const t of rows) {
    const d = Number(t.txn_date.slice(8, 10));
    daily[d - 1] += Number(t.amount);
    const list = byDay.get(d) || []; list.push(t); byDay.set(d, list);
  }
  let run = 0;
  const days = daily.map((spent, i) => {
    const day = i + 1;
    if (day <= lastDay) run += spent;
    return {
      day,
      spent: day <= lastDay ? spent : null,
      cum: day <= lastDay ? run : null,
      typicalCum: typicalCum[i],
      aboveNormal: threshold != null && day <= lastDay && spent > threshold,
    };
  });
  const actualCum = run;
  const projected = isCurrent ? actualCum + avgDay * (dim - lastDay) : null;
  const typicalToday = lastDay ? typicalCum[lastDay - 1] : null;
  const aboveDays = days.filter((d) => d.aboveNormal)
    .map((d) => {
      const top = (byDay.get(d.day) || []).sort((a, b) => b.amount - a.amount)[0];
      return { date: `${key}-${String(d.day).padStart(2, '0')}`, spent: d.spent, topMerchant: top?.merchant || top?.description || null };
    })
    .sort((a, b) => b.spent - a.spent);

  return {
    days, daysInMonth: dim, lastDay, isCurrent, actualCum, projected,
    typicalToday, typicalTotal: typicalCum[dim - 1], avgDay, threshold,
    aboveDays, historyMonthCount: hist.length,
  };
}

// ---------------------------------------------------------------- weekly burn rate
// Recommended weekly day-to-day budget:
//   (average monthly income − fixed costs − savings goal) × 12 / 52,
// from the last up to 3 complete months. Falls back to 90 % of the past average
// week when there is no income data (e.g. only receipts are tracked).
export function burnRate({ txns, loans = [], today, savingsPct = 20 }) {
  const hist = historyMonths(txns, new Date(today.getFullYear(), today.getMonth(), 1), 3);
  const months = hist.map((m) => {
    const rows = monthRows(txns, m);
    const debits = rows.filter((t) => t.direction === 'debit');
    return {
      income: sum(rows.filter((t) => t.direction === 'credit').map((t) => t.amount)),
      fixed: sum(debits.filter((t) => isFixed(t, loans)).map((t) => t.amount)),
      variable: sum(debits.filter((t) => !isFixed(t, loans)).map((t) => t.amount)),
      days: daysInMonth(m.getFullYear(), m.getMonth()),
      loanRowsSeen: debits.some((t) => LOAN_CATEGORY.test(catName(t))),
      rows: debits,
    };
  });

  // Loans whose payments never show up in the ledger still cost money every month.
  const unseenLoanPayments = sum((loans || []).map((l) => {
    if (!l.monthly_payment || Number(l.balance) <= 0) return 0;
    const seen = l.payment_pattern
      ? months.some((m) => m.rows.some((t) => matchesLoan(t, [l])))
      : months.some((m) => m.loanRowsSeen);
    return seen ? 0 : Number(l.monthly_payment);
  }));

  const incomeMonthly = mean(months.map((m) => m.income));
  const fixedMonthly = mean(months.map((m) => m.fixed)) + unseenLoanPayments;
  const savingsMonthly = (Math.max(0, Math.min(90, Number(savingsPct))) / 100) * incomeMonthly;
  const avgWeekVariable = months.length ? mean(months.map((m) => (m.variable / m.days) * 7)) : 0;

  let basis = 'none';
  let budgetMonthly = 0;
  let weekly = 0;
  let deficit = 0;
  if (months.length && incomeMonthly > 0) {
    basis = 'income';
    budgetMonthly = incomeMonthly - fixedMonthly - savingsMonthly;
    if (budgetMonthly < 0) { deficit = -budgetMonthly; budgetMonthly = 0; }
    weekly = (budgetMonthly * 12) / 52;
  } else if (months.length && avgWeekVariable > 0) {
    basis = 'history';
    weekly = avgWeekVariable * 0.9;
    budgetMonthly = (weekly * 52) / 12;
  }

  const ws = weekStart(today);
  const wsIso = iso(ws), todayIso = iso(today);
  const weekSpent = sum(txns.filter((t) => t.direction === 'debit' && !isFixed(t, loans)
    && t.txn_date >= wsIso && t.txn_date <= todayIso).map((t) => t.amount));
  const daysLeft = 7 - ((today.getDay() + 6) % 7); // including today
  const weekLeft = weekly - weekSpent;

  return {
    basis, monthsUsed: months.length, incomeMonthly, fixedMonthly, unseenLoanPayments,
    savingsPct: Number(savingsPct), savingsMonthly, budgetMonthly, deficit, weekly,
    avgWeekVariable, weekStart: wsIso, weekSpent, weekLeft, daysLeft,
    perDayLeft: weekLeft > 0 ? weekLeft / daysLeft : 0,
  };
}

// ---------------------------------------------------------------- loans
// Month-by-month simulation from today's balance: months to payoff, payoff date,
// interest still to pay. A payment that doesn't cover the monthly interest never
// pays the loan off.
export function loanSchedule(loan, today = new Date()) {
  const balance = Number(loan.balance || 0);
  const payment = Number(loan.monthly_payment || 0);
  const r = Number(loan.interest_rate || 0) / 100 / 12;
  const original = Number(loan.original_amount || 0);
  const paidPct = original > 0 ? Math.max(0, Math.min(100, ((original - balance) / original) * 100)) : null;
  if (balance <= 0) return { monthsLeft: 0, payoffDate: iso(today), interestLeft: 0, paidPct: 100, neverPaysOff: false };
  if (!payment) return { monthsLeft: null, payoffDate: loan.end_date || null, interestLeft: null, paidPct, neverPaysOff: false };
  if (payment <= balance * r) return { monthsLeft: null, payoffDate: null, interestLeft: null, paidPct, neverPaysOff: true };

  let b = balance, months = 0, interest = 0;
  while (b > 0.005 && months < 1200) {
    const i = b * r;
    interest += i;
    b = b + i - payment;
    months++;
  }
  const payoff = new Date(today.getFullYear(), today.getMonth() + months, 1);
  return { monthsLeft: months, payoffDate: iso(payoff).slice(0, 7), interestLeft: interest, paidPct, neverPaysOff: false };
}

// ---------------------------------------------------------------- heads-up
// Recent day-to-day purchases worth a second look, each with the reason it was
// picked. Health, groceries, kids and transport are never flagged.
export function headsUpCandidates({ txns, loans = [], reviewedIds = new Set(), today, limit = 3 }) {
  const todayIso = iso(today);
  const since = iso(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 30));
  const variable = txns.filter((t) => t.direction === 'debit' && !isFixed(t, loans));
  const amounts = variable.map((t) => Number(t.amount)).sort((a, b) => a - b);
  const median = quantile(amounts, 0.5);
  const p90 = quantile(amounts, 0.9);
  const floor = Math.max(15, median);

  const recent = variable.filter((t) => t.txn_date >= since && t.txn_date <= todayIso);
  const firstSeen = new Map();
  for (const t of [...variable].sort((a, b) => (a.txn_date < b.txn_date ? -1 : 1))) {
    const k = (t.merchant || t.description || '').toLowerCase();
    if (k && !firstSeen.has(k)) firstSeen.set(k, t.id);
  }
  const merchantCount = new Map();
  for (const t of recent) {
    const k = (t.merchant || t.description || '').toLowerCase();
    merchantCount.set(k, (merchantCount.get(k) || 0) + 1);
  }

  const picks = [];
  for (const t of recent) {
    if (reviewedIds.has(t.id) || EXEMPT_CATEGORY.test(catName(t))) continue;
    const amt = Number(t.amount);
    if (amt < floor) continue;
    const k = (t.merchant || t.description || '').toLowerCase();
    let reason = null, score = 0;
    if (amounts.length >= 10 && amt >= p90 && amt >= 3 * median) {
      reason = 'Bigger than 90% of your purchases'; score = amt / median + 2;
    } else if (merchantCount.get(k) >= 4) {
      reason = `${merchantCount.get(k)} purchases here in the last 30 days`; score = merchantCount.get(k);
    } else if (firstSeen.get(k) === t.id && amt >= 2 * median) {
      reason = 'First time you shopped here'; score = amt / median;
    } else if (/shopping|entertain|dining|restaurant|travel|hobby|electronic|subscript|abo|other|^$/i.test(catName(t)) && amt >= 1.5 * median) {
      reason = `A bigger-than-usual ${catName(t) || 'uncategorized'} purchase`; score = amt / median;
    }
    if (reason) picks.push({ txn: t, reason, score });
  }
  // One per merchant, highest score first.
  const seen = new Set();
  return picks.sort((a, b) => b.score - a.score)
    .filter((p) => { const k = (p.txn.merchant || p.txn.description || '').toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true; })
    .slice(0, limit)
    .map(({ txn, reason }) => ({ txn, reason }));
}
