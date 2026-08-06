"""Admin CLI: `python -m app.cli <command>`.

    adduser <name> [password]   create an account, print its API token
    passwd <name> [password]    change a password
    token <name>                rotate and print the iOS Shortcut token
    users                       list accounts
    scan-library                adopt files that were copied into the library by hand
    reprocess [--all|--failed|--review|<id>...]
    import <folder|zip> [--user NAME] [--into FOLDER] [--group-images]
                                bulk import, e.g. a CamScanner export
    organize [--apply] [--folder F]
                                apply the filing rules to what is already here
    gdrive-check                verify Drive access and list what it can see
    gdrive-sync [--full] [--limit N]
                                pull new files from the watched Drive folder
    status                      queue + capability overview
"""

from __future__ import annotations

import getpass
import sys
import time
from pathlib import Path

from . import auth, db, enhance, extract, gdrive, importer, llm, pdfbuild, routing, storage, worker
from .config import settings
from .pipeline import enqueue, process_document


def _prompt_password(given: str | None) -> str:
    if given:
        return given
    first = getpass.getpass("password: ")
    if first != getpass.getpass("repeat: "):
        sys.exit("passwords do not match")
    return first


def cmd_adduser(args: list[str]) -> None:
    if not args:
        sys.exit("usage: adduser <name> [password]")
    password = _prompt_password(args[1] if len(args) > 1 else None)
    try:
        user = auth.create_user(args[0], password)
    except ValueError as exc:
        sys.exit(str(exc))
    print(f"created {user['username']} (id {user['id']})")
    print(f"API token (for the iOS Shortcut): {user['api_token']}")


def cmd_passwd(args: list[str]) -> None:
    if not args:
        sys.exit("usage: passwd <name> [password]")
    password = _prompt_password(args[1] if len(args) > 1 else None)
    try:
        auth.set_password(args[0], password)
    except ValueError as exc:
        sys.exit(str(exc))
    print("password updated")


def cmd_token(args: list[str]) -> None:
    if not args:
        sys.exit("usage: token <name>")
    row = db.query_one("SELECT id FROM users WHERE username = ?", (args[0].strip().lower(),))
    if not row:
        sys.exit("no such user")
    print(auth.rotate_token(int(row["id"])))


def cmd_users(_: list[str]) -> None:
    rows = db.query("SELECT id, username, created_at FROM users ORDER BY id")
    if not rows:
        print("no users yet — run: python -m app.cli adduser <name>")
        return
    for row in rows:
        created = time.strftime("%Y-%m-%d", time.localtime(row["created_at"]))
        print(f"{row['id']:>3}  {row['username']:<20} created {created}")


def cmd_scan_library(_: list[str]) -> None:
    """Pick up files dropped into the library folder outside the app."""
    known = {
        (r["folder"], r["filename"])
        for r in db.query("SELECT folder, filename FROM documents")
    }
    added = 0
    for folder in storage.list_folders():
        directory = storage.folder_path(folder)
        if not directory.exists():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.name.startswith("."):
                continue
            if (folder, path.name) in known:
                continue
            now = time.time()
            doc_id = db.insert("documents", {
                "folder": folder,
                "filename": path.name,
                "original_name": path.name,
                "ext": path.suffix.lower(),
                "mime": storage.guess_mime(path.name),
                "size": path.stat().st_size,
                "sha256": storage.sha256_file(path),
                "status": "pending",
                "next_attempt": now,
                "uploaded_by": "filesystem",
                "created_at": now,
                "updated_at": now,
            })
            db.log_event(doc_id, "adopted", f"{folder}/{path.name}", "cli")
            added += 1
    print(f"adopted {added} file(s)")


def cmd_reprocess(args: list[str]) -> None:
    if args and args[0] == "--all":
        rows = db.query("SELECT id FROM documents")
    elif args and args[0] == "--failed":
        rows = db.query("SELECT id FROM documents WHERE status = 'failed'")
    elif args and args[0] == "--review":
        rows = db.query("SELECT id FROM documents WHERE needs_review = 1")
    elif args:
        rows = [{"id": int(a)} for a in args if a.isdigit()]
    else:
        sys.exit("usage: reprocess [--all|--failed|--review|<id>...]")

    ids = [int(r["id"]) for r in rows]
    for doc_id in ids:
        db.update("documents", doc_id, {"attempts": 0, "pinned_name": 0})
        enqueue(doc_id)
    print(f"queued {len(ids)} document(s)")

    if not worker.is_running():
        print("worker not running — processing inline")
        for doc_id in ids:
            print(f"  {doc_id}: {process_document(doc_id)}")


