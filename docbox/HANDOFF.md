# Handoff: setting up Docbox for the Jose family

This is the brief for whoever (or whatever) sets this up on the real machine.
The code is finished and tested; what remains is configuration with real
credentials, which cannot be done from here.

Repository: `docbox/` on branch `claude/shared-doc-library-llm-f8491v`.

---

## What this is

A shared document library for Ajit and Cashmy that replaces CamScanner Premium.
Scan or import a document, and a model reads it, names it
`YYYYMMDD-what-it-is.pdf` and files it into a folder. CamScanner's own auto-export
to Google Drive is the import path, so old scans and new ones both flow in.

## What is already built and tested

| | |
|---|---|
| Scanner | edge detection, dewarping (true page aspect from the camera geometry), shadow removal, Magic/B&W/Grey/Colour filters, multi-page review UI |
| PDFs | real A4 page geometry, 300 dpi target, invisible OCR text layer so scans are searchable |
| Model | provider-agnostic: **Nous Research** (default), OpenAI, OpenRouter, or local Ollama |
| Import | Google Drive (recursive, incremental, dedupes), plus zip and local folder |
| Filing | rules into nested folders; documents about one person go to `Family/<Name>/…` |
| Apps | installable PWA for iOS Safari + an iOS Shortcut for the share sheet |
| Tests | 101, none needing an API key, OCR, a camera or the network |

## What is left to do — the five tasks

Everything below needs a real secret or a real machine, which is why it was not
done already.

### 1. Install and create accounts

```bash
cd docbox
make install
make adduser NAME=ajit
make adduser NAME=cashmy
```

Each command prints an API token — that is what goes in each phone's Shortcut.
Save both.

Install the system tools too, or OCR and searchable PDFs stay off:

```bash
# macOS
brew install tesseract tesseract-lang poppler
# Debian/Ubuntu
sudo apt install tesseract-ocr poppler-utils
```

### 2. Attach the Nous Research API key

```bash
export DOCBOX_LLM_PROVIDER=nous
export DOCBOX_LLM_API_KEY=<the key from portal.nousresearch.com>
export DOCBOX_LLM_MODEL=            # empty = provider default (Hermes-4-70B)
```

Then check what that key can actually reach and pick a model from the list:

```bash
make status
```

`make status` prints the models the key can see. If `Hermes-4-70B` is not among
them, set `DOCBOX_LLM_MODEL` to one that is. Do not guess from documentation —
use that list.

**Say this to Ajit and Cashmy once, plainly:** with a hosted provider, the text
of every document — bank statements, medical letters, payslips, the children's
records — is sent to Nous Research's API to be named. That is the trade for
better naming than a 3B model on a laptop. `DOCBOX_LLM_PROVIDER=ollama` plus
`ollama pull qwen2.5:3b` keeps everything on the machine instead, and nothing
else in the app changes. Their call — but they should make it knowingly.

### 3. Set the household

```bash
export DOCBOX_HOUSEHOLD="Ajit Jose,Cashmy Joy,Aiden John,Abram John,Eva John"
```

The model is told these names, and a document that is clearly *about* one of them
— a medical letter, an ID, a school report, a payslip — is filed under
`Family/Aiden John/Medical` and so on. A gas bill addressed to Ajit is still a
bill; only the person-shaped document types route this way. The list of those
types is `people_rules` in `<data>/routing.json`.

### 4. Connect Google Drive

Full instructions with the exact Google Cloud clicks: **`GDRIVE.md`**. Short
version:

1. Google Cloud → new project → enable the **Google Drive API**.
2. Create a **service account**, download its **JSON key**.
3. In Drive, **share the CamScanner export folder** with the service account's
   email address (Viewer).
4. Configure and verify:

```bash
export DOCBOX_GDRIVE_ENABLED=true
export DOCBOX_GDRIVE_CREDENTIALS=$HOME/.docbox/gdrive.json
export DOCBOX_GDRIVE_FOLDER_NAME=CamScanner
python -m app.cli gdrive-check      # prove it before trusting it
python -m app.cli gdrive-sync       # first pull
```

The watcher then runs every 15 minutes on its own. It is read-only: it never
writes to, moves or deletes anything in Drive.

### 5. Put it on the phones

1. Serve it somewhere both phones can reach — **Tailscale** is the least work
   (install on the server and both phones, use the tailnet URL, no ports opened).
   HTTPS matters if it leaves the LAN: the session cookie and API tokens are
   bearer credentials.
2. On each phone: open the URL in **Safari** → Share → **Add to Home Screen**.
3. Build the two Shortcuts from **`SHORTCUT.md`**: one for the share sheet, one
   that uses Apple's *Scan Document* for a live edge-detection viewfinder. That
   second one replaces the CamScanner icon on the home screen.

iOS Safari cannot put a web app in the share sheet — only Shortcuts can. That is
an Apple limitation, not a missing feature here.

---

## Then: bring the history in, and check the filing

```bash
python -m app.cli gdrive-sync --full     # everything CamScanner ever exported
python -m app.cli status                 # watch the queue drain
python -m app.cli organize               # dry run: prints every proposed move
python -m app.cli organize --apply       # commit it
```

Budget roughly 2–10 seconds per document. A thousand documents is an evening.

**Look at `organize`'s dry run before applying it.** It is the moment to catch a
rule that files things somewhere they do not want, while it is still free to
change. The rules live in `<data>/routing.json` and are plain JSON.

---

## Things to leave alone unless asked

- **The confidence floor.** Anything the model is unsure about deliberately
  stays in the inbox with a *check name* badge. Filing something wrongly is worse
  than not filing it — a document in the wrong folder is lost, one in the inbox
  is merely untidy. If they want more filed automatically, lower
  `confidence_floor` in `routing.json` and expect more mistakes.
- **Pinned names.** Once someone renames a document by hand, no future AI pass
  touches it. That is intentional.
- **The `.trash/` folder.** Deletes are soft. Do not "clean it up" without asking.

## Where to read more

| File | What is in it |
|---|---|
| `README.md` | overview, setup, API, architecture |
| `SCANNING.md` | how the scanner works, the filters, tuning, speed |
| `GDRIVE.md` | Google Drive setup and behaviour |
| `MIGRATING.md` | getting documents out of CamScanner, and the feature comparison |
| `SHORTCUT.md` | the two iOS Shortcuts, step by step |
| `.env.example` | every setting, with comments |

## Known gaps

Not built, and listed here so nobody goes looking: ID card mode, e-signature,
PDF passwords, OCR-to-Word export, and a live edge-detection viewfinder inside
the web app (use the Apple Shortcut for that). Search is `LIKE` over names and
the first 4 000 characters of text — fine for a household library, worth moving
to SQLite FTS5 if it ever gets slow.
