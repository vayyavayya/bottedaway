# Google Drive import

CamScanner auto-exports to Google Drive. Point Docbox at that folder and the
loop closes: scan on the phone → CamScanner drops a PDF in Drive → Docbox picks
it up within minutes, OCRs it, names it and files it. Nothing to press.

It also works for anything else that lands in a Drive folder — a scanner that
emails to Drive, a shared folder, files you drop in yourself.

---

## Setting it up (about ten minutes, once)

A **service account** is the right choice here: it needs no browser, no
re-consent every week, and it can only see folders you explicitly share with it.

### 1. Make the service account

1. Go to <https://console.cloud.google.com/> and create a project (any name).
2. **APIs & Services → Library → Google Drive API → Enable**.
3. **APIs & Services → Credentials → Create credentials → Service account**.
   Name it `docbox`, skip the optional role and user steps, **Done**.
4. Click the new service account → **Keys → Add key → Create new key → JSON**.
   A `.json` file downloads. Keep it — it is a credential.
5. Copy the service account's **email address**. It looks like
   `docbox@your-project-123456.iam.gserviceaccount.com`.

### 2. Share the CamScanner folder with it

In Google Drive, right-click the folder CamScanner exports into → **Share** →
paste that email → **Viewer** → Send. (Google may warn that it is not a normal
account; that is expected.)

Sharing one folder is the whole security boundary: the service account cannot
see anything else in your Drive.

### 3. Tell Docbox

```bash
# put the key somewhere the app can read, and only the app
mkdir -p ~/.docbox && mv ~/Downloads/your-project-*.json ~/.docbox/gdrive.json
chmod 600 ~/.docbox/gdrive.json

export DOCBOX_GDRIVE_ENABLED=true
export DOCBOX_GDRIVE_CREDENTIALS=$HOME/.docbox/gdrive.json
export DOCBOX_GDRIVE_FOLDER_NAME=CamScanner      # or the folder's exact name
export DOCBOX_GDRIVE_POLL_MINUTES=15
```

If several folders share that name, use the id instead — open the folder in
Drive and take the last part of the URL
(`drive.google.com/drive/folders/`**`1a2B3c...`**):

```bash
export DOCBOX_GDRIVE_FOLDER_ID=1a2B3c...
```

### 4. Check it before trusting it

```bash
python -m app.cli gdrive-check
```

It prints whether auth works, which folder it resolved, and the first files it
can see. If that looks right:

```bash
python -m app.cli gdrive-sync        # pull everything new, once
```

Then start the app normally — the watcher runs on its own every
`DOCBOX_GDRIVE_POLL_MINUTES`.

---

## How the sync behaves

- **Incremental.** Each run asks only for files modified since the last one.
- **The cursor follows the newest file actually seen**, not the clock. Resuming
  from "now" would silently skip a file uploaded while the previous sync was
  still downloading.
- **Never twice.** Dedupe is by content hash, so a re-run, an overlapping
  window, or the same scan re-uploaded under a new name all land once. Renaming
  a file in Drive does not re-import it.
- **Recursive.** Subfolders are walked, and the subfolder name is kept as a hint
  for the model — `Insurance/Car` is real signal about what a document is.
- **Skips what it should:** Google Docs/Sheets/Slides (no bytes to download),
  `.ini`/`.DS_Store` leftovers, and anything with an extension the library does
  not accept.
- **Read-only.** The scope is `drive.readonly`. Docbox never writes to, moves or
  deletes anything in your Drive. Cleaning up Drive afterwards is your call.

Files are copied, not moved — Drive keeps its copy. If you want Drive to stay
tidy, delete from Drive once you can see the documents in Docbox; the content
hash means a later re-scan will not bring them back.

## Controls

| | |
|---|---|
| `make status` | last sync time, folder, whether the watcher is running |
| `python -m app.cli gdrive-sync` | pull now |
| `python -m app.cli gdrive-sync --full` | ignore the cursor and re-check everything (safe; duplicates are skipped) |
| `python -m app.cli gdrive-sync --limit 50` | try a small batch first |
| Settings → **Check Drive now** | the same thing from the app |
| `DOCBOX_GDRIVE_INTO=Scanner` | land Drive files in a folder other than the inbox |

## If something goes wrong

| Symptom | Cause |
|---|---|
| `no Drive folder named 'CamScanner' is visible` | The folder was not shared with the service account's email, or the name differs. Use `DOCBOX_GDRIVE_FOLDER_ID`. |
| `service-account auth needs google-auth` | `pip install google-auth` (it is in `requirements.txt`). |
| `403 Google Drive API has not been used` | Step 1.2 — enable the Drive API in that project. |
| Sync finds nothing after a CamScanner scan | CamScanner may export on a delay or only on Wi-Fi. Check the file is in Drive first, then `gdrive-sync --full`. |
| Everything imported as duplicates | They are already in the library — that is the dedupe working. |

## Using your own Google account instead

If you would rather it act as you than as a service account, put a file with
`client_id`, `client_secret` and `refresh_token` at `DOCBOX_GDRIVE_CREDENTIALS`
(scope `drive.readonly`). Docbox refreshes the access token itself. The
service-account route is still recommended: nothing to re-consent, and it can
only see the one folder.
