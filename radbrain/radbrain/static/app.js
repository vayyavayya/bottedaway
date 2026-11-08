"use strict";
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const COL = {B1: "var(--b1)", B2: "var(--b2)", B3: "var(--b3)"};
const get = (u) => fetch(u).then((r) => r.json());
const post = (u, b) => fetch(u, {method: "POST", headers: {"Content-Type": "application/json", "X-RadBrain": "1"}, body: JSON.stringify(b || {})}).then((r) => r.json());
const pct = (x) => (x == null ? "–" : Math.round(x * 100) + " %");

document.querySelectorAll("nav button").forEach((b) => b.onclick = () => {
  document.querySelectorAll("nav button").forEach((x) => x.classList.toggle("on", x === b));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.id === b.dataset.tab));
  ({overview: loadOverview, entities: loadEntities, rate: loadRate, rules: loadRules, quarantine: loadQuarantine, signers: loadSigners}[b.dataset.tab] || (() => {}))();
});

function bar(v, max, color, label) {
  const w = Math.min(100, (100 * v) / Math.max(1, max));
  return `<div class="bar"><i style="width:${w}%;background:${color}"></i><span>${label}</span></div>`;
}

async function loadOverview() {
  const o = await get("/api/overview");
  $("#qn").textContent = o.quarantine ? `(${o.quarantine})` : "";
  $("#badge").innerHTML = o.synthetic && !o.real ? '<span class="pill syn">SYNTHETISCHE DATEN</span>' : "";
  const warn = [];
  if (!o.signers_configured) warn.push("signers.json ist leer — Unterzeichner können nicht zugeordnet werden.");
  if (o.unassigned && (o.unassigned.pairs + o.unassigned.finals)) warn.push(`${o.unassigned.pairs + o.unassigned.finals} Erfassungen ohne erkannten Unterzeichner (Library → zuordnen).`);
  if (!o.models.ok) warn.push("Lokales Ollama nicht erreichbar — Correct läuft nur regelbasiert, Suche per Trigramm.");
  $("#ov-warn").innerHTML = warn.map((w) => `<div class="flag warn">${esc(w)}</div>`).join("");
  $("#ov-brains").innerHTML = Object.entries(o.brains).map(([c, b]) => `<div class="card"><h3 style="color:${COL[c]}">${c} · ${esc(b.role)}
     <span class="pill ${b.live ? "live" : "notlive"}">${b.live ? "LIVE" : `live ab ${o.targets.live_at} echten Paaren`}</span></h3>
     Paare ${bar(b.pairs, o.targets.pairs, COL[c], `${b.pairs} / ${o.targets.pairs}`)}
     Endbefunde ${bar(b.finals, o.targets.finals, COL[c], `${b.finals} / ${o.targets.finals}`)}
     <div class="small">${b.rules} Regeln · ${b.real_pairs} echte Paare</div></div>`).join("");
  renderEval(o.eval, o.eval_history);
  const m = o.models;
  $("#ov-models").innerHTML = `<div class="card small">Ollama ${m.ok ? "erreichbar" : "NICHT erreichbar"} · LLM <code>${esc(o.settings.llm)}</code> ${m.llm ? "✓" : "✗"} · Embedding <code>${esc(o.settings.embed)}</code> ${m.embed ? "✓" : "✗"}</div>`;
}