def _flag(args: list[str], name: str) -> bool:
    return name in args


def _value(args: list[str], name: str, default: str = "") -> str:
    if name in args:
        index = args.index(name)
        if index + 1 < len(args):
            return args[index + 1]
    return default


def cmd_import(args: list[str]) -> None:
    if not args:
        sys.exit("usage: import <folder|zip> [--user NAME] [--into FOLDER] [--group-images]")

    source = Path(args[0]).expanduser()
    user = _value(args, "--user") or _default_user()
    into = _value(args, "--into") or None
    group = _flag(args, "--group-images")

    if not source.exists():
        sys.exit(f"no such path: {source}")

    def show(report) -> None:
        done = report.imported + report.skipped_duplicate + report.skipped_unsupported + report.failed
        print(
            f"\r  {done}/{report.total}  imported {report.imported}"
            f"  duplicates {report.skipped_duplicate}"
            f"  skipped {report.skipped_unsupported}"
            f"  failed {report.failed}",
            end="", flush=True,
        )

    print(f"importing {source} as {user}...")
    if source.is_file() and source.suffix.lower() == ".zip":
        report = importer.import_zip(source.read_bytes(), user, into=into, group_images=group)
    else:
        report = importer.import_folder(source, user, into=into, group_images=group, progress=show)
    print()
    for line in report.errors[:10]:
        print(f"  ! {line}")
    print(
        f"done: {report.imported} imported, {report.skipped_duplicate} duplicates, "
        f"{report.skipped_unsupported} unsupported, {report.failed} failed"
    )
    if not worker.is_running():
        print("start the server (or `make run`) to let the model read and file them")


def _default_user() -> str:
    row = db.query_one("SELECT username FROM users ORDER BY id LIMIT 1")
    if not row:
        sys.exit("no users yet — run: python -m app.cli adduser <name>")
    return row["username"]


def cmd_organize(args: list[str]) -> None:
    """Apply the filing rules to documents already in the library."""
    from .llm import Analysis

    apply = _flag(args, "--apply")
    folder = _value(args, "--folder")
    config = routing.load_rules()

    where, params = ["status = 'done'", "pinned_name = 0"], []
    if folder:
        where.append("(folder = ? OR folder LIKE ?)")
        params.extend([folder, f"{folder}/%"])
    rows = db.query(f"SELECT * FROM documents WHERE {' AND '.join(where)}", params)

    moved = 0
    for row in rows:
        analysis = Analysis(
            date=row["doc_date"], title=row["title"], doc_type=row["doc_type"],
            correspondent=row["correspondent"], summary=row["summary"],
            confidence=row["confidence"],
            source="llm" if row["confidence"] else "heuristic",
        )
        route = routing.choose_folder(analysis, row["text_excerpt"],
                                      current=row["folder"], config=config)
        if not route.confident or route.folder == row["folder"]:
            continue
        moved += 1
        arrow = "->" if apply else "would ->"
        print(f"  {row['folder']}/{row['filename']}  {arrow}  {route.folder}  ({route.rule})")
        if apply:
            final = storage.move_document(row["folder"], row["filename"],
                                          route.folder, row["filename"])
            db.update("documents", int(row["id"]), {
                "folder": route.folder, "filename": final,
                "routed_by": route.rule, "updated_at": time.time(),
            })
    if apply and moved:
        storage.prune_empty_folders()
    print(f"{moved} document(s) {'moved' if apply else 'would move'} "
          f"(of {len(rows)} considered)")
    if not apply and moved:
        print("re-run with --apply to do it")


