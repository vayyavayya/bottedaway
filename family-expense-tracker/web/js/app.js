import { supabase, CONFIG_OK, DEFAULT_CURRENCY } from './supabaseClient.js';
import * as store from './store.js';
import { money, fmtDate, monthLabel, esc, donutSVG, toast, DOC_TYPES } from './ui.js';

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

  const from = iso(startOfMonth(state.month));
  const to = iso(endOfMonth(state.month));
  const prev = startOfMonth(new Date(state.month.getFullYear(), state.month.getMonth() - 1, 1));

  let txns, prevTxns;
  try {
    [txns, prevTxns] = await Promise.all([
      store.getTransactions(state.household.id, from, to),
      store.getTransactions(state.household.id, iso(startOfMonth(prev)), iso(endOfMonth(prev))),
    ]);
  } catch (e) { v.innerHTML = `<div class="error-banner">${esc(e.message)}</div>`; return; }

  if (txns.length) state.currency = txns[0].currency || state.currency;

  const debits = txns.filter((t) => t.direction === 'debit');
  const credits = txns.filter((t) => t.direction === 'credit');
  const totalSpent = sum(debits.map((t) => t.amount));
  const totalIn = sum(credits.map((t) => t.amount));
  const prevSpent = sum(prevTxns.filter((t) => t.direction === 'debit').map((t) => t.amount));

  const byCat = groupByCategory(debits);
  const legend = byCat.map((g) => `
    <div class="leg"><span class="dot" style="background:${g.color}"></span>
      <span>${esc(g.icon)} ${esc(g.name)}</span>
      <span class="pct">${totalSpent ? Math.round((g.value / totalSpent) * 100) : 0}%</span>
      <span class="amt">${money(g.value, state.currency)}</span></div>`).join('');

  const bars = byCat.slice(0, 6).map((g) => {
    const pct = totalSpent ? (g.value / totalSpent) * 100 : 0;
    return `<div class="bar-row"><span class="ic">${esc(g.icon)}</span>
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
      <div class="stat"><div class="label">Spent</div><div class="value spend">${money(totalSpent, state.currency)}</div></div>
      <div class="stat"><div class="label">Money in</div><div class="value credit">${money(totalIn, state.currency)}</div></div>
    </section>

    ${txns.length === 0 ? emptyState('No activity yet this month', 'Tap ＋ to snap a grocery bill or upload a statement.') : `
    <section class="card">
      <div class="section-title" style="margin:0 0 12px">Where it went</div>
      <div class="donut-wrap">
        ${donutSVG(byCat.map((g) => ({ value: g.value, color: g.color })))}
        <div class="legend">${legend || '<span class="muted">No spending recorded.</span>'}</div>
      </div>
    </section>

    ${bars ? `<section class="card"><div class="section-title" style="margin:0 0 6px">Top categories</div>${bars}</section>` : ''}

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
  const email = await store.auth.email();
  const members = await store.getMembers(state.household.id);
  const memberRows = members.map((m) =>
    `<div class="kv"><span class="k">${esc(m.display_name || 'Member')}</span><span>${m.role}</span></div>`).join('');

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
    const cur = m.get(id) || { value: 0, name: cat.name || 'Uncategorized', icon: cat.icon || '📦', color: cat.color || '#64748b' };
    cur.value += Number(t.amount || 0);
    m.set(id, cur);
  }
  return [...m.values()].sort((a, b) => b.value - a.value);
}
function emptyState(title, sub) {
  return `<div class="empty"><div class="big">🧾</div><h3 style="margin:8px 0 4px">${esc(title)}</h3>
    <p class="muted">${esc(sub)}</p></div>`;
}
