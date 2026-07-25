// createClient comes from the vendored UMD bundle loaded in index.html (window.supabase).
const { createClient } = window.supabase || {};

const cfg = window.APP_CONFIG || {};

export const CONFIG_OK =
  !window.__CONFIG_MISSING__ &&
  typeof createClient === 'function' &&
  cfg.SUPABASE_URL &&
  cfg.SUPABASE_ANON_KEY &&
  !cfg.SUPABASE_URL.includes('YOUR-PROJECT');

export const DEFAULT_CURRENCY = cfg.DEFAULT_CURRENCY || 'USD';

export const supabase = CONFIG_OK
  ? createClient(cfg.SUPABASE_URL, cfg.SUPABASE_ANON_KEY, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    })
  : null;
