// Supabase Edge Function: analyze-document
//
// Receives a { document_id }, downloads the stored image/PDF, asks Claude to read
// and itemise it, and writes structured rows (receipt + line items + ledger
// transactions) back to the database.
//
// The ANTHROPIC_API_KEY lives only here as a Function secret — it is never shipped
// to the phones/browser.
//
// Required Function secrets (set with `supabase secrets set ...`):
//   ANTHROPIC_API_KEY   — your Anthropic API key
//   ANTHROPIC_MODEL     — optional, defaults to claude-opus-5
// SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are injected automatically.

import { createClient } from 'npm:@supabase/supabase-js@2';
import { corsHeaders, json } from '../_shared/cors.ts';

const ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages';
const MODEL = Deno.env.get('ANTHROPIC_MODEL') ?? 'claude-opus-5';

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: corsHeaders });
  if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405);

  try {
    const authHeader = req.headers.get('Authorization') ?? '';
    if (!authHeader) return json({ error: 'missing authorization' }, 401);

    const { document_id } = await req.json().catch(() => ({}));
    if (!document_id) return json({ error: 'document_id is required' }, 400);

    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const anonKey = Deno.env.get('SUPABASE_ANON_KEY')!;
    const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const anthropicKey = Deno.env.get('ANTHROPIC_API_KEY');
    if (!anthropicKey) return json({ error: 'ANTHROPIC_API_KEY not configured' }, 500);

    // Caller-scoped client: RLS ensures the user can only see their own household's
    // document. If the select returns nothing, they aren't allowed to touch it.
    const userClient = createClient(supabaseUrl, anonKey, {
      global: { headers: { Authorization: authHeader } },
    });
    const { data: userData } = await userClient.auth.getUser();
    const user = userData?.user;
    if (!user) return json({ error: 'invalid session' }, 401);

    const { data: doc, error: docErr } = await userClient
      .from('documents')
      .select('*')
      .eq('id', document_id)
      .single();
    if (docErr || !doc) return json({ error: 'document not found or access denied' }, 403);

    // Privileged client for storage download + writes.
    const admin = createClient(supabaseUrl, serviceKey);

    await admin.from('documents').update({ status: 'processing', error_message: null })
      .eq('id', document_id);

    // Household categories drive the classification enum.
    const { data: cats } = await admin
      .from('categories')
      .select('id, name')
      .eq('household_id', doc.household_id)
      .order('sort_order');
    const categoryNames = (cats ?? []).map((c) => c.name);
    const catIdByName = new Map((cats ?? []).map((c) => [c.name.toLowerCase(), c.id]));
    const otherId = catIdByName.get('other') ?? (cats?.[0]?.id ?? null);
    const resolveCat = (name?: string) =>
      (name && catIdByName.get(name.toLowerCase())) || otherId;

    // Download the stored file.
    const { data: file, error: dlErr } = await admin.storage
      .from('documents')
      .download(doc.storage_path);
    if (dlErr || !file) {
      await fail(admin, document_id, 'could not download stored file');
      return json({ error: 'could not download stored file' }, 500);
    }
    const bytes = new Uint8Array(await file.arrayBuffer());
    const base64 = base64Encode(bytes);
    const mime = doc.mime_type || guessMime(doc.storage_path);
    const isPdf = mime === 'application/pdf';

    // Build the model request.
    const isStatement = doc.doc_type === 'bank_statement';
    const schema = isStatement
      ? statementSchema(categoryNames)
      : receiptSchema(categoryNames);
    const prompt = isStatement
      ? statementPrompt(categoryNames)
      : receiptPrompt(doc.doc_type, categoryNames);

    const fileBlock = isPdf
      ? { type: 'document', source: { type: 'base64', media_type: 'application/pdf', data: base64 } }
      : { type: 'image', source: { type: 'base64', media_type: mime, data: base64 } };

    const body = {
      model: MODEL,
      max_tokens: 8000,
      output_config: {
        effort: 'low',
        format: { type: 'json_schema', schema },
      },
      messages: [
        { role: 'user', content: [fileBlock, { type: 'text', text: prompt }] },
      ],
    };

    const aiResp = await fetch(ANTHROPIC_API_URL, {
      method: 'POST',
      headers: {
        'x-api-key': anthropicKey,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!aiResp.ok) {
      const errText = await aiResp.text();
      await fail(admin, document_id, `AI request failed: ${aiResp.status}`);
      return json({ error: 'AI request failed', detail: errText }, 502);
    }

    const aiJson = await aiResp.json();
    if (aiJson.stop_reason === 'refusal') {
      await fail(admin, document_id, 'The model declined to analyse this document.');
      return json({ error: 'analysis refused' }, 422);
    }
    const textBlock = (aiJson.content ?? []).find((b: any) => b.type === 'text');
    if (!textBlock) {
      await fail(admin, document_id, 'empty model response');
      return json({ error: 'empty model response' }, 502);
    }
    const parsed = JSON.parse(textBlock.text);

    if (isStatement) {
      const result = await saveStatement(admin, doc, user.id, parsed, resolveCat);
      await admin.from('documents').update({ status: 'analyzed' }).eq('id', document_id);
      return json({ ok: true, type: 'bank_statement', ...result });
    } else {
      const result = await saveReceipt(admin, doc, user.id, parsed, resolveCat);
      await admin.from('documents').update({ status: 'analyzed' }).eq('id', document_id);
      return json({ ok: true, type: doc.doc_type, ...result });
    }
  } catch (e) {
    return json({ error: 'unexpected error', detail: String(e) }, 500);
  }
});

