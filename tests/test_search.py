import sqlite3

import pytest

from x_local_archive.db import build_fts_query, import_json, search


def seed(write_json, database):
    alice = write_json(
        "alice.json",
        {
            "tweets": [
                {
                    "id": "1",
                    "text": "价值投资在中国市场的实践",
                    "username": "alice",
                    "created_at": "2024-04-21T17:46:07Z",
                },
                {"id": "3", "text": "价值 投资 分开出现", "username": "alice"},
            ]
        },
    )
    bob = write_json(
        "bob.json",
        {"tweets": [{"id": "2", "text": "SQLite full text search", "username": "bob"}]},
    )
    import_json(database, alice, "alice", "bookmark")
    import_json(database, bob, "bob", "like")
    return database


def test_cjk_substring_search(write_json, database):
    seed(write_json, database)
    ids = {row["id"] for row in search(database, "价值投资")}
    assert "1" in ids
    assert {row["id"] for row in search(database, "投资")} == {"1", "3"}
    # Reversed characters must not match: adjacency is enforced by a phrase.
    assert search(database, "资投") == []
    assert search(database, "值价") == []


def test_ascii_prefix_search(write_json, database):
    seed(write_json, database)
    assert search(database, "sqlit")[0]["id"] == "2"
    assert search(database, "SQL")[0]["id"] == "2"
    assert search(database, "full")[0]["id"] == "2"


def test_search_filters_and_case_insensitive_account(write_json, database):
    seed(write_json, database)
    assert {row["id"] for row in search(database, "投资", entry_type="bookmark")} == {"1", "3"}
    assert {row["id"] for row in search(database, "投资", entry_type="like")} == set()
    assert search(database, "SQLite", account="BOB")[0]["id"] == "2"
    assert search(database, "SQLite", account="alice") == []


def test_search_returns_a_snippet(write_json, database):
    seed(write_json, database)
    result = next(row for row in search(database, "价值投资") if row["id"] == "1")
    assert "价值投资" in result["snippet"]


def test_search_validates_limit_and_offset(write_json, database):
    seed(write_json, database)
    with pytest.raises(ValueError):
        search(database, "投资", 0)
    with pytest.raises(ValueError):
        search(database, "投资", 1001)
    with pytest.raises(ValueError):
        search(database, "投资", offset=-1)


def test_search_handles_special_characters(write_json, database):
    source = write_json(
        "export.json", {"tweets": [{"id": "s1", "text": "C++ OR (archive)", "username": "a"}]}
    )
    import_json(database, source, "owner", "bookmark")
    assert search(database, "C++")[0]["id"] == "s1"
    assert search(database, "OR")[0]["id"] == "s1"
    assert search(database, "(archive")[0]["id"] == "s1"
    with pytest.raises(ValueError):
        search(database, "+++")


def test_search_on_uninitialized_database(tmp_path):
    path = tmp_path / "empty.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE placeholder (id INTEGER)")
    with pytest.raises(ValueError, match="not initialized"):
        search(path, "anything")


def test_fts_query_builder():
    assert build_fts_query("价值投资") == '"价 值 投 资"'
    assert build_fts_query("sqlit") == '"sqlit"*'
    assert build_fts_query("AI 投资") == '"AI"* AND "投 资"'
    with pytest.raises(ValueError):
        build_fts_query("+++")


def test_search_filters(write_json, database):
    first = write_json(
        "a.json",
        {
            "account": "alice",
            "type": "bookmark",
            "folder_id": "f1",
            "tweets": [
                {
                    "id": "1",
                    "text": "投资 AI",
                    "author_username": "alice",
                    "author_id": "42",
                    "created_at": "2024-01-01T00:00:00Z",
                    "media": [{"url": "https://m/a.jpg", "type": "photo"}],
                }
            ],
        },
    )
    second = write_json(
        "b.json",
        {
            "account": "alice",
            "type": "bookmark",
            "tweets": [
                {
                    "id": "2",
                    "text": "投资 BTC",
                    "author_username": "bob",
                    "author_id": "43",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            ],
        },
    )
    import_json(database, first, "alice", "bookmark")
    import_json(database, second, "alice", "bookmark")

    assert {row["id"] for row in search(database, "投资", author="alice")} == {"1"}
    assert {row["id"] for row in search(database, "投资", author="43")} == {"2"}
    assert {row["id"] for row in search(database, "投资", since="2024-06-01")} == {"2"}
    assert {row["id"] for row in search(database, "投资", until="2024-12-31")} == {"1"}
    assert {row["id"] for row in search(database, "投资", has_media=True)} == {"1"}
    assert {row["id"] for row in search(database, "投资", folder="f1")} == {"1"}
