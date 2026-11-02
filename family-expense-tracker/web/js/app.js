import { supabase, CONFIG_OK, DEFAULT_CURRENCY } from './supabaseClient.js';
import * as store from './store.js';
import { money, fmtDate, monthLabel, esc, donutSVG, outlookSVG, toast, DOC_TYPES } from './ui.js';
import { monthOutlook, burnRate, loanSchedule, headsUpCandidates, matchesLoan } from './finance.js';

const appEl = document.getElementById('app');

const state = {
  session: null,
  household: null,
  membership: null,
  categories: [],
  currency: DEFAULT_CURRENCY,
  view: 'home',
  month: startOfMonth(new Date()),
  captureType: 'receipt',
  captureFile: null,
  chat: [],
  span: [],       // up to 7 months of transactions behind the Home screen
  loans: null,    // null until loaded, or when the loans table isn't deployed yet
  reviews: null,  // purchase reviews; null when not deployed yet
};

// ------------------------------------------------------------------ boot
(async function boot() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js').catch(() => {});
  }
  if (!CONFIG_OK) return renderConfigMissing();

  state.session = await store.auth.session();
  store.auth.onChange(async (session) => {
    const wasSignedIn = !!state.session;
    state.session = session;
    if (!session) return renderAuth();
    if (!wasSignedIn) await afterLogin();
  });

  if (!state.session) return renderAuth();
  await afterLogin();
})();

async function afterLogin() {
  try {
    const hh = await store.getMyHousehold();
    if (!hh) return renderOnboarding();
    state.household = hh.household;
    state.membership = hh.membership;
    state.categories = await store.getCategories(hh.household.id);
    state.view = 'home';
    renderShell();
  } catch (e) {
    renderError(e);
  }
}

// ------------------------------------------------------------------ helpers
function startOfMonth(d) { return new Date(d.getFullYear(), d.getMonth(), 1); }
function endOfMonth(d) { return new Date(d.getFullYear(), d.getMonth() + 1, 0); }
function iso(d) {
  // Local-date string — toISOString() would shift Berlin midnights back one day (UTC).
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
function mount(html) { appEl.innerHTML = html; }
function catById(id) { return state.categories.find((c) => c.id === id); }

function renderError(e) {
  mount(`<div class="centered"><div class="card"><h2>Something went wrong</h2>
    <p class="muted">${esc(e.message || e)}</p>
    <button class="btn" onclick="location.reload()">Reload</button></div></div>`);
}

// ------------------------------------------------------------------ config missing
function renderConfigMissing() {
  mount(`<div class="centered">
    <div class="brand"><div class="mark" style="background:#0f766e;display:grid;place-content:center;font-size:2rem">📊</div>
      <h1>Hearth</h1></div>
    <div class="card">
      <h2 style="margin-top:0">Almost there</h2>
      <p class="muted">Create <code>web/config.js</code> from <code>config.example.js</code> and add your
      Supabase URL and anon key, then reload. See <strong>SETUP.md</strong> for the full walkthrough.</p>
    </div>
  </div>`);
}

// ------------------------------------------------------------------ auth
function renderAuth(mode = 'signin') {
  mount(`
    <div class="centered">
      <div class="brand">
        <img class="mark" src="./icons/icon-192.png" alt="" />
        <h1>Hearth</h1>
        <p>Your family's money, in one calm place.</p>
      </div>
      <div class="tabs">
        <button data-mode="signin" class="${mode === 'signin' ? 'active' : ''}">Sign in</button>
        <button data-mode="signup" class="${mode === 'signup' ? 'active' : ''}">Create account</button>
      </div>
      <div id="auth-err"></div>
      <form id="auth-form">
        <div class="field"><label>Email</label><input type="email" name="email" autocomplete="email" required /></div>
        <div class="field"><label>Password</label>
          <input type="password" name="password" autocomplete="${mode === 'signup' ? 'new-password' : 'current-password'}" minlength="6" required /></div>
        <button class="btn" type="submit">${mode === 'signup' ? 'Create account' : 'Sign in'}</button>
      </form>
      <p class="muted" style="text-align:center;margin-top:16px">
        ${mode === 'signup' ? 'One account per person. Share a household after signing in.' : 'Welcome back.'}
      </p>
    </div>`);

  appEl.querySelectorAll('.tabs button').forEach((b) =>
    b.addEventListener('click', () => renderAuth(b.dataset.mode)));

  appEl.querySelector('#auth-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button');
    const email = e.target.email.value.trim();
    const password = e.target.password.value;
    const errBox = appEl.querySelector('#auth-err');
    errBox.innerHTML = '';
    btn.disabled = true;
    btn.textContent = 'Please wait…';
    try {
      const { data, error } = mode === 'signup'
        ? await store.auth.signUp(email, password)
        : await store.auth.signIn(email, password);
      if (error) throw error;
      if (mode === 'signup' && !data.session) {
        errBox.innerHTML = `<div class="error-banner">Check your email to confirm your account, then sign in.</div>`;
        btn.disabled = false; btn.textContent = 'Create account';
        return;
      }
      // onChange handler will drive afterLogin()
    } catch (err) {
      errBox.innerHTML = `<div class="error-banner">${esc(err.message || 'Could not sign in')}</div>`;
      btn.disabled = false;
      btn.textContent = mode === 'signup' ? 'Create account' : 'Sign in';
    }
  });
}

// ------------------------------------------------------------------ onboarding
function renderOnboarding(mode = 'create') {
  mount(`
    <div class="centered">
      <div class="brand"><img class="mark" src="./icons/icon-192.png" alt="" /><h1>Set up your household</h1>
        <p>You and your partner share one private space.</p></div>
      <div class="tabs">
        <button data-mode="create" class="${mode === 'create' ? 'active' : ''}">Create new</button>
        <button data-mode="join" class="${mode === 'join' ? 'active' : ''}">Join with code</button>
      </div>
      <div id="ob-err"></div>
      ${mode === 'create' ? `
        <form id="ob-form">
          <div class="field"><label>Household name</label><input name="name" placeholder="The Smiths" required /></div>
          <div class="field"><label>Your name</label><input name="dname" placeholder="Alex" /></div>
          <button class="btn" type="submit">Create household</button>
        </form>` : `
        <form id="ob-form">
          <div class="field"><label>Invite code</label><input name="code" placeholder="ABC12345" required style="text-transform:uppercase" /></div>
          <div class="field"><label>Your name</label><input name="dname" placeholder="Sam" /></div>
          <button class="btn" type="submit">Join household</button>
        </form>`}
      <button class="btn ghost" id="ob-signout" style="margin-top:14px">Sign out</button>
    </div>`);

  appEl.querySelectorAll('.tabs button').forEach((b) =>
    b.addEventListener('click', () => renderOnboarding(b.dataset.mode)));
  appEl.querySelector('#ob-signout').addEventListener('click', () => store.auth.signOut());

  appEl.querySelector('#ob-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type=submit]');
    const errBox = appEl.querySelector('#ob-err');
    errBox.innerHTML = '';
    btn.disabled = true; btn.textContent = 'Working…';
    try {
      if (mode === 'create') {
        await store.createHousehold(e.target.name.value, e.target.dname.value);
      } else {
        await store.joinHousehold(e.target.code.value, e.target.dname.value);
      }
      await afterLogin();
    } catch (err) {
      errBox.innerHTML = `<div class="error-banner">${esc(err.message || 'Failed')}</div>`;
      btn.disabled = false; btn.textContent = mode === 'create' ? 'Create household' : 'Join household';
    }
  });
}

// ------------------------------------------------------------------ shell
function renderShell() {
  const subtitle = state.household?.name || '';
  mount(`
    <div class="topbar">
      <div><h1>Hearth</h1><div class="sub">${esc(subtitle)}</div></div>
      <button id="fb-open" aria-label="Send feedback">💬 Feedback</button>
    </div>
    <div class="view" id="view"></div>
    <button class="fab" id="fab" title="Add bill">＋</button>
    <div class="tabbar">
      ${tabBtn('home', '🏠', 'Home')}
      ${tabBtn('capture', '📷', 'Add')}
      ${tabBtn('ask', '💬', 'Ask')}
      ${tabBtn('documents', '🗂️', 'Docs')}
      ${tabBtn('settings', '⚙️', 'Settings')}
    </div>`);

  appEl.querySelectorAll('.tabbar button').forEach((b) =>
    b.addEventListener('click', () => { state.view = b.dataset.view; renderView(); }));
  appEl.querySelector('#fab').addEventListener('click', () => { state.view = 'capture'; renderView(); });
  appEl.querySelector('#fb-open').addEventListener('click', () => openFeedbackSheet());
  renderView();
}