// --------------------------------------------------------------------------
async function fail(admin: any, id: string, message: string) {
  await admin.from('documents').update({ status: 'failed', error_message: message }).eq('id', id);
}

async function saveReceipt(admin: any, doc: any, userId: string, p: any, resolveCat: (n?: string) => any) {
  const total = num(p.total);
  const { data: receipt } = await admin.from('receipts').insert({
    document_id: doc.id,
    household_id: doc.household_id,
    merchant: p.merchant || null,
    purchased_at: p.purchased_at || null,
    currency: p.currency || 'USD',
    subtotal: num(p.subtotal),
    tax: num(p.tax),
    total,
    category_id: resolveCat(p.category),
    raw_analysis: p,
    created_by: userId,
  }).select().single();

  const items = Array.isArray(p.line_items) ? p.line_items : [];
  if (items.length && receipt) {
    await admin.from('line_items').insert(
      items.map((it: any, i: number) => ({
        receipt_id: receipt.id,
        description: it.description || null,
        quantity: num(it.quantity),
        unit_price: num(it.unit_price),
        amount: num(it.amount),
        category_id: resolveCat(it.category),
        position: i,
      })),
    );
  }

  // One ledger transaction for the receipt total.
  await admin.from('transactions').insert({
    household_id: doc.household_id,
    document_id: doc.id,
    receipt_id: receipt?.id ?? null,
    txn_date: p.purchased_at || new Date().toISOString().slice(0, 10),
    merchant: p.merchant || null,
    description: p.merchant || doc.doc_type,
    amount: Math.abs(total || 0),
    direction: 'debit',
    currency: p.currency || 'USD',
    category_id: resolveCat(p.category),
    source: doc.doc_type === 'utility_bill' ? 'utility_bill' : 'receipt',
    created_by: userId,
  });

  return { receipt, line_item_count: items.length, total };
}

async function saveStatement(admin: any, doc: any, userId: string, p: any, resolveCat: (n?: string) => any) {
  const txns = Array.isArray(p.transactions) ? p.transactions : [];
  const rows = txns
    .filter((t: any) => t && (t.amount != null))
    .map((t: any) => ({
      household_id: doc.household_id,
      document_id: doc.id,
      txn_date: t.date || new Date().toISOString().slice(0, 10),
      merchant: t.merchant || null,
      description: t.description || t.merchant || 'Statement line',
      amount: Math.abs(num(t.amount) || 0),
      direction: t.direction === 'credit' ? 'credit' : 'debit',
      currency: p.currency || 'USD',
      category_id: resolveCat(t.category),
      source: 'bank_statement',
      created_by: userId,
    }));
  if (rows.length) await admin.from('transactions').insert(rows);
  return { transaction_count: rows.length };
}

