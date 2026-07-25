# Hearth — Family Finances 📊

A private, installable app for you and your partner to snap grocery bills, upload
bank statements and utility bills, and see where the family's money goes each month.

- **Snap a bill** → it's saved as a **PDF**, read and itemized by AI, and added to your spending.
- **Upload a bank statement (PDF or photo)** → every transaction is extracted and categorized.
- **Monthly insights** → totals, category breakdown, top merchants, and trends vs. last month.
- **Shared** → you and your partner see the same data via a private household.
- **Installs on both iPhones** — no App Store needed. Open in Safari → *Share* → *Add to Home Screen*.

## How it's built

| Piece | Tech | Why |
|------|------|-----|
| App | Progressive Web App (vanilla JS, no build step) | Installs on iPhone from Safari; hostable as static files |
| Data + login + storage | [Supabase](https://supabase.com) (Postgres + Auth + Storage) | Private cloud sync between both phones, with Row Level Security |
| Bill/statement reading | [Claude](https://www.anthropic.com) via a Supabase Edge Function | Your API key stays server-side, never on the phones |

```
 iPhone (PWA)  ──▶  Supabase Auth / Postgres / Storage   (your private data)
      │                       ▲
      └── analyze ──▶  Edge Function ──▶  Claude API   (reads & itemizes bills)
                        (holds the ANTHROPIC_API_KEY)
```

## Project layout

```
family-expense-tracker/
├── web/                     # the installable app (deploy this folder as a static site)
│   ├── index.html
│   ├── config.example.js    # copy to config.js and add your Supabase keys
│   ├── js/  css/  icons/
│   └── sw.js  manifest.webmanifest
├── supabase/
│   ├── migrations/          # run these in the Supabase SQL editor
│   └── functions/analyze-document/   # the AI edge function
└── scripts/generate-icons.mjs        # regenerates the app icons
```

## Get started

See **[SETUP.md](./SETUP.md)** — about 15 minutes, mostly copy-paste. No coding required.

## Privacy

Your bills and statements live in **your own** Supabase project. Row Level Security means
only members of your household can read them. The only data that leaves your project is the
image/PDF you choose to analyze, sent to the Anthropic API for reading — and only from the
server-side function, never broadcast from the phones.