function tabBtn(view, emoji, label) {
  return `<button data-view="${view}" class="${state.view === view ? 'active' : ''}">
    <span class="e">${emoji}</span>${label}</button>`;
}

function renderView() {
  appEl.querySelectorAll('.tabbar button').forEach((b) =>
    b.classList.toggle('active', b.dataset.view === state.view));
  const map = { home: viewHome, capture: viewCapture, ask: viewAsk, documents: viewDocuments, settings: viewSettings };
  (map[state.view] || viewHome)();
}

// ------------------------------------------------------------------ HOME
async function viewHome() {
  const v = document.getElementById('view');
  v.innerHTML = `<div class="processing-note"><span class="spinner dark"></span> Loading your month…</div>`;

  const monthStart = startOfMonth(state.month);
  const from = iso(monthStart);
  const to = iso(endOfMonth(state.month));
  const prev = startOfMonth(new Date(state.month.getFullYear(), state.month.getMonth() - 1, 1));
  const prevFrom = iso(prev), prevTo = iso(endOfMonth(prev));
  // Six months of history before the viewed month feed the outlook and burn rate.
  const spanFrom = iso(new Date(monthStart.getFullYear(), monthStart.getMonth() - 6, 1));

  let span, loans, reviews;
  try {
    [span, loans, reviews] = await Promise.all([
      store.getTransactionsSpan(state.household.id, spanFrom, to),
      store.getLoans(state.household.id).catch(() => null),          // null → not deployed yet
      store.getPurchaseReviews(state.household.id).catch(() => null),
    ]);
  } catch (e) { v.innerHTML = `<div class="error-banner">${esc(e.message)}</div>`; return; }
  Object.assign(state, { span, loans, reviews });
  const txns = span.filter((t) => t.txn_date >= from && t.txn_date <= to);
  const prevTxns = span.filter((t) => t.txn_date >= prevFrom && t.txn_date <= prevTo);

  if (txns.length) state.currency = txns[0].currency || state.currency;

  const today = new Date();
  const isCurrentMonth = from === iso(startOfMonth(today));
  const loanList = loans || [];
  const burn = isCurrentMonth
    ? burnRate({ txns: span, loans: loanList, today, savingsPct: state.household.savings_target_pct ?? 20 })
    : null;
  const outlook = monthStart <= today ? monthOutlook({ txns: span, loans: loanList, monthStart, today }) : null;
  const showOutlook = outlook && outlook.lastDay > 0 && (outlook.actualCum > 0 || outlook.historyMonthCount > 0);
  const headsUp = isCurrentMonth && reviews !== null
    ? headsUpCandidates({ txns: span, loans: loanList, reviewedIds: new Set(reviews.map((r) => r.transaction_id)), today })
    : [];
  const recentVerdicts = (reviews || []).filter((r) => r.status === 'reviewed').slice(0, 2);

  const debits = txns.filter((t) => t.direction === 'debit');
  const credits = txns.filter((t) => t.direction === 'credit');
  const totalSpent = sum(debits.map((t) => t.amount));
  const totalIn = sum(credits.map((t) => t.amount));
  const prevSpent = sum(prevTxns.filter((t) => t.direction === 'debit').map((t) => t.amount));

  const byCat = groupByCategory(debits);
  const legend = byCat.map((g) => `
    <div class="leg" data-cat="${g.id}" style="cursor:pointer"><span class="dot" style="background:${g.color}"></span>
      <span>${esc(g.icon)} ${esc(g.name)}</span>
      <span class="pct">${totalSpent ? Math.round((g.value / totalSpent) * 100) : 0}%</span>
      <span class="amt">${money(g.value, state.currency)}</span></div>`).join('');

  const bars = byCat.slice(0, 6).map((g) => {
    const pct = totalSpent ? (g.value / totalSpent) * 100 : 0;
    return `<div class="bar-row" data-cat="${g.id}" style="cursor:pointer"><span class="ic">${esc(g.icon)}</span>
      <span class="nm">${esc(g.name)}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${g.color}"></div></div>
      <span class="amt">${money(g.value, state.currency)}</span></div>`;
  }).join('');

  const recent = txns.slice(0, 12).map(txnRow).join('');

  v.innerHTML = `
    <div class="month-nav">
      <button id="prevM">‹</button>
      <span class="m">${monthLabel(state.month)}</span>
      <button id="nextM">›</button>
    </div>

    <section class="stat-grid">
      <div class="stat" data-flow="debit" style="cursor:pointer"><div class="label">Spent</div><div class="value spend">${money(totalSpent, state.currency)}</div></div>
      <div class="stat" data-flow="credit" style="cursor:pointer"><div class="label">Money in</div><div class="value credit">${money(totalIn, state.currency)}</div></div>
    </section>

    ${burn ? burnCard(burn) : ''}
    ${showOutlook ? outlookCard(outlook, burn) : ''}
    ${headsUp.length || recentVerdicts.length ? headsUpCard(headsUp, recentVerdicts) : ''}

    ${txns.length === 0 ? emptyState('No activity yet this month', 'Tap ＋ to snap a grocery bill or upload a statement.') : `
    <section class="card">
      <div class="section-title" style="margin:0 0 12px">Where it went</div>
      <div class="donut-wrap">
        ${donutSVG(byCat.map((g) => ({ value: g.value, color: g.color })))}
        <div class="legend">${legend || '<span class="muted">No spending recorded.</span>'}</div>
      </div>
    </section>

    ${bars ? `<section class="card"><div class="section-title" style="margin:0 0 6px">Top categories</div>${bars}</section>` : ''}`}

    ${loans !== null ? loansCard(loanList) : ''}

    ${txns.length === 0 ? '' : `
    <section class="insight">
      <h3>💡 Insights — ${monthLabel(state.month)}</h3>
      <ul>${insightLines(totalSpent, prevSpent, byCat, debits).map((l) => `<li>${l}</li>`).join('')}</ul>
    </section>

    <section>
      <div class="section-title">Recent activity</div>
      <div class="card"><div class="list">${recent}</div></div>
    </section>`}
  `;

  v.querySelector('#prevM').addEventListener('click', () => {
    state.month = startOfMonth(new Date(state.month.getFullYear(), state.month.getMonth() - 1, 1));
    viewHome();
  });
  v.querySelector('#nextM').addEventListener('click', () => {
    state.month = startOfMonth(new Date(state.month.getFullYear(), state.month.getMonth() + 1, 1));
    viewHome();
  });
  v.querySelectorAll('[data-cat]').forEach((el) =>
    el.addEventListener('click', () => openCategorySheet(el.dataset.cat, byCat, debits)));
  v.querySelectorAll('[data-flow]').forEach((el) =>
    el.addEventListener('click', () => openFlowSheet(el.dataset.flow, el.dataset.flow === 'debit' ? debits : credits)));
  v.querySelector('#burn-info')?.addEventListener('click', () => openBurnSheet(burn));
  v.querySelectorAll('[data-review]').forEach((el) => el.addEventListener('click', () => {
    openReviewSheet(el.dataset.review, headsUp.find((c) => c.txn.id === el.dataset.review)?.reason);
  }));
  v.querySelectorAll('[data-skip]').forEach((el) => el.addEventListener('click', async () => {
    el.disabled = true;
    try { await store.dismissPurchase(state.household.id, el.dataset.skip); toast('Skipped'); viewHome(); }
    catch (e) { el.disabled = false; toast(e.message || 'Could not skip'); }
  }));
  v.querySelectorAll('[data-verdict]').forEach((el) =>
    el.addEventListener('click', () => openVerdictSheet(el.dataset.verdict)));
  v.querySelectorAll('[data-loan]').forEach((el) =>
    el.addEventListener('click', () => openLoanSheet(el.dataset.loan)));
  v.querySelector('#loan-add')?.addEventListener('click', () => openLoanForm());
}

