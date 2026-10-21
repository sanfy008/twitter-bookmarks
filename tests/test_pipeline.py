import sqlite3

from x_local_archive.db import import_json, prune, search, stats, verify_database


def userscript_payload():
    """Mirror the exact shape produced by exportData() in the v2 userscript."""
    return {
        "account": "ethan151300",
        "type": "bookmark",
        "exported_at": "2026-10-21T06:00:00.000Z",
        "newest_id": "1782103537234973176",
        "oldest_id": "1600000000000000003",
        "total_tweets": 4,
        "tweets": [
            {
                "id": "1782103537234973176",
                "author_username": "alice",
                "author_name": "Alice",
                "text": "价值投资 hello",
                "created_at": "2024-04-21T17:46:07.000Z",
                "url": "https://x.com/alice/status/1782103537234973176",
                "media": [
                    {"url": "https://pbs.twimg.com/media/a.jpg", "type": "photo"},
                    {"url": "https://pbs.twimg.com/media/b.mp4", "type": "video"},
                ],
            },
            {
                "id": "1800000000000000002",
                "author_username": "carol",
                "author_name": "Carol",
                "text": "wrapped",
                "created_at": "2024-04-23T00:00:00.000Z",
                "url": "https://x.com/carol/status/1800000000000000002",
                "media": [],
            },
            {
                "id": "1700000000000000001",
                "author_username": "bob",
                "author_name": "Bob",
                "text": "quoted tweet",
                "created_at": "2024-04-22T00:00:00.000Z",
                "url": "https://x.com/bob/status/1700000000000000001",
                "media": [],
            },
            {
                "id": "1600000000000000003",
                "author_username": "dave",
                "author_name": "Dave",
                "text": "quoted body",
                "created_at": "2024-04-24T00:00:00.000Z",
                "url": "https://x.com/dave/status/1600000000000000003",
                "media": [],
            },
        ],
    }


def test_userscript_payload_end_to_end(write_json, database):
    source = write_json("bookmarks_ethan151300.json", userscript_payload())

    result = import_json(database, source, "Ethan151300", "bookmark")
    assert (result.records_seen, result.tweets_inserted, result.errors) == (4, 4, 0)

    summary = stats(database)
    assert summary["tweets"] == 4
    assert summary["bookmarks"] == 4
    assert summary["media"] == 2
    assert summary["empty_text"] == 0
    assert summary["unknown_author"] == 0
    assert summary["accounts"] == [
        {"username": "ethan151300", "created_at": summary["accounts"][0]["created_at"]}
    ]

    # Chinese substring search reaches the right author and URL.
    hit = search(database, "价值投资")[0]
    assert hit["author_username"] == "alice"
    assert hit["url"] == "https://x.com/alice/status/1782103537234973176"
    assert hit["created_at"] == "2024-04-21T17:46:07+00:00"
    assert "价值投资" in hit["snippet"]

    assert search(database, "quoted body")[0]["author_username"] == "dave"
    assert search(database, "SQLite") == []

    with sqlite3.connect(database) as connection:
        media = connection.execute(
            "SELECT media_type FROM tweet_media ORDER BY media_type"
        ).fetchall()
        assert media == [("photo",), ("video",)]
        run = connection.execute(
            """SELECT account, entry_type, exported_at, newest_id, total_tweets,
            source_sha256, source_path FROM import_runs ORDER BY id DESC LIMIT 1"""
        ).fetchone()
    assert run[0] == "ethan151300"
    assert run[1] == "bookmark"
    assert run[2] == "2026-10-21T06:00:00+00:00"
    assert run[3] == "1782103537234973176"
    assert run[4] == 4
    assert len(run[5]) == 64
    assert run[6] == "bookmarks_ethan151300.json"

    assert verify_database(database) == {"integrity": "ok", "foreign_keys": "ok", "fts": "ok"}

    # Re-importing the same export is a no-op.
    again = import_json(database, source, "Ethan151300", "bookmark")
    assert (again.tweets_inserted, again.tweets_updated, again.entries_inserted) == (0, 0, 0)


def test_raw_graphql_tweet_end_to_end(write_json, database):
    raw = {
        "tweets": [
            {
                "__typename": "TweetWithVisibilityResults",
                "tweet": {
                    "__typename": "Tweet",
                    "rest_id": "1782103537234973176",
                    "core": {
                        "user_results": {
                            "result": {
                                "__typename": "User",
                                "rest_id": "42",
                                "core": {"screen_name": "alice", "name": "Alice"},
                            }
                        }
                    },
                    "legacy": {
                        "full_text": "价值投资 hello",
                        "created_at": "Sun Apr 21 17:46:07 +0000 2024",
                        "extended_entities": {
                            "media": [
                                {
                                    "media_url_https": "https://pbs.twimg.com/media/a.jpg",
                                    "type": "photo",
                                }
                            ]
                        },
                    },
                },
            },
            # A User object in the same list must be rejected, not stored.
            {
                "__typename": "User",
                "rest_id": "42",
                "legacy": {},
            },
        ]
    }
    source = write_json("raw.json", raw)
    result = import_json(database, source, "alice", "bookmark")
    assert (result.tweets_inserted, result.errors) == (1, 1)
    assert "not a tweet object" in result.error_samples[0]

    summary = stats(database)
    assert summary["tweets"] == 1
    assert summary["unknown_author"] == 0
    hit = search(database, "价值投资")[0]
    assert hit["author_username"] == "alice"
    assert hit["url"] == "https://x.com/alice/status/1782103537234973176"
    assert hit["created_at"] == "2024-04-21T17:46:07+00:00"


def test_legacy_polluted_payload_can_be_pruned(write_json, database):
    """Old exports contained author objects as fake tweets; prune must clean them."""
    legacy = {
        "tweets": [
            {
                "id": "1597654998971604992",
                "author_username": "unknown",
                "author_name": "",
                "text": "",
                "created_at": "2026-10-07T04:23:05.213Z",
                "url": "https://x.com/unknown/status/1597654998971604992",
                "media_urls": [],
            },
            {
                "id": "1782103537234973176",
                "author_username": "alice",
                "author_name": "Alice",
                "text": "real tweet",
                "created_at": "2024-04-21T17:46:07.000Z",
                "url": "https://x.com/alice/status/1782103537234973176",
                "media_urls": [],
            },
        ]
    }
    source = write_json("legacy.json", legacy)
    import_json(database, source, "owner", "bookmark")
    assert stats(database)["empty_text"] == 1

    result = prune(database)
    assert result["removed_empty"] == 1
    assert stats(database)["tweets"] == 1
    assert search(database, "real tweet")[0]["author_username"] == "alice"
    assert verify_database(database)["fts"] == "ok"
