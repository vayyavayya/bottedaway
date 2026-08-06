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
    // Nested folders show as `Invoices` with a faint `Finance ›` in front, so a
    // deep tree still fits on a phone.
    const parts = folder.name.split('/');
    const leaf = parts.pop();
    const trail = parts.length ? `<span class="count">${esc(parts.join(' › '))} ›</span> ` : '';
    const count = folder.total ?? folder.count;
    chips.push(
      `<button class="chip ${active}" data-folder="${esc(folder.name)}" title="${esc(folder.name)}">` +
      `${folder.inbox ? '📥 ' : ''}${trail}${esc(leaf)}<span class="count">${count}</span></button>`
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
  openScanner([...event.target.files]);
  event.target.value = '';
};

/* --------------------------------------------------------------- scanner */

const scan = { pages: [], index: 0, mode: 'auto', busy: false, backfilling: false };

/** Shrink a photo before previewing it — a 4000px capture makes the round trip
 *  slow, and the preview only has to look right on a phone screen. */
function previewCopy(file, maxEdge = 1100) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scaleBy = Math.min(1, maxEdge / Math.max(img.width, img.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(img.width * scaleBy);
      canvas.height = Math.round(img.height * scaleBy);
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      canvas.toBlob((blob) => resolve(blob || file), 'image/jpeg', 0.85);
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file); };
    img.src = url;
  });
}

async function openScanner(files) {
  if (!files.length) return;
  scan.pages = [];
  scan.index = 0;
  scan.mode = 'auto';
  el('scanner').classList.remove('hidden');
  el('scan-name').value = '';
  el('scan-folder').innerHTML = state.folders
    .map((f) => `<option value="${esc(f.name)}">${esc(f.name)}</option>`).join('');
  await addScanPages(files);
}

async function addScanPages(files) {
  for (const file of files) {
    scan.pages.push({ file, small: await previewCopy(file), preview: null, mode: null });
  }
  renderScanPages();
  await showScanPage(scan.pages.length - files.length);
}

function renderScanPages() {
  el('scan-count').textContent = `${scan.pages.length} page${scan.pages.length === 1 ? '' : 's'}`;
  el('scan-pages').innerHTML = scan.pages.map((page, i) => `
    <button class="scan-thumb ${i === scan.index ? 'active' : ''}" data-page="${i}">
      ${page.preview ? `<img src="${page.preview}" alt="">` : ''}
      <span>${i + 1}</span>
    </button>`).join('');
  el('scan-pages').querySelectorAll('[data-page]').forEach((node) => {
    node.onclick = () => showScanPage(Number(node.dataset.page));
  });
  el('scan-save').disabled = !scan.pages.length;
}

/** Enhance one page server-side and cache the result on the page object. */
async function renderPage(page) {
  const form = new FormData();
  form.append('file', page.small, 'page.jpg');
  form.append('mode', scan.mode);
  const response = await fetch('/api/enhance/preview', {
    method: 'POST', body: form, credentials: 'same-origin',
  });
  if (!response.ok) throw new Error(await response.text());
  const report = JSON.parse(response.headers.get('X-Scan-Report') || '{}');
  if (page.preview) URL.revokeObjectURL(page.preview);
  page.preview = URL.createObjectURL(await response.blob());
  page.mode = scan.mode;
  return report;
}

async function showScanPage(index) {
  if (!scan.pages.length) { closeScanner(); return; }
  scan.index = Math.max(0, Math.min(index, scan.pages.length - 1));
  const page = scan.pages[scan.index];
  renderScanPages();

  if (page.preview && page.mode === scan.mode) {
    el('scan-preview').src = page.preview;
    backfillPreviews();
    return;
  }
  el('scan-spinner').classList.remove('hidden');
  try {
    const report = await renderPage(page);
    el('scan-preview').src = page.preview;
    el('scan-note').textContent = [
      report.cropped ? 'edges found' : 'no edges found — full frame kept',
      report.applied ? `filter: ${report.applied}` : '',
      ...(report.warnings || []),
    ].filter(Boolean).join(' · ');
    renderScanPages();
  } catch (error) {
    el('scan-note').textContent = `preview failed: ${error.message}`;
    el('scan-preview').src = URL.createObjectURL(page.small);
  } finally {
    el('scan-spinner').classList.add('hidden');
  }
  backfillPreviews();
}