// ------------------------------------------------------------------ WEEKLY BURN
function burnCard(b) {
  const cur = state.currency;
  const title = '<div class="section-title" style="margin:0">🔥 Weekly burn rate</div>';
  if (b.basis === 'none') {
    return `<section class="card">${title}<p class="muted" style="margin:6px 0 0">Your recommended weekly budget
      appears after your first full month in Hearth.</p></section>`;
  }
  const pct = b.weekly > 0 ? Math.min(100, (b.weekSpent / b.weekly) * 100) : 100;
  const over = b.weekLeft < 0;
  return `<section class="card">
    <div class="burn-head">
      <div>${title}<div class="burn-rate">${money(b.weekly, cur)}<span> a week, recommended</span></div></div>
      <button class="btn small secondary" id="burn-info">How?</button>
    </div>
    <div class="meter"><div class="meter-fill ${over ? 'over' : pct > 80 ? 'warn' : ''}" style="width:${pct}%"></div></div>
    <p class="burn-line">${over
      ? `<strong>${money(-b.weekLeft, cur)} over</strong> this week — ${money(b.weekSpent, cur)} spent since Monday.`
      : `${money(b.weekSpent, cur)} spent since Monday · <strong>${money(b.weekLeft, cur)} left</strong>, about
         ${money(b.perDayLeft, cur)} a day for the ${b.daysLeft} day${b.daysLeft === 1 ? '' : 's'} left.`}</p>
    ${b.deficit > 0 ? `<div class="warn-banner">Fixed costs plus your ${b.savingsPct}% savings goal come to
      ${money(b.deficit, cur)} a month more than your income. Lower the savings goal, or look at your fixed costs.</div>` : ''}
    ${b.basis === 'history' ? '<p class="muted small-note">No income in Hearth yet, so this is 90% of your usual week.</p>' : ''}
  </section>`;
}

function openBurnSheet(b) {
  const cur = state.currency;
  const months = `${b.monthsUsed} full month${b.monthsUsed === 1 ? '' : 's'}`;
  const math = b.basis === 'income' ? `
    <p class="muted" style="margin:0 0 8px">From your last ${months}:</p>
    <div class="kv"><span class="k">Average money in</span><span>${money(b.incomeMonthly, cur)}</span></div>
    <div class="kv"><span class="k">Fixed costs (rent, utilities, insurance, taxes, loans)</span><span>− ${money(b.fixedMonthly, cur)}</span></div>
    <div class="kv"><span class="k">Savings goal (${b.savingsPct}%)</span><span>− ${money(b.savingsMonthly, cur)}</span></div>
    <div class="kv total"><span class="k">Left for day-to-day spending</span><span>${money(b.budgetMonthly, cur)} a month</span></div>
    <div class="kv total"><span class="k">Per week (× 12 ÷ 52)</span><span>${money(b.weekly, cur)}</span></div>
    ${b.unseenLoanPayments ? `<p class="muted small-note">Includes ${money(b.unseenLoanPayments, cur)} of loan payments that don't show up in your bank feed.</p>` : ''}`
    : `
    <p class="muted" style="margin:0 0 8px">No income has come into Hearth yet, so this uses your last ${months}:</p>
    <div class="kv"><span class="k">Your usual week of day-to-day spending</span><span>${money(b.avgWeekVariable, cur)}</span></div>
    <div class="kv total"><span class="k">Recommended: 90% of that</span><span>${money(b.weekly, cur)}</span></div>`;
  showSheet(`
    <h2>🔥 How your weekly burn rate is worked out</h2>
    ${math}
    <form id="sv-form" class="row" style="margin-top:14px;align-items:flex-end">
      <div class="field" style="margin:0"><label>Savings goal (% of income)</label>
        <input id="sv-pct" inputmode="decimal" value="${b.savingsPct}" /></div>
      <button class="btn small" type="submit" style="flex:0 0 auto">Save</button>
    </form>
    <div id="sv-err"></div>
    <p class="muted small-note">Day-to-day spending is everything except the fixed costs above. The week runs Monday to Sunday.</p>`);
  document.getElementById('sv-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const pct = parseNum(document.getElementById('sv-pct').value);
    const err = document.getElementById('sv-err');
    if (pct == null || pct < 0 || pct > 90) { err.innerHTML = '<div class="error-banner">Enter a number from 0 to 90.</div>'; return; }
    try {
      await store.updateSavingsTarget(state.household.id, pct);
      state.household.savings_target_pct = pct;
      closeSheet(); toast('Savings goal updated'); viewHome();
    } catch (ex) { err.innerHTML = `<div class="error-banner">${esc(ex.message || 'Could not save')}</div>`; }
  });
}

// ------------------------------------------------------------------ MONTH OUTLOOK
function outlookCard(o, burn) {
  const cur = state.currency;
  const budget = o.isCurrent && burn && burn.basis !== 'none' ? burn.budgetMonthly : null;
  const chart = o.historyMonthCount ? o : { ...o, projected: null };
  let summary;
  if (o.isCurrent) {
    const diff = o.typicalToday != null ? o.actualCum - o.typicalToday : null;
    summary = `Day ${o.lastDay}: <strong>${money(o.actualCum, cur)}</strong> spent`
      + (diff != null && Math.abs(diff) >= 1 ? `, ${money(Math.abs(diff), cur)} ${diff > 0 ? 'above' : 'below'} your usual pace.` : '.')
      + (o.historyMonthCount ? ` At this pace you'll reach about <strong>${money(o.projected, cur)}</strong> by the end of the month${budget ? ` (budget ${money(budget, cur)})` : ''}.` : '');
  } else {
    summary = `<strong>${money(o.actualCum, cur)}</strong> of day-to-day spending`
      + (o.typicalTotal != null ? `, against ${money(o.typicalTotal, cur)} in a usual month.` : '.');
  }
  const above = o.aboveDays.slice(0, 3).map((d) => `<li><strong>${fmtDate(d.date)}</strong> · ${money(d.spent, cur)}${d.topMerchant ? ` · ${esc(d.topMerchant)}` : ''}</li>`).join('');
  return `<section class="card">
    <div class="section-title" style="margin:0 0 8px">📈 Month outlook</div>
    ${outlookSVG(chart, { budget })}
    <div class="ol-legend"><span class="k-actual">This month</span>${o.historyMonthCount ? '<span class="k-typical">Usual month</span>' : ''}${chart.projected != null ? '<span class="k-proj">Projection</span>' : ''}${budget ? '<span class="k-budget">Budget</span>' : ''}${o.threshold ? '<span class="k-hi">Above a normal day</span>' : ''}</div>
    <p class="ol-summary">${summary}</p>
    ${above ? `<div class="section-title" style="margin:10px 0 4px">Days above normal (over ${money(o.threshold, cur)})</div><ul class="ol-days">${above}</ul>` : ''}
    <p class="muted small-note">${o.historyMonthCount ? '' : 'Your usual month and the projection appear after your first full month. '}Day-to-day spending only: rent, utilities, insurance, taxes and loans are left out.</p>
  </section>`;
}

// ------------------------------------------------------------------ PURCHASE HEADS-UP
const VERDICTS = {
  necessary: ['✅', 'Necessary'],
  nice_to_have: ['🙂', 'Nice to have'],
  unnecessary: ['⚠️', 'Likely unnecessary'],
};
function verdictChip(v) {
  const [emoji, label] = VERDICTS[v] || ['💬', 'Reviewed'];
  return `<span class="verdict v-${esc(v)}">${emoji} ${label}</span>`;
}

