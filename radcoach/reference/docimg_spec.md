# docimg: push images into Google Docs from the Mac Studio

Hand this file to Claude Code on the Mac Studio. Build it, then test it end to end yourself.

## Why this is needed
- The cloud coach can already insert **public** images into Google Docs. It passes a public URL (for example Wikimedia Commons) to `insertInlineImage`, and Google fetches the image. This was verified on 09.10.2026.
- The cloud coach **cannot** push its **own** images, such as annotated CT slices with arrows and labels. It has no public host to put them on, and its Drive upload only takes the file as inline base64 text, which fails at real image sizes.
- docimg fills that gap on the Mac.

## Requirements
1. Python 3 with google-api-python-client, google-auth-oauthlib and Pillow. Use OAuth as Ajit's Google account with the scopes `drive.file` and `documents`. The doc owner has shared the docs with this account as editor.
2. CLI: `docimg push --doc <docId> --tab <tabId> --after "<exact paragraph start text>" --image file.png [--width 440] [--caption "..."]`
   - Upload the PNG to the Drive folder „RadCoach images“, creating the folder if needed.
   - Add a temporary permission `anyone / reader`.
   - Read the doc, find the first paragraph in the tab that starts with the `--after` text, and insert `"\n"` before that paragraph's newline.
   - Insert the image with `insertInlineImage` at the new paragraph, using the URI `https://drive.google.com/uc?export=download&id=<id>`. If Docs rejects it, fall back to `https://lh3.googleusercontent.com/d/<id>`.
   - If `--caption` is set, insert it as a plain, non-italic line under the image.
   - Use `writeControl.requiredRevisionId` from a fresh read. On a mismatch, re-read and retry up to 3 times.
   - Verify: re-read the doc, check that the inlineObject exists, download its `contentUri` and compare its size and hash to the uploaded file.
   - **Delete the anyone permission afterwards.** Docs keeps its own copy, so the image stays.
3. Watched outbox: `~/RadCoach/outbox/`. A pair of files, `x.png` and `x.json`, triggers a push.
   - `x.json` holds `{doc, tab, after, width, caption, deidentified}`.
   - Refuse the push unless `deidentified` is `true`, and move the pair to `~/RadCoach/rejected/` with a reason file.
   - After success, move the pair to `~/RadCoach/done/` and write a log line.
   - Run it via launchd, polling every 15 s.
4. Optional: `docimg annotate in.png spec.json out.png` draws arrows, circles and labels from a JSON list, `[{type:"arrow", from:[x,y], to:[x,y], label:"..."}]`. Use DejaVu Sans Bold, red and cyan, and a 3 px outline so it stays readable on CT.

## Privacy
- Never upload an image whose header shows a name, date of birth or patient ID. Crop it first.
- Public sharing lasts only seconds, from upload until the insert is verified. After that, remove the permission and keep the Drive file private.

## How the coach uses it
- When the chat is linked to the Mac (desktop app → „Link to this computer“), the coach writes `x.png` and `x.json` into `~/RadCoach/outbox/`, and the Mac pushes them into the doc.
- Scheduled coaching sessions can do the same only if they are allowed to use this computer.

## Test checklist
1. A test image goes into a scratch doc.
2. The permission is gone afterwards; check it with `permissions.list`.
3. A revision mismatch while the doc is being edited is handled.
4. A pair with `deidentified: false` is rejected.
5. A real push lands under an „Answer:“ paragraph in CT Standard.