/** Fill in the other thumbnails one at a time, so the strip isn't a row of
 *  blanks while you look at page 1. Serial on purpose: the enhancement is CPU
 *  work on the server and the visible page must not queue behind five others. */
async function backfillPreviews() {
  if (scan.backfilling) return;
  scan.backfilling = true;
  try {
    for (const page of scan.pages) {
      if (page.mode === scan.mode) continue;
      const mode = scan.mode;
      try {
        await renderPage(page);
      } catch {
        break;      // offline or server busy: leave the rest blank, no spam
      }
      if (mode !== scan.mode) break;   // the user switched filters; start over
      renderScanPages();
    }
  } finally {
    scan.backfilling = false;
  }
}

el('scan-modes').querySelectorAll('[data-mode]').forEach((btn) => {
  btn.onclick = () => {
    scan.mode = btn.dataset.mode;
    el('scan-modes').querySelectorAll('.chip').forEach((c) => c.classList.remove('active'));
    btn.classList.add('active');
    scan.pages.forEach((p) => { p.mode = null; });   // every page re-renders lazily
    showScanPage(scan.index);
  };
});

el('scan-prev').onclick = () => showScanPage(scan.index - 1);
el('scan-next').onclick = () => showScanPage(scan.index + 1);

el('scan-delete').onclick = () => {
  const [removed] = scan.pages.splice(scan.index, 1);
  if (removed?.preview) URL.revokeObjectURL(removed.preview);
  if (!scan.pages.length) { closeScanner(); return; }
  showScanPage(Math.min(scan.index, scan.pages.length - 1));
};

function movePage(delta) {
  const target = scan.index + delta;
  if (target < 0 || target >= scan.pages.length) return;
  const [page] = scan.pages.splice(scan.index, 1);
  scan.pages.splice(target, 0, page);
  showScanPage(target);
}
el('scan-rotate-left').onclick = () => movePage(-1);
el('scan-rotate-right').onclick = () => movePage(1);

el('scan-more').onchange = (event) => {
  addScanPages([...event.target.files]);
  event.target.value = '';
};

el('scan-cancel').onclick = () => closeScanner();

function closeScanner() {
  scan.pages.forEach((p) => p.preview && URL.revokeObjectURL(p.preview));
  scan.pages = [];
  el('scanner').classList.add('hidden');
  el('scan-preview').removeAttribute('src');
  el('scan-note').textContent = '';
}