function headsUpCard(candidates, verdicts) {
  const cur = state.currency;
  const items = candidates.map(({ txn, reason }) => `<div class="hu-item">
      <div class="hu-body">
        <div class="t">${esc(txn.merchant || txn.description || 'Purchase')} · <strong>${money(txn.amount, txn.currency || cur)}</strong></div>
        <div class="s">${fmtDate(txn.txn_date)} · ${esc(reason)}</div>
      </div>
      <div class="hu-actions">
        <button class="btn small" data-review="${txn.id}">Review</button>
        <button class="btn small ghost" data-skip="${txn.id}">Not now</button>
      </div>
    </div>`).join('');
  const recent = verdicts.map((r) => `<div class="hu-verdict" data-verdict="${r.transaction_id}">
      ${verdictChip(r.verdict)}<span>${esc(r.headline || '')}</span></div>`).join('');
  return `<section class="card">
    <div class="section-title" style="margin:0 0 6px">🤔 Worth a second look?</div>
    ${items ? `<p class="muted" style="margin:0 0 4px">Tell Claude what these were and why you bought them, and get an honest take.</p>${items}` : ''}
    ${recent ? `<div class="section-title" style="margin:${items ? 14 : 4}px 0 6px">Recent verdicts</div>${recent}` : ''}
  </section>`;
}

function verdictBlock(r) {
  return `<div class="verdict-block">${verdictChip(r.verdict)}
    <h3>${esc(r.headline || '')}</h3>
    <p>${esc(r.feedback || '')}</p>
    ${r.tip ? `<p class="tip">💡 ${esc(r.tip)}</p>` : ''}
    ${r.what ? `<p class="muted small-note">You said: “${esc(r.what)}”${r.why ? ` — ${esc(r.why)}` : ''}</p>` : ''}
  </div>`;
}

function openReviewSheet(txnId, reason) {
  const t = state.span.find((x) => x.id === txnId);
  if (!t) return;
  showSheet(`
    <h2>🤔 ${esc(t.merchant || t.description || 'Purchase')} · ${money(t.amount, t.currency || state.currency)}</h2>
    <p class="muted" style="margin:0 0 12px">${fmtDate(t.txn_date)} · ${esc(t.categories?.name || 'Uncategorized')}${reason ? ` · ${esc(reason)}` : ''}</p>
    <form id="rv-form">
      <div class="field"><label>What was it?</label>
        <input id="rv-what" maxlength="500" required placeholder="e.g. Noise-cancelling headphones" /></div>
      <div class="field"><label>Why did you buy it?</label>
        <textarea id="rv-why" rows="3" maxlength="1000" required placeholder="e.g. My old pair broke and I'm on calls all day"></textarea></div>
      <div id="rv-err"></div>
      <button class="btn" type="submit">Ask Claude</button>
    </form>
    <div id="rv-result"></div>`);
  document.getElementById('rv-what').focus();
  document.getElementById('rv-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const what = document.getElementById('rv-what').value.trim();
    const why = document.getElementById('rv-why').value.trim();
    const err = document.getElementById('rv-err');
    err.innerHTML = '';
    if (what.length < 2 || why.length < 2) {
      err.innerHTML = '<div class="error-banner">Add a few words for both, so Claude can judge it fairly.</div>';
      return;
    }
    const form = e.target;
    const btn = form.querySelector('button[type=submit]');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Claude is thinking…';
    try {
      const review = await store.reviewPurchase(txnId, what, why);
      form.remove();
      document.getElementById('rv-result').innerHTML = `${verdictBlock(review)}
        <button class="btn" id="rv-done" style="margin-top:14px">Done</button>`;
      document.getElementById('rv-done').addEventListener('click', () => { closeSheet(); viewHome(); });
    } catch (ex) {
      err.innerHTML = `<div class="error-banner">${esc(ex.message || 'Could not get a review')}</div>`;
      btn.disabled = false; btn.textContent = 'Ask Claude';
    }
  });
}

function openVerdictSheet(txnId) {
  const r = (state.reviews || []).find((x) => x.transaction_id === txnId);
  if (!r) return;
  const t = state.span.find((x) => x.id === txnId);
  const title = t ? `${esc(t.merchant || t.description || 'Purchase')} · ${money(t.amount, t.currency || state.currency)}` : esc(r.what || 'Purchase');
  showSheet(`<h2>🤔 ${title}</h2>${t ? `<p class="muted" style="margin:0 0 12px">${fmtDate(t.txn_date)}</p>` : ''}${verdictBlock(r)}`);
}

// ------------------------------------------------------------------ LOANS
const LOAN_COLORS = ['#0d9488', '#f59e0b', '#6366f1', '#e11d48', '#0ea5e9', '#8b5cf6', '#84cc16', '#f97316'];
const LOAN_KINDS = {
  mortgage: ['🏠', 'Mortgage'], car: ['🚗', 'Car loan'], personal: ['💳', 'Personal loan'],
  credit_card: ['💳', 'Credit card'], student: ['🎓', 'Student loan'], family: ['👪', 'Family or friends'], other: ['📄', 'Other'],
};

function compactMoney(amount) {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: state.currency, notation: 'compact', maximumFractionDigits: 1 }).format(amount);
  } catch { return money(amount, state.currency); }
}
function wholeMoney(amount) {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency: state.currency, maximumFractionDigits: 0 }).format(amount);
  } catch { return money(amount, state.currency); }
}
function monthYear(ym) {
  const [y, m] = ym.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
}
function ordinal(n) {
  const suffix = n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th';
  return `${n}${suffix}`;
}
function parseNum(s) {
  let t = String(s ?? '').trim().replace(/\s/g, '');
  if (!t) return null;
  if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.'); // German: 1.234,56
  const n = Number(t);
  return Number.isFinite(n) ? n : NaN;
}

function loansCard(loans) {
  const cur = state.currency;
  if (!loans.length) {
    return `<section class="card">
      <div class="section-title" style="margin:0 0 6px">🏦 Loans</div>
      <p class="muted" style="margin:0 0 12px">Add your loans to see what you owe, what they cost each month,
      and when each one is paid off.</p>
      <button class="btn secondary" id="loan-add">＋ Add a loan</button>
    </section>`;
  }
  const total = sum(loans.map((l) => l.balance));
  const monthly = sum(loans.map((l) => l.monthly_payment || 0));
  const schedules = loans.map((l) => loanSchedule(l));
  const interest = sum(schedules.map((s) => s.interestLeft || 0));
  const unknownInterest = schedules.some((s) => s.interestLeft == null);
  const debtFree = schedules.every((s) => s.payoffDate) ? schedules.map((s) => s.payoffDate).sort().at(-1) : null;
  const color = (i) => LOAN_COLORS[i % LOAN_COLORS.length];
  const legend = loans.map((l, i) => `
    <div class="leg" data-loan="${l.id}" style="cursor:pointer"><span class="dot" style="background:${color(i)}"></span>
      <span>${esc(l.name)}</span>
      <span class="pct">${total ? Math.round((l.balance / total) * 100) : 0}%</span>
      <span class="amt">${wholeMoney(l.balance)}</span></div>`).join('');
  return `<section class="card">
    <div class="section-title" style="margin:0 0 12px">🏦 Loans</div>
    <div class="donut-wrap">
      ${donutSVG(loans.map((l, i) => ({ value: Number(l.balance), color: color(i) })), { center: { top: compactMoney(total), bottom: 'owed' } })}
      <div class="legend">${legend}</div>
    </div>
    <div class="loan-stats">
      <div><span>Monthly payments</span><strong>${money(monthly, cur)}</strong></div>
      <div><span>Interest still to pay</span><strong>${unknownInterest ? 'at least ' : ''}${money(interest, cur)}</strong></div>
      <div><span>Debt-free</span><strong>${debtFree ? monthYear(debtFree) : '—'}</strong></div>
    </div>
    ${schedules.some((s) => s.neverPaysOff) ? `<div class="warn-banner">One payment doesn't cover its loan's interest,
      so that balance never goes down. Tap the loan for details.</div>` : ''}
    <button class="btn secondary" id="loan-add" style="margin-top:12px">＋ Add a loan</button>
  </section>`;
}

