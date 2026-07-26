// Supabase Edge Function: ask  (verify_jwt = true)
//
// The in-app assistant. Receives { question, history? } from a signed-in user,
// builds a compact financial context for their household, lets Claude answer —
// with a search tool for digging into specific transactions when needed.

import { createClient } from 'npm:@supabase/supabase-js@2';
import { corsHeaders, json } from '../_shared/cors.ts';

const MODEL = Deno.env.get('ANTHROPIC_MODEL') ?? 'claude-sonnet-5';

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: corsHeaders });
  if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405);
  try {
    const anthropicKey = Deno.env.get('ANTHROPIC_API_KEY');
    if (!anthropicKey) return json({ error: 'ANTHROPIC_API_KEY not configured' }, 500);

    const { question, history } = await req.json().catch(() => ({}));
    if (!question || typeof question !== 'string') return json({ error: 'question is required' }, 400);

    // Caller identity + household (RLS-scoped client).
    const authHeader = req.headers.get('Authorization') ?? '';
    const userClient = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_ANON_KEY')!, {
      global: { headers: { Authorization: authHeader } },
    });
    const { data: userData } = await userClient.auth.getUser();
    if (!userData?.user) return json({ error: 'invalid session' }, 401);
    const { data: mem } = await userClient.from('household_members')
      .select('household_id, display_name, households(name, invite_code)').limit(1).maybeSingle();
    if (!mem) return json({ error: 'no household yet' }, 400);
    const hh = mem.household_id;

    const admin = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!);

    // ---- Build compact context ------------------------------------------------
    const since = new Date(Date.now() - 130 * 864e5).toISOString().slice(0, 10);
    const { data: txns } = await admin.from('transactions')
      .select('txn_date, merchant, description, amount, direction, excluded, source, categories(name)')
      .eq('household_id', hh).gte('txn_date', since)
      .order('txn_date', { ascending: false }).limit(2000);
    const { data: cats } = await admin.from('categories')
      .select('name').eq('household_id', hh).order('sort_order');
    const { data: members } = await admin.from('household_members')
      .select('display_name, role').eq('household_id', hh);
    const { data: conns } = await admin.from('bank_connections')
      .select('label, status, valid_until').eq('household_id', hh).neq('status', 'revoked');

    const months: Record<string, Record<string, number>> = {};
    const flows: Record<string, { in: number; out: number; hidden: number }> = {};
    for (const t of txns ?? []) {
      const m = t.txn_date.slice(0, 7);
      flows[m] ??= { in: 0, out: 0, hidden: 0 };
      const amt = Number(t.amount);
      if (t.excluded) { flows[m].hidden += amt; continue; }
      if (t.direction === 'credit') { flows[m].in += amt; continue; }
      flows[m].out += amt;
      months[m] ??= {};
      const c = (t as any).categories?.name ?? 'Other';
      months[m][c] = (months[m][c] ?? 0) + amt;
    }
    const monthLines = Object.keys(months).sort().reverse().map((m) => {
      const catStr = Object.entries(months[m]).sort((a, b) => b[1] - a[1])
        .map(([c, v]) => `${c} ${v.toFixed(0)}`).join(', ');
      const f = flows[m];
      return `${m}: spent ${f.out.toFixed(0)}, money-in ${f.in.toFixed(0)} (internal transfers hidden: ${f.hidden.toFixed(0)}) | ${catStr}`;
    }).join('\n');

    const recent = (txns ?? []).filter((t) => !t.excluded).slice(0, 40).map((t) =>
      `${t.txn_date} ${t.direction === 'credit' ? '+' : '-'}${Number(t.amount).toFixed(2)} ${((t.merchant ?? t.description) ?? '').slice(0, 45)} [${(t as any).categories?.name ?? '?'}] (${t.source})`).join('\n');

    const system = [
      `You are Hearth's assistant — the private expense tracker of the household "${(mem as any).households?.name}".`,
      `You answer questions from household member "${mem.display_name ?? 'a member'}" about THEIR OWN family finances. Be warm, concise, and concrete. Default currency: EUR.`,
      `Today is ${new Date().toISOString().slice(0, 10)}.`,
      `Members: ${(members ?? []).map((m) => `${m.display_name} (${m.role})`).join(', ')}.`,
      `Categories: ${(cats ?? []).map((c) => c.name).join(', ')}.`,
      `Bank feeds: ${(conns ?? []).map((c) => `${c.label}: ${c.status}${c.valid_until ? ' until ' + String(c.valid_until).slice(0, 10) : ''}`).join('; ')}. Feeds sync every 6 hours; receipts are scanned in-app.`,
      `"Internal transfers hidden" = money moved between the household's own accounts, deliberately excluded from spending/income totals.`,
      ``,
      `MONTHLY SUMMARY (last ~4 months):`,
      monthLines || 'no data yet',
      ``,
      `MOST RECENT TRANSACTIONS (up to 40):`,
      recent || 'none',
      ``,
      `Use the search_transactions tool when the user asks about something not visible above (a specific merchant, an older date range, a specific amount). Never invent numbers — search instead. If data genuinely isn't there (older than the bank history, unconnected accounts), say so.`,
    ].join('\n');

    const tools = [{
      name: 'search_transactions',
      description: 'Search the household transaction ledger by keyword and/or date range. Returns matching rows, newest first.',
      input_schema: {
        type: 'object',
        properties: {
          keywords: { type: 'string', description: 'text matched against merchant and description (case-insensitive substring)' },
          date_from: { type: 'string', description: 'YYYY-MM-DD inclusive' },
          date_to: { type: 'string', description: 'YYYY-MM-DD inclusive' },
          include_hidden: { type: 'boolean', description: 'set true to include internal self-transfers' },
        },
      },
    }];

    const messages: any[] = [
      ...(Array.isArray(history) ? history.slice(-8).map((h: any) => ({ role: h.role === 'assistant' ? 'assistant' : 'user', content: String(h.text ?? '').slice(0, 2000) })) : []),
      { role: 'user', content: question.slice(0, 2000) },
    ];

    let answer = '';
    let lastText = '';
    const ROUNDS = 5;
    for (let round = 0; round < ROUNDS; round++) {
      const finalRound = round === ROUNDS - 1;
      const resp = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: { 'x-api-key': anthropicKey, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
        body: JSON.stringify({
          model: MODEL, max_tokens: 1500, system, tools, messages,
          // Last round: no more searching — answer with what you have.
          ...(finalRound ? { tool_choice: { type: 'none' } } : {}),
        }),
      });
      if (!resp.ok) return json({ error: 'assistant unavailable', detail: (await resp.text()).slice(0, 200) }, 502);
      const body = await resp.json();
      const textParts = (body.content ?? []).filter((b: any) => b.type === 'text').map((b: any) => b.text);
      if (textParts.length) lastText = textParts.join('\n');
      if (body.stop_reason !== 'tool_use') { answer = textParts.join('\n'); break; }

      messages.push({ role: 'assistant', content: body.content });
      const results: any[] = [];
      for (const block of body.content.filter((b: any) => b.type === 'tool_use')) {
        const inp = block.input ?? {};
        let q = admin.from('transactions')
          .select('txn_date, merchant, description, amount, direction, excluded, source, categories(name)')
          .eq('household_id', hh).order('txn_date', { ascending: false }).limit(30);
        if (!inp.include_hidden) q = q.eq('excluded', false);
        if (inp.date_from) q = q.gte('txn_date', inp.date_from);
        if (inp.date_to) q = q.lte('txn_date', inp.date_to);
        if (inp.keywords) {
          // PostgREST or() syntax wants * as the wildcard, not %.
          const kw = String(inp.keywords).replace(/[%,()*]/g, '').trim();
          if (kw) q = q.or(`merchant.ilike.*${kw}*,description.ilike.*${kw}*`);
        }
        const { data: found, error } = await q;
        const lines = error ? `search error: ${error.message}` : (found ?? []).map((t) =>
          `${t.txn_date} ${t.direction === 'credit' ? '+' : '-'}${Number(t.amount).toFixed(2)} ${((t.merchant ?? t.description) ?? '').slice(0, 60)} [${(t as any).categories?.name ?? '?'}]${t.excluded ? ' (hidden transfer)' : ''}`).join('\n') || 'no matches';
        results.push({ type: 'tool_result', tool_use_id: block.id, content: lines });
      }
      messages.push({ role: 'user', content: results });
    }
    if (!answer) answer = lastText || 'Sorry — I could not finish answering that one. Try rephrasing?';
    return json({ answer });
  } catch (e) {
    return json({ error: 'unexpected error', detail: String(e).slice(0, 200) }, 500);
  }
});