el('scan-save').onclick = async () => {
  if (!scan.pages.length || scan.busy) return;
  scan.busy = true;
  el('scan-save').disabled = true;
  const form = new FormData();
  // The originals go to the server: the previews were downscaled for speed.
  scan.pages.forEach((page, i) => form.append('files', page.file, `page-${i + 1}.jpg`));
  form.append('mode', scan.mode);
  form.append('folder', el('scan-folder').value || '');
  form.append('name', el('scan-name').value || '');

  busy(true);
  toast(`Building a ${scan.pages.length}-page PDF…`);
  try {
    const result = await api('/api/scan', { method: 'POST', body: form });
    const pdf = result.scan?.pdf || {};
    closeScanner();
    toast(pdf.searchable ? 'Saved — searchable PDF' : 'Saved');
    await refreshAll();
  } catch (error) {
    toast(`Could not save: ${error.message}`);
    el('scan-save').disabled = false;
  } finally {
    scan.busy = false;
    busy(false);
  }
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
      <div class="kv"><span>Model</span><span>${esc(llm.provider || '')} · ${esc(llm.model || '')} ${llm.reachable ? '· ready' : (llm.has_key ? '· unreachable' : '· no API key')}</span></div>
      <div class="kv"><span>Where</span><span>${llm.local ? 'on your machine' : 'hosted — document text is sent to the provider'}</span></div>
      <div class="kv"><span>OCR</span><span>${health.extraction && health.extraction.tesseract ? 'tesseract ready' : 'not installed'}</span></div>
      <div class="kv"><span>Scanning</span><span>${(health.scanning || {}).opencv ? 'full pipeline' : 'basic (no OpenCV)'} · ${(health.scanning || {}).tesseract_pdf ? 'searchable PDFs' : 'image PDFs'}</span></div>
      <div class="kv"><span>Auto-filing</span><span>${health.auto_file ? 'on' : 'off'}</span></div>
    </div>

    <p class="muted" style="margin-top:18px">Google Drive</p>
    <div class="kv"><span>Folder</span><span>${esc(String((health.gdrive || {}).folder || '—'))}</span></div>
    <div class="kv"><span>Watcher</span><span>${(health.gdrive || {}).watcher_running ? 'checking every ' + (health.gdrive || {}).poll_minutes + ' min' : 'off'}</span></div>
    <div class="kv"><span>Last sync</span><span>${(health.gdrive || {}).last_sync ? prettyDate((health.gdrive || {}).last_sync) : 'never'}</span></div>
    <div class="rowbtns">
      <button class="ghost" id="drive-sync">Check Drive now</button>
      <button class="ghost" id="drive-full">Re-scan everything</button>
    </div>

    <p class="muted" style="margin-top:18px">Bring in an old library</p>
    <label class="action wide">
      <input type="file" id="import-zip" accept=".zip,application/zip" hidden>
      <span>Upload a zipped export (CamScanner, Files, Drive)</span>
    </label>
    <div class="field">
      <label for="import-path">…or a folder already on the server</label>
      <input id="import-path" type="text" placeholder="/Users/you/iCloud Drive/CamScanner"
             autocapitalize="none" autocorrect="off">
    </div>
    <div class="rowbtns">
      <button class="ghost" id="import-go">Import folder</button>
      <button class="ghost" id="organize-dry">Preview filing</button>
      <button class="ghost" id="organize-go">File everything</button>
    </div>
    <p class="muted" id="import-status" style="white-space:pre-wrap"></p>

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
  const status = (text) => { el('import-status').textContent = text; };

  const driveSync = async (full) => {
    busy(true);
    status(full ? 'Re-reading the whole Drive folder…' : 'Checking Google Drive…');
    try {
      const result = await postJson(`/api/gdrive/sync?full=${full}`, {});
      status(`Drive: looked at ${result.scanned}, imported ${result.imported}, `
             + `${result.duplicates} already here, ${result.skipped} skipped, `
             + `${result.failed} failed.`);
      await refreshAll();
    } catch (error) {
      status(`Drive sync failed: ${error.message}`);
    } finally {
      busy(false);
    }
  };
  el('drive-sync').onclick = () => driveSync(false);
  el('drive-full').onclick = () => driveSync(true);

  el('import-zip').onchange = async (event) => {
    const file = event.target.files[0];
    event.target.value = '';
    if (!file) return;
    const form = new FormData();
    form.append('file', file, file.name);
    busy(true);
    status(`Uploading ${file.name}… this can take a while for a big export.`);
    try {
      const result = await api('/api/import/zip', { method: 'POST', body: form });
      status(`Imported ${result.imported}, ${result.duplicates} already here, `
             + `${result.unsupported} skipped, ${result.failed} failed. `
             + `The model is reading them now.`);
      await refreshAll();
    } catch (error) {
      status(`Import failed: ${error.message}`);
    } finally {
      busy(false);
    }
  };

  el('import-go').onclick = async () => {
    const path = el('import-path').value.trim();
    if (!path) { status('Give the folder path on the machine running Docbox.'); return; }
    busy(true);
    status('Walking the folder…');
    try {
      const result = await postJson('/api/import/folder', { path });
      status(`Imported ${result.imported}, ${result.duplicates} already here, `
             + `${result.unsupported} skipped, ${result.failed} failed.`);
      await refreshAll();
    } catch (error) {
      status(`Import failed: ${error.message}`);
    } finally {
      busy(false);
    }
  };

  const organize = async (apply) => {
    busy(true);
    try {
      const result = await postJson('/api/organize', { apply });
      if (!result.would_move) { status('Nothing to move — everything is already filed.'); return; }
      if (apply) {
        status(`Filed ${result.moved} document(s).`);
        await refreshAll();
      } else {
        const sample = result.moves.slice(0, 8)
          .map((m) => `${m.filename} → ${m.to}`).join('\n');
        status(`${result.would_move} would move:\n${sample}`
               + (result.would_move > 8 ? `\n…and ${result.would_move - 8} more` : ''));
      }
    } catch (error) {
      status(error.message);
    } finally {
      busy(false);
    }
  };
  el('organize-dry').onclick = () => organize(false);
  el('organize-go').onclick = () => organize(true);

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
