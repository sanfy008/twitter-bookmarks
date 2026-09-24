from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tweets (
    id TEXT PRIMARY KEY,
    author_username TEXT NOT NULL,
    author_name TEXT,
    text TEXT NOT NULL,
    created_at TEXT,
    url TEXT,
    raw_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS archive_entries (
    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    tweet_id TEXT NOT NULL REFERENCES tweets(id) ON DELETE CASCADE,
    entry_type TEXT NOT NULL CHECK (entry_type IN ('bookmark', 'like')),
    archived_at TEXT NOT NULL,
    PRIMARY KEY (account_id, tweet_id, entry_type)
);
CREATE TABLE IF NOT EXISTS tweet_media (
    id INTEGER PRIMARY KEY,
    tweet_id TEXT NOT NULL REFERENCES tweets(id) ON DELETE CASCADE,
    media_url TEXT NOT NULL,
    media_type TEXT,
    local_path TEXT,
    UNIQUE (tweet_id, media_url)
);
CREATE TABLE IF NOT EXISTS import_runs (
    id INTEGER PRIMARY KEY,
    source_path TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    records_seen INTEGER NOT NULL DEFAULT 0,
    tweets_inserted INTEGER NOT NULL DEFAULT 0,
    tweets_updated INTEGER NOT NULL DEFAULT 0,
    entries_inserted INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0
);
CREATE VIRTUAL TABLE IF NOT EXISTS tweets_fts USING fts5(
    tweet_id UNINDEXED, text, author_name, author_username, tokenize='unicode61'
);
CREATE TRIGGER IF NOT EXISTS tweets_ai AFTER INSERT ON tweets BEGIN
    INSERT INTO tweets_fts(tweet_id,text,author_name,author_username)
    VALUES(new.id,new.text,coalesce(new.author_name,''),new.author_username);
END;
CREATE TRIGGER IF NOT EXISTS tweets_ad AFTER DELETE ON tweets BEGIN
    DELETE FROM tweets_fts WHERE tweet_id=old.id;
END;
CREATE TRIGGER IF NOT EXISTS tweets_au AFTER UPDATE ON tweets BEGIN
    DELETE FROM tweets_fts WHERE tweet_id=old.id;
    INSERT INTO tweets_fts(tweet_id,text,author_name,author_username)
    VALUES(new.id,new.text,coalesce(new.author_name,''),new.author_username);
END;
"""


@dataclass(frozen=True)
class ImportStats:
    records_seen: int = 0
    tweets_inserted: int = 0
    tweets_updated: int = 0
    entries_inserted: int = 0
    errors: int = 0


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(path: str | Path) -> sqlite3.Connection:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    return connection


def initialize(path: str | Path) -> None:
    with connect(path) as connection:
        connection.executescript(SCHEMA)


def _first(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return default


def _records(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object or array")
    for key in ("tweets", "bookmarks", "likes", "items", "data"):
        if isinstance(payload.get(key), list):
            return payload[key]
    if any(key in payload for key in ("id", "id_str", "tweet_id", "rest_id")):
        return [payload]
    raise ValueError("Could not find a supported tweet collection")


def _normalize(record: dict[str, Any]) -> dict[str, Any]:
    legacy = record.get("legacy") if isinstance(record.get("legacy"), dict) else {}
    source = {**legacy, **record}
    author = record.get("author") if isinstance(record.get("author"), dict) else {}
    user = record.get("user") if isinstance(record.get("user"), dict) else {}
    tweet_id = str(_first(source, "id", "id_str", "tweet_id", "rest_id", default="")).strip()
    if not tweet_id:
        raise ValueError("tweet id is missing")
    username = str(
        _first(source, "author_username", "username", "screen_name", default="")
        or _first(author, "username", "screen_name", default="")
        or _first(user, "username", "screen_name", default="")
    ).lstrip("@").strip() or "unknown"
    author_name = str(
        _first(source, "author_name", "name", default="")
        or _first(author, "name", default="")
        or _first(user, "name", default="")
    ).strip()
    text = str(_first(source, "text", "full_text", "content", default="")).strip()
    created_at = _first(source, "created_at", "createdAt", "date")
    url = _first(source, "url", "tweet_url", "permalink")
    if not url and username != "unknown":
        url = f"https://x.com/{username}/status/{tweet_id}"
    media: list[dict[str, str]] = []
    media_value = _first(source, "media", "media_urls", default=[])
    if isinstance(media_value, list):
        for item in media_value:
            if isinstance(item, str):
                media.append({"url": item, "type": "unknown"})
            elif isinstance(item, dict):
                media_url = _first(item, "url", "media_url_https", "media_url", "expanded_url")
                if media_url:
                    media.append({"url": str(media_url), "type": str(_first(item, "type", default="unknown"))})
    canonical = {
        "id": tweet_id,
        "author_username": username,
        "author_name": author_name,
        "text": text,
        "created_at": str(created_at) if created_at else None,
        "url": str(url) if url else None,
        "media": media,
    }
    canonical["content_hash"] = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    canonical["raw_json"] = json.dumps(record, ensure_ascii=False, sort_keys=True)
    return canonical


def import_json(database: str | Path, source: str | Path, account: str, entry_type: str) -> ImportStats:
    if entry_type not in {"bookmark", "like"}:
        raise ValueError("entry_type must be bookmark or like")
    account = account.lstrip("@").strip()
    if not account:
        raise ValueError("account must not be empty")
    source_path = Path(source).resolve()
    records = _records(json.loads(source_path.read_text(encoding="utf-8-sig")))
    initialize(database)
    started_at = utc_now()
    with connect(database) as connection:
        run_id = connection.execute(
            "INSERT INTO import_runs(source_path,started_at) VALUES(?,?)", (str(source_path), started_at)
        ).lastrowid
        connection.execute(
            "INSERT INTO accounts(username,created_at) VALUES(?,?) ON CONFLICT(username) DO NOTHING",
            (account, started_at),
        )
        account_id = connection.execute("SELECT id FROM accounts WHERE username=?", (account,)).fetchone()["id"]
        seen = inserted = updated = entries = errors = 0
        for record in records:
            seen += 1
            try:
                if not isinstance(record, dict):
                    raise ValueError("record must be an object")
                tweet = _normalize(record)
                existing = connection.execute("SELECT content_hash FROM tweets WHERE id=?", (tweet["id"],)).fetchone()
                now = utc_now()
                if existing is None:
                    connection.execute(
                        """INSERT INTO tweets(id,author_username,author_name,text,created_at,url,raw_json,
                        content_hash,first_seen_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (tweet["id"], tweet["author_username"], tweet["author_name"], tweet["text"],
                         tweet["created_at"], tweet["url"], tweet["raw_json"], tweet["content_hash"], now, now),
                    )
                    inserted += 1
                elif existing["content_hash"] != tweet["content_hash"]:
                    connection.execute(
                        """UPDATE tweets SET author_username=?,author_name=?,text=?,created_at=?,url=?,
                        raw_json=?,content_hash=?,updated_at=? WHERE id=?""",
                        (tweet["author_username"], tweet["author_name"], tweet["text"], tweet["created_at"],
                         tweet["url"], tweet["raw_json"], tweet["content_hash"], now, tweet["id"]),
                    )
                    updated += 1
                cursor = connection.execute(
                    """INSERT INTO archive_entries(account_id,tweet_id,entry_type,archived_at) VALUES(?,?,?,?)
                    ON CONFLICT(account_id,tweet_id,entry_type) DO NOTHING""",
                    (account_id, tweet["id"], entry_type, now),
                )
                entries += cursor.rowcount
                for media in tweet["media"]:
                    connection.execute(
                        """INSERT INTO tweet_media(tweet_id,media_url,media_type) VALUES(?,?,?)
                        ON CONFLICT(tweet_id,media_url) DO UPDATE SET media_type=excluded.media_type""",
                        (tweet["id"], media["url"], media["type"]),
                    )
            except (KeyError, TypeError, ValueError):
                errors += 1
        connection.execute(
            """UPDATE import_runs SET finished_at=?,records_seen=?,tweets_inserted=?,tweets_updated=?,
            entries_inserted=?,errors=? WHERE id=?""",
            (utc_now(), seen, inserted, updated, entries, errors, run_id),
        )
    return ImportStats(seen, inserted, updated, entries, errors)


def search(database: str | Path, query: str, limit: int = 20) -> list[dict[str, Any]]:
    if not query.strip():
        raise ValueError("query must not be empty")
    with connect(database) as connection:
        rows = connection.execute(
            """SELECT t.id,t.author_username,t.author_name,t.text,t.created_at,t.url,
            bm25(tweets_fts) AS rank FROM tweets_fts JOIN tweets t ON t.id=tweets_fts.tweet_id
            WHERE tweets_fts MATCH ? ORDER BY rank,t.created_at DESC LIMIT ?""", (query, limit)
        ).fetchall()
    return [dict(row) for row in rows]


def integrity_check(database: str | Path) -> str:
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    with connect(database) as connection:
        return str(connection.execute("PRAGMA integrity_check").fetchone()[0])


def backup(database: str | Path, destination: str | Path) -> Path:
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    target = Path(destination).resolve()
    if target.is_dir() or not target.suffix:
        target.mkdir(parents=True, exist_ok=True)
        target = target / f"x-archive-{datetime.now():%Y%m%d-%H%M%S}.sqlite3"
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
    with connect(database) as source_connection:
        with sqlite3.connect(target) as destination_connection:
            source_connection.backup(destination_connection)
    if integrity_check(target) != "ok":
        target.unlink(missing_ok=True)
        raise RuntimeError("backup integrity check failed")
    return target
