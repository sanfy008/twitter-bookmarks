from __future__ import annotations

import argparse
import json
from pathlib import Path

from .db import backup, import_json, initialize, integrity_check, search


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="x-archive", description="Local-first X archive")
    parser.add_argument("--database", type=Path, default=Path("data/archive.sqlite3"))
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    importer = commands.add_parser("import")
    importer.add_argument("source", type=Path)
    importer.add_argument("--account", required=True)
    importer.add_argument("--type", choices=("bookmark", "like"), required=True)
    finder = commands.add_parser("search")
    finder.add_argument("query")
    finder.add_argument("--limit", type=int, default=20)
    backup_parser = commands.add_parser("backup")
    backup_parser.add_argument("destination", type=Path, nargs="?", default=Path("backups"))
    commands.add_parser("verify")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            initialize(args.database)
            print(f"Initialized: {args.database.resolve()}")
        elif args.command == "import":
            stats = import_json(args.database, args.source, args.account, args.type)
            print(json.dumps(stats.__dict__, ensure_ascii=False, indent=2))
            return 1 if stats.errors else 0
        elif args.command == "search":
            print(json.dumps(search(args.database, args.query, args.limit), ensure_ascii=False, indent=2))
        elif args.command == "backup":
            print(f"Backup verified: {backup(args.database, args.destination)}")
        elif args.command == "verify":
            result = integrity_check(args.database)
            print(result)
            return 0 if result == "ok" else 1
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}")
        return 2
    return 0
