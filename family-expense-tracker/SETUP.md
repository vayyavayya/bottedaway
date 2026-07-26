# Setup guide — Hearth

About **15 minutes**, mostly copy-paste. You'll create a free Supabase project, load the
database, deploy the AI function, host the app, and install it on both iPhones.

You need:
- A free [Supabase](https://supabase.com) account.
- An [Anthropic API key](https://console.anthropic.com) (for the bill reading). Pay-as-you-go.
- 5 minutes of terminal time for two commands (deploying the function).

---

## ⚡ Fast path (one script does steps 2–5)

If you'd rather not do steps 2–5 by hand, run the installer — it applies the database,
deploys the AI function, stores your key, and writes `config.js` for you. Your secrets
never leave your machine.

1. Create a Supabase project (dashboard → **New project**) and note its **ref** (the
   `xxxx` in `xxxx.supabase.co`).
2. Create a Supabase **access token**: dashboard → **Account → Access Tokens**.
3. Install the Supabase CLI: `brew install supabase/tap/supabase` (or `npm i -g supabase`).
4. Run it:
   ```bash
   cd family-expense-tracker
   ./scripts/setup.sh
   ```
   It'll ask for the token, project ref, your Anthropic key, and a model choice — then do
   the rest. When it finishes, jump to **step 6 (Host the app)** below.

Prefer to understand each piece? Do it manually below instead.

---

---

## 1. Create a Supabase project

1. Go to [supabase.com](https://supabase.com) → **New project**. Pick a name and a strong
   database password. Wait ~2 minutes for it to provision.
2. Open **Project Settings → API** and keep this tab handy. You'll need:
   - **Project URL** (e.g. `https://abcd1234.supabase.co`)
   - **anon public** key

---

## 2. Load the database

1. In Supabase, open **SQL Editor → New query**.
2. Paste the entire contents of `supabase/migrations/0001_init.sql`, click **Run**.
3. New query again → paste `supabase/migrations/0002_storage.sql`, click **Run**.

That creates the tables, the private `documents` storage bucket, Row Level Security,
and the household helper functions.

---

## 3. Deploy the AI function (bill reader)

This runs on Supabase and holds your Anthropic key so it never reaches the phones.

Install the Supabase CLI (once):

```bash
# macOS
brew install supabase/tap/supabase
# or npm (any OS)
npm install -g supabase
```

Then, from inside the `family-expense-tracker/` folder:

```bash
supabase login
supabase link --project-ref YOUR_PROJECT_REF        # the abcd1234 from your URL
supabase functions deploy analyze-document
supabase secrets set ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Optional — control AI cost.** The reader defaults to the top-quality `claude-opus-5`
model. To use a cheaper/faster model, set:

```bash
# Good balance of price and quality:
supabase secrets set ANTHROPIC_MODEL=claude-sonnet-5
# Cheapest:
supabase secrets set ANTHROPIC_MODEL=claude-haiku-4-5
```

(`SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` are provided to the
function automatically — you don't set those.)

---

## 4. Turn on email login

In Supabase → **Authentication → Providers → Email**: it's on by default.

- For a smooth two-person start you can turn **“Confirm email” off** (Authentication →
  Providers → Email). Then sign-up logs you straight in.
- If you leave it on, each of you confirms via a link in your inbox before first sign-in.

---

## 5. Configure the app

1. Copy the example config:
   ```bash
   cp web/config.example.js web/config.js
   ```
2. Edit `web/config.js` and paste your **Project URL** and **anon** key from step 1.
   Optionally set `DEFAULT_CURRENCY` (e.g. `"USD"`, `"INR"`, `"EUR"`).

The anon key is safe in the browser — Row Level Security is what protects your data.

---

## 6. Host the app

The app is just static files in `web/`. Any static host works. Easiest options:

**Netlify (drag-and-drop, no account gymnastics)**
1. Go to [app.netlify.com/drop](https://app.netlify.com/drop).
2. Drag the **`web`** folder onto the page. You get a URL like `https://something.netlify.app`.

**Vercel**
```bash
npm i -g vercel
cd web && vercel --prod
```

**Test locally first (optional)**
```bash
cd web && python3 -m http.server 8080
# open http://localhost:8080
```

> One requirement: it must be served over **HTTPS** (Netlify/Vercel do this automatically).
> The camera, service worker, and “Add to Home Screen” all need HTTPS. `localhost` is fine for testing.

---

## 7. Add the CORS-friendly URL (already handled)

The AI function already allows requests from any origin, so your Netlify/Vercel URL works
out of the box. Nothing to configure.

---

## 8. Install on your iPhones 📱

On **each** phone:
1. Open the hosted URL in **Safari** (must be Safari for install to work).
2. Tap the **Share** button (the square with an up-arrow).
3. Tap **Add to Home Screen** → **Add**.
4. Launch **Hearth** from the home screen — it opens full-screen like a normal app.

---

## 9. First run

1. **You:** open Hearth → **Create account** → then **Create household** (name it, e.g. “The Smiths”).
2. Go to **Settings** → copy the **invite code**.
3. **Your partner:** installs the app, taps **Create account**, then **Join with code** and enters it.
4. Tap **＋** to snap your first grocery bill. It's saved as a PDF, itemized, and added to your month.

---

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| App says “Almost there / config.js” | You skipped step 5, or the URL/key still says `YOUR-PROJECT`. |
| “Analysis failed” after snapping | Check the function has the key: `supabase secrets list`. Redeploy with `supabase functions deploy analyze-document`. |
| Camera doesn't open | The site must be **HTTPS**. Use the Netlify/Vercel URL, not a plain `http://` address. |
| Can't add to Home Screen | Use **Safari** (not Chrome) on iOS; the option only appears there. |
| Partner can't see your data | Make sure they **Joined with the code** rather than creating a new household. |
| Bank statement missed some rows | Very long/low-quality scans are harder; try a clearer PDF, or split it. |

## Regenerating the icons (optional)

```bash
node scripts/generate-icons.mjs
```

## What it costs

- **Supabase**: free tier is plenty for a family.
- **Anthropic**: pay per bill analyzed. A receipt is a small request; switch
  `ANTHROPIC_MODEL` to `claude-haiku-4-5` (step 3) to minimize cost.