def cmd_gdrive_check(_: list[str]) -> None:
    """Prove the credentials work before trusting the watcher with them."""
    if not settings.gdrive_credentials:
        sys.exit("DOCBOX_GDRIVE_CREDENTIALS is not set (path to the JSON key)")
    try:
        gdrive.access_token(force=True)
        print("auth:      ok")
    except gdrive.DriveError as exc:
        sys.exit(f"auth failed: {exc}")

    folder_id = settings.gdrive_folder_id
    if folder_id:
        print(f"folder id: {folder_id}")
    else:
        folder_id = gdrive.find_folder(settings.gdrive_folder_name) or ""
        if not folder_id:
            sys.exit(
                f"no folder named {settings.gdrive_folder_name!r} is visible.\n"
                "Share it with the service account's email address, or set "
                "DOCBOX_GDRIVE_FOLDER_ID."
            )
        print(f"folder:    {settings.gdrive_folder_name} -> {folder_id}")

    files = gdrive.list_children(folder_id)
    print(f"visible:   {len(files)} file(s)")
    for item in files[:10]:
        where = item.get("_path") or "/"
        print(f"  {where:<24} {item['name']}")
    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more")


def cmd_gdrive_sync(args: list[str]) -> None:
    full = _flag(args, "--full")
    limit = int(_value(args, "--limit", "0") or 0)
    try:
        report = gdrive.sync(full=full, limit=limit)
    except gdrive.DriveError as exc:
        sys.exit(str(exc))
    print(f"scanned {report.scanned}, imported {report.imported}, "
          f"duplicates {report.duplicates}, skipped {report.skipped}, failed {report.failed}")
    for line in report.errors[:10]:
        print(f"  ! {line}")
    if not worker.is_running():
        print("start the server to let the model read and file them")


def cmd_status(_: list[str]) -> None:
    row = db.query_one(
        "SELECT COUNT(*) AS total, SUM(status='pending') AS pending, "
        "SUM(status='failed') AS failed, SUM(needs_review=1) AS review FROM documents"
    )
    print(f"library:   {settings.library_dir}")
    print(f"database:  {settings.db_path}")
    print(f"documents: {row['total'] or 0} "
          f"(pending {row['pending'] or 0}, failed {row['failed'] or 0}, review {row['review'] or 0})")
    where = "on this machine" if llm.is_local() else "HOSTED — document text leaves this machine"
    print(f"model:     {llm.provider()} {llm.model_name()} ({where})")
    print(f"           {llm.base_url()} reachable={llm.available()} "
          f"key={'set' if settings.llm_api_key else 'none'}")
    if settings.household:
        print(f"household: {', '.join(settings.household)}")
    drive = gdrive.status()
    if drive["configured"]:
        last = time.strftime("%Y-%m-%d %H:%M", time.localtime(drive["last_sync"])) if drive["last_sync"] else "never"
        print(f"gdrive:    {drive['folder']} -> {drive['into']} "
              f"(watcher {'on' if drive['watcher_running'] else 'off'}, last sync {last})")
    installed = llm.installed_models()
    if installed:
        print(f"models:    {', '.join(installed)}")
    print(f"extract:   {extract.capabilities()}")
    print(f"scanning:  {enhance.available()} {pdfbuild.capabilities()}")
    print(f"routing:   {routing.rules_path()} (auto_file={routing.load_rules().get('auto_file')})")
    batches = db.query("SELECT * FROM batches ORDER BY id DESC LIMIT 3")
    for batch in batches:
        print(f"import:    {batch['source']} -> {batch['imported']}/{batch['total']} "
              f"({batch['status']})")


COMMANDS = {
    "adduser": cmd_adduser,
    "passwd": cmd_passwd,
    "token": cmd_token,
    "users": cmd_users,
    "scan-library": cmd_scan_library,
    "reprocess": cmd_reprocess,
    "import": cmd_import,
    "organize": cmd_organize,
    "gdrive-check": cmd_gdrive_check,
    "gdrive-sync": cmd_gdrive_sync,
    "status": cmd_status,
}


def main(argv: list[str] | None = None) -> None:
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(__doc__)
        return
    command = COMMANDS.get(argv[0])
    if not command:
        sys.exit(f"unknown command {argv[0]!r}\n{__doc__}")
    settings.ensure_dirs()
    settings.resolve_secret()
    db.init_db()
    command(argv[1:])


if __name__ == "__main__":
    main()