function renderEval(ev, hist) {
  if (!ev) { $("#ov-eval").innerHTML = '<p class="hint">Noch keine Evaluation.</p>'; return; }
  $("#ev-note").innerHTML = ev.synthetic ? '<span class="pill syn">synthetisch — kein Leistungsnachweis</span>' : "";
  const W = 560, H = 190, pad = 34, codes = Object.keys(ev.by_signer);
  const bw = (W - pad * 2) / Math.max(1, codes.length);
  let svg = `<svg width="${W}" height="${H}" role="img" aria-label="chrF Entwurf vs Engine">`;
  for (let y = 80; y <= 100; y += 5) {
    const yy = H - pad - ((y - 80) / 20) * (H - pad * 2);
    svg += `<line x1="${pad}" x2="${W - pad}" y1="${yy}" y2="${yy}" stroke="#e3e6ef"/><text x="4" y="${yy + 4}">${y}</text>`;
  }
  codes.forEach((c, i) => {
    const s = ev.by_signer[c];
    [["chrf_draft", "#c9cdd9", 0], ["chrf_engine", COL[c], 1]].forEach(([k, col, j]) => {
      const v = Math.max(80, s[k] ?? 80), h = ((v - 80) / 20) * (H - pad * 2);
      const x = pad + i * bw + 12 + j * (bw / 2 - 10);
      svg += `<rect x="${x}" y="${H - pad - h}" width="${bw / 2 - 16}" height="${h}" fill="${col}"><title>${k} ${s[k]}</title></rect>`;
      svg += `<text x="${x}" y="${H - pad - h - 3}">${s[k] ?? "–"}</text>`;
    });
    svg += `<text x="${pad + i * bw + bw / 2 - 8}" y="${H - 10}">${c}</text>`;
  });
  svg += "</svg>";
  const tbl = codes.map((c) => { const s = ev.by_signer[c]; return `<tr><td>${c}</td><td>${s.n_test}/${s.n_train}</td><td>${s.chrf_draft} → <b>${s.chrf_engine}</b></td><td>${s.ned_draft} → <b>${s.ned_engine}</b></td><td>${pct(s.predict_recall)} / ${pct(s.predict_precision)}</td></tr>`; }).join("");
  $("#ov-eval").innerHTML = `<div class="card">${svg}<div class="small">grau = unveränderter Entwurf, farbig = Engine (chrF gegen die echte Endfassung, höher = näher)</div>
   <table class="grid" style="margin-top:8px"><tr><th>Brain</th><th>Test/Train</th><th>chrF</th><th>Edit-Distanz</th><th>Predict Recall/Precision</th></tr>${tbl}</table>
   <div class="small">${new Date(ev.at * 1000).toLocaleString("de-DE")} · ${hist.length} Läufe</div></div>`;
}
$("#btn-mine").onclick = async () => { $("#ov-status").textContent = "mine …"; const r = await post("/api/mine"); $("#ov-status").textContent = `${r.rules} Regeln aus ${r.pairs} Paaren`; loadOverview(); };
$("#btn-eval").onclick = async () => { $("#ov-status").textContent = "Evaluation läuft …"; await post("/api/eval", {llm: false}); $("#ov-status").textContent = "fertig"; loadOverview(); };

async function loadEntities() {
  const d = await get("/api/entities");
  $("#win").textContent = d.window;
  const max = Math.max(1, ...d.entities.flatMap((e) => Object.values(e.by).map((b) => b.pairs)));
  let h = '<table class="grid"><tr><th>Entität</th><th>Region</th><th>B1</th><th>B2</th><th>B3</th></tr>';
  for (const e of d.entities) {
    h += `<tr><td class="l">${esc(e.label)}</td><td class="l small">${esc(e.region)}</td>`;
    for (const c of ["B1", "B2", "B3"]) {
      const b = e.by[c], a = 0.08 + 0.85 * (b.pairs / max);
      h += `<td class="cell${b.saturated ? " sat" : ""}" data-s="${c}" data-e="${e.key}" style="background:color-mix(in srgb, ${COL[c]} ${Math.round(a * 100)}%, white)" title="${b.pairs} Paare, ${b.finals} Endbefunde, ${b.since_new} seit letzter neuer Regel">${b.pairs}${b.finals ? `<span class="small"> +${b.finals}</span>` : ""}${b.saturated ? " ✓" : ""}</td>`;
    }
    h += "</tr>";
  }
  $("#ent-grid").innerHTML = h + "</table>";
  $("#ent-grid").querySelectorAll("td.cell").forEach((td) => td.onclick = () => showList("#ent-list", {signer: td.dataset.s, entity: td.dataset.e}));
  $("#ent-next").innerHTML = Object.entries(d.open_next).map(([c, items]) => `<div class="card"><h3 style="color:${COL[c]}">${c}: als Nächstes</h3>${items.slice(0, 8).map((i) => `<div>${esc(i.label)} <span class="small">· ${i.pairs} Paare</span></div>`).join("") || '<span class="hint">alles gesättigt</span>'}</div>`).join("");
}

