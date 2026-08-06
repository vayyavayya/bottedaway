/* Docbox front-end. Vanilla JS, no build step — edit and reload. */

const state = {
  user: null,
  folders: [],
  folder: '',        // '' = everything
  filter: 'all',     // all | review | pending
  query: '',
  docs: [],
  poll: null,
};

const el = (id) => document.getElementById(id);

const TYPE_ICONS = {
  pdf: '📄', jpg: '🖼️', jpeg: '🖼️', png: '🖼️', heic: '🖼️', webp: '🖼️',
  txt: '📝', md: '📝', docx: '📃', doc: '📃', xlsx: '📊', zip: '🗜️',
};

/* ------------------------------------------------------------------ util */

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function toast(message, ms = 2400) {
  const node = el('toast');
  node.textContent = message;
  node.classList.remove('hidden');
  clearTimeout(node._timer);
  node._timer = setTimeout(() => node.classList.add('hidden'), ms);
}

function busy(on) {
  el('progress').classList.toggle('hidden', !on);
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: 'same-origin', ...options });
  if (response.status === 401) {
    showAuth();
    throw new Error('not signed in');
  }
  const isJson = (response.headers.get('content-type') || '').includes('json');
  const body = isJson ? await response.json() : await response.text();
  if (!response.ok) throw new Error((body && body.detail) || response.statusText);
  return body;
}

const postJson = (path, data) => api(path, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(data),
});

function prettyDate(seconds) {
  if (!seconds) return '';
  const date = new Date(seconds * 1000);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  return sameDay
    ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString([], { day: '2-digit', month: 'short', year: '2-digit' });
}