function num(v: any): number | null {
  if (v === null || v === undefined || v === '') return null;
  const n = typeof v === 'number' ? v : parseFloat(String(v).replace(/[^0-9.-]/g, ''));
  return Number.isFinite(n) ? n : null;
}

function guessMime(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase();
  if (ext === 'png') return 'image/png';
  if (ext === 'webp') return 'image/webp';
  if (ext === 'pdf') return 'application/pdf';
  if (ext === 'heic' || ext === 'heif') return 'image/jpeg';
  return 'image/jpeg';
}

function base64Encode(bytes: Uint8Array): string {
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

// --------------------------------------------------------------------------
// Prompts + schemas
// --------------------------------------------------------------------------
function receiptPrompt(docType: string, categories: string[]): string {
  const what = docType === 'utility_bill' ? 'utility bill' : 'store receipt';
  return [
    `You are reading a photo of a ${what}. Extract the details accurately.`,
    `- merchant: the store / provider name.`,
    `- purchased_at: the transaction or bill date as YYYY-MM-DD (empty string if not visible).`,
    `- currency: 3-letter code (guess from symbols; default USD).`,
    `- subtotal, tax, total: numeric amounts (0 if not shown). "total" is the final amount paid or due.`,
    `- category: pick the single best fit from: ${categories.join(', ')}.`,
    `- line_items: each purchased item with description, quantity, unit_price, amount, and its own best-fit category.`,
    `If this is a utility bill with no itemisation, return an empty line_items array and put the amount due in total.`,
    `Only output the structured object.`,
  ].join('\n');
}

function statementPrompt(categories: string[]): string {
  return [
    `You are reading a bank or credit-card statement. Extract every transaction line you can see.`,
    `For each transaction:`,
    `- date: YYYY-MM-DD.`,
    `- description: the raw statement text.`,
    `- merchant: a cleaned-up merchant name if you can infer one.`,
    `- amount: the absolute value as a positive number.`,
    `- direction: "debit" for money spent/withdrawn, "credit" for money received/refunded/deposited.`,
    `- category: the single best fit from: ${categories.join(', ')}.`,
    `Ignore running balances, headers, and summary rows — only real transactions.`,
    `Only output the structured object.`,
  ].join('\n');
}

function categoryEnum(categories: string[]) {
  const list = categories.length ? categories : ['Other'];
  return { type: 'string', enum: list };
}

function receiptSchema(categories: string[]) {
  return {
    type: 'object',
    additionalProperties: false,
    properties: {
      merchant: { type: 'string' },
      purchased_at: { type: 'string', description: 'YYYY-MM-DD or empty' },
      currency: { type: 'string' },
      subtotal: { type: 'number' },
      tax: { type: 'number' },
      total: { type: 'number' },
      category: categoryEnum(categories),
      line_items: {
        type: 'array',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            description: { type: 'string' },
            quantity: { type: 'number' },
            unit_price: { type: 'number' },
            amount: { type: 'number' },
            category: categoryEnum(categories),
          },
          required: ['description', 'quantity', 'unit_price', 'amount', 'category'],
        },
      },
    },
    required: ['merchant', 'purchased_at', 'currency', 'subtotal', 'tax', 'total', 'category', 'line_items'],
  };
}

function statementSchema(categories: string[]) {
  return {
    type: 'object',
    additionalProperties: false,
    properties: {
      account_label: { type: 'string' },
      currency: { type: 'string' },
      transactions: {
        type: 'array',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            date: { type: 'string', description: 'YYYY-MM-DD' },
            description: { type: 'string' },
            merchant: { type: 'string' },
            amount: { type: 'number' },
            direction: { type: 'string', enum: ['debit', 'credit'] },
            category: categoryEnum(categories),
          },
          required: ['date', 'description', 'merchant', 'amount', 'direction', 'category'],
        },
      },
    },
    required: ['account_label', 'currency', 'transactions'],
  };
}
