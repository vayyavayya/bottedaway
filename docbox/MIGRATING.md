# Moving in from CamScanner

The goal: every document you have ever scanned, out of a subscription app and
into a folder of plainly named PDFs that you own.

Three steps — get them out, import them, let the model file them.

---

## 1. Get your documents out of CamScanner

Do this while your Premium subscription is still active; export is easier with it.

**From the iOS app (best for keeping multi-page documents intact)**

1. Open a folder → tap **Select** → **Select All**.
2. **Share** → **PDF** (not JPG — PDF keeps the page grouping).
3. **Save to Files** → choose a folder in iCloud Drive, e.g. `CamScanner Export`.
4. Repeat per folder. Keep the folder names — Docbox reads them as a hint about
   what each document is.

**From the desktop web app** (`cs.camscanner.com`) — faster for a big library:
select documents → **Download** → unzip.

**Watch out for**

- Documents still only in the CamScanner cloud: open each once so it syncs down
  before exporting, or export from the web app instead.
- The "Export as JPG" option splits a multi-page document into separate images.
  If that already happened, see `--group-images` below.
- Tag/collection metadata does not export. Folder names do, and they are worth
  keeping.

---

## 2. Import

**From the app** — Settings → *Upload a zipped export*. Zip the export folder
first (on a Mac: right-click → Compress). Good up to a few hundred megabytes.

**From the command line** — the right choice for a large library:

```bash
python -m app.cli import ~/Library/Mobile\ Documents/com~apple~CloudDocs/CamScanner\ Export --user you
```

Options:

| Flag | What it does |
|---|---|
| `--into "Old scans"` | Import into a folder other than the inbox |
| `--group-images` | Rebuild multi-page documents that were exported as `Doc 3_1.jpg`, `Doc 3_2.jpg`, … into single PDFs |
| `--user NAME` | Attribute the import to an account (defaults to the first one) |

What the importer does:

- Walks the tree recursively; skips `.DS_Store`, `._resource` forks, `.ini`
  leftovers and anything that is not a document.
- Skips files it already has, by **content hash** — re-running an import is safe
  and re-importing a renamed copy will not duplicate it.
- Remembers the folder each file came from (`Insurance`, `Bills/2023`) and puts
  that in the prompt, so the model has your own filing as context.
- Records the run as a batch you can watch: `python -m app.cli status`.

Nothing is renamed or moved during the import itself — files land first, and the
worker reads them afterwards. An interrupted import can simply be re-run.

---

## 3. Let it file everything

Each document is OCR'd, read by the local model, renamed `YYYYMMDD-what-it-is`
and moved to a folder by the rules in `<data>/routing.json`.

Expect roughly **2–10 seconds per document** depending on page count, OCR and the
model — a thousand documents is an evening, not a weekend. It runs one at a time
in the background; you can use the app while it works.

Watch it:

```bash
python -m app.cli status         # queue, batches, capabilities
```

### Check the filing before trusting it

```bash
python -m app.cli organize                # dry run: prints every proposed move
python -m app.cli organize --apply        # do it
```

The same two buttons exist in the app under Settings (*Preview filing* /
*File everything*).

Editing `<data>/routing.json` and re-running `organize` reshapes the whole
library. Rules are tried top to bottom, first match wins:

```json
{
  "auto_file": true,
  "confidence_floor": 0.55,
  "keyword_rules": [
    { "name": "car", "keywords": ["kfz", "vehicle registration"], "folder": "Car" }
  ],
  "rules": [
    { "name": "invoices", "doc_type": ["invoice"], "folder": "Finance/Invoices/{year}" }
  ]
}
```

`{year}` and `{yyyymm}` expand from the document's own date, not today's.

**Anything the model is not sure about stays in the inbox.** That is deliberate:
a wrongly filed document is harder to find than an unfiled one. Documents below
`confidence_floor`, and anything that fell back to heuristics, keep their place
and get a *check name* badge.

---

## 4. Once you are happy

- Point `DOCBOX_LIBRARY_DIR` at a synced folder (iCloud Drive, Syncthing, a NAS)
  so both phones see the files in the Files app.
- Build the Shortcut on each phone (`SHORTCUT.md`) so the share sheet and the
  scanner replace the CamScanner icon.
- Cancel the subscription.

## What you keep, and what you lose

| CamScanner Premium | Docbox |
|---|---|
| Edge detection, dewarping, Magic/Omnifix filter | Yes — `app/enhance.py`, see `SCANNING.md` |
| Multi-page PDF, chosen quality | Yes — 300 dpi target, real A4 page geometry |
| OCR + searchable PDF | Yes, with tesseract installed |
| Cloud sync across devices | Your own synced folder — no third-party copy |
| Auto-naming | Better: a local LLM names *and* files by content |
| ID card mode, e-signature, PDF password, book mode | **No** — not built |
| OCR to Word/Excel export | **No** — text extraction only |
| Live edge-detection viewfinder | **No** in the browser; use the Apple *Scan Document* Shortcut for that (`SHORTCUT.md`) |
