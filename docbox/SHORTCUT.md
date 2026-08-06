# Getting Docbox into the iOS Share Sheet

The share sheet is the whole point, so this is worth ten minutes per phone.

**The constraint, up front:** iOS Safari does *not* support the Web Share Target
API. A web app installed to the home screen cannot appear in the share sheet on
iOS, no matter how it is built — only App Store apps and **Shortcuts** can. So
the share button is a Shortcut. It behaves identically to a native share
extension: long-press anything, tap *Docbox*, done. (The `share_target` entry in
`manifest.webmanifest` covers Android and desktop Chrome, where it does work.)

---

## 1. Install the PWA (both phones)

1. Open your Docbox URL in **Safari** (not Chrome — only Safari can install).
2. Share button → **Add to Home Screen** → *Add*.
3. Open it from the home screen and sign in. The session lasts 90 days.

You now have an app icon, full-screen UI, camera scanning and the library.

## 2. Get your token

In the app: **⚙ Settings → Copy token**. Each of you has your own — uploads are
labelled with who sent them. Rotating a token invalidates the old Shortcut.

## 3. Build the Shortcut (once per phone, ~2 minutes)

Shortcuts app → **+** → rename it **Docbox** (this is the name that shows up in
the share sheet) → **ℹ️ (Details)** → turn on **Show in Share Sheet**.

Under *Share Sheet Types*, keep **Files, Images, PDFs, URLs, Text** and turn the
rest off.

Then add these actions in order:

| # | Action | Settings |
|---|--------|----------|
| 1 | **Get Files from Input** *(optional but tidy)* | Input: `Shortcut Input` |
| 2 | **Get Contents of URL** | see below |

Configure action 2:

- **URL**: `https://YOUR-DOCBOX-HOST/api/upload`
- **Method**: `POST`
- **Headers**: add one header
  - Key: `Authorization`
  - Value: `Bearer PASTE-YOUR-TOKEN-HERE`
- **Request Body**: `Form`
  - Field name `files`, type **File**, value: `Shortcut Input`
  - *(optional)* field name `folder`, type Text, value: `Inbox`

Tap **Done**. That's it.

### Using it

Long-press a PDF in Mail, a photo in Photos, a scan in the Files app, a page in
Safari → share → **Docbox**. It lands in the inbox and the local model renames it
within a few seconds.

### Optional: a nicer confirmation

Append a **Show Notification** action with text `Filed to Docbox` so you get
feedback without opening the app.

### Optional: scan straight from the Shortcut

Add **Scan Document** (Apple's built-in scanner, with edge detection) as action 1
and feed `Scanned Document` into the form field instead of `Shortcut Input`.
Multi-page scans arrive as a single PDF. Put this Shortcut on your home screen
and it becomes a one-tap scanner.

---

## 4. Sending several photos as one document

Two ways:

- **In the app**: tap **Scan**, take/choose multiple photos — more than one photo
  is automatically stapled into a single PDF, in the order chosen.
- **In a Shortcut**: post them all to `/api/upload` with an extra form field
  `combine` = `true`.

## 5. Sharing a link instead of a file

The same Shortcut handles URLs — they are filed as a small `.txt` note that the
model names from the page title. If you want a dedicated one, POST JSON to
`/api/link`:

```json
{ "url": "https://example.com/article", "title": "Optional title" }
```

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `401` | Token wrong, or a space crept into `Bearer <token>` |
| `400 no files in request` | The form field must be named `files` and typed **File** |
| `400 unsupported file type` | See `ALLOWED_EXTS` in `app/storage.py` |
| Shortcut missing from the share sheet | *Show in Share Sheet* is off, or the input types exclude that item |
| Works at home, not on cellular | Docbox is on your LAN — see the remote-access section in `README.md` |
