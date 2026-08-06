# Docbox

A shared document library for two people, built to replace a CamScanner
subscription: scan with the phone, get a clean high-quality searchable PDF, and
have a local LLM name it `YYYYMMDD-what-it-is.pdf` and file it in the right
folder.

Everything runs on your own machine. No cloud, no subscription, no third party
holding your bank statements.

- **Scanner** with edge detection, dewarping, shadow removal and one-tap
  enhancement — our answer to CamScanner's Omnifix. See [`SCANNING.md`](SCANNING.md).
- **Bulk import** of your existing CamScanner library, OCR'd and filed
  automatically. See [`MIGRATING.md`](MIGRATING.md).
- **Home-screen app** for iOS Safari: folders, search inside document text,
  rename, move.
- **Share-sheet ingest** through a small iOS Shortcut. See [`SHORTCUT.md`](SHORTCUT.md).
- **The library is just folders and files.** Point it at a synced folder and both
  of you have the documents in the Files app too. Delete the app tomorrow and the
  documents are still there, well named.

---

## How it works

```
 iOS share sheet ─┐
 camera scan   ───┼──▶  enhance  ──▶  Inbox/  ──▶  worker  ──▶  extract text ──▶ local LLM
 bulk import   ───┤     dewarp        (raw file)              pdf text │ OCR    date/title/type
 web upload    ───┘     de-shadow                                      │             │
                                                                 no text found       ▼
                                                                       ▼        rename + file
                                                              vision model      Finance/Invoices/2024
                                                                       │
                                                                still nothing
                                                                       ▼
                                                        keep the name, flag "check name",
                                                              leave it in the inbox
```

The file is written to disk **before** anything clever happens, and every failure
path keeps it. An offline model, a missing OCR binary, a hopeless scan — each
costs you a rename, never a document. Anything the model is unsure about stays in
the inbox rather than being filed somewhere you will never find it.

---

## Setup

### 1. Install the model

```bash
brew install ollama          # or: https://ollama.com/download
ollama serve &
ollama pull qwen2.5:3b       # ~2 GB, fine on any recent Mac or a mini PC
```

Alternatives: `llama3.2:3b` (faster), `qwen2.5:7b` (better on messy OCR, ~5 GB).

### 2. Install OCR and image tooling

```bash
# macOS
brew install tesseract tesseract-lang poppler
# Debian/Ubuntu
sudo apt install tesseract-ocr tesseract-ocr-deu poppler-utils
```

Without tesseract, PDFs with a text layer still work, scans fall back to their
original names, and PDFs are not searchable. `make status` tells you what you have.

### 3. Run it

```bash
make install
make adduser NAME=you     # prints your Shortcut token
make adduser NAME=her
make run                  # http://localhost:8484
```

Or with Docker, which bundles Ollama, OCR, poppler and OpenCV:

```bash
docker compose up -d
docker compose exec ollama ollama pull qwen2.5:3b
```

### 4. Point it at a folder you already sync (recommended)

```bash
export DOCBOX_LIBRARY_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Documents/Docbox"
```

See [`.env.example`](.env.example) for every setting.

### 5. On each phone

Open the URL in **Safari** → Share → **Add to Home Screen**, then build the
Shortcut from [`SHORTCUT.md`](SHORTCUT.md) (about two minutes) so Docbox appears
in the share sheet.

---

## Using it

| | |
|---|---|
| **Scan** | Take one or more photos → review each page, pick a filter (Auto / Magic / B&W / Grey / Colour / Photo), reorder or delete pages → save as one PDF. |
| **Inbox** | Where everything lands, and where anything the model was unsure about stays. |
| **Auto-filing** | Confident documents move to `Finance/Invoices/2024`, `Medical/2023`, `Insurance`… by the rules in `<data>/routing.json`, which you can edit. |
| **Check name** badge | The model was unsure. Tap, fix the name, save — your name is then pinned and survives every future AI pass. |
| **Search** | Matches names, sender, and the extracted text, so you can find a document by a word inside it. |
| **Import** | Settings → upload a zipped export, or `python -m app.cli import <folder>`. |
| **Preview filing / File everything** | Dry-run the filing rules over the whole library, then apply them. |
| **Delete** | Moves to `.trash/` inside the library. Nothing is destroyed. |

