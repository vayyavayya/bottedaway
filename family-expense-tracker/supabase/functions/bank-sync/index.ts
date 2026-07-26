// Supabase Edge Function: bank-sync  (deployed with verify_jwt = false; guarded
// by the x-sync-key header checked against the SYNC_KEY secret).
//
// For every active bank connection: pull booked transactions from Enable Banking,
// skip ones we already have (external_ref), skip ones that match a scanned
// receipt (same amount within ±3 days), categorize the rest with Claude, and
// insert them into the shared ledger with source = 'bank_feed'.

import { createClient } from 'npm:@supabase/supabase-js@2';
import { eb } from '../_shared/enablebanking.ts';

const CATEGORIZE_MODEL = Deno.env.get('ANTHROPIC_CATEGORIZE_MODEL') ?? 'claude-haiku-4-5';

Deno.serve(async (req) => {
  if (req.headers.get('x-sync-key') !== Deno.env.get('SYNC_KEY')) {
    return json({ error: 'forbidden' }, 403);
  }
  const admin = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!);
  const report: Record<string, unknown>[] = [];

  const { data: conns } = await admin.from('bank_connections')
    .select('*').eq('status', 'active');

  for (const conn of conns ?? []) {
    const r: Record<string, unknown> = { connection: conn.label, fetched: 0, inserted: 0, dup: 0, receiptMatch: 0 };
    try {
      if (conn.valid_until && new Date(conn.valid_until) < new Date()) {
        await admin.from('bank_connections').update({ status: 'expired' }).eq('id', conn.id);
        r.note = 'consent expired — needs re-authorization';
        report.push(r); continue;
      }

      const since = conn.last_synced_at
        ? new Date(Date.parse(conn.last_synced_at) - 5 * 864e5)
        : new Date(Date.now() - 90 * 864e5);
      const dateFrom = since.toISOString().slice(0, 10);

      // Household categories for classification.
      const { data: cats } = await admin.from('categories')
        .select('id, name').eq('household_id', conn.household_id).order('sort_order');
      const catIdByName = new Map((cats ?? []).map((c) => [c.name.toLowerCase(), c.id]));
      const otherId = catIdByName.get('other') ?? (cats?.[0]?.id ?? null);

      const candidates: any[] = [];
      for (const acc of (conn.accounts ?? [])) {
        const uid = acc.uid;
        if (!uid) continue;
        let ck: string | null = null;
        do {
          const q = new URLSearchParams({ date_from: dateFrom });
          if (ck) q.set('continuation_key', ck);
          const resp = await eb(`/accounts/${uid}/transactions?${q}`);
          if (!resp.ok) {
            r.note = `fetch failed HTTP ${resp.status}: ${(await resp.text()).slice(0, 200)}`;
            break;
          }
          const body = await resp.json();
          for (const t of body.transactions ?? []) {
            if ((t.status ?? 'BOOK') !== 'BOOK') continue;
            const amtRaw = parseFloat(t.transaction_amount?.amount ?? '0');
            if (!amtRaw) continue;
            const direction = t.credit_debit_indicator ? (t.credit_debit_indicator === 'CRDT' ? 'credit' : 'debit') : (amtRaw < 0 ? 'debit' : 'credit');
            const amount = Math.abs(amtRaw);
            const date = t.booking_date || t.value_date || new Date().toISOString().slice(0, 10);
            const counterparty = direction === 'debit'
              ? (t.creditor?.name ?? null) : (t.debtor?.name ?? null);
            const remit = Array.isArray(t.remittance_information)
              ? t.remittance_information.join(' ').trim() : (t.remittance_information ?? '');
            const ref = t.entry_reference ||
              `h:${await hash(`${uid}|${date}|${t.transaction_amount?.amount}|${remit}`.toLowerCase())}`;
            candidates.push({
              external_ref: `${conn.aspsp_name}:${ref}`,
              txn_date: date, merchant: counterparty,
              description: remit || counterparty || 'Bank transaction',
              amount, direction,
              currency: t.transaction_amount?.currency ?? 'EUR',
            });
          }
          ck = body.continuation_key ?? null;
        } while (ck);
      }
      r.fetched = candidates.length;

      if (candidates.length) {
        // Drop ones already imported.
        const refs = candidates.map((c) => c.external_ref);
        const { data: existing } = await admin.from('transactions')
          .select('external_ref').eq('household_id', conn.household_id).in('external_ref', refs);
        const seen = new Set((existing ?? []).map((e) => e.external_ref));
        let fresh = candidates.filter((c) => !seen.has(c.external_ref));
        r.dup = candidates.length - fresh.length;

        // Drop ones that match a scanned receipt/bill (±3 days, same amount, debits only).
        if (fresh.length) {
          const min = fresh.reduce((m, c) => c.txn_date < m ? c.txn_date : m, fresh[0].txn_date);
          const { data: recTxns } = await admin.from('transactions')
            .select('txn_date, amount, direction')
            .eq('household_id', conn.household_id)
            .in('source', ['receipt', 'utility_bill'])
            .gte('txn_date', addDays(min, -4));
          const before = fresh.length;
          fresh = fresh.filter((c) => c.direction === 'credit' || !(recTxns ?? []).some((rt) =>
            rt.direction === 'debit' &&
            Math.abs(Number(rt.amount) - c.amount) < 0.005 &&
            Math.abs(Date.parse(rt.txn_date) - Date.parse(c.txn_date)) <= 3 * 864e5));
          r.receiptMatch = before - fresh.length;
        }

        if (fresh.length) {
          const catNames = (cats ?? []).map((c) => c.name);
          const assigned = await categorize(fresh, catNames);
          const rows = fresh.map((c, i) => ({
            household_id: conn.household_id,
            txn_date: c.txn_date, merchant: c.merchant,
            description: c.description, amount: c.amount,
            direction: c.direction, currency: c.currency,
            category_id: catIdByName.get((assigned[i] ?? 'other').toLowerCase()) ?? otherId,
            source: 'bank_feed', external_ref: c.external_ref,
          }));
          const { error } = await admin.from('transactions')
            .upsert(rows, { onConflict: 'household_id,external_ref', ignoreDuplicates: true });
          if (error) throw error;
          r.inserted = rows.length;
        }
      }
      await admin.from('bank_connections').update({ last_synced_at: new Date().toISOString() }).eq('id', conn.id);
    } catch (e) {
      r.error = String(e?.message ?? e);
    }
    report.push(r);
  }
  return json({ ok: true, report });
});

