import { supabase } from './supabaseClient.js';
import { normalizeImage, imageToPdf } from './pdf.js';

// ---------- Auth ----------
export const auth = {
  session: () => supabase.auth.getSession().then((r) => r.data.session),
  onChange: (cb) => supabase.auth.onAuthStateChange((_e, session) => cb(session)),
  signUp: (email, password) => supabase.auth.signUp({ email, password }),
  signIn: (email, password) => supabase.auth.signInWithPassword({ email, password }),
  signOut: () => supabase.auth.signOut(),
  userId: async () => (await supabase.auth.getUser()).data.user?.id ?? null,
  email: async () => (await supabase.auth.getUser()).data.user?.email ?? null,
};

// ---------- Household ----------
export async function getMyHousehold() {
  const { data, error } = await supabase
    .from('household_members')
    .select('role, display_name, households(*)')
    .order('joined_at', { ascending: true })
    .limit(1)
    .maybeSingle();
  if (error) throw error;
  if (!data || !data.households) return null;
  return {
    household: data.households,
    membership: { role: data.role, display_name: data.display_name },
  };
}

export async function createHousehold(name, displayName) {
  const { data, error } = await supabase.rpc('create_household', {
    p_name: name,
    p_display_name: displayName || null,
  });
  if (error) throw error;
  return Array.isArray(data) ? data[0] : data;
}

export async function joinHousehold(code, displayName) {
  const { data, error } = await supabase.rpc('join_household', {
    p_code: code,
    p_display_name: displayName || null,
  });
  if (error) throw error;
  return Array.isArray(data) ? data[0] : data;
}

export async function getMembers(householdId) {
  const { data } = await supabase
    .from('household_members')
    .select('user_id, role, display_name')
    .eq('household_id', householdId);
  return data || [];
}

// ---------- Categories ----------
export async function getCategories(householdId) {
  const { data, error } = await supabase
    .from('categories')
    .select('*')
    .eq('household_id', householdId)
    .order('sort_order');
  if (error) throw error;
  return data || [];
}

// ---------- Upload + AI analysis ----------
export async function uploadAndAnalyze({ householdId, file, docType, onStatus }) {
  const isPdf = file.type === 'application/pdf' || /\.pdf$/i.test(file.name || '');
  const isImage = !isPdf;

  onStatus?.('Saving document…');
  const userId = await auth.userId();
  const { data: doc, error } = await supabase
    .from('documents')
    .insert({
      household_id: householdId,
      uploaded_by: userId,
      doc_type: docType,
      original_filename: file.name || null,
      mime_type: isPdf ? 'application/pdf' : 'image/jpeg',
      status: 'uploaded',
    })
    .select()
    .single();
  if (error) throw error;

  const base = `${householdId}/${doc.id}`;
  let storagePath;
  let pdfPath = null;

  if (isImage) {
    onStatus?.('Preparing photo…');
    const { jpegBlob, dataUrl, width, height } = await normalizeImage(file);
    storagePath = `${base}/original.jpg`;
    const up1 = await supabase.storage.from('documents')
      .upload(storagePath, jpegBlob, { contentType: 'image/jpeg', upsert: true });
    if (up1.error) throw up1.error;

    // Store a PDF copy of the bill, as requested.
    const pdfBlob = imageToPdf(dataUrl, width, height);
    pdfPath = `${base}/document.pdf`;
    await supabase.storage.from('documents')
      .upload(pdfPath, pdfBlob, { contentType: 'application/pdf', upsert: true });
  } else {
    const ext = (file.name?.split('.').pop() || 'pdf').toLowerCase();
    storagePath = `${base}/original.${ext}`;
    const up = await supabase.storage.from('documents')
      .upload(storagePath, file, { contentType: 'application/pdf', upsert: true });
    if (up.error) throw up.error;
    pdfPath = storagePath;
  }

  await supabase.from('documents')
    .update({ storage_path: storagePath, pdf_path: pdfPath })
    .eq('id', doc.id);

  onStatus?.('Reading with AI…');
  const { data: result, error: fnErr } = await supabase.functions.invoke('analyze-document', {
    body: { document_id: doc.id },
  });
  if (fnErr) {
    let msg = fnErr.message || 'Analysis failed';
    try {
      const body = await fnErr.context?.json?.();
      if (body?.error) msg = body.error;
    } catch { /* ignore */ }
    throw new Error(msg);
  }
  if (result?.error) throw new Error(result.error);
  return { document: doc, result };
}

// ---------- Documents ----------
export async function listDocuments(householdId) {
  const { data, error } = await supabase
    .from('documents')
    .select('*, receipts(merchant, total, currency, purchased_at)')
    .eq('household_id', householdId)
    .order('created_at', { ascending: false });
  if (error) throw error;
  return data || [];
}

export async function getDocumentDetail(docId) {
  const [{ data: doc }, { data: receipts }, { data: txns }] = await Promise.all([
    supabase.from('documents').select('*').eq('id', docId).single(),
    supabase.from('receipts')
      .select('*, categories(name, icon, color), line_items(*)')
      .eq('document_id', docId),
    supabase.from('transactions')
      .select('*, categories(name, icon, color)')
      .eq('document_id', docId)
      .order('txn_date', { ascending: true }),
  ]);
  return { doc, receipt: receipts?.[0] || null, transactions: txns || [] };
}

export async function deleteDocument(doc) {
  // Remove ledger rows that wouldn't cascade (bank-statement lines have no receipt).
  await supabase.from('transactions').delete().eq('document_id', doc.id);
  const paths = [doc.storage_path, doc.pdf_path].filter(Boolean)
    .filter((v, i, a) => a.indexOf(v) === i);
  if (paths.length) await supabase.storage.from('documents').remove(paths);
  const { error } = await supabase.from('documents').delete().eq('id', doc.id);
  if (error) throw error;
}

export async function signedUrl(path) {
  if (!path) return null;
  const { data } = await supabase.storage.from('documents').createSignedUrl(path, 3600);
  return data?.signedUrl || null;
}

// ---------- Transactions / insights ----------
export async function getTransactions(householdId, fromDate, toDate) {
  const { data, error } = await supabase
    .from('transactions')
    .select('id, txn_date, merchant, description, amount, direction, currency, category_id, source, categories(name, icon, color)')
    .eq('household_id', householdId)
    .eq('excluded', false)          // self-transfers between own accounts stay hidden
    .gte('txn_date', fromDate)
    .lte('txn_date', toDate)
    .order('txn_date', { ascending: false });
  if (error) throw error;
  return data || [];
}

export async function updateTransactionCategory(txnId, categoryId) {
  const { error } = await supabase.from('transactions')
    .update({ category_id: categoryId }).eq('id', txnId);
  if (error) throw error;
}

// ---------- Assistant ----------
export async function askAssistant(question, history) {
  const { data, error } = await supabase.functions.invoke('ask', {
    body: { question, history },
  });
  if (error) {
    let msg = error.message || 'Assistant unavailable';
    try {
      const body = await error.context?.json?.();
      if (body?.error) msg = body.error;
    } catch { /* ignore */ }
    throw new Error(msg);
  }
  if (data?.error) throw new Error(data.error);
  return data.answer;
}