Files copied into the library folder by hand are picked up with `make scan-library`.

---

## Remote access

Docbox binds to your LAN. To use it away from home, pick one:

- **Tailscale** (simplest): install on the server and both phones, use the
  tailnet URL. No ports opened.
- **Cloudflare Tunnel**: `cloudflared tunnel --url http://localhost:8484`.
- **Reverse proxy** (Caddy/nginx) with a real certificate.

Put HTTPS in front of it if it leaves your LAN: the session cookie and the
Shortcut token are bearer credentials.

---

## Layout

```
app/
  main.py      FastAPI routes: auth, documents, scan, import, organize
  enhance.py   the scanner: page detection, dewarp, de-shadow, filters
  pdfbuild.py  high-quality PDFs with a searchable text layer
  importer.py  bulk import of an old library (folder or zip), with hints
  routing.py   the filing rules — which folder a document belongs in
  ingest.py    upload -> inbox (hash dedupe, parallel page enhancement)
  pipeline.py  the job: extract -> analyse -> rename -> file
  worker.py    background thread; queue state in SQLite, so restarts resume
  extract.py   pdf text, OCR, docx, images — every dependency optional
  llm.py       Ollama client, prompt, tolerant JSON parsing, heuristic fallback
  naming.py    slugs, date parsing, YYYYMMDD-title.ext, collision handling
  storage.py   nested folders, path safety, moves, soft delete
  auth.py      scrypt passwords, HMAC sessions, per-user API tokens
  cli.py       adduser / import / organize / reprocess / status
web/           the PWA — plain HTML, CSS and JS, no build step
tests/         84 tests
```

```bash
make test     # no Ollama, OCR or camera needed; all stubbed or synthesised
make status   # what this machine can actually do right now
```

The scanner tests are worth knowing about: they project a page through a real
pinhole camera model, so the true corner positions and the true A4 aspect are
known exactly and the pipeline is measured against them rather than eyeballed.

---

## Things worth knowing before you extend it

- **Auto-filing is conservative on purpose.** Below `confidence_floor` (0.55) or
  when the model was not involved at all, documents stay in the inbox. Loosen it
  in `routing.json` if you would rather have more filed and occasionally wrong.
- **Folders nest up to four levels** (`naming.MAX_FOLDER_DEPTH`). Tapping a
  parent shows everything underneath it.
- **Search is `LIKE`** over names and the first 4 000 characters of extracted
  text. SQLite FTS5 is the obvious upgrade for a large library.
- **One document at a time** through the worker, on purpose: a 3B model on a
  laptop is happier serial. Scan *pages* are parallel; documents are not.
- **The prompt is in `llm.py`** (`SYSTEM_PROMPT`) — the first place to tune if
  names come out wrong. `DOC_TYPES` is the closed vocabulary the rules match on.
- **Filename shape** is `naming.build_filename()`. Want `YYYYMMDD-sender-type-title`?
  One function, and it is unit-tested.
- **Re-enhancing a saved PDF is not possible** — the original photos are gone
  once the PDF is built, which is why the scanner asks for the filter before
  saving. Single-image documents can be re-enhanced (`/api/documents/{id}/enhance`).

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/scan` | photos → one enhanced searchable PDF (`mode`, `crop`, `orient`, `searchable`) |
| `POST` | `/api/enhance/preview` | enhance one image and hand it straight back |
| `POST` | `/api/upload` | multipart `files[]`, optional `folder`, `combine=true` |
| `POST` | `/api/import/zip` | upload a zipped export |
| `POST` | `/api/import/folder` | import a path on the server |
| `GET` | `/api/batches` | import progress |
| `POST` | `/api/organize` | dry-run (`apply:false`) or apply the filing rules |
| `GET`/`PUT` | `/api/routing` | read or replace the filing rules |
| `GET` | `/api/documents` | `?folder=&q=&status=&review=true&deep=true` |
| `GET` | `/api/documents/{id}/file` | inline preview, `?download=true` to save |
| `PATCH` | `/api/documents/{id}` | rename, move, edit fields, pin the name |
| `POST` | `/api/documents/{id}/reprocess` | run the model again |
| `GET` | `/api/health` | model reachable? OCR? OpenCV? worker alive? |

Auth is a session cookie in the browser, or `Authorization: Bearer <token>` for
Shortcuts.
