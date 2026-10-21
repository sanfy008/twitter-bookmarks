from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

LATEST_SCHEMA_VERSION = 7

# Base schema (version 0). Everything newer is applied through MIGRATIONS so
# existing archives can be upgraded in place.
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

# Migrations that only need SQL. Versions 2 and 3 need Python data transforms
# and live in _migrate_fts / _migrate_accounts.
MIGRATIONS: dict[int, list[str]] = {
    1: [
        "CREATE INDEX IF NOT EXISTS idx_archive_entries_tweet ON archive_entries(tweet_id)",
        "CREATE INDEX IF NOT EXISTS idx_tweets_created_at ON tweets(created_at)",
    ],
    4: [
        "ALTER TABLE import_runs ADD COLUMN account TEXT",
        "ALTER TABLE import_runs ADD COLUMN entry_type TEXT",
        "ALTER TABLE import_runs ADD COLUMN exported_at TEXT",
        "ALTER TABLE import_runs ADD COLUMN newest_id TEXT",
        "ALTER TABLE import_runs ADD COLUMN total_tweets INTEGER",
        "ALTER TABLE import_runs ADD COLUMN source_sha256 TEXT",
    ],
    5: [
        """CREATE TABLE IF NOT EXISTS import_errors (
            id INTEGER PRIMARY KEY,
            run_id INTEGER NOT NULL REFERENCES import_runs(id) ON DELETE CASCADE,
            record_index INTEGER NOT NULL,
            reason TEXT NOT NULL,
            snippet TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS idx_import_errors_run ON import_errors(run_id)",
    ],
}

# CJK ideographs. FTS5's unicode61 tokenizer treats a contiguous CJK run as a
# single token, which makes substring search impossible. We index a copy of the
# text with every CJK character separated by spaces and query it with phrase
# expressions, which gives exact adjacent-substring matching without extra
# dependencies.
_CJK_CHAR = re.compile(r"([\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff])")
_CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")
_QUERY_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+|[A-Za-z0-9_]+")

_TWEET_TYPES = {"Tweet", "TweetWithVisibilityResults"}
_MEDIA_KEYS = ("media_url_https", "media_url", "url", "expanded_url")


@dataclass(frozen=True)
class ImportStats:
    records_seen: int = 0
    tweets_inserted: int = 0
    tweets_updated: int = 0
    entries_inserted: int = 0
    errors: int = 0
    error_samples: tuple[str, ...] = ()


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def to_index_text(value: str | None) -> str:
    """Return an FTS-friendly copy of *value* with CJK characters separated."""
    return _CJK_CHAR.sub(r" \1 ", value or "")


def build_fts_query(query: str) -> str:
    """Build a safe FTS5 expression that supports CJK substrings and ASCII prefixes."""
    parts: list[str] = []
    for run in _QUERY_RUN.findall(query):
        if _CJK_RUN.fullmatch(run):
            # A phrase of single-character tokens enforces adjacency and order.
            parts.append('"' + " ".join(run) + '"')
        else:
            parts.append(f'"{run}"*')
    if not parts:
        raise ValueError("query must contain at least one letter, number, or underscore")
    return " AND ".join(parts)


def connect(
    path: str | Path, *, read_only: bool = False, configure: bool = True
) -> sqlite3.Connection:
    database = Path(path)
    if read_only:
        if not database.is_file():
            raise FileNotFoundError(f"database does not exist: {database}")
        connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    else:
        database.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database)
        if configure:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=FULL")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def _connect_read(path: str | Path) -> sqlite3.Connection:
    """Open read-only when possible; fall back to read-write for WAL edge cases."""
    try:
        return connect(path, read_only=True)
    except sqlite3.Error:
        return connect(path)


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name=?", (name,)
        ).fetchone()
        is not None
    )


def _optimize_fts(connection: sqlite3.Connection) -> None:
    if _table_exists(connection, "tweets_fts"):
        with suppress(sqlite3.Error):
            connection.execute("INSERT INTO tweets_fts(tweets_fts) VALUES('optimize')")


def initialize(path: str | Path) -> None:
    with closing(connect(path)) as connection, connection:
        connection.executescript(SCHEMA)
        migrated = migrate(connection)
    if migrated:
        # Migrations that rewrite rows leave dead FTS segments; merge them before
        # compacting the file.
        with closing(connect(path)) as connection:
            _optimize_fts(connection)
            connection.commit()
            connection.execute("VACUUM")


def migrate(connection: sqlite3.Connection) -> bool:
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if version >= LATEST_SCHEMA_VERSION:
        return False
    for target in range(version + 1, LATEST_SCHEMA_VERSION + 1):
        if target in (2, 6):
            _migrate_fts(connection)
        elif target == 3:
            _migrate_accounts(connection)
        elif target == 7:
            _migrate_metadata(connection)
        else:
            for statement in MIGRATIONS.get(target, []):
                connection.execute(statement)
        connection.execute(f"PRAGMA user_version={target}")
    connection.commit()
    return True


def _create_fts_triggers(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS tweets_ai AFTER INSERT ON tweets BEGIN
            INSERT INTO tweets_fts(rowid,text,author_name,author_username)
            VALUES(new.pk,new.fts_text,new.fts_author,new.author_username);
        END;
        CREATE TRIGGER IF NOT EXISTS tweets_ad AFTER DELETE ON tweets BEGIN
            INSERT INTO tweets_fts(tweets_fts,rowid,text,author_name,author_username)
            VALUES('delete',old.pk,old.fts_text,old.fts_author,old.author_username);
        END;
        CREATE TRIGGER IF NOT EXISTS tweets_au AFTER UPDATE ON tweets BEGIN
            INSERT INTO tweets_fts(tweets_fts,rowid,text,author_name,author_username)
            VALUES('delete',old.pk,old.fts_text,old.fts_author,old.author_username);
            INSERT INTO tweets_fts(rowid,text,author_name,author_username)
            VALUES(new.pk,new.fts_text,new.fts_author,new.author_username);
        END;
        """
    )


def _fts_is_contentless(connection: sqlite3.Connection) -> bool:
    row = connection.execute("SELECT sql FROM sqlite_master WHERE name='tweets_fts'").fetchone()
    return bool(row and row[0] and "content=''" in row[0].replace('"', "'"))


def _migrate_fts(connection: sqlite3.Connection) -> None:
    """Rebuild the tweet table with a stable integer key and a contentless FTS5
    index. The integer key keeps the FTS rowid mapping valid across VACUUM.
    """
    columns = {row[1] for row in connection.execute("PRAGMA table_info(tweets)")}
    if "pk" in columns and "fts_text" in columns and _fts_is_contentless(connection):
        return

    if "pk" not in columns:
        connection.executescript(
            """
            PRAGMA foreign_keys=OFF;
            BEGIN;
            CREATE TABLE tweets_new (
                pk INTEGER PRIMARY KEY,
                id TEXT NOT NULL UNIQUE,
                author_username TEXT NOT NULL,
                author_name TEXT,
                text TEXT NOT NULL,
                created_at TEXT,
                url TEXT,
                raw_json TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                fts_text TEXT NOT NULL DEFAULT '',
                fts_author TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO tweets_new(id,author_username,author_name,text,created_at,url,raw_json,
                content_hash,first_seen_at,updated_at,fts_text,fts_author)
            SELECT id,author_username,author_name,text,created_at,url,raw_json,
                content_hash,first_seen_at,updated_at,'','' FROM tweets;
            DROP TABLE tweets;
            ALTER TABLE tweets_new RENAME TO tweets;
            COMMIT;
            PRAGMA foreign_keys=ON;
            """
        )
    else:
        if "fts_text" not in columns:
            connection.execute("ALTER TABLE tweets ADD COLUMN fts_text TEXT NOT NULL DEFAULT ''")
        if "fts_author" not in columns:
            connection.execute("ALTER TABLE tweets ADD COLUMN fts_author TEXT NOT NULL DEFAULT ''")

    rows = connection.execute("SELECT id, text, author_name FROM tweets").fetchall()
    connection.executemany(
        "UPDATE tweets SET fts_text=?, fts_author=? WHERE id=?",
        [
            (to_index_text(row["text"]), to_index_text(row["author_name"]), row["id"])
            for row in rows
        ],
    )

    connection.executescript(
        """
        DROP TRIGGER IF EXISTS tweets_ai;
        DROP TRIGGER IF EXISTS tweets_ad;
        DROP TRIGGER IF EXISTS tweets_au;
        DROP TABLE IF EXISTS tweets_fts;
        CREATE VIRTUAL TABLE tweets_fts USING fts5(
            text, author_name, author_username, content='', tokenize='unicode61'
        );
        """
    )
    connection.execute(
        """INSERT INTO tweets_fts(rowid,text,author_name,author_username)
        SELECT pk, fts_text, fts_author, author_username FROM tweets"""
    )
    _create_fts_triggers(connection)


def _migrate_accounts(connection: sqlite3.Connection) -> None:
    duplicates = connection.execute(
        """SELECT lower(username) AS handle, group_concat(id) AS ids
        FROM accounts GROUP BY handle HAVING count(*) > 1"""
    ).fetchall()
    for duplicate in duplicates:
        ids = [int(value) for value in str(duplicate["ids"]).split(",")]
        keep, dropped = ids[0], ids[1:]
        for account_id in dropped:
            connection.execute(
                """INSERT OR IGNORE INTO archive_entries(account_id,tweet_id,entry_type,archived_at)
                SELECT ?,tweet_id,entry_type,archived_at FROM archive_entries WHERE account_id=?""",
                (keep, account_id),
            )
            connection.execute("DELETE FROM archive_entries WHERE account_id=?", (account_id,))
            connection.execute("DELETE FROM accounts WHERE id=?", (account_id,))
    connection.execute(
        "UPDATE accounts SET username=lower(username) WHERE username<>lower(username)"
    )


def _basename(value: str) -> str:
    return re.split(r"[\\/]", value)[-1]


def _migrate_metadata(connection: sqlite3.Connection) -> None:
    """Normalize legacy timestamps and stop storing absolute source paths."""
    rows = connection.execute(
        "SELECT id, created_at FROM tweets WHERE created_at IS NOT NULL"
    ).fetchall()
    updates = []
    for row in rows:
        normalized = _iso_utc(row["created_at"])
        if normalized != row["created_at"]:
            updates.append((normalized, row["id"]))
    connection.executemany("UPDATE tweets SET created_at=? WHERE id=?", updates)

    imports = connection.execute("SELECT id, source_path FROM import_runs").fetchall()
    connection.executemany(
        "UPDATE import_runs SET source_path=? WHERE id=?",
        [
            (_basename(row["source_path"]), row["id"])
            for row in imports
            if _basename(row["source_path"]) != row["source_path"]
        ],
    )


def _first(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None and value != "":
            return value
    return default


def _iso_utc(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC).isoformat(timespec="seconds")
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat(timespec="seconds")


def _author(record: dict[str, Any]) -> tuple[str, str]:
    result = ((record.get("core") or {}).get("user_results") or {}).get("result") or {}
    core = result.get("core") or {}
    legacy = result.get("legacy") or {}
    return (
        str(core.get("screen_name") or legacy.get("screen_name") or ""),
        str(core.get("name") or legacy.get("name") or ""),
    )


def _media(record: dict[str, Any], legacy: dict[str, Any]) -> list[dict[str, str]]:
    value = record.get("media") or record.get("media_urls")
    if value is None:
        extended = (legacy.get("extended_entities") or {}).get("media")
        entities = (legacy.get("entities") or {}).get("media")
        value = extended or entities or []
    if not isinstance(value, list):
        return []
    media: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, str):
            url, media_type = item, "unknown"
        elif isinstance(item, dict):
            url = _first(item, *_MEDIA_KEYS)
            media_type = str(_first(item, "type", default="unknown"))
        else:
            continue
        if not url or str(url) in seen:
            continue
        seen.add(str(url))
        media.append({"url": str(url), "type": media_type})
    return media


def _records(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object or array")
    for key in ("tweets", "bookmarks", "likes", "items", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            try:
                return _records(value)
            except ValueError:
                continue
    if any(key in payload for key in ("id", "id_str", "tweet_id", "rest_id")):
        return [payload]
    raise ValueError("Could not find a supported tweet collection")


def _normalize(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("__typename") == "TweetWithVisibilityResults" and isinstance(
        record.get("tweet"), dict
    ):
        record = record["tweet"]
    typename = record.get("__typename")
    if typename and typename not in _TWEET_TYPES:
        raise ValueError(f"not a tweet object: {typename}")

    legacy = record.get("legacy") if isinstance(record.get("legacy"), dict) else {}
    source = {**legacy, **record}
    author = record.get("author") if isinstance(record.get("author"), dict) else {}
    user = record.get("user") if isinstance(record.get("user"), dict) else {}

    tweet_id = str(_first(source, "rest_id", "id_str", "tweet_id", "id", default="")).strip()
    if not tweet_id:
        raise ValueError("tweet id is missing")

    graph_username, graph_name = _author(record)
    username = (
        graph_username
        or str(
            _first(source, "author_username", "username", "screen_name", default="")
            or _first(author, "username", "screen_name", default="")
            or _first(user, "username", "screen_name", default="")
        )
        .lstrip("@")
        .strip()
        or "unknown"
    )
    author_name = (
        graph_name
        or str(
            _first(source, "author_name", "name", default="")
            or _first(author, "name", default="")
            or _first(user, "name", default="")
        ).strip()
    )

    note = ((record.get("note_tweet") or {}).get("note_tweet_results") or {}).get("result") or {}
    text = str(
        note.get("text") or _first(source, "text", "full_text", "content", default="")
    ).strip()
    created_at = _iso_utc(_first(source, "created_at", "createdAt", "date"))
    media = _media(record, legacy)

    url = _first(source, "url", "tweet_url", "permalink")
    if not url and username != "unknown" and tweet_id.isdigit():
        url = f"https://x.com/{username}/status/{tweet_id}"

    canonical = {
        "id": tweet_id,
        "author_username": username,
        "author_name": author_name,
        "text": text,
        "created_at": created_at,
        "url": str(url) if url else None,
        "media": media,
    }
    canonical["content_hash"] = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    canonical["raw_json"] = json.dumps(record, ensure_ascii=False, sort_keys=True)
    return canonical


def _error_snippet(record: Any) -> str:
    try:
        rendered = json.dumps(record, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        rendered = str(record)
    return rendered[:200]


def _existing_hashes(connection: sqlite3.Connection, ids: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    unique = list(dict.fromkeys(ids))
    for start in range(0, len(unique), 500):
        chunk = unique[start : start + 500]
        placeholders = ",".join("?" for _ in chunk)
        rows = connection.execute(
            f"SELECT id, content_hash FROM tweets WHERE id IN ({placeholders})", chunk
        )
        result.update({row["id"]: row["content_hash"] for row in rows})
    return result


def _sync_media(connection: sqlite3.Connection, tweet: dict[str, Any]) -> None:
    media = tweet["media"]
    urls = [item["url"] for item in media]
    if urls:
        placeholders = ",".join("?" for _ in urls)
        connection.execute(
            f"DELETE FROM tweet_media WHERE tweet_id=? AND media_url NOT IN ({placeholders})",
            (tweet["id"], *urls),
        )
    else:
        connection.execute("DELETE FROM tweet_media WHERE tweet_id=?", (tweet["id"],))
    connection.executemany(
        """INSERT INTO tweet_media(tweet_id,media_url,media_type) VALUES(?,?,?)
        ON CONFLICT(tweet_id,media_url) DO UPDATE SET media_type=excluded.media_type""",
        [(tweet["id"], item["url"], item["type"]) for item in media],
    )


def import_json(
    database: str | Path, source: str | Path, account: str, entry_type: str
) -> ImportStats:
    if entry_type not in {"bookmark", "like"}:
        raise ValueError("entry_type must be bookmark or like")
    account = account.lstrip("@").strip().lower()
    if not account:
        raise ValueError("account must not be empty")

    source_path = Path(source).resolve()
    raw_bytes = source_path.read_bytes()
    payload = json.loads(raw_bytes.decode("utf-8-sig"))
    records = _records(payload)
    metadata = payload if isinstance(payload, dict) else {}

    declared_type = metadata.get("type")
    if declared_type and declared_type != entry_type:
        raise ValueError(
            f"payload type {declared_type!r} does not match requested type {entry_type!r}"
        )
    declared_account = metadata.get("account")
    if declared_account and str(declared_account).lstrip("@").strip().lower() != account:
        raise ValueError(
            f"payload account {declared_account!r} does not match requested account {account!r}"
        )

    exported_at = _iso_utc(metadata.get("exported_at"))
    newest_id = metadata.get("newest_id")
    total_tweets = metadata.get("total_tweets")
    source_sha256 = hashlib.sha256(raw_bytes).hexdigest()

    initialize(database)
    started_at = utc_now()

    seen = 0
    errors: list[tuple[int, str, str]] = []
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        seen += 1
        try:
            if not isinstance(record, dict):
                raise ValueError("record must be an object")
            normalized.append(_normalize(record))
        except (KeyError, TypeError, ValueError) as exc:
            errors.append((index, str(exc), _error_snippet(record)))

    inserted = updated = entries = 0
    with closing(connect(database)) as connection, connection:
        run_id = connection.execute(
            """INSERT INTO import_runs(source_path,started_at,account,entry_type,exported_at,
            newest_id,total_tweets,source_sha256) VALUES(?,?,?,?,?,?,?,?)""",
            (
                source_path.name,
                started_at,
                account,
                entry_type,
                exported_at,
                str(newest_id) if newest_id is not None else None,
                int(total_tweets) if isinstance(total_tweets, int) else None,
                source_sha256,
            ),
        ).lastrowid
        connection.execute(
            "INSERT INTO accounts(username,created_at) VALUES(?,?)"
            " ON CONFLICT(username) DO NOTHING",
            (account, started_at),
        )
        account_id = connection.execute(
            "SELECT id FROM accounts WHERE username=?", (account,)
        ).fetchone()["id"]

        existing = _existing_hashes(connection, [tweet["id"] for tweet in normalized])
        now = utc_now()
        for tweet in normalized:
            previous_hash = existing.get(tweet["id"])
            if previous_hash is None:
                connection.execute(
                    """INSERT INTO tweets(id,author_username,author_name,text,created_at,url,
                    raw_json,content_hash,first_seen_at,updated_at,fts_text,fts_author)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        tweet["id"],
                        tweet["author_username"],
                        tweet["author_name"],
                        tweet["text"],
                        tweet["created_at"],
                        tweet["url"],
                        tweet["raw_json"],
                        tweet["content_hash"],
                        now,
                        now,
                        to_index_text(tweet["text"]),
                        to_index_text(tweet["author_name"]),
                    ),
                )
                _sync_media(connection, tweet)
                inserted += 1
            elif previous_hash != tweet["content_hash"]:
                connection.execute(
                    """UPDATE tweets SET author_username=?,author_name=?,text=?,created_at=?,url=?,
                    raw_json=?,content_hash=?,updated_at=?,fts_text=?,fts_author=? WHERE id=?""",
                    (
                        tweet["author_username"],
                        tweet["author_name"],
                        tweet["text"],
                        tweet["created_at"],
                        tweet["url"],
                        tweet["raw_json"],
                        tweet["content_hash"],
                        now,
                        to_index_text(tweet["text"]),
                        to_index_text(tweet["author_name"]),
                        tweet["id"],
                    ),
                )
                _sync_media(connection, tweet)
                updated += 1

            cursor = connection.execute(
                """INSERT INTO archive_entries(account_id,tweet_id,entry_type,archived_at)
                VALUES(?,?,?,?) ON CONFLICT(account_id,tweet_id,entry_type) DO NOTHING""",
                (account_id, tweet["id"], entry_type, now),
            )
            entries += cursor.rowcount

        if errors:
            connection.executemany(
                """INSERT INTO import_errors(run_id,record_index,reason,snippet) VALUES(?,?,?,?)""",
                [(run_id, index, reason, snippet) for index, reason, snippet in errors],
            )
        connection.execute(
            """UPDATE import_runs SET finished_at=?,records_seen=?,tweets_inserted=?,
            tweets_updated=?,entries_inserted=?,errors=? WHERE id=?""",
            (utc_now(), seen, inserted, updated, entries, len(errors), run_id),
        )

    samples = tuple(f"#{index}: {reason}" for index, reason, _ in errors[:5])
    return ImportStats(seen, inserted, updated, entries, len(errors), samples)


def _snippet(text: str, query: str, radius: int = 60) -> str:
    if not text:
        return ""
    lowered = text.lower()
    matches: list[tuple[int, str]] = []
    for term in _QUERY_RUN.findall(query):
        position = lowered.find(term.lower())
        if position >= 0:
            matches.append((position, term))
    if not matches:
        return text[: radius * 2] + ("…" if len(text) > radius * 2 else "")
    position, term = min(matches)
    start = max(0, position - radius)
    end = min(len(text), position + len(term) + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


def search(
    database: str | Path,
    query: str,
    limit: int = 20,
    *,
    offset: int = 0,
    entry_type: str | None = None,
    account: str | None = None,
) -> list[dict[str, Any]]:
    if not query.strip():
        raise ValueError("query must not be empty")
    if not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if entry_type is not None and entry_type not in {"bookmark", "like"}:
        raise ValueError("entry_type must be bookmark or like")

    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    fts_query = build_fts_query(query)

    with closing(_connect_read(database)) as connection:
        if not _table_exists(connection, "tweets_fts"):
            raise ValueError("database is not initialized; run init or import first")
        tweet_columns = {row[1] for row in connection.execute("PRAGMA table_info(tweets)")}
        fts_columns = {row[1] for row in connection.execute("PRAGMA table_info(tweets_fts)")}
        if "pk" in tweet_columns and "tweet_id" not in fts_columns:
            join = "t.pk=tweets_fts.rowid"
        elif "tweet_id" in fts_columns:
            join = "t.id=tweets_fts.tweet_id"
        else:
            raise ValueError("unsupported database schema; run init to migrate")
        sql = f"""SELECT t.id,t.author_username,t.author_name,t.text,t.created_at,t.url,
        bm25(tweets_fts) AS rank FROM tweets_fts JOIN tweets t ON {join}
        WHERE tweets_fts MATCH ?"""
        params: list[Any] = [fts_query]
        if entry_type is not None or account is not None:
            sql += (
                " AND EXISTS (SELECT 1 FROM archive_entries e JOIN accounts a ON a.id=e.account_id"
                " WHERE e.tweet_id=t.id"
            )
            if entry_type is not None:
                sql += " AND e.entry_type=?"
                params.append(entry_type)
            if account is not None:
                sql += " AND lower(a.username)=lower(?)"
                params.append(account.lstrip("@").strip())
            sql += ")"
        sql += " ORDER BY rank,t.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = connection.execute(sql, params).fetchall()

    return [{**dict(row), "snippet": _snippet(row["text"], query)} for row in rows]


def integrity_check(database: str | Path) -> str:
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    with closing(_connect_read(database)) as connection:
        return str(connection.execute("PRAGMA integrity_check").fetchone()[0])


def _check_fts(database: Path) -> str:
    """Run the FTS5 integrity check. It needs a writable handle even though it
    does not modify data, so open without changing the journal mode."""
    last_error: sqlite3.Error | None = None
    for configure in (False, True):
        try:
            with closing(connect(database, configure=configure)) as connection:
                connection.execute("INSERT INTO tweets_fts(tweets_fts) VALUES('integrity-check')")
            return "ok"
        except sqlite3.Error as exc:
            last_error = exc
    return f"failed: {last_error}"


def verify_database(database: str | Path) -> dict[str, str]:
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    with closing(_connect_read(database)) as connection:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        has_fts = _table_exists(connection, "tweets_fts")
    return {
        "integrity": integrity,
        "foreign_keys": "ok" if not foreign_keys else f"{len(foreign_keys)} violation(s)",
        "fts": _check_fts(database) if has_fts else "skipped",
    }


def backup(database: str | Path, destination: str | Path, *, keep: int = 10) -> Path:
    source = Path(database)
    if not source.is_file():
        raise FileNotFoundError(f"database does not exist: {source}")
    target = Path(destination).resolve()
    if target == source.resolve():
        raise ValueError("backup destination must differ from the source database")
    if target.is_dir() or not target.suffix:
        target.mkdir(parents=True, exist_ok=True)
        target = target / f"x-archive-{datetime.now():%Y%m%d-%H%M%S}.sqlite3"
    else:
        target.parent.mkdir(parents=True, exist_ok=True)

    with (
        closing(connect(source)) as source_connection,
        source_connection,
        closing(sqlite3.connect(target)) as destination_connection,
        destination_connection,
    ):
        source_connection.backup(destination_connection)
        # The backup inherits the WAL header from the source. Switch it back to
        # DELETE so the file is self-contained and leaves no -wal/-shm siblings.
        destination_connection.execute("PRAGMA journal_mode=DELETE")

    if integrity_check(target) != "ok":
        target.unlink(missing_ok=True)
        raise RuntimeError("backup integrity check failed")

    if keep > 0:
        for stale in sorted(target.parent.glob("x-archive-*.sqlite3"))[:-keep]:
            stale.unlink(missing_ok=True)
    return target


def stats(database: str | Path) -> dict[str, Any]:
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    with closing(_connect_read(database)) as connection:

        def scalar(sql: str, params: tuple[Any, ...] = ()) -> Any:
            return connection.execute(sql, params).fetchone()[0]

        last_import = connection.execute(
            "SELECT * FROM import_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return {
            "database": str(database.resolve()),
            "size_bytes": database.stat().st_size,
            "schema_version": scalar("PRAGMA user_version"),
            "tweets": scalar("SELECT count(*) FROM tweets"),
            "bookmarks": scalar("SELECT count(*) FROM archive_entries WHERE entry_type='bookmark'"),
            "likes": scalar("SELECT count(*) FROM archive_entries WHERE entry_type='like'"),
            "media": scalar("SELECT count(*) FROM tweet_media"),
            "empty_text": scalar("SELECT count(*) FROM tweets WHERE text=''"),
            "unknown_author": scalar(
                "SELECT count(*) FROM tweets WHERE author_username IN ('', 'unknown')"
            ),
            "accounts": [
                dict(row)
                for row in connection.execute(
                    "SELECT username, created_at FROM accounts ORDER BY username"
                )
            ],
            "created_range": dict(
                connection.execute(
                    "SELECT min(created_at) AS oldest, max(created_at) AS newest FROM tweets"
                ).fetchone()
            ),
            "last_import": dict(last_import) if last_import else None,
        }


def forget_account(database: str | Path, account: str, *, vacuum: bool = True) -> dict[str, Any]:
    """Remove one account and every archive entry that belongs to it."""
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    handle = account.lstrip("@").strip().lower()
    if not handle:
        raise ValueError("account must not be empty")
    with closing(connect(database)) as connection, connection:
        row = connection.execute(
            "SELECT id FROM accounts WHERE lower(username)=lower(?)", (handle,)
        ).fetchone()
        if row is None:
            return {"account": handle, "removed": False, "orphan_tweets_removed": 0}
        connection.execute("DELETE FROM accounts WHERE id=?", (row["id"],))
        removed = connection.execute(
            "DELETE FROM tweets WHERE id NOT IN (SELECT tweet_id FROM archive_entries)"
        ).rowcount
    if vacuum:
        with closing(connect(database)) as connection:
            _optimize_fts(connection)
            connection.commit()
            connection.execute("VACUUM")
    return {"account": handle, "removed": True, "orphan_tweets_removed": removed}


def prune(database: str | Path, *, dry_run: bool = False, vacuum: bool = True) -> dict[str, Any]:
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    empty_where = "text='' AND author_username IN ('', 'unknown')"
    with closing(connect(database)) as connection, connection:
        empty = connection.execute(f"SELECT count(*) FROM tweets WHERE {empty_where}").fetchone()[0]
        orphan = connection.execute(
            """SELECT count(*) FROM tweets t
            WHERE NOT EXISTS (SELECT 1 FROM archive_entries e WHERE e.tweet_id=t.id)"""
        ).fetchone()[0]
        removed_empty = removed_orphan = removed_accounts = 0
        if not dry_run:
            removed_empty = connection.execute(f"DELETE FROM tweets WHERE {empty_where}").rowcount
            removed_orphan = connection.execute(
                """DELETE FROM tweets WHERE id NOT IN (SELECT tweet_id FROM archive_entries)"""
            ).rowcount
            removed_accounts = connection.execute(
                "DELETE FROM accounts WHERE id NOT IN "
                "(SELECT DISTINCT account_id FROM archive_entries)"
            ).rowcount

    if vacuum and not dry_run:
        with closing(connect(database)) as connection:
            _optimize_fts(connection)
            connection.commit()
            connection.execute("VACUUM")

    return {
        "dry_run": dry_run,
        "empty_text": empty,
        "orphan": orphan,
        "removed_empty": removed_empty,
        "removed_orphan": removed_orphan,
        "removed_accounts": removed_accounts,
    }