function openLoanSheet(id) {
  const l = (state.loans || []).find((x) => x.id === id);
  if (!l) return;
  const s = loanSchedule(l);
  const cur = state.currency;
  const [emoji, kindLabel] = LOAN_KINDS[l.kind] || LOAN_KINDS.other;
  const payments = l.payment_pattern
    ? state.span.filter((t) => t.direction === 'debit' && matchesLoan(t, [l]))
    : [];
  const payoff = s.neverPaysOff ? 'Never, at this payment'
    : s.monthsLeft != null ? `${monthYear(s.payoffDate)} · ${s.monthsLeft} month${s.monthsLeft === 1 ? '' : 's'}`
    : l.end_date ? fmtDate(l.end_date) : '—';
  const row = (k, val) => `<div class="kv"><span class="k">${k}</span><span>${val}</span></div>`;
  showSheet(`
    <h2>${emoji} ${esc(l.name)}</h2>
    <p class="muted" style="margin:0 0 10px">${esc(kindLabel)}${l.lender ? ` · ${esc(l.lender)}` : ''}</p>
    ${s.paidPct != null ? `<div class="meter"><div class="meter-fill" style="width:${s.paidPct}%"></div></div>
      <p class="muted small-note" style="margin:6px 0 10px">${Math.round(s.paidPct)}% paid off of ${money(l.original_amount, cur)}</p>` : ''}
    ${row('Still owed', `<strong>${money(l.balance, cur)}</strong>`)}
    ${row('Interest rate', `${Number(l.interest_rate || 0).toLocaleString(undefined, { maximumFractionDigits: 3 })}% a year`)}
    ${row('Monthly payment', l.monthly_payment ? money(l.monthly_payment, cur) : '—')}
    ${row('Paid off', payoff)}
    ${row('Interest still to pay', s.interestLeft != null ? money(s.interestLeft, cur) : '—')}
    ${l.payment_day ? row('Payment day', `${ordinal(l.payment_day)} of the month`) : ''}
    ${l.payment_pattern ? row('Last payment seen', payments[0]
      ? `${fmtDate(payments[0].txn_date)} · ${money(payments[0].amount, payments[0].currency || cur)}`
      : 'None in the last 7 months') : ''}
    ${l.notes ? `<p class="muted small-note" style="margin-top:8px">${esc(l.notes)}</p>` : ''}
    ${s.neverPaysOff ? `<div class="warn-banner">${money(l.monthly_payment, cur)} a month doesn't cover the
      ${money((l.balance * l.interest_rate) / 1200, cur)} of monthly interest, so the balance grows. Talk to
      ${esc(l.lender || 'the lender')} about the payment.</div>` : ''}
    <div class="row" style="margin-top:16px">
      <button class="btn secondary" id="loan-edit">Edit</button>
      <button class="btn danger" id="loan-del">Delete</button>
    </div>`);
  document.getElementById('loan-edit').addEventListener('click', () => openLoanForm(l));
  document.getElementById('loan-del').addEventListener('click', async () => {
    if (!confirm(`Delete “${l.name}”?`)) return;
    try { await store.deleteLoan(l.id); closeSheet(); toast('Loan deleted'); viewHome(); }
    catch (e) { toast(e.message || 'Could not delete'); }
  });
}

function openLoanForm(l = null) {
  closeSheet();
  const val = (v) => (v == null ? '' : esc(String(v)));
  const field = (label, html) => `<div class="field"><label>${label}</label>${html}</div>`;
  const num = (id, v, ph) => `<input id="${id}" inputmode="decimal" autocomplete="off" value="${val(v)}" placeholder="${ph}" />`;
  showSheet(`
    <h2>${l ? 'Edit loan' : '🏦 Add a loan'}</h2>
    <form id="loan-form">
      ${field('Name', `<input id="ln-name" maxlength="80" required value="${val(l?.name)}" placeholder="e.g. Car loan" />`)}
      <div class="row">
        ${field('Type', `<select id="ln-kind">${Object.entries(LOAN_KINDS).map(([k, [e, t]]) =>
          `<option value="${k}" ${(l?.kind || 'other') === k ? 'selected' : ''}>${e} ${t}</option>`).join('')}</select>`)}
        ${field('Lender', `<input id="ln-lender" maxlength="80" value="${val(l?.lender)}" placeholder="e.g. Santander" />`)}
      </div>
      <div class="row">
        ${field('Still owed', num('ln-balance', l?.balance, '12500'))}
        ${field('Original amount', num('ln-orig', l?.original_amount, '20000'))}
      </div>
      <div class="row">
        ${field('Interest rate (% a year)', num('ln-rate', l?.interest_rate, '4.9'))}
        ${field('Monthly payment', num('ln-pay', l?.monthly_payment, '350'))}
      </div>
      <div class="row">
        ${field('Payment day', `<input id="ln-day" inputmode="numeric" value="${val(l?.payment_day)}" placeholder="1–31" />`)}
        ${field('Ends (optional)', `<input id="ln-end" type="date" value="${val(l?.end_date)}" />`)}
      </div>
      ${field('Text on your bank statement', `<input id="ln-pattern" maxlength="60" value="${val(l?.payment_pattern)}" placeholder="e.g. SANTANDER" />`)}
      <p class="muted small-note" style="margin:-6px 2px 12px">Lets Hearth find this loan's payments in your bank feed.</p>
      ${field('Notes', `<textarea id="ln-notes" rows="2" maxlength="500">${val(l?.notes)}</textarea>`)}
      <div id="ln-err"></div>
      <button class="btn" type="submit">Save loan</button>
    </form>`);
  document.getElementById('loan-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const get = (id) => document.getElementById(id).value;
    const err = document.getElementById('ln-err');
    const loan = {
      id: l?.id,
      name: get('ln-name').trim(),
      kind: get('ln-kind'),
      lender: get('ln-lender').trim() || null,
      balance: parseNum(get('ln-balance')),
      original_amount: parseNum(get('ln-orig')),
      interest_rate: parseNum(get('ln-rate')) ?? 0,
      monthly_payment: parseNum(get('ln-pay')),
      payment_day: parseNum(get('ln-day')),
      end_date: get('ln-end') || null,
      payment_pattern: get('ln-pattern').trim() || null,
      notes: get('ln-notes').trim() || null,
    };
    const problem = !loan.name ? 'Give the loan a name.'
      : loan.balance == null || Number.isNaN(loan.balance) || loan.balance < 0 ? 'Enter how much is still owed.'
      : [loan.original_amount, loan.monthly_payment].some((n) => Number.isNaN(n) || n < 0) ? 'Amounts must be numbers of 0 or more.'
      : Number.isNaN(loan.interest_rate) || loan.interest_rate < 0 || loan.interest_rate > 100 ? 'The interest rate must be between 0 and 100.'
      : loan.payment_day != null && (!Number.isInteger(loan.payment_day) || loan.payment_day < 1 || loan.payment_day > 31) ? 'The payment day must be 1 to 31.'
      : null;
    if (problem) { err.innerHTML = `<div class="error-banner">${problem}</div>`; return; }
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true; btn.textContent = 'Saving…';
    try {
      await store.saveLoan(state.household.id, loan);
      closeSheet(); toast('Loan saved'); viewHome();
    } catch (ex) {
      err.innerHTML = `<div class="error-banner">${esc(ex.message || 'Could not save the loan')}</div>`;
      btn.disabled = false; btn.textContent = 'Save loan';
    }
  });
}

function openFlowSheet(direction, rows) {
  const credit = direction === 'credit';
  const total = rows.reduce((s, t) => s + Number(t.amount || 0), 0);
  const sorted = [...rows].sort((a, b) => (a.txn_date < b.txn_date ? 1 : -1));
  const items = sorted.map((t) => `<div class="item">
      <div class="ic">${esc(t.categories?.icon || (credit ? '💰' : '💳'))}</div>
      <div class="body">
        <div class="t">${esc(t.merchant || t.description || 'Transaction')}</div>
        <div class="s">${fmtDate(t.txn_date)} · ${esc(t.categories?.name || (credit ? 'Income' : 'Uncategorized'))}${t.source === 'bank_feed' ? '' : ' · 🧾'}</div>
      </div>
      <div class="amt ${credit ? 'credit' : ''}">${credit ? '+' : ''}${money(t.amount, t.currency || state.currency)}</div>
    </div>`).join('');
  showSheet(`
    <h2>${credit ? '💰 Money in' : '💸 Spent'} — ${monthLabel(state.month)}</h2>
    <p class="muted" style="margin:2px 0 10px">${sorted.length} transaction${sorted.length === 1 ? '' : 's'} ·
      <strong>${money(total, state.currency)}</strong></p>
    <div class="list" style="max-height:56vh;overflow-y:auto">${items || '<p class="muted">Nothing here.</p>'}</div>`);
}

