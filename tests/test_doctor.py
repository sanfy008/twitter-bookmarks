import sqlite3

from x_local_archive.db import doctor, import_json, undo_run


def payload(tweet_id: str) -> dict:
    return {
        "account": "alice",
        "type": "bookmark",
        "tweets": [
            {
                "id": tweet_id,
                "text": f"tweet {tweet_id}",
                "author_username": "alice",
                "author_id": "42",
                "created_at": "2024-01-01T00:00:00Z",
            }
        ],
    }


def test_doctor_is_clean_and_undo_removes_a_run(write_json, database):
    source = write_json("a.json", payload("1"))
    import_json(database, source, "alice", "bookmark")

    result = doctor(database)
    assert result["verify"] == {"integrity": "ok", "foreign_keys": "ok", "fts": "ok"}
    assert result["issues"] == []
    assert result["counts"]["tweets"] == 1
    assert result["counts"]["media"] == 0
    assert result["last_backup"] is None

    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO tweets(id,author_username,text,raw_json,content_hash,
            first_seen_at,updated_at) VALUES('9','x','orphan','{}','h','2024-01-01','2024-01-01')"""
        )
    result = doctor(database)
    assert any("orphan" in issue for issue in result["issues"])

    result = undo_run(database, 1)
    assert result["entries_removed"] == 1
    assert result["orphan_tweets_removed"] == 2
    assert doctor(database)["counts"]["tweets"] == 0


def test_undo_does_not_remove_shared_entries(write_json, database):
    first = write_json("a.json", payload("1"))
    second = write_json("b.json", payload("1"))
    import_json(database, first, "alice", "bookmark")
    import_json(database, second, "alice", "bookmark")

    # The second import did not create a new archive entry (same account/tweet/type),
    # so undoing it must not remove the entry owned by the first run.
    result = undo_run(database, 2)
    assert result["entries_removed"] == 0
    assert result["orphan_tweets_removed"] == 0
    assert doctor(database)["counts"]["tweets"] == 1