function fileSize(bytes) {
  if (!bytes) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value.toFixed(value < 10 && unit > 0 ? 1 : 0)} ${units[unit]}`;
}

/* ------------------------------------------------------------------ auth */

function showAuth(needsSetup = false) {
  el('app').classList.add('hidden');
  el('auth').classList.remove('hidden');
  el('auth-sub').textContent = needsSetup
    ? 'First run — choose your account'
    : 'Shared document library';
  el('auth-submit').textContent = needsSetup ? 'Create account' : 'Sign in';
  el('auth-form').dataset.mode = needsSetup ? 'setup' : 'login';
  if (state.poll) { clearInterval(state.poll); state.poll = null; }
}

function showApp() {
  el('auth').classList.add('hidden');
  el('app').classList.remove('hidden');
}

el('auth-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  el('auth-error').textContent = '';
  const mode = event.target.dataset.mode === 'setup' ? '/api/setup' : '/api/login';
  const payload = { username: el('auth-user').value, password: el('auth-pass').value };
  try {
    busy(true);
    const result = await postJson(mode, payload);
    state.user = result.user;
    el('auth-pass').value = '';
    showApp();
    await refreshAll();
  } catch (error) {
    el('auth-error').textContent = error.message;
  } finally {
    busy(false);
  }
});

/* --------------------------------------------------------------- folders */

function renderFolders() {
  const nav = el('folders');
  const chips = [`<button class="chip ${state.folder === '' ? 'active' : ''}" data-folder="">All folders</button>`];
  for (const folder of state.folders) {
    const active = state.folder === folder.name ? 'active' : '';
    chips.push(
      `<button class="chip ${active}" data-folder="${esc(folder.name)}">` +
      `${folder.inbox ? '📥 ' : ''}${esc(folder.name)}<span class="count">${folder.count}</span></button>`
    );
  }
  nav.innerHTML = chips.join('');
  nav.querySelectorAll('[data-folder]').forEach((btn) => {
    btn.onclick = () => { state.folder = btn.dataset.folder; renderFolders(); loadDocs(); };
  });
}

document.querySelectorAll('.filters .chip').forEach((btn) => {
  btn.onclick = () => {
    state.filter = btn.dataset.filter;
    document.querySelectorAll('.filters .chip').forEach((b) => b.classList.remove('active'));
    btn.classList.add('active');
    loadDocs();
  };
});

/* ------------------------------------------------------------------ list */

function statusBadge(doc) {
  if (doc.status === 'pending') return '<span class="badge working">queued</span>';
  if (doc.status === 'processing') return '<span class="badge working">reading…</span>';
  if (doc.status === 'failed') return '<span class="badge failed">failed</span>';
  if (doc.needs_review) return '<span class="badge review">check name</span>';
  return '';
}

function renderList() {
  const list = el('list');
  if (!state.docs.length) {
    list.innerHTML = `<div class="empty">Nothing here yet.<br>Scan or upload something.</div>`;
    return;
  }
  list.innerHTML = state.docs.map((doc) => {
    const icon = TYPE_ICONS[(doc.ext || '').replace('.', '')] || '📄';
    const meta = [
      doc.correspondent,
      doc.doc_type,
      state.folder ? '' : doc.folder,
      fileSize(doc.size),
      prettyDate(doc.created_at),
    ].filter(Boolean).join(' · ');
    return `
      <article class="card ${doc.needs_review ? 'review' : ''}" data-id="${doc.id}">
        <div class="thumb">${icon}</div>
        <div class="grow">
          <p class="name">${esc(doc.filename)}</p>
          <div class="meta">${esc(meta)}</div>
          <div class="badges">${statusBadge(doc)}</div>
        </div>
      </article>`;
  }).join('');
  list.querySelectorAll('.card').forEach((card) => {
    card.onclick = () => openDoc(Number(card.dataset.id));
  });
}

async function loadDocs() {
  const params = new URLSearchParams();
  if (state.folder) params.set('folder', state.folder);
  if (state.query) params.set('q', state.query);
  if (state.filter === 'review') params.set('review', 'true');
  if (state.filter === 'pending') params.set('status', 'pending');
  const data = await api(`/api/documents?${params}`);
  state.docs = data.documents;
  renderList();
  schedulePoll();
}

function schedulePoll() {
  const working = state.docs.some((d) => d.status === 'pending' || d.status === 'processing');
  if (working && !state.poll) {
    state.poll = setInterval(async () => {
      try { await loadDocs(); await loadFolders(); } catch { /* offline; try again */ }
    }, 3000);
  } else if (!working && state.poll) {
    clearInterval(state.poll);
    state.poll = null;
  }
}

async function loadFolders() {
  const data = await api('/api/folders');
  state.folders = data.folders;
  renderFolders();
}

async function refreshAll() {
  busy(true);
  try {
    await loadFolders();
    await loadDocs();
  } finally {
    busy(false);
  }
}

/* ----------------------------------------------------------------- sheet */

function openSheet(html) {
  el('sheet-content').innerHTML = html;
  el('sheet').classList.remove('hidden');
}

function closeSheet() {
  el('sheet').classList.add('hidden');
  el('sheet-content').innerHTML = '';
}

el('sheet').addEventListener('click', (event) => {
  if (event.target.dataset.close !== undefined) closeSheet();
});

function previewHtml(doc) {
  const src = `/api/documents/${doc.id}/file`;
  if ((doc.mime || '').startsWith('image/')) {
    return `<div class="preview"><img src="${src}" alt="${esc(doc.filename)}"></div>`;
  }
  if (doc.ext === '.pdf') {
    return `<div class="preview"><iframe src="${src}#view=FitH" title="preview"></iframe></div>`;
  }
  return '';
}

async function openDoc(id) {
  busy(true);
  let doc;
  try {
    doc = (await api(`/api/documents/${id}`)).document;
  } catch (error) {
    toast(error.message);
    return;
  } finally {
    busy(false);
  }

  const folderOptions = state.folders
    .map((f) => `<option value="${esc(f.name)}" ${f.name === doc.folder ? 'selected' : ''}>${esc(f.name)}</option>`)
    .join('');

  openSheet(`
    <h2>${esc(doc.filename)}</h2>
    <p class="muted">${esc(doc.summary || doc.original_name)}</p>
    ${previewHtml(doc)}

    <div class="field">
      <label for="f-name">File name</label>
      <input id="f-name" type="text" value="${esc(doc.filename)}">
    </div>
    <div class="field">
      <label for="f-folder">Folder</label>
      <select id="f-folder">${folderOptions}</select>
    </div>

    <div class="rowbtns">
      <button class="primary" id="f-save">Save</button>
      <button class="ghost" id="f-reprocess">Rename with AI</button>
      <a class="ghost" href="/api/documents/${doc.id}/file?download=true" download>Download</a>
      <button class="ghost danger" id="f-delete">Delete</button>
    </div>

    <div style="margin-top:18px">
      <div class="kv"><span>Original</span><span>${esc(doc.original_name)}</span></div>
      <div class="kv"><span>Sender</span><span>${esc(doc.correspondent || '—')}</span></div>
      <div class="kv"><span>Type</span><span>${esc(doc.doc_type || '—')}</span></div>
      <div class="kv"><span>Doc date</span><span>${esc(doc.doc_date || '—')}</span></div>
      <div class="kv"><span>Confidence</span><span>${doc.confidence ? Math.round(doc.confidence * 100) + '%' : '—'}</span></div>
      <div class="kv"><span>Added by</span><span>${esc(doc.uploaded_by)} · ${prettyDate(doc.created_at)}</span></div>
      <div class="kv"><span>Status</span><span>${esc(doc.status)}${doc.error ? ' · ' + esc(doc.error) : ''}</span></div>
    </div>

    ${doc.text_excerpt ? `<p class="muted" style="margin-top:14px">Text the model read</p>
      <pre class="excerpt">${esc(doc.text_excerpt.slice(0, 1500))}</pre>` : ''}
  `);

  el('f-save').onclick = async () => {
    try {
      busy(true);
      await api(`/api/documents/${doc.id}`, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ filename: el('f-name').value, folder: el('f-folder').value }),
      });
      closeSheet();
      toast('Saved');
      await refreshAll();
    } catch (error) {
      toast(error.message);
    } finally {
      busy(false);
    }
  };

  el('f-reprocess').onclick = async () => {
    try {
      await postJson(`/api/documents/${doc.id}/reprocess`, {});
      closeSheet();
      toast('Reading it again…');
      await loadDocs();
    } catch (error) {
      toast(error.message);
    }
  };

  el('f-delete').onclick = async () => {
    if (!confirm(`Delete ${doc.filename}? It moves to .trash in the library.`)) return;
    try {
      await api(`/api/documents/${doc.id}`, { method: 'DELETE' });
      closeSheet();
      toast('Deleted');
      await refreshAll();
    } catch (error) {
      toast(error.message);
    }
  };
}

/* ---------------------------------------------------------------- upload */

async function sendFiles(files, { combine = false } = {}) {
  if (!files.length) return;
  const form = new FormData();
  for (const file of files) form.append('files', file, file.name || 'scan.jpg');
  if (state.folder) form.append('folder', state.folder);
  if (combine) form.append('combine', 'true');

  busy(true);
  toast(combine ? `Making a PDF from ${files.length} page(s)…` : `Uploading ${files.length} file(s)…`);
  try {
    const result = await api('/api/upload', { method: 'POST', body: form });
    const results = result.results || [result];
    const dupes = results.filter((r) => r.duplicate).length;
    toast(dupes ? `Added ${results.length - dupes}, ${dupes} already in the library` : 'Added — reading it now');
    await refreshAll();
  } catch (error) {
    toast(`Upload failed: ${error.message}`);
  } finally {
    busy(false);
  }
}

el('input-files').onchange = (event) => {
  sendFiles([...event.target.files]);
  event.target.value = '';
};

el('input-scan').onchange = (event) => {
  const files = [...event.target.files];
  // More than one photo means a multi-page document: staple it into one PDF.
  sendFiles(files, { combine: files.length > 1 });
  event.target.value = '';
};

el('btn-newfolder').onclick = async () => {
  const name = prompt('New folder name');
  if (!name) return;
  try {
    await postJson('/api/folders', { name });
    await loadFolders();
    toast('Folder created');
  } catch (error) {
    toast(error.message);
  }
};

el('btn-refresh').onclick = () => refreshAll();

let searchTimer;
el('search').oninput = (event) => {
  clearTimeout(searchTimer);
  const value = event.target.value;
  searchTimer = setTimeout(() => { state.query = value; loadDocs(); }, 250);
};

/* -------------------------------------------------------------- settings */

el('btn-settings').onclick = async () => {
  busy(true);
  let info = {};
  let health = {};
  try {
    info = await api('/api/me');
    health = await api('/api/health');
  } catch (error) {
    toast(error.message);
    return;
  } finally {
    busy(false);
  }

  const llm = health.llm || {};
  const shortcutUrl = `${location.origin}/api/upload`;
  openSheet(`
    <h2>Settings</h2>
    <p class="muted">Signed in as ${esc(info.user.username)}</p>

    <div style="margin-top:14px">
      <div class="kv"><span>Library</span><span>${esc(health.library || '')}</span></div>
      <div class="kv"><span>Worker</span><span>${health.worker_running ? 'running' : 'stopped'}</span></div>
      <div class="kv"><span>Model</span><span>${esc(llm.model || '')} ${llm.reachable ? '· ready' : '· offline'}</span></div>
      <div class="kv"><span>OCR</span><span>${health.extraction && health.extraction.tesseract ? 'tesseract ready' : 'not installed'}</span></div>
    </div>

    <p class="muted" style="margin-top:18px">iOS Share Sheet token</p>
    <code class="token" id="tok">${esc(info.api_token)}</code>
    <div class="rowbtns">
      <button class="ghost" id="copy-token">Copy token</button>
      <button class="ghost" id="copy-url">Copy upload URL</button>
      <button class="ghost" id="rotate-token">New token</button>
      <button class="ghost danger" id="logout">Sign out</button>
    </div>
    <p class="muted" style="margin-top:12px">
      Endpoint: <code>${esc(shortcutUrl)}</code><br>
      Build the Shortcut once per phone — see SHORTCUT.md in the repo.
    </p>
  `);

  const copy = async (text, label) => {
    try {
      await navigator.clipboard.writeText(text);
      toast(`${label} copied`);
    } catch {
      toast('Copy failed — long-press to select');
    }
  };
  el('copy-token').onclick = () => copy(el('tok').textContent, 'Token');
  el('copy-url').onclick = () => copy(shortcutUrl, 'URL');
  el('rotate-token').onclick = async () => {
    if (!confirm('Old Shortcuts will stop working. Continue?')) return;
    const result = await postJson('/api/me/token', {});
    el('tok').textContent = result.api_token;
    toast('New token — update your Shortcut');
  };
  el('logout').onclick = async () => {
    await postJson('/api/logout', {});
    closeSheet();
    state.user = null;
    showAuth();
  };
};

/* ------------------------------------------------------------------ boot */

async function boot() {
  document.querySelector('.filters .chip[data-filter="all"]').classList.add('active');
  try {
    const health = await api('/api/health');
    if (health.needs_setup) { showAuth(true); return; }
    const me = await api('/api/me');
    state.user = me.user;
    showApp();
    await refreshAll();
  } catch {
    showAuth(false);
  }
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
}

document.addEventListener('visibilitychange', () => {
  if (!document.hidden && state.user) refreshAll().catch(() => {});
});

boot();
