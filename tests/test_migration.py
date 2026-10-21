import sqlite3
from contextlib import closing

from x_local_archive.db import LATEST_SCHEMA_VERSION, SCHEMA, initialize, search


def _create_v0_database(path):
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript(SCHEMA)
        connection.execute(
            """INSERT INTO tweets(id,author_username,author_name,text,created_at,url,raw_json,
            content_hash,first_seen_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                "1",
                "alice",
                "Alice",
                "价值投资",
                "Sun Apr 21 17:46:07 +0000 2024",
                "https://x.com/alice/status/1",
                "{}",
                "hash",
                "2024-04-21T17:46:07+00:00",
                "2024-04-21T17:46:07+00:00",
            ),
        )
        connection.execute(
            """INSERT INTO import_runs(source_path,started_at,records_seen)
            VALUES(?,?,?)""",
            (r"D:\Private\bookmarks.json", "2024-04-21T17:46:07+00:00", 1),
        )


def test_v0_database_is_migrated_in_place(tmp_path):
    path = tmp_path / "old.sqlite3"
    _create_v0_database(path)

    initialize(path)

    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == LATEST_SCHEMA_VERSION
        fts_text = connection.execute("SELECT fts_text FROM tweets").fetchone()[0]
        assert fts_text.split() == ["价", "值", "投", "资"]
        assert connection.execute("SELECT created_at FROM tweets").fetchone()[0] == (
            "2024-04-21T17:46:07+00:00"
        )
        assert connection.execute("SELECT source_path FROM import_runs").fetchone()[0] == (
            "bookmarks.json"
        )
        assert connection.execute("SELECT count(*) FROM tweets_fts").fetchone()[0] == 1
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_archive_entries_tweet'"
        ).fetchone()
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='import_errors'"
        ).fetchone()
        for table in ("users", "tweet_entities", "tweet_metrics", "bookmark_folders"):
            assert connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
        tweet_columns = {row[1] for row in connection.execute("PRAGMA table_info(tweets)")}
        assert {
            "author_id",
            "conversation_id",
            "quoted_tweet_id",
            "lang",
            "status",
        } <= tweet_columns
        entry_columns = {row[1] for row in connection.execute("PRAGMA table_info(archive_entries)")}
        assert {"folder_id", "run_id", "read_status"} <= entry_columns

    assert search(path, "价值投资")[0]["id"] == "1"


def test_initialize_is_idempotent(tmp_path):
    path = tmp_path / "archive.sqlite3"
    initialize(path)
    initialize(path)
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == LATEST_SCHEMA_VERSION
