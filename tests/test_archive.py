import json
import sqlite3

from x_local_archive.cli import main
from x_local_archive.db import backup, import_json, integrity_check, search


def payload():
    return {
        "tweets": [
            {
                "id": "1001",
                "text": "SQLite 本地归档测试",
                "author": {"username": "alice", "name": "Alice"},
                "created_at": "2026-09-24T00:00:00Z",
                "media_urls": ["https://example.test/image.jpg"],
            },
            {"id_str": "1002", "full_text": "Local first archive", "screen_name": "bob"},
        ]
    }


def test_idempotency_membership_search_update_and_backup(write_json, database, tmp_path):
    source = write_json("export.json", payload())
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

    value = payload()
    value["tweets"][0]["text"] = "SQLite updated text"
    write_json("export.json", value)
    assert import_json(database, source, "owner", "bookmark").tweets_updated == 1
    assert search(database, "updated")[0]["id"] == "1001"

    destination = backup(database, tmp_path / "backups")
    assert destination.exists()
    assert integrity_check(destination) == "ok"
    assert search(destination, "archive")[0]["id"] == "1002"


def test_invalid_record_is_counted(write_json, database):
    value = payload()
    value["tweets"].append({"text": "missing id"})
    source = write_json("export.json", value)
    result = import_json(database, source, "owner", "bookmark")
    assert result.records_seen == 3
    assert result.tweets_inserted == 2
    assert result.errors == 1
    assert result.error_samples and "tweet id is missing" in result.error_samples[0]


def test_media_replacement_and_removal_delete_stale_rows(write_json, database):
    tweet = {"id": "media-1", "text": "media test", "username": "alice", "media_urls": []}
    source = database.parent / "export.json"

    tweet["media_urls"] = ["https://example.test/a.jpg"]
    source.write_text(json.dumps({"tweets": [tweet]}), encoding="utf-8")
    import_json(database, source, "owner", "bookmark")

    tweet["media_urls"] = ["https://example.test/b.jpg"]
    source.write_text(json.dumps({"tweets": [tweet]}), encoding="utf-8")
    assert import_json(database, source, "owner", "bookmark").tweets_updated == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT media_url FROM tweet_media").fetchall() == [
            ("https://example.test/b.jpg",)
        ]

    tweet["media_urls"] = []
    source.write_text(json.dumps({"tweets": [tweet]}), encoding="utf-8")
    assert import_json(database, source, "owner", "bookmark").tweets_updated == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM tweet_media").fetchone()[0] == 0


def test_import_closes_the_database_handle(write_json, database):
    source = write_json("export.json", payload())
    import_json(database, source, "owner", "bookmark")
    search(database, "SQLite")
    # On Windows an open handle would raise PermissionError here.
    database.unlink()


def test_accounts_are_case_insensitive(write_json, database):
    source = write_json("export.json", payload())
    import_json(database, source, "Alice", "bookmark")
    result = import_json(database, source, "ALICE", "bookmark")
    assert result.entries_inserted == 0
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM accounts").fetchone()[0] == 1
        assert connection.execute("SELECT username FROM accounts").fetchone()[0] == "alice"


def test_import_rejects_mismatched_metadata(write_json, database):
    source = write_json(
        "export.json",
        {"account": "alice", "type": "like", "tweets": [{"id": "1", "text": "x"}]},
    )
    try:
        import_json(database, source, "alice", "bookmark")
    except ValueError as error:
        assert "does not match" in str(error)
    else:  # pragma: no cover - the assertion below is the real failure path
        raise AssertionError("mismatched payload type was accepted")


def test_backup_closes_handles_and_leaves_no_wal_files(write_json, database, tmp_path):
    source = write_json("export.json", payload())
    import_json(database, source, "owner", "bookmark")
    destination = backup(database, tmp_path / "backups")
    assert not destination.with_name(destination.name + "-wal").exists()
    assert not destination.with_name(destination.name + "-shm").exists()
    # The backup must be deletable immediately (no lingering Windows handle).
    destination.unlink()


def test_backup_retention(tmp_path, write_json, database):
    source = write_json("export.json", payload())
    import_json(database, source, "owner", "bookmark")
    destination = tmp_path / "backups"
    destination.mkdir()
    for name in (
        "x-archive-20200101-000000.sqlite3",
        "x-archive-20200102-000000.sqlite3",
        "x-archive-20200103-000000.sqlite3",
    ):
        (destination / name).write_bytes(b"stale")

    backup(database, destination, keep=2)
    remaining = sorted(path.name for path in destination.glob("x-archive-*.sqlite3"))
    assert len(remaining) == 2
    assert "x-archive-20200103-000000.sqlite3" in remaining
    assert "x-archive-20200101-000000.sqlite3" not in remaining
    assert "x-archive-20200102-000000.sqlite3" not in remaining


def test_cli_import_search_and_missing_database_exit_codes(write_json, database, tmp_path, capsys):
    source = write_json("export.json", payload())
    assert (
        main(
            [
                "--database",
                str(database),
                "import",
                str(source),
                "--account",
                "owner",
                "--type",
                "bookmark",
            ]
        )
        == 0
    )
    assert "tweets_inserted" in capsys.readouterr().out
    assert main(["--database", str(database), "search", "SQLite"]) == 0
    assert "1001" in capsys.readouterr().out
    assert main(["--database", str(tmp_path / "missing.sqlite3"), "verify"]) == 2
    assert "does not exist" in capsys.readouterr().out
    missing = tmp_path / "not-created.sqlite3"
    assert main(["--database", str(missing), "search", "SQLite"]) == 2
    assert "does not exist" in capsys.readouterr().out
    assert not missing.exists()
