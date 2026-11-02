// Supabase Edge Function: bank-callback  (deployed with verify_jwt = false)
//
// Target of the Enable Banking authorization redirect. The user approves access
// at their bank, EB redirects here with ?code=...&state=<connection_id>.<token>,
// and we exchange the code for a session, storing the account list on the
// matching bank_connections row.

import { createClient } from 'npm:@supabase/supabase-js@2';
import { eb } from '../_shared/enablebanking.ts';

const page = (title: string, body: string, ok = true) =>
  new Response(
    `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
     <title>${title}</title>
     <style>body{font-family:-apple-system,system-ui,sans-serif;display:grid;place-content:center;
     min-height:90vh;text-align:center;padding:24px;background:#f8fafc;color:#0f172a}
     .big{font-size:64px}h1{margin:8px 0}p{color:#475569;max-width:34em}</style></head>
     <body><div><div class="big">${ok ? '✅' : '⚠️'}</div><h1>${title}</h1><p>${body}</p></div></body></html>`,
    { status: ok ? 200 : 400, headers: { 'Content-Type': 'text/html; charset=utf-8' } },
  );

Deno.serve(async (req) => {
  try {
    const url = new URL(req.url);
    const code = url.searchParams.get('code');
    const state = url.searchParams.get('state') ?? '';
    const err = url.searchParams.get('error');
    if (err) return page('Authorization cancelled', `The bank reported: ${err}. You can close this tab and try again with a new link.`, false);
    if (!code || !state.includes('.')) return page('Missing details', 'This link is only reached at the end of a bank authorization.', false);

    const [connId, token] = state.split('.', 2);
    const admin = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!);

    let { data: conn } = await admin.from('bank_connections')
      .select('*').eq('id', connId).eq('state_token', token).maybeSingle();

    // Authorizations started outside our links (e.g. Enable Banking's own
    // "Activate by linking accounts" flow) carry an unknown state. Still
    // complete them: exchange the code and attach to the household.
    if (!conn) {
      const { data: hh } = await admin.from('households')
        .select('id').order('created_at').limit(1).maybeSingle();
      if (!hh) return page('No household yet', 'Create your household in the Hearth app first, then link the bank again.', false);
      const { data: created, error: insErr } = await admin.from('bank_connections').insert({
        household_id: hh.id,
        label: 'Linked bank',
        aspsp_name: 'unknown',
        state_token: state || 'external',
      }).select().single();
      if (insErr || !created) return page('Could not record connection', insErr?.message ?? 'insert failed', false);
      conn = created;
    }

    const resp = await eb('/sessions', { method: 'POST', body: JSON.stringify({ code }) });
    if (!resp.ok) {
      const detail = await resp.text();
      console.error('session exchange failed', resp.status, detail);
      return page('Could not complete', `The session exchange failed (HTTP ${resp.status}). Ask for a fresh link and try again.`, false);
    }
    const session = await resp.json();

    const aspspName = session.aspsp?.name ?? conn.aspsp_name;
    await admin.from('bank_connections').update({
      session_id: session.session_id,
      accounts: session.accounts ?? [],
      status: 'active',
      valid_until: session.access?.valid_until ?? null,
      aspsp_name: aspspName,
      aspsp_country: session.aspsp?.country ?? conn.aspsp_country,
      label: conn.label === 'Linked bank' ? `${aspspName} (${new Date().toISOString().slice(0, 10)})` : conn.label,
    }).eq('id', conn.id);

    const n = (session.accounts ?? []).length;
    return page('Bank connected', `${conn.label} is linked (${n} account${n === 1 ? '' : 's'}). ` +
      `You can close this tab — transactions will start appearing in Hearth after the next sync (within a few hours).`);
  } catch (e) {
    console.error(e);
    return page('Unexpected error', String(e?.message ?? e), false);
  }
});
