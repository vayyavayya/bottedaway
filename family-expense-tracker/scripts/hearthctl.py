#!/usr/bin/env python3
"""hearthctl — operator CLI for Hearth's Supabase project (standard library only).

Used by the feedback worker (see FEEDBACK_LOOP.md) and for applying migrations.
It talks to the Supabase Management API, so it needs a personal access token and
the project ref:

    export SUPABASE_ACCESS_TOKEN=sbp_...      # or put both lines in
    export PROJECT_REF=abcd1234               # ~/.config/hearth/env  (KEY=VALUE)

Commands:
    hearthctl.py sql <file.sql>                         run a SQL file (e.g. a migration)
    hearthctl.py feedback list [--all]                  open feedback as JSON (oldest first)
    hearthctl.py feedback show <id>                     one item as JSON
    hearthctl.py feedback status <id> <status> [--note TEXT | --note-file PATH]
                                                        set status (+ reply shown in the app)

Statuses: new, in_progress, needs_info, shipped, declined.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API = "https://api.supabase.com"
STATUSES = ("new", "in_progress", "needs_info", "shipped", "declined")
OPEN_STATUSES = ("new", "in_progress")


def load_credentials():
    env_file = Path.home() / ".config" / "hearth" / "env"
    file_vals = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                file_vals[key.strip().removeprefix("export ").strip()] = val.strip().strip("'\"")
    token = os.environ.get("SUPABASE_ACCESS_TOKEN") or file_vals.get("SUPABASE_ACCESS_TOKEN")
    ref = os.environ.get("PROJECT_REF") or file_vals.get("PROJECT_REF")
    if not token or not ref:
        sys.exit("hearthctl: set SUPABASE_ACCESS_TOKEN and PROJECT_REF (env or ~/.config/hearth/env)")
    return token, ref


def run_sql(query):
    token, ref = load_credentials()
    req = urllib.request.Request(
        f"{API}/v1/projects/{ref}/database/query",
        data=json.dumps({"query": query}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "hearthctl/1.0",  # Cloudflare rejects urllib's default agent
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode() or "[]"
    except urllib.error.HTTPError as e:
        sys.exit(f"hearthctl: SQL failed — HTTP {e.code}: {e.read().decode()[:500]}")
    except urllib.error.URLError as e:
        sys.exit(f"hearthctl: cannot reach Supabase — {e.reason}")
    return json.loads(body)


def lit(value):
    """Quote a Python string as a SQL literal (standard_conforming_strings is on)."""
    if value is None:
        return "null"
    text = str(value)
    if "\x00" in text:
        sys.exit("hearthctl: text may not contain NUL bytes")
    return "'" + text.replace("'", "''") + "'"


def checked_uuid(value):
    try:
        return str(uuid.UUID(value))
    except ValueError:
        sys.exit(f"hearthctl: not a valid id: {value!r}")


FEEDBACK_COLUMNS = """
    f.id, f.created_at, f.updated_at, f.kind, f.status, f.author_name,
    f.message, f.context, f.resolution_note, f.household_id, h.name as household
"""


def cmd_sql(args):
    print(json.dumps(run_sql(Path(args.file).read_text()), indent=2, default=str))


def cmd_feedback_list(args):
    where = "" if args.all else f"where f.status in ({', '.join(lit(s) for s in OPEN_STATUSES)})"
    rows = run_sql(f"""
        select {FEEDBACK_COLUMNS}
        from feedback f join households h on h.id = f.household_id
        {where}
        order by f.created_at asc
        limit 100
    """)
    print(json.dumps(rows, indent=2, default=str))


def cmd_feedback_show(args):
    rows = run_sql(f"""
        select {FEEDBACK_COLUMNS}
        from feedback f join households h on h.id = f.household_id
        where f.id = {lit(checked_uuid(args.id))}
    """)
    if not rows:
        sys.exit("hearthctl: no such feedback item")
    print(json.dumps(rows[0], indent=2, default=str))


def cmd_feedback_status(args):
    if args.status not in STATUSES:
        sys.exit(f"hearthctl: status must be one of {', '.join(STATUSES)}")
    note = Path(args.note_file).read_text().strip() if args.note_file else args.note
    if note is not None and len(note) > 4000:
        sys.exit("hearthctl: note is longer than 4000 characters")
    note_sql = f", resolution_note = {lit(note)}" if note is not None else ""
    rows = run_sql(f"""
        update feedback set status = {lit(args.status)}{note_sql}
        where id = {lit(checked_uuid(args.id))}
        returning id, status, resolution_note, updated_at
    """)
    if not rows:
        sys.exit("hearthctl: no such feedback item")
    print(json.dumps(rows[0], indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(prog="hearthctl", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sql = sub.add_parser("sql", help="run a SQL file")
    p_sql.add_argument("file")
    p_sql.set_defaults(func=cmd_sql)

    p_fb = sub.add_parser("feedback", help="read and answer in-app feedback")
    fb = p_fb.add_subparsers(dest="fbcmd", required=True)

    p_list = fb.add_parser("list", help="open items (new + in_progress), oldest first")
    p_list.add_argument("--all", action="store_true", help="include every status")
    p_list.set_defaults(func=cmd_feedback_list)

    p_show = fb.add_parser("show", help="one item")
    p_show.add_argument("id")
    p_show.set_defaults(func=cmd_feedback_show)

    p_status = fb.add_parser("status", help="set status and optional reply")
    p_status.add_argument("id")
    p_status.add_argument("status")
    note = p_status.add_mutually_exclusive_group()
    note.add_argument("--note", help="reply shown to the family in the app")
    note.add_argument("--note-file", help="read the reply from a file")
    p_status.set_defaults(func=cmd_feedback_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
