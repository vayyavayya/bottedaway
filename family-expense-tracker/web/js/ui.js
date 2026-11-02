// Small presentation helpers shared across views.

export function money(amount, currency = 'USD') {
  const n = Number(amount || 0);
  try {
    return new Intl.NumberFormat(undefined, {
      style: 'currency', currency, maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return `${currency} ${n.toFixed(2)}`;
  }
}

export function fmtDate(d) {
  if (!d) return '';
  const date = typeof d === 'string' ? new Date(d + 'T00:00:00') : d;
  if (isNaN(date)) return String(d);
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

export function monthLabel(date) {
  return date.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
}

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

// Donut chart from [{ value, color }]. Returns an <svg> string. `center` puts a
// value (top) and a caption (bottom) in the hole.
export function donutSVG(segments, { size = 132, stroke = 20, center = null } = {}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  let offset = 0;
  const cx = size / 2;
  const arcs = segments.map((seg) => {
    const frac = seg.value / total;
    const dash = frac * c;
    const el = `<circle cx="${cx}" cy="${cx}" r="${r}" fill="none"
      stroke="${seg.color}" stroke-width="${stroke}"
      stroke-dasharray="${dash} ${c - dash}"
      stroke-dashoffset="${-offset}"
      transform="rotate(-90 ${cx} ${cx})" stroke-linecap="butt" />`;
    offset += dash;
    return el;
  }).join('');
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <circle cx="${cx}" cy="${cx}" r="${r}" fill="none" style="stroke:var(--surface-2)" stroke-width="${stroke}" />
    ${arcs}
    ${center ? `<text x="${cx}" y="${cx - 2}" text-anchor="middle" class="donut-top">${esc(center.top)}</text>
      <text x="${cx}" y="${cx + 15}" text-anchor="middle" class="donut-bottom">${esc(center.bottom)}</text>` : ''}
  </svg>`;
}

// Month outlook chart. Top: cumulative day-to-day spending (solid), the usual
// month (dashed), the projection to month end (dotted) and the monthly budget
// (amber). Bottom strip: one bar per day, highlighted above a normal day.
export function outlookSVG(o, { budget = null } = {}) {
  const W = 320, top = 8, plotH = 112, gap = 14, barH = 34, left = 4, right = 4;
  const H = top + plotH + gap + barH + 4;
  const n = o.daysInMonth;
  const x = (day) => left + ((day - 0.5) / n) * (W - left - right);
  const maxY = Math.max(1, o.actualCum || 0, o.projected || 0, o.typicalTotal || 0, budget || 0) * 1.08;
  const y = (v) => top + plotH - (v / maxY) * plotH;

  const pts = (key) => o.days.filter((d) => d[key] != null).map((d) => `${x(d.day).toFixed(1)},${y(d[key]).toFixed(1)}`).join(' ');
  const typical = o.days[0]?.typicalCum != null ? `<polyline class="ol-typical" points="${pts('typicalCum')}" />` : '';
  const actual = o.lastDay ? `<polyline class="ol-actual" points="${pts('cum')}" />` : '';
  const proj = o.projected != null && o.lastDay < n
    ? `<line class="ol-proj" x1="${x(o.lastDay)}" y1="${y(o.actualCum)}" x2="${x(n)}" y2="${y(o.projected)}" />
       <circle class="ol-proj-dot" cx="${x(n)}" cy="${y(o.projected)}" r="3" />` : '';
  const budgetLine = budget ? `<line class="ol-budget" x1="${left}" x2="${W - right}" y1="${y(budget)}" y2="${y(budget)}" />` : '';
  const todayMark = o.isCurrent ? `<line class="ol-today" x1="${x(o.lastDay)}" x2="${x(o.lastDay)}" y1="${top}" y2="${top + plotH}" />` : '';

  const maxBar = Math.max(1, ...o.days.map((d) => d.spent || 0), o.threshold || 0);
  const bw = Math.max(2, ((W - left - right) / n) * 0.7);
  const barTop = top + plotH + gap;
  const bars = o.days.filter((d) => d.spent).map((d) => {
    const h = Math.max(1.5, (d.spent / maxBar) * barH);
    return `<rect class="${d.aboveNormal ? 'ol-bar-hi' : 'ol-bar'}" x="${(x(d.day) - bw / 2).toFixed(1)}" y="${(barTop + barH - h).toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="1" />`;
  }).join('');
  const thr = o.threshold ? `<line class="ol-threshold" x1="${left}" x2="${W - right}" y1="${barTop + barH - (o.threshold / maxBar) * barH}" y2="${barTop + barH - (o.threshold / maxBar) * barH}" />` : '';

  return `<svg class="outlook-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Spending outlook for the month">
    <line class="ol-axis" x1="${left}" x2="${W - right}" y1="${top + plotH}" y2="${top + plotH}" />
    ${budgetLine}${typical}${todayMark}${actual}${proj}
    <line class="ol-axis" x1="${left}" x2="${W - right}" y1="${barTop + barH}" y2="${barTop + barH}" />
    ${thr}${bars}
  </svg>`;
}

let toastTimer;
export function toast(msg) {
  let t = document.getElementById('toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'toast';
    t.className = 'toast';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  requestAnimationFrame(() => t.classList.add('show'));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2600);
}

export const DOC_TYPES = {
  receipt: { label: 'Receipt', emoji: '🧾' },
  utility_bill: { label: 'Utility', emoji: '💡' },
  bank_statement: { label: 'Statement', emoji: '🏦' },
  other: { label: 'Other', emoji: '📄' },
};
