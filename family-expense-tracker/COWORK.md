# Cowork runbook — finish setting up Hearth

**Paste this whole file to Claude Cowork on the Mac** (or just say: *"Follow COWORK.md in
family-expense-tracker to set up and deploy this app."*). It has real terminal + network
access on the Mac, so it can do everything this describes.

---

## Goal
Get the **Hearth** family-expense app fully running: a Supabase backend, the AI bill-reader
function deployed, and the web app hosted at an HTTPS URL that installs on two iPhones.

The repo already contains the finished app (`web/`), the database (`supabase/migrations/`),
the AI function (`supabase/functions/analyze-document/`), and an installer
(`scripts/setup.sh`). You are wiring it to live accounts.

## What to ask the human for (collect up front)
1. **Supabase access token** — have them create one at
   https://supabase.com/dashboard/account/tokens (starts `sbp_`).
2. **Supabase project ref** — the `xxxx` in `xxxx.supabase.co`. If they don't have a project
   yet, ask them to click **New project** at https://supabase.com/dashboard (2 minutes), or
   offer to create one for them via the Management API (needs their org id + a DB password).
3. **Anthropic API key** — from https://console.anthropic.com (starts `sk-ant-`).
4. **Which model** for cost/quality: `claude-opus-5` (best), `claude-sonnet-5` (balanced —
   recommend this), or `claude-haiku-4-5` (cheapest).
5. **Where to host** — Netlify, Vercel, or Cloudflare Pages (recommend Netlify).

Handle these secrets carefully: pass them to the tools below, don't print them back, and
don't commit `web/config.js` (it's git-ignored).

## Steps

### 1. Prereqs
```bash
cd family-expense-tracker
command -v supabase || brew install supabase/tap/supabase
command -v node && command -v python3 && command -v curl
```

### 2. Run the installer (backend wiring)
It applies the DB schema + storage bucket, deploys the `analyze-document` function, stores
the Anthropic key as a Function secret, optionally auto-confirms emails, and writes
`web/config.js`. It's interactive — feed it the answers you collected:
```bash
./scripts/setup.sh
```
If you prefer non-interactive, export first, then run:
```bash
export SUPABASE_ACCESS_TOKEN=sbp_...   PROJECT_REF=xxxx
export ANTHROPIC_API_KEY=sk-ant-...    CONFIRM_OFF=Y
./scripts/setup.sh   # still prompts for model + currency; pick 2 and USD (or their choice)
```
Verify it ends with **"Done! ✅"** and that `web/config.js` now has a real URL + anon key.

### 3. Host the `web/` folder over HTTPS
Pick the host they chose. Examples:
```bash
# Netlify (will prompt a browser login the first time)
npx netlify-cli deploy --prod --dir=web

# Vercel
npx vercel deploy web --prod

# Cloudflare Pages
npx wrangler pages deploy web
```
Capture the final **https://…** URL and give it to the human.

### 4. Smoke-test before handing off
- Open the URL in a normal browser. You should see the Hearth **sign-in** screen with no
  console errors.
- Create a test account → **Create household** → open **Settings**, confirm an invite code
  shows. (You can delete this test user later in Supabase → Authentication → Users.)
- If you have any receipt image handy, add it via **＋** and confirm it returns a total and
  items (this exercises the AI function end-to-end). If the function errors, run
  `supabase functions logs analyze-document --project-ref xxxx` and fix.

### 5. Tell the human how to install on their iPhones
> On each phone, open **<the URL>** in **Safari** → tap **Share** → **Add to Home Screen**.
> First person: **Create account → Create household**, then share the invite code from
> **Settings**. Second person: **Create account → Join with code**.

## Success criteria
- `web/config.js` points at the real project.
- `analyze-document` is deployed and has `ANTHROPIC_API_KEY` set (`supabase secrets list --project-ref xxxx`).
- The hosted HTTPS URL loads the sign-in screen.
- A test receipt analyzes without error (if a sample was available).

## If something breaks
- **Anon key empty / project unreachable** → token lacks access to that project ref, or the
  ref is wrong.
- **`analyze-document` 401** → the app must send a logged-in session; make sure you tested
  while signed in.
- **`analyze-document` 500 "ANTHROPIC_API_KEY not configured"** → re-run
  `supabase secrets set --project-ref xxxx ANTHROPIC_API_KEY=... ` then redeploy.
- **Camera won't open on iPhone** → the site must be HTTPS (the host URLs above are).