async function categorize(txns: any[], categories: string[]): Promise<string[]> {
  const key = Deno.env.get('ANTHROPIC_API_KEY');
  if (!key || !txns.length || !categories.length) return txns.map(() => 'Other');
  const list = txns.map((t, i) =>
    `${i}. ${t.direction} €${t.amount} — ${t.merchant ?? ''} ${t.description ?? ''}`.trim()).join('\n');
  try {
    const resp = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
      body: JSON.stringify({
        model: CATEGORIZE_MODEL, max_tokens: 4000,
        output_config: {
          effort: 'low',
          format: {
            type: 'json_schema',
            schema: {
              type: 'object', additionalProperties: false,
              properties: { categories: { type: 'array', items: { type: 'string', enum: categories } } },
              required: ['categories'],
            },
          },
        },
        messages: [{
          role: 'user',
          content: `Assign the best-fitting category to each bank transaction of a family household. ` +
            `Available categories: ${categories.join(', ')}. Salary/refunds/incoming → Other unless clearly fitting. ` +
            `Return exactly ${txns.length} entries, in order.\n\n${list}`,
        }],
      }),
    });
    if (!resp.ok) throw new Error(`AI ${resp.status}`);
    const body = await resp.json();
    const text = (body.content ?? []).find((b: any) => b.type === 'text')?.text ?? '{}';
    const out = JSON.parse(text).categories ?? [];
    return txns.map((_, i) => out[i] ?? 'Other');
  } catch (_e) {
    return txns.map(() => 'Other');
  }
}

async function hash(s: string): Promise<string> {
  const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return Array.from(new Uint8Array(d)).slice(0, 12).map((b) => b.toString(16).padStart(2, '0')).join('');
}
function addDays(iso: string, d: number): string {
  return new Date(Date.parse(iso) + d * 864e5).toISOString().slice(0, 10);
}
function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}