function openCategorySheet(catId, byCat, debits) {
  const g = byCat.find((x) => String(x.id) === String(catId));
  if (!g) return;
  const rows = debits
    .filter((t) => (t.category_id || 'none') === g.id)
    .sort((a, b) => (a.txn_date < b.txn_date ? 1 : -1));
  const items = rows.map((t) => `<div class="item">
      <div class="ic">${esc(g.icon)}</div>
      <div class="body">
        <div class="t">${esc(t.merchant || t.description || 'Transaction')}</div>
        <div class="s">${fmtDate(t.txn_date)}${t.source === 'bank_feed' ? '' : ' · 🧾 scanned'}</div>
      </div>
      <div class="amt">${money(t.amount, t.currency || state.currency)}</div>
    </div>`).join('');
  showSheet(`
    <h2>${esc(g.icon)} ${esc(g.name)} — ${monthLabel(state.month)}</h2>
    <p class="muted" style="margin:2px 0 10px">${rows.length} transaction${rows.length === 1 ? '' : 's'} ·
      <strong>${money(g.value, state.currency)}</strong></p>
    <div class="list" style="max-height:56vh;overflow-y:auto">${items || '<p class="muted">Nothing here.</p>'}</div>`);
}

function txnRow(t) {
  const cat = t.categories || {};
  const credit = t.direction === 'credit';
  return `<div class="item">
    <div class="ic">${esc(cat.icon || (credit ? '💰' : '💳'))}</div>
    <div class="body">
      <div class="t">${esc(t.merchant || t.description || 'Transaction')}</div>
      <div class="s">${fmtDate(t.txn_date)} · ${esc(cat.name || 'Uncategorized')}</div>
    </div>
    <div class="amt ${credit ? 'credit' : ''}">${credit ? '+' : ''}${money(t.amount, t.currency || state.currency)}</div>
  </div>`;
}

function insightLines(total, prev, byCat, debits) {
  const lines = [];
  const cur = state.currency;
  lines.push(`You spent <strong>${money(total, cur)}</strong> across <strong>${debits.length}</strong> ${debits.length === 1 ? 'purchase' : 'purchases'}.`);
  if (byCat[0] && total) {
    const pct = Math.round((byCat[0].value / total) * 100);
    lines.push(`Biggest category: <strong>${esc(byCat[0].icon)} ${esc(byCat[0].name)}</strong> — ${money(byCat[0].value, cur)} (${pct}%).`);
  }
  const merchants = groupBy(debits, (t) => t.merchant || t.description || 'Other');
  const topM = merchants.sort((a, b) => b.value - a.value)[0];
  if (topM && topM.key !== 'Other') {
    lines.push(`Most spent at <strong>${esc(topM.key)}</strong>: ${money(topM.value, cur)}.`);
  }
  if (prev > 0) {
    const diff = total - prev;
    const pct = Math.round(Math.abs(diff) / prev * 100);
    if (Math.abs(diff) > 0.01) {
      lines.push(diff > 0
        ? `You're spending <strong>${pct}% more</strong> than last month (${money(prev, cur)}).`
        : `Nice — <strong>${pct}% less</strong> than last month (${money(prev, cur)}). 🎉`);
    }
  }
  const dining = byCat.find((g) => /dining/i.test(g.name));
  if (dining && total && dining.value / total > 0.25) {
    lines.push(`Heads up: dining out is over a quarter of your spending this month.`);
  }
  return lines;
}

// ------------------------------------------------------------------ CAPTURE
function viewCapture() {
  const v = document.getElementById('view');
  const t = state.captureType;
  v.innerHTML = `
    <section class="card">
      <div class="section-title" style="margin:0 0 10px">What are you adding?</div>
      <div class="type-choice">
        ${typeChip('receipt', '🧾', 'Receipt')}
        ${typeChip('utility_bill', '💡', 'Utility bill')}
        ${typeChip('bank_statement', '🏦', 'Statement')}
      </div>
      <div class="row">
        <button class="btn amber" id="btn-camera">📷 Take photo</button>
        <button class="btn secondary" id="btn-file">📎 Choose file</button>
      </div>
      <p class="muted" style="margin:12px 2px 0">
        ${t === 'bank_statement'
          ? 'Pick a PDF or image of your statement — every transaction gets read and categorized.'
          : 'Snap the bill. It’s saved as a PDF, itemized, and added to your spending.'}
      </p>
      <input id="in-camera" type="file" accept="image/*" capture="environment" hidden />
      <input id="in-file" type="file" accept="image/*,application/pdf" hidden />
    </section>
    <div id="capture-result"></div>`;

  v.querySelectorAll('.type-choice button').forEach((b) =>
    b.addEventListener('click', () => { state.captureType = b.dataset.type; viewCapture(); }));
  v.querySelector('#btn-camera').addEventListener('click', () => v.querySelector('#in-camera').click());
  v.querySelector('#btn-file').addEventListener('click', () => v.querySelector('#in-file').click());
  v.querySelector('#in-camera').addEventListener('change', (e) => handleFile(e.target.files[0]));
  v.querySelector('#in-file').addEventListener('change', (e) => handleFile(e.target.files[0]));
}

function typeChip(type, e, label) {
  return `<button data-type="${type}" class="${state.captureType === type ? 'active' : ''}">
    <span class="e">${e}</span>${label}</button>`;
}

async function handleFile(file) {
  if (!file) return;
  const box = document.getElementById('capture-result');
  const isImg = file.type.startsWith('image/');
  const previewUrl = isImg ? URL.createObjectURL(file) : null;
  box.innerHTML = `
    <div class="card">
      ${previewUrl ? `<img class="preview" src="${previewUrl}" alt="preview" />` : `<p class="muted">📄 ${esc(file.name)}</p>`}
      <div class="processing-note"><span class="spinner dark"></span> <span id="cap-status">Starting…</span></div>
    </div>`;

  try {
    const { result } = await store.uploadAndAnalyze({
      householdId: state.household.id,
      file,
      docType: state.captureType,
      onStatus: (s) => { const el = document.getElementById('cap-status'); if (el) el.textContent = s; },
    });
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    box.innerHTML = renderCaptureResult(result);
    toast('Saved & analyzed ✓');
  } catch (e) {
    box.innerHTML = `<div class="card"><div class="error-banner">${esc(e.message || 'Failed')}</div>
      <button class="btn secondary" id="retry">Try again</button></div>`;
    document.getElementById('retry')?.addEventListener('click', () => { box.innerHTML = ''; });
  }
}

function renderCaptureResult(result) {
  if (result?.type === 'bank_statement') {
    return `<div class="card">
      <h2 style="margin:0 0 6px">Statement added ✓</h2>
      <p class="muted">${result.transaction_count} transaction(s) read and categorized.</p>
      <button class="btn" onclick="location.reload()">Done</button>
    </div>`;
  }
  const r = result?.receipt;
  return `<div class="card">
    <h2 style="margin:0 0 6px">${esc(r?.merchant || 'Receipt')} ✓</h2>
    <div class="kv"><span class="k">Total</span><span><strong>${money(r?.total, r?.currency || state.currency)}</strong></span></div>
    ${r?.purchased_at ? `<div class="kv"><span class="k">Date</span><span>${fmtDate(r.purchased_at)}</span></div>` : ''}
    <div class="kv"><span class="k">Items read</span><span>${result?.line_item_count ?? 0}</span></div>
    <button class="btn" style="margin-top:10px" id="cap-done">Done</button>
  </div>`;
}

// wire the "Done" button after render (event delegation on view)
document.addEventListener('click', (e) => {
  if (e.target && e.target.id === 'cap-done') { state.view = 'home'; renderView(); }
});