async function showList(sel, q) {
  const rows = await get("/api/captures?" + new URLSearchParams(q));
  $(sel).innerHTML = `<h2>${rows.length} Fälle</h2><div class="list">${rows.slice().reverse().map((r) => `<div data-id="${r.id}">#${r.id} · ${r.kind === "pair" ? "Paar" : "Endbefund"} · ${r.signer || "<b>nicht zugeordnet</b>"} · ${esc(r.modality || "?")} ${esc(r.region || "")} · ${esc(r.pathologies.join(", "))}${r.change_rate != null ? ` · Änderung ${pct(r.change_rate)}` : ""}${r.synthetic ? ' <span class="pill syn">syn</span>' : ""}</div>`).join("")}</div>`;
  $(sel).querySelectorAll(".list div").forEach((d) => d.onclick = () => showCapture(d.dataset.id, sel));
}

async function showCapture(id, sel) {
  const c = await get("/api/capture/" + id);
  const assign = c.signer ? "" : `<div class="row">Zuordnen: ${["B1", "B2", "B3"].map((s) => `<button data-a="${s}">${s}</button>`).join("")}</div>`;
  const body = c.html ? `<h4>Befund</h4>${c.html.befund}<h4>Beurteilung</h4>${c.html.beurteilung}` :
    `<h4>Befund</h4>${esc(c.final_befund).replace(/\n/g, "<br>")}<h4>Beurteilung</h4>${esc(c.final_beurteilung).replace(/\n/g, "<br>")}`;
  const el = document.createElement("div");
  el.className = "out";
  el.innerHTML = `<b>#${c.id}</b> ${esc(c.exam || "")} · ${c.signer || "?"} · ${esc(c.pathologies.join(", "))}${assign}${c.fragestellung ? `<h4>Fragestellung</h4>${esc(c.fragestellung)}` : ""}${body}`;
  el.querySelectorAll("button[data-a]").forEach((b) => b.onclick = async () => { await post("/api/assign", {id: c.id, signer: b.dataset.a}); b.parentElement.innerHTML = "zugeordnet: " + b.dataset.a; });
  const host = $(sel);
  host.querySelectorAll(".out").forEach((x) => x.remove());
  host.prepend(el);
}

async function loadRate() {
  const d = await get("/api/changerate");
  const s = d.series;
  if (!s.length) { $("#rate-chart").innerHTML = '<p class="hint">Noch keine eigenen Entwürfe erfasst (signers.json → "me").</p>'; $("#rate-ent").innerHTML = ""; return; }
  const W = 900, H = 240, pad = 36;
  const x = (i) => pad + (i / Math.max(1, s.length - 1)) * (W - pad * 2), y = (v) => H - pad - v * (H - pad * 2);
  let svg = `<svg width="${W}" height="${H}">`;
  for (const v of [0, 0.1, 0.2, 0.3, 0.4, 0.5]) svg += `<line x1="${pad}" x2="${W - pad}" y1="${y(v)}" y2="${y(v)}" stroke="#e3e6ef"/><text x="2" y="${y(v) + 4}">${v * 100}%</text>`;
  s.forEach((p, i) => svg += `<circle cx="${x(i)}" cy="${y(Math.min(0.5, p.rate))}" r="3" fill="${COL[p.signer] || "#999"}" opacity=".55"><title>#${p.id} ${p.signer} ${pct(p.rate)} ${p.pathologies.join(", ")}</title></circle>`);
  const ma = s.map((_, i) => { const w = s.slice(Math.max(0, i - 9), i + 1); return w.reduce((a, b) => a + b.rate, 0) / w.length; });
  svg += `<polyline fill="none" stroke="var(--ink)" stroke-width="2" points="${ma.map((v, i) => `${x(i)},${y(Math.min(0.5, v))}`).join(" ")}"/>`;
  if (d.others_mean != null) svg += `<line x1="${pad}" x2="${W - pad}" y1="${y(d.others_mean)}" y2="${y(d.others_mean)}" stroke="var(--warn)" stroke-dasharray="4 3"/><text x="${W - pad - 140}" y="${y(d.others_mean) - 4}">Ø andere Assistenzärzte ${pct(d.others_mean)}</text>`;
  $("#rate-chart").innerHTML = `<div class="card">${svg + "</svg>"}</div>`;
  const mx = Math.max(0.01, ...d.per_entity.map((e) => e.mean));
  $("#rate-ent").innerHTML = `<div class="card">${d.per_entity.map((e) => `<div class="row" style="margin:2px 0"><span style="width:220px">${esc(e.label)} <span class="small">(${e.n})</span></span><div class="bar" style="flex:1;margin:0"><i style="width:${(100 * e.mean) / mx}%;background:var(--acc)"></i><span>${pct(e.mean)}</span></div></div>`).join("")}</div>`;
}

