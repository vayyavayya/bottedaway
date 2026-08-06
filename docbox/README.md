# Docbox

A shared document library for two people, with an inbox you can dump anything
into and a small local LLM that reads each document and renames it
`YYYYMMDD-what-it-is.pdf`.

Scan a bank letter with your phone, it arrives as `IMG_0042.pdf`, and a few
seconds later it is `20240317-stadtwerke-electricity-bill.pdf` — filed, searchable,
and never sent to anyone else's computer.

- **Home-screen app** for iOS Safari (PWA): folders, search, camera scanning,
  rename, move.
- **Share-sheet ingest** via a small iOS Shortcut — see [`SHORTCUT.md`](SHORTCUT.md).
- **Local model only.** Ollama on your machine. Nothing leaves the house.
- **The library is just folders and files.** Point it at a synced folder and both
  of you have the documents in the Files app too. Delete the app tomorrow and the
  documents are still there, well named.

---

## How it works

```
 iOS share sheet ─┐
 camera scan   ───┼──▶  Inbox/  ──▶  worker  ──▶  extract text  ──▶  local LLM  ──▶  rename
 web upload    ───┘     (raw file)               pdf text │ OCR      date/title       on disk
                                                          │
                                                    no text found
                                                          ▼
                                              vision model (optional)
                                                          │
                                                   still nothing
                                                          ▼
                                          date scraped from text + flagged "check name"
```

The file is written to disk **before** anything clever happens, and every failure
path keeps the file and flags it for review. An offline model, a broken scan, or
a document in a language the model mangles costs you a rename, never a document.

---

## Setup

### 1. Install the model

```bash
brew install ollama          # or: https://ollama.com/download
ollama serve &
ollama pull qwen2.5:3b       # ~2 GB, runs fine on any recent Mac or a mini PC
```

`qwen2.5:3b` is a good default. Alternatives worth trying: `llama3.2:3b`
(faster), `qwen2.5:7b` (noticeably better on messy OCR, ~5 GB).

### 2. Install OCR (for anything scanned)

```bash
brew install tesseract tesseract-lang poppler   # macOS
sudo apt install tesseract-ocr tesseract-ocr-deu poppler-utils   # Debian/Ubuntu
```

Without these, PDFs with a text layer still work; photos and scans fall back to
their original names and get flagged.

### 3. Run Docbox

```bash
make install
make adduser NAME=you     # prints your Shortcut token
make adduser NAME=her
make run                  # http://localhost:8484
```

Or with Docker (bundles Ollama, OCR and poppler):

```bash
docker compose up -d
docker compose exec ollama ollama pull qwen2.5:3b
```

Then open the app, add it to your home screen, and build the Shortcut:
[`SHORTCUT.md`](SHORTCUT.md).

### 4. Point it at a folder you already sync (optional, recommended)

```bash
export DOCBOX_LIBRARY_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Documents/Docbox"
```

Both of you then see the same named files in the iOS Files app, with or without
the web app. See [`.env.example`](.env.example) for every setting.

---

## Using it

| | |
|---|---|
| **Inbox** | Everything lands here. It is the pile you clean up when you feel like it. |
| **Scan** | Camera → multiple photos become one PDF, in order. |
| **Upload** | Any file from the Files app. |
| **Check name** badge | The model was unsure. Tap, fix the name, save — your name is then pinned and survives future AI passes. |
| **Rename with AI** | Re-runs the model, e.g. after installing a better one. |
| **Search** | Matches file names, sender, and the extracted text — so you can find a document by a word inside it. |
| **Delete** | Moves to `.trash/` inside the library. Nothing is destroyed. |

Files you copy into the library folder by hand are picked up with
`make scan-library`.

---

## Remote access

Docbox binds to your LAN by default. To use it away from home, pick one:

- **Tailscale** (simplest): install on the server and both phones, then use the
  tailnet URL. No ports opened.
- **Cloudflare Tunnel**: `cloudflared tunnel --url http://localhost:8484` gives
  you an HTTPS hostname.
- **Reverse proxy** (Caddy/nginx) with a real certificate.

Put HTTPS in front of it if it leaves your LAN: the session cookie and the
Shortcut token are bearer credentials.

---

## Layout

```
app/
  main.py      FastAPI routes: auth, documents, upload, share target
  ingest.py    upload -> inbox (dedupe by hash, images -> single PDF, links)
  pipeline.py  the job: extract -> analyse -> rename, with the fallback ladder
  worker.py    background thread; queue state lives in SQLite so restarts resume
  extract.py   pdf text, OCR, docx, images — every dependency optional
  llm.py       Ollama client, prompt, tolerant JSON parsing, heuristic fallback
  naming.py    slugs, date parsing, YYYYMMDD-title.ext, collision handling
  storage.py   path safety, moves, soft delete
  auth.py      scrypt passwords, HMAC sessions, per-user API tokens
  cli.py       adduser / token / status / scan-library / reprocess
web/           the PWA — plain HTML, CSS and JS, no build step
tests/         33 tests, including a stub Ollama for the full rename flow
```

```bash
make test     # no Ollama or OCR needed; both are stubbed or disabled
make status   # what the box can actually do right now
```

---

## Things worth knowing before you extend it

- **Auth is deliberately small** — two accounts, shared library, no per-document
  permissions. Adding roles means touching `auth.py` and every route.
- **Search is `LIKE`** over names and the first 4 000 characters of extracted
  text. SQLite FTS5 is the obvious upgrade if the library gets large.
- **Folders are one level deep.** Nesting means changing `safe_folder()`,
  `storage.folder_path()` and the folder chips in `web/app.js`.
- **One document at a time** through the worker, on purpose: a 3B model on a
  laptop is happier serial. Raise it in `worker.py` if you have a GPU.
- **The model prompt is in `llm.py`** (`SYSTEM_PROMPT`) — that is the first place
  to tune if the names come out wrong. `DOC_TYPES` is the closed vocabulary.
- **Filename shape** is `naming.build_filename()`. Want
  `YYYYMMDD-sender-type-title`? It is one function and it is unit-tested.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/upload` | multipart `files[]`, optional `folder`, `combine=true` |
| `POST` | `/api/scan` | images in order → one PDF |
| `POST` | `/api/link` | `{url, title, note}` |
| `GET` | `/api/documents` | `?folder=&q=&status=&review=true` |
| `GET` | `/api/documents/{id}/file` | inline preview, `?download=true` to save |
| `PATCH` | `/api/documents/{id}` | rename, move, edit fields, pin the name |
| `POST` | `/api/documents/{id}/reprocess` | run the model again |
| `GET` | `/api/health` | model reachable? OCR installed? worker alive? |

Auth is a session cookie in the browser, or `Authorization: Bearer <token>` for
Shortcuts.
