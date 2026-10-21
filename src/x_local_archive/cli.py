from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .db import (
    backup,
    doctor,
    forget_account,
    import_json,
    initialize,
    prune,
    search,
    stats,
    undo_run,
    verify_database,
)
from .export import export_data
from .inspect import inspect_export


def _configure_stdio() -> None:
    """Avoid UnicodeEncodeError on legacy Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError, OSError):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if os.name == "nt":
        with contextlib.suppress(AttributeError, OSError):
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="x-archive", description="Local-first X archive")
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="database path (default: $X_ARCHIVE_DB or data/archive.sqlite3)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init")

    importer = commands.add_parser("import")
    importer.add_argument("source", type=Path)
    importer.add_argument("--account", required=True)
    importer.add_argument("--type", choices=("bookmark", "like"), required=True)

    finder = commands.add_parser("search")
    finder.add_argument("query")
    finder.add_argument("--limit", type=int, default=20)
    finder.add_argument("--offset", type=int, default=0)
    finder.add_argument("--type", dest="entry_type", choices=("bookmark", "like"))
    finder.add_argument("--account")
    finder.add_argument("--author")
    finder.add_argument("--since")
    finder.add_argument("--until")
    finder.add_argument("--has-media", action="store_true")
    finder.add_argument("--folder")

    exporter = commands.add_parser("export")
    exporter.add_argument("--format", choices=("json", "csv", "md", "html"), default="json")
    exporter.add_argument("--out", type=Path)
    exporter.add_argument("--query")
    exporter.add_argument("--limit", type=int, default=1000)
    exporter.add_argument("--offset", type=int, default=0)
    exporter.add_argument("--type", dest="entry_type", choices=("bookmark", "like"))
    exporter.add_argument("--account")
    exporter.add_argument("--author")
    exporter.add_argument("--since")
    exporter.add_argument("--until")
    exporter.add_argument("--has-media", action="store_true")
    exporter.add_argument("--folder")

    backup_parser = commands.add_parser("backup")
    backup_parser.add_argument("destination", type=Path, nargs="?", default=Path("backups"))
    backup_parser.add_argument(
        "--keep", type=int, default=10, help="number of timestamped backups to retain (0 = all)"
    )

    commands.add_parser("verify")
    commands.add_parser("stats")
    commands.add_parser("doctor")

    pruner = commands.add_parser("prune")
    pruner.add_argument("--dry-run", action="store_true")
    pruner.add_argument("--no-vacuum", action="store_true")

    forget = commands.add_parser("forget")
    forget.add_argument("--account", required=True)
    forget.add_argument("--no-vacuum", action="store_true")

    inspector = commands.add_parser("inspect")
    inspector.add_argument("source", type=Path)

    undo = commands.add_parser("undo")
    undo.add_argument("--run", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    if args.database is None:
        args.database = Path(os.environ.get("X_ARCHIVE_DB", "data/archive.sqlite3"))
    try:
        if args.command == "init":
            initialize(args.database)
            print(f"Initialized: {args.database.resolve()}")
        elif args.command == "import":
            result = import_json(args.database, args.source, args.account, args.type)
            print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
            return 1 if result.errors else 0
        elif args.command == "search":
            print(
                json.dumps(
                    search(
                        args.database,
                        args.query,
                        args.limit,
                        offset=args.offset,
                        entry_type=args.entry_type,
                        account=args.account,
                        author=args.author,
                        since=args.since,
                        until=args.until,
                        has_media=args.has_media,
                        folder=args.folder,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "export":
            result = export_data(
                args.database,
                args.out,
                fmt=args.format,
                query=args.query,
                limit=args.limit,
                offset=args.offset,
                entry_type=args.entry_type,
                account=args.account,
                author=args.author,
                since=args.since,
                until=args.until,
                has_media=args.has_media,
                folder=args.folder,
            )
            print(result)
        elif args.command == "backup":
            print(f"Backup verified: {backup(args.database, args.destination, keep=args.keep)}")
        elif args.command == "verify":
            result = verify_database(args.database)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if all(value == "ok" for value in result.values()) else 1
        elif args.command == "stats":
            print(json.dumps(stats(args.database), ensure_ascii=False, indent=2))
        elif args.command == "doctor":
            result = doctor(args.database)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if result["issues"] else 0
        elif args.command == "undo":
            print(
                json.dumps(
                    undo_run(args.database, args.run),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "prune":
            print(
                json.dumps(
                    prune(args.database, dry_run=args.dry_run, vacuum=not args.no_vacuum),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "forget":
            print(
                json.dumps(
                    forget_account(args.database, args.account, vacuum=not args.no_vacuum),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "inspect":
            print(json.dumps(inspect_export(args.source), ensure_ascii=False, indent=2))
    except (FileNotFoundError, OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as error:
        print(f"error: {error}")
        return 2
    return 0
