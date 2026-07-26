#!/usr/bin/env node
// Generates the PWA / iOS home-screen icons as raster PNGs.
// Pure Node (zlib only) so it runs anywhere without native image libraries.
// Draws a rounded brand-colour tile with a simple "insights" bar-chart glyph.

import { deflateSync } from 'node:zlib';
import { writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const OUT_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', 'web', 'icons');
mkdirSync(OUT_DIR, { recursive: true });

// Brand palette
const BG = [15, 118, 110]; // teal-700  #0F766E
const BG2 = [13, 148, 136]; // teal-600 for a soft vertical gradient
const BAR = [240, 253, 250]; // near-white
const ACCENT = [251, 191, 36]; // amber-400 highlight bar

function lerp(a, b, t) {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ];
}

function makeIcon(size, { maskable = false } = {}) {
  const px = new Uint8Array(size * size * 4); // RGBA
  const radius = maskable ? 0 : Math.round(size * 0.22);
  const inset = 0; // full-bleed; OS applies its own mask on iOS

  const set = (x, y, [r, g, b], a = 255) => {
    if (x < 0 || y < 0 || x >= size || y >= size) return;
    const i = (y * size + x) * 4;
    // simple alpha-over
    const na = a / 255;
    px[i] = Math.round(px[i] * (1 - na) + r * na);
    px[i + 1] = Math.round(px[i + 1] * (1 - na) + g * na);
    px[i + 2] = Math.round(px[i + 2] * (1 - na) + b * na);
    px[i + 3] = Math.max(px[i + 3], a);
  };

  const inRounded = (x, y) => {
    if (maskable) return true;
    const minX = inset, minY = inset, maxX = size - inset - 1, maxY = size - inset - 1;
    if (x < minX || y < minY || x > maxX || y > maxY) return false;
    // corner rounding
    const corners = [
      [minX + radius, minY + radius],
      [maxX - radius, minY + radius],
      [minX + radius, maxY - radius],
      [maxX - radius, maxY - radius],
    ];
    const nearLeft = x < minX + radius;
    const nearRight = x > maxX - radius;
    const nearTop = y < minY + radius;
    const nearBottom = y > maxY - radius;
    if ((nearLeft || nearRight) && (nearTop || nearBottom)) {
      const cx = nearLeft ? minX + radius : maxX - radius;
      const cy = nearTop ? minY + radius : maxY - radius;
      return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2;
    }
    return true;
  };

  // background gradient tile
  for (let y = 0; y < size; y++) {
    const t = y / (size - 1);
    const col = lerp(BG, BG2, t);
    for (let x = 0; x < size; x++) {
      if (inRounded(x, y)) set(x, y, col, 255);
    }
  }

  // bar chart glyph: 3 rounded bars sitting on a baseline
  const bars = [
    { hFrac: 0.34, col: BAR },
    { hFrac: 0.52, col: ACCENT },
    { hFrac: 0.44, col: BAR },
  ];
  const areaW = size * 0.52;
  const areaX = (size - areaW) / 2;
  const baseline = size * 0.70;
  const gap = areaW * 0.10;
  const barW = (areaW - gap * (bars.length - 1)) / bars.length;
  const rBar = Math.max(2, Math.round(barW * 0.22));

  bars.forEach((bar, idx) => {
    const bx = areaX + idx * (barW + gap);
    const bh = size * bar.hFrac;
    const by = baseline - bh;
    for (let y = Math.floor(by); y < baseline; y++) {
      for (let x = Math.floor(bx); x < bx + barW; x++) {
        // round only the top corners of each bar
        const nearTop = y < by + rBar;
        const nearLeft = x < bx + rBar;
        const nearRight = x > bx + barW - rBar;
        if (nearTop && (nearLeft || nearRight)) {
          const cx = nearLeft ? bx + rBar : bx + barW - rBar;
          const cy = by + rBar;
          if ((x - cx) ** 2 + (y - cy) ** 2 > rBar ** 2) continue;
        }
        set(x, y, bar.col, 255);
      }
    }
  });

  // baseline underline
  const ulY = Math.round(baseline);
  for (let x = Math.floor(areaX); x < areaX + areaW; x++) {
    for (let t = 0; t < Math.max(2, Math.round(size * 0.012)); t++) {
      set(x, ulY + t, BAR, 235);
    }
  }

  return encodePNG(size, size, px);
}

// --- Minimal PNG encoder (truecolour + alpha, no filtering) ---
function encodePNG(width, height, rgba) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // colour type RGBA
  ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;

  // raw scanlines with filter byte 0
  const stride = width * 4;
  const raw = Buffer.alloc((stride + 1) * height);
  for (let y = 0; y < height; y++) {
    raw[y * (stride + 1)] = 0;
    Buffer.from(rgba.buffer, y * stride, stride).copy(raw, y * (stride + 1) + 1);
  }
  const idatData = deflateSync(raw, { level: 9 });

  const chunk = (type, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length, 0);
    const typeBuf = Buffer.from(type, 'ascii');
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])) >>> 0, 0);
    return Buffer.concat([len, typeBuf, data, crc]);
  };

  return Buffer.concat([
    sig,
    chunk('IHDR', ihdr),
    chunk('IDAT', idatData),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();
function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

const targets = [
  { name: 'icon-192.png', size: 192 },
  { name: 'icon-512.png', size: 512 },
  { name: 'icon-maskable-512.png', size: 512, maskable: true },
  { name: 'apple-touch-icon.png', size: 180 },
  { name: 'favicon-32.png', size: 32 },
];

for (const t of targets) {
  const png = makeIcon(t.size, { maskable: t.maskable });
  writeFileSync(join(OUT_DIR, t.name), png);
  console.log(`wrote icons/${t.name} (${png.length} bytes)`);
}
console.log('Done.');
