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

// Donut chart from [{ value, color }]. Returns an <svg> string.
export function donutSVG(segments, { size = 132, stroke = 20 } = {}) {
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