// ------------------------------------------------------------------ ASK
function viewAsk() {
  const v = document.getElementById('view');
  const log = state.chat.map(chatBubble).join('');
  v.innerHTML = `
    <div class="chat-wrap">
      <div class="chat-log" id="chat-log">
        ${log || `<div class="chat-hello">
          <div class="big">💬</div>
          <h3>Ask about your money</h3>
          <p class="muted">Try: “How much did we spend on groceries this month?” ·
          “What was that €240 in July?” · “Compare June and July.”</p></div>`}
      </div>
      <form class="chat-inrow" id="chat-form">
        <input id="chat-in" placeholder="Ask anything…" autocomplete="off" />
        <button class="btn small" type="submit">➤</button>
      </form>
    </div>`;
  const logEl = v.querySelector('#chat-log');
  logEl.scrollTop = logEl.scrollHeight;

  v.querySelector('#chat-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = v.querySelector('#chat-in');
    const q = input.value.trim();
    if (!q) return;
    input.value = '';
    state.chat.push({ role: 'user', text: q });
    state.chat.push({ role: 'assistant', text: null }); // spinner slot
    renderChatLog();
    try {
      const history = state.chat.filter((m) => m.text).slice(0, -1);
      const answer = await store.askAssistant(q, history);
      state.chat[state.chat.length - 1] = { role: 'assistant', text: answer };
    } catch (err) {
      state.chat[state.chat.length - 1] = { role: 'assistant', text: `⚠️ ${err.message || 'Something went wrong.'}` };
    }
    renderChatLog();
  });
}

function renderChatLog() {
  const logEl = document.getElementById('chat-log');
  if (!logEl) return;
  logEl.innerHTML = state.chat.map(chatBubble).join('');
  logEl.scrollTop = logEl.scrollHeight;
}

function chatBubble(m) {
  if (m.text === null) {
    return `<div class="chat-msg assistant"><span class="spinner dark"></span></div>`;
  }
  return `<div class="chat-msg ${m.role}">${esc(m.text).replace(/\n/g, '<br>')}</div>`;
}

// ------------------------------------------------------------------ DOCUMENTS
async function viewDocuments() {
  const v = document.getElementById('view');
  v.innerHTML = `<div class="processing-note"><span class="spinner dark"></span> Loading documents…</div>`;
  let docs;
  try { docs = await store.listDocuments(state.household.id); }
  catch (e) { v.innerHTML = `<div class="error-banner">${esc(e.message)}</div>`; return; }

  if (!docs.length) {
    v.innerHTML = emptyState('No documents yet', 'Bills and statements you add will appear here.');
    return;
  }

  const rows = docs.map((d) => {
    const type = DOC_TYPES[d.doc_type] || DOC_TYPES.other;
    const r = d.receipts?.[0];
    const sub = r?.total != null
      ? `${money(r.total, r.currency || state.currency)} · ${fmtDate(r.purchased_at || d.created_at)}`
      : `${type.label} · ${fmtDate(d.created_at)}`;
    return `<div class="item" data-doc="${d.id}" style="cursor:pointer">
      <div class="ic">${type.emoji}</div>
      <div class="body"><div class="t">${esc(r?.merchant || d.original_filename || type.label)}</div>
        <div class="s">${esc(sub)}</div></div>
      <span class="pill ${d.status}">${d.status}</span>
    </div>`;
  }).join('');

  v.innerHTML = `<div class="section-title">All documents</div><div class="card"><div class="list">${rows}</div></div>`;
  v.querySelectorAll('[data-doc]').forEach((el) =>
    el.addEventListener('click', () => openDocSheet(el.dataset.doc)));
}

async function openDocSheet(docId) {
  const { doc, receipt, transactions } = await store.getDocumentDetail(docId);
  const type = DOC_TYPES[doc.doc_type] || DOC_TYPES.other;
  const pdfBtn = doc.pdf_path
    ? `<button class="btn secondary" id="sheet-pdf">📄 Open PDF</button>` : '';

  let bodyHtml = '';
  if (receipt) {
    const items = (receipt.line_items || []).sort((a, b) => (a.position || 0) - (b.position || 0));
    const itemRows = items.map((it) => `<tr>
      <td>${esc(it.description || '')}</td>
      <td class="r">${it.amount != null ? money(it.amount, receipt.currency || state.currency) : ''}</td></tr>`).join('');
    bodyHtml = `
      <div class="kv"><span class="k">Merchant</span><span>${esc(receipt.merchant || '—')}</span></div>
      <div class="kv"><span class="k">Date</span><span>${fmtDate(receipt.purchased_at)}</span></div>
      ${receipt.tax != null ? `<div class="kv"><span class="k">Tax</span><span>${money(receipt.tax, receipt.currency || state.currency)}</span></div>` : ''}
      <div class="kv"><span class="k">Total</span><span><strong>${money(receipt.total, receipt.currency || state.currency)}</strong></span></div>
      <div class="field" style="margin-top:12px"><label>Category</label>${categorySelect(txnCatId(transactions))}</div>
      ${itemRows ? `<div class="section-title" style="margin:14px 4px 6px">Items</div>
        <table class="li-table"><tbody>${itemRows}</tbody></table>` : ''}`;
  } else if (transactions.length) {
    const rows = transactions.map((t) => `<div class="item">
      <div class="ic">${esc(t.categories?.icon || '💳')}</div>
      <div class="body"><div class="t">${esc(t.merchant || t.description)}</div>
        <div class="s">${fmtDate(t.txn_date)}</div></div>
      <div class="amt ${t.direction === 'credit' ? 'credit' : ''}">${t.direction === 'credit' ? '+' : ''}${money(t.amount, t.currency || state.currency)}</div>
    </div>`).join('');
    bodyHtml = `<p class="muted">${transactions.length} transactions from this statement.</p>
      <div class="list">${rows}</div>`;
  } else {
    bodyHtml = doc.status === 'failed'
      ? `<div class="error-banner">${esc(doc.error_message || 'Analysis failed')}</div>`
      : `<p class="muted">No structured data yet.</p>`;
  }

  showSheet(`
    <h2>${type.emoji} ${esc(receipt?.merchant || type.label)}</h2>
    ${bodyHtml}
    <div class="row" style="margin-top:16px">
      ${pdfBtn}
      <button class="btn danger" id="sheet-del">Delete</button>
    </div>`);

  if (doc.pdf_path) {
    document.getElementById('sheet-pdf').addEventListener('click', async () => {
      const url = await store.signedUrl(doc.pdf_path);
      if (url) window.open(url, '_blank');
    });
  }
  document.getElementById('sheet-del').addEventListener('click', async () => {
    if (!confirm('Delete this document and its data?')) return;
    await store.deleteDocument(doc);
    closeSheet();
    toast('Deleted');
    viewDocuments();
  });
  const sel = document.getElementById('cat-select');
  if (sel) sel.addEventListener('change', async () => {
    for (const t of transactions) await store.updateTransactionCategory(t.id, sel.value);
    toast('Category updated');
  });
}

function txnCatId(transactions) { return transactions[0]?.category_id || ''; }
function categorySelect(selectedId) {
  return `<select id="cat-select">${state.categories.map((c) =>
    `<option value="${c.id}" ${c.id === selectedId ? 'selected' : ''}>${esc(c.icon)} ${esc(c.name)}</option>`).join('')}</select>`;
}

