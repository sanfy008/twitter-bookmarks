import json
import sqlite3

import pytest

from x_local_archive.cli import main
from x_local_archive.db import backup, import_json, integrity_check, search


def payload():
    return {"tweets": [
        {"id": "1001", "text": "SQLite 本地归档测试", "author": {"username": "alice", "name": "Alice"},
         "created_at": "2026-09-24T00:00:00Z", "media_urls": ["https://example.test/image.jpg"]},
        {"id_str": "1002", "full_text": "Local first archive", "screen_name": "bob"},
    ]}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_idempotency_membership_search_update_and_backup(tmp_path):
    source, database = tmp_path / "export.json", tmp_path / "archive.sqlite3"
    value = payload()
    write_json(source, value)
    first = import_json(database, source, "owner", "bookmark")
    second = import_json(database, source, "owner", "bookmark")
    liked = import_json(database, source, "owner", "like")
    assert (first.tweets_inserted, first.entries_inserted) == (2, 2)
    assert (second.tweets_inserted, second.entries_inserted) == (0, 0)
    assert liked.entries_inserted == 2
    assert search(database, "SQLite")[0]["id"] == "1001"
    assert search(database, "本地归档测试")[0]["id"] == "1001"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM tweets").fetchone()[0] == 2
        assert connection.execute("SELECT count(*) FROM archive_entries").fetchone()[0] == 4
    value["tweets"][0]["text"] = "SQLite updated text"
    write_json(source, value)
    assert import_json(database, source, "owner", "bookmark").tweets_updated == 1
    assert search(database, "updated")[0]["id"] == "1001"
    destination = backup(database, tmp_path / "backups")
    assert destination.exists()
    assert integrity_check(destination) == "ok"
    assert search(destination, "archive")[0]["id"] == "1002"


def test_invalid_record_is_counted(tmp_path):
    source, database = tmp_path / "export.json", tmp_path / "archive.sqlite3"
    value = payload()
    value["tweets"].append({"text": "missing id"})
    write_json(source, value)
    result = import_json(database, source, "owner", "bookmark")
    assert result.records_seen == 3
    assert result.tweets_inserted == 2
    assert result.errors == 1


def test_missing_database_is_not_reported_as_healthy(tmp_path):
    with pytest.raises(FileNotFoundError):
        integrity_check(tmp_path / "missing.sqlite3")
    with pytest.raises(FileNotFoundError):
        backup(tmp_path / "missing.sqlite3", tmp_path / "backup.sqlite3")


def test_cli_import_search_and_missing_database_exit_codes(tmp_path, capsys):
    source, database = tmp_path / "export.json", tmp_path / "archive.sqlite3"
    write_json(source, payload())
    assert main(["--database", str(database), "import", str(source), "--account", "owner", "--type", "bookmark"]) == 0
    assert "tweets_inserted" in capsys.readouterr().out
    assert main(["--database", str(database), "search", "SQLite"]) == 0
    assert "1001" in capsys.readouterr().out
    assert main(["--database", str(tmp_path / "missing.sqlite3"), "verify"]) == 2
    assert "does not exist" in capsys.readouterr().out