let ruleSigner = "B1";
async function loadRules() {
  $("#rules-sel").innerHTML = ["B1", "B2", "B3"].map((c) => `<button class="${c === ruleSigner ? "primary" : ""}" data-s="${c}">${c}</button>`).join("");
  $("#rules-sel").querySelectorAll("button").forEach((b) => b.onclick = () => { ruleSigner = b.dataset.s; loadRules(); });
  const rs = await get("/api/rules?signer=" + ruleSigner);
  $("#rules-list").innerHTML = rs.length ? rs.map((r) => `<div class="card" style="margin:6px 0"><span class="pill ${r.scope.startsWith("HOUSE") ? "house" : "pers"}">${r.scope}</span> <b>${r.rid}</b> ${esc(r.label)}${r.condition ? ` <span class="small">nur ${esc(r.condition.region)}</span>` : ""}
     ${bar(r.count, r.present, COL[ruleSigner], `${r.count}/${r.present} · ${pct(r.consistency)}`)}
     ${r.examples.map((e) => `<div class="small">#${e.capture}: <i>${esc(e.draft) || "—"}</i> → <b>${esc(e.final) || "—"}</b></div>`).join("")}</div>`).join("") : '<p class="hint">Noch keine Regeln (ab 3 wiederkehrenden Korrekturen).</p>';
}

function flagsHtml(fl) { return (fl || []).map((f) => `<div class="flag ${f.level}">${esc(f.text)}${f.en ? `<div class="small">${esc(f.en)}</div>` : ""}</div>`).join(""); }
$("#c-go").onclick = async () => {
  $("#c-status").textContent = "läuft …";
  const r = await post("/api/correct", {draft: $("#c-draft").value, signer: $("#c-signer").value, llm: $("#c-llm").checked});
  if (r.error) { $("#c-status").textContent = r.error; return; }
  $("#c-status").textContent = `${r.rules_applied.length} Regeln · ${r.llm_used ? "LLM " + r.model : "nur Regeln"} · Beispiele ${r.examples.map((e) => "#" + e.id).join(", ")}`;
  $("#c-out").innerHTML = flagsHtml(r.flags) + `<div class="out">${Object.entries(r.html).map(([k, v]) => `<h4>${k === "befund" ? "Befund" : "Beurteilung"}</h4>${v}`).join("")}</div>
    <div class="out"><h4>Why</h4>${r.explanations.map((e) => `<div>• ${esc(e.en)} <span class="small">[${esc(e.source)}${e.example ? " · Beispiel #" + e.example : ""}${e.scope ? " · " + esc(e.scope) : ""}]</span></div>`).join("") || '<span class="hint">keine Änderungen</span>'}</div>
    <div class="row"><button id="c-copy">Korrigierten Text kopieren</button></div>`;
  $("#c-copy").onclick = () => navigator.clipboard.writeText(`Befund:\n${r.sections_out.befund || ""}\n\nBeurteilung:\n${r.sections_out.beurteilung || ""}`);
};
$("#p-go").onclick = async () => {
  const r = await post("/api/predict", {draft: $("#p-draft").value, signer: $("#p-signer").value});
  $("#p-out").innerHTML = flagsHtml(r.flags) + `<div class="out"><h4>Befund</h4>${r.html.befund || ""}<h4>Beurteilung</h4>${r.html.beurteilung || ""}</div>
   <div class="out">${r.hits.map((h) => `<div>${pct(h.p)} · <b>${h.rule}</b> ${esc(h.label)} <span class="pill ${h.scope.startsWith("HOUSE") ? "house" : "pers"}">${h.scope}</span></div>`).join("") || '<span class="hint">nichts vorhergesagt</span>'}</div>`;
};
$("#a-go").onclick = async () => {
  const r = await post("/api/ask", {question: $("#a-q").value, llm: $("#a-llm").checked});
  if (!r.entity) { $("#a-out").innerHTML = `<div class="flag warn">${esc(r.answer)}</div>`; return; }
  $("#a-out").innerHTML = (r.answer ? `<div class="out">${esc(r.answer)}</div>` : "") + `<div class="grid3">${Object.entries(r.by_signer).map(([c, v]) => `<div class="card" style="${r.codes.includes(c) ? "" : "opacity:.6"}"><h3 style="color:${COL[c]}">${c} · ${esc(r.label)} <span class="small">(${v.n} Fälle)</span></h3>
     ${v.examples.map((e) => `<div>„${esc(e.text)}“ <span class="small">×${e.count} · #${e.capture}</span></div>`).join("") || '<span class="hint">keine Beispiele</span>'}
     ${v.beurteilung_rules.length ? `<div class="small" style="margin-top:6px">Beurteilungs-Regeln: ${v.beurteilung_rules.map((x) => esc(x.label)).join(" · ")}</div>` : ""}</div>`).join("")}</div>`;
};

async function loadQuarantine() {
  const q = await get("/api/quarantine");
  $("#q-list").innerHTML = q.length ? `<div class="list">${q.map((x) => `<div data-id="${esc(x.id)}">${esc(x.id)} · ${x.kind} · ${esc(x.reasons.join("; "))}</div>`).join("")}</div>` : '<p class="hint">Quarantäne leer.</p>';
  $("#q-list").querySelectorAll(".list div").forEach((d) => d.onclick = () => showQ(d.dataset.id));
  $("#q-detail").innerHTML = "";
}
async function showQ(id) {
  const p = await get("/api/quarantine/" + encodeURIComponent(id));
  $("#q-detail").innerHTML = `<div class="out"><b>${esc(p.id)}</b> · ${esc(p.reasons.join("; "))}
   <p class="small">So würde es gespeichert (bereinigt). Unbekannte Wörter: anhaken, wenn es KEINE Namen sind.</p>
   <div class="row">${p.unknown_words.map((w) => `<label><input type="checkbox" value="${esc(w)}"> ${esc(w)}</label>`).join("") || "—"}</div>
   ${p.draft_scrubbed ? `<h4>Entwurf</h4><pre>${esc(p.draft_scrubbed)}</pre>` : ""}<h4>Endfassung</h4><pre>${esc(p.final_scrubbed)}</pre>
   <div class="row"><button class="primary" id="q-rel">Freigeben</button><button id="q-dis">Verwerfen</button></div></div>`;
  $("#q-rel").onclick = async () => {
    const cleared = [...document.querySelectorAll("#q-detail input:checked")].map((i) => i.value);
    const r = await post(`/api/quarantine/${encodeURIComponent(id)}/release`, {cleared_words: cleared});
    alert(r.status === "saved" ? "gespeichert #" + r.id : r.status + " " + (r.reason || "")); loadQuarantine();
  };
  $("#q-dis").onclick = async () => { await post(`/api/quarantine/${encodeURIComponent(id)}/discard`); loadQuarantine(); };
}
async function loadSigners() {
  const rows = await get("/api/signers");
  const open = rows.filter((r) => !r.assigned).length;
  $("#sn").textContent = open ? `(${open})` : "";
  $("#s-list").innerHTML = rows.length ? `<table class="grid"><tr><th>Name</th><th>Rolle (Signatur)</th><th>signiert</th><th>Entwürfe</th><th>Zuordnung</th></tr>${rows.map((r) => `<tr><td class="l"><b>${esc(r.name)}</b></td><td class="l small">${esc(Object.entries(r.roles).map(([k, v]) => k + " ×" + v).join(", "))}</td><td>${r.final}</td><td>${r.draft}</td><td class="l">${["B1", "B2", "B3", "me", "staff"].map((c) => `<button data-k="${r.key}" data-c="${c}" class="${r.assigned === c ? "primary" : ""}">${c === "me" ? "Ich" : c === "staff" ? "Andere" : c}</button>`).join(" ")}</td></tr>`).join("")}</table>` : '<p class="hint">Noch keine Signaturen gesehen — erste Erfassung machen.</p>';
  $("#s-list").querySelectorAll("button[data-k]").forEach((b) => b.onclick = async () => { const r = await post("/api/signers/assign", {key: b.dataset.k, code: b.dataset.c}); if (r.error) alert(r.error); loadSigners(); });
}
$("#l-go").onclick = () => showList("#l-list", {signer: $("#l-signer").value, kind: $("#l-kind").value});
loadOverview();
setInterval(() => { if ($("#overview").classList.contains("on")) loadOverview(); }, 30000);