// ------------------------------------------------------------------ SETTINGS
async function viewSettings() {
  const v = document.getElementById('view');
  const [email, members, feedback] = await Promise.all([
    store.auth.email(),
    store.getMembers(state.household.id),
    store.listFeedback(state.household.id).catch(() => null), // null → table not deployed yet
  ]);
  const memberRows = members.map((m) =>
    `<div class="kv"><span class="k">${esc(m.display_name || 'Member')}</span><span>${m.role}</span></div>`).join('');
  const feedbackList = feedback === null
    ? '<p class="muted" style="margin:12px 0 0">Feedback history appears here once the latest database update is applied.</p>'
    : feedback.map(feedbackItem).join('');

  v.innerHTML = `
    <section class="card">
      <div class="section-title" style="margin:0 0 8px">Household</div>
      <div class="kv"><span class="k">Name</span><span>${esc(state.household.name)}</span></div>
      <div class="section-title" style="margin:14px 0 6px">Invite your partner</div>
      <p class="muted" style="margin:0 0 8px">Share this code — they tap “Join with code” when they sign up.</p>
      <div class="copyrow"><code id="invite">${esc(state.household.invite_code)}</code>
        <button class="btn small" id="copy">Copy</button></div>
    </section>

    <section class="card">
      <div class="section-title" style="margin:0 0 8px">Feedback & requests</div>
      <p class="muted" style="margin:0 0 12px">Spotted a bug, a wrong number, or want something new? Tell Claude —
      it works through your feedback, ships the improvements, and replies right here.</p>
      <button class="btn" id="fb-new">💬 Send feedback</button>
      <div class="fb-list">${feedbackList}</div>
    </section>

    <section class="card">
      <div class="section-title" style="margin:0 0 8px">Members</div>
      ${memberRows || '<p class="muted">Just you so far.</p>'}
    </section>

    <section class="card">
      <div class="section-title" style="margin:0 0 8px">Account</div>
      <div class="kv"><span class="k">Signed in as</span><span>${esc(email || '')}</span></div>
      <button class="btn danger" id="signout" style="margin-top:12px">Sign out</button>
    </section>

    <section class="card">
      <div class="section-title" style="margin:0 0 8px">Install on your iPhone</div>
      <p class="muted" style="margin:0">In Safari, tap the <strong>Share</strong> button, then
      <strong>“Add to Home Screen.”</strong> Hearth then opens like a normal app.</p>
    </section>`;

  v.querySelector('#copy').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(state.household.invite_code); toast('Copied ✓'); }
    catch { toast(state.household.invite_code); }
  });
  v.querySelector('#signout').addEventListener('click', () => store.auth.signOut());
  v.querySelector('#fb-new').addEventListener('click', () => openFeedbackSheet());
  v.querySelectorAll('[data-fb-reply]').forEach((b) => b.addEventListener('click', () => {
    const original = feedback?.find((f) => f.id === b.dataset.fbReply);
    const quote = original ? original.message.slice(0, 80).replace(/\s+/g, ' ') : '';
    openFeedbackSheet('other', quote ? `Re: “${quote}${original.message.length > 80 ? '…' : ''}” — ` : '');
  }));
}

// ------------------------------------------------------------------ FEEDBACK
const FEEDBACK_KINDS = {
  bug: { emoji: '🐞', label: 'Bug', hint: 'What happened, and what did you expect instead?' },
  idea: { emoji: '💡', label: 'Idea', hint: 'What would make Hearth more useful for you?' },
  data: { emoji: '🔢', label: 'Wrong data', hint: 'Which number, transaction or category looks wrong — and what should it be?' },
  other: { emoji: '💬', label: 'Other', hint: 'Anything on your mind about Hearth.' },
};

const FEEDBACK_STATUS = {
  new: 'Received',
  in_progress: 'Working on it',
  needs_info: 'Question for you',
  shipped: 'Done ✓',
  declined: 'Not planned',
};

// Where the sender was when they wrote it — enough for Claude to reproduce, no financial data.
function feedbackContext() {
  return {
    view: state.view,
    month: iso(state.month).slice(0, 7),
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    installed: window.matchMedia?.('(display-mode: standalone)').matches || navigator.standalone === true,
    user_agent: navigator.userAgent,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  };
}

function openFeedbackSheet(kind = 'bug', prefill = '') {
  closeSheet();
  let current = kind;
  showSheet(`
    <h2>💬 Feedback for Hearth</h2>
    <p class="muted" style="margin:0 0 12px">Goes to Claude, who works through it, ships improvements,
    and replies under <strong>Settings → Feedback</strong>.</p>
    <div class="type-choice four" id="fb-kinds">
      ${Object.entries(FEEDBACK_KINDS).map(([k, v]) => `<button type="button" data-kind="${k}" class="${k === kind ? 'active' : ''}">
        <span class="e">${v.emoji}</span>${v.label}</button>`).join('')}
    </div>
    <form id="fb-form">
      <div class="field"><textarea id="fb-msg" rows="5" maxlength="4000" required
        placeholder="${esc(FEEDBACK_KINDS[kind].hint)}"></textarea></div>
      <p class="muted fb-note">Includes which screen and month you were on and your device type.
      Your transactions aren't attached — mention specifics (date, shop, amount) if they matter.</p>
      <div id="fb-err"></div>
      <button class="btn" type="submit">Send feedback</button>
    </form>`);

  const msg = document.getElementById('fb-msg');
  msg.value = prefill;
  msg.focus();
  document.querySelectorAll('#fb-kinds button').forEach((b) => b.addEventListener('click', () => {
    current = b.dataset.kind;
    document.querySelectorAll('#fb-kinds button').forEach((x) => x.classList.toggle('active', x === b));
    msg.placeholder = FEEDBACK_KINDS[current].hint;
  }));

  document.getElementById('fb-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = msg.value.trim();
    const errBox = document.getElementById('fb-err');
    errBox.innerHTML = '';
    if (text.length < 3) {
      errBox.innerHTML = '<div class="error-banner">Add a few words so Claude knows what you mean.</div>';
      return;
    }
    const btn = e.target.querySelector('button[type=submit]');
    btn.disabled = true; btn.textContent = 'Sending…';
    try {
      await store.sendFeedback({
        householdId: state.household.id,
        authorName: state.membership?.display_name,
        kind: current,
        message: text,
        context: feedbackContext(),
      });
      closeSheet();
      toast('Sent to Claude ✓');
      if (state.view === 'settings') viewSettings();
    } catch (err) {
      errBox.innerHTML = `<div class="error-banner">${esc(err.message || 'Could not send feedback')}</div>`;
      btn.disabled = false; btn.textContent = 'Send feedback';
    }
  });
}

function feedbackItem(f) {
  const k = FEEDBACK_KINDS[f.kind] || FEEDBACK_KINDS.other;
  return `<div class="fb-item">
    <div class="fb-head">
      <span>${k.emoji} <strong>${esc(k.label)}</strong> · ${fmtDate(new Date(f.created_at))}${f.author_name ? ` · ${esc(f.author_name)}` : ''}</span>
      <span class="pill fb-${esc(f.status)}">${esc(FEEDBACK_STATUS[f.status] || f.status)}</span>
    </div>
    <div class="fb-msg">${esc(f.message)}</div>
    ${f.resolution_note ? `<div class="fb-reply"><span class="who">Claude</span>${esc(f.resolution_note).replace(/\n/g, '<br>')}</div>` : ''}
    ${f.status === 'needs_info' ? `<button class="btn small secondary" data-fb-reply="${f.id}">Reply</button>` : ''}
  </div>`;
}

// ------------------------------------------------------------------ sheet
function showSheet(inner) {
  const back = document.createElement('div');
  back.className = 'sheet-backdrop';
  back.id = 'sheet-backdrop';
  back.innerHTML = `<div class="sheet"><div class="grab"></div>${inner}</div>`;
  back.addEventListener('click', (e) => { if (e.target === back) closeSheet(); });
  document.body.appendChild(back);
}
function closeSheet() { document.getElementById('sheet-backdrop')?.remove(); }

// ------------------------------------------------------------------ tiny utils
function sum(arr) { return arr.reduce((s, x) => s + Number(x || 0), 0); }
function groupBy(arr, keyFn) {
  const m = new Map();
  for (const x of arr) {
    const k = keyFn(x);
    m.set(k, (m.get(k) || 0) + Number(x.amount || 0));
  }
  return [...m.entries()].map(([key, value]) => ({ key, value }));
}
function groupByCategory(debits) {
  const m = new Map();
  for (const t of debits) {
    const cat = t.categories || {};
    const id = t.category_id || 'none';
    const cur = m.get(id) || { id, value: 0, name: cat.name || 'Uncategorized', icon: cat.icon || '📦', color: cat.color || '#64748b' };
    cur.value += Number(t.amount || 0);
    m.set(id, cur);
  }
  return [...m.values()].sort((a, b) => b.value - a.value);
}
function emptyState(title, sub) {
  return `<div class="empty"><div class="big">🧾</div><h3 style="margin:8px 0 4px">${esc(title)}</h3>
    <p class="muted">${esc(sub)}</p></div>`;
}
