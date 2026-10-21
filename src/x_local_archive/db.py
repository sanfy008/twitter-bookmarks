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

LATEST_SCHEMA_VERSION = 8

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
    8: [
        "ALTER TABLE tweets ADD COLUMN author_id TEXT",
        "ALTER TABLE tweets ADD COLUMN conversation_id TEXT",
        "ALTER TABLE tweets ADD COLUMN in_reply_to_id TEXT",
        "ALTER TABLE tweets ADD COLUMN quoted_tweet_id TEXT",
        "ALTER TABLE tweets ADD COLUMN retweeted_tweet_id TEXT",
        "ALTER TABLE tweets ADD COLUMN lang TEXT",
        "ALTER TABLE tweets ADD COLUMN source TEXT",
        "ALTER TABLE tweets ADD COLUMN status TEXT NOT NULL DEFAULT 'available'",
        "ALTER TABLE tweets ADD COLUMN last_checked_at TEXT",
        """CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            handle TEXT NOT NULL,
            name TEXT,
            followers INTEGER,
            verified INTEGER,
            avatar_url TEXT,
            first_seen_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS tweet_entities (
            tweet_id TEXT NOT NULL REFERENCES tweets(id) ON DELETE CASCADE,
            kind TEXT NOT NULL CHECK (kind IN ('hashtag', 'mention', 'url', 'symbol')),
            value TEXT NOT NULL,
            expanded TEXT,
            PRIMARY KEY (tweet_id, kind, value)
        )""",
        """CREATE TABLE IF NOT EXISTS tweet_metrics (
            tweet_id TEXT NOT NULL REFERENCES tweets(id) ON DELETE CASCADE,
            captured_at TEXT NOT NULL,
            favorite_count INTEGER,
            retweet_count INTEGER,
            reply_count INTEGER,
            quote_count INTEGER,
            bookmark_count INTEGER,
            view_count INTEGER,
            PRIMARY KEY (tweet_id, captured_at)
        )""",
        """CREATE TABLE IF NOT EXISTS bookmark_folders (
            folder_id TEXT PRIMARY KEY,
            account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            name TEXT,
            first_seen_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        "ALTER TABLE archive_entries ADD COLUMN folder_id TEXT",
        "ALTER TABLE archive_entries ADD COLUMN run_id INTEGER",
        "ALTER TABLE archive_entries ADD COLUMN read_status TEXT NOT NULL DEFAULT 'unread'",
        "ALTER TABLE tweet_media ADD COLUMN media_id TEXT",
        "ALTER TABLE tweet_media ADD COLUMN width INTEGER",
        "ALTER TABLE tweet_media ADD COLUMN height INTEGER",
        "ALTER TABLE tweet_media ADD COLUMN duration_ms INTEGER",
        "ALTER TABLE tweet_media ADD COLUMN alt_text TEXT",
        "ALTER TABLE tweet_media ADD COLUMN variants_json TEXT",
        "ALTER TABLE tweet_media ADD COLUMN sha256 TEXT",
        "ALTER TABLE tweet_media ADD COLUMN downloaded_at TEXT",
        "ALTER TABLE tweet_media ADD COLUMN status TEXT NOT NULL DEFAULT 'remote'",
        "ALTER TABLE import_runs ADD COLUMN folder_id TEXT",
        "CREATE INDEX IF NOT EXISTS idx_tweets_author ON tweets(author_username)",
        "CREATE INDEX IF NOT EXISTS idx_tweets_author_id ON tweets(author_id)",
        "CREATE INDEX IF NOT EXISTS idx_entities_value ON tweet_entities(kind, value)",
        "CREATE INDEX IF NOT EXISTS idx_metrics_tweet ON tweet_metrics(tweet_id)",
        "CREATE INDEX IF NOT EXISTS idx_entries_folder ON archive_entries(folder_id)",
        "CREATE INDEX IF NOT EXISTS idx_users_handle ON users(handle)",
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


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bool_int(value: Any) -> int:
    return 1 if value else 0


def _media(record: dict[str, Any], legacy: dict[str, Any]) -> list[dict[str, Any]]:
    value = record.get("media") or record.get("media_urls")
    if value is None:
        extended = (legacy.get("extended_entities") or {}).get("media")
        entities = (legacy.get("entities") or {}).get("media")
        value = extended or entities or []
    if not isinstance(value, list):
        return []
    media: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, str):
            data: dict[str, Any] = {"url": item, "type": "unknown"}
        elif isinstance(item, dict):
            original = (
                item.get("original_info") if isinstance(item.get("original_info"), dict) else {}
            )
            video = item.get("video_info") if isinstance(item.get("video_info"), dict) else {}
            variants = video.get("variants") or item.get("variants")
            if variants is None:
                variants_json = None
            elif isinstance(variants, str):
                variants_json = variants
            else:
                variants_json = json.dumps(variants, ensure_ascii=False, sort_keys=True)
            data = {
                "url": str(_first(item, *_MEDIA_KEYS) or ""),
                "type": str(_first(item, "type", default="unknown")),
                "media_id": str(_first(item, "media_id", "media_key", "id_str", default=""))
                or None,
                "width": _int_or_none(_first(original, "width", default=item.get("width"))),
                "height": _int_or_none(_first(original, "height", default=item.get("height"))),
                "duration_ms": _int_or_none(
                    _first(video, "duration_millis", default=item.get("duration_ms"))
                ),
                "alt_text": _first(item, "alt_text", "ext_alt_text"),
                "variants": variants_json,
            }
        else:
            continue
        url = data["url"]
        if not url or url in seen:
            continue
        seen.add(url)
        media.append(data)
    return media


def _entities(record: dict[str, Any], legacy: dict[str, Any]) -> list[dict[str, Any]]:
    value = record.get("entities")
    if not isinstance(value, dict):
        value = legacy.get("entities") if isinstance(legacy.get("entities"), dict) else {}
    entities: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, text: Any, expanded: Any = None) -> None:
        if not text:
            return
        key = (kind, str(text))
        if key in seen:
            return
        seen.add(key)
        entities.append(
            {
                "kind": kind,
                "value": str(text),
                "expanded": str(expanded) if expanded else None,
            }
        )

    for item in value.get("hashtags") or []:
        add("hashtag", item if isinstance(item, str) else item.get("text"))
    for item in value.get("user_mentions") or value.get("mentions") or []:
        add(
            "mention",
            item if isinstance(item, str) else item.get("screen_name") or item.get("username"),
        )
    for item in value.get("urls") or []:
        if isinstance(item, str):
            add("url", item)
        elif isinstance(item, dict):
            add(
                "url",
                item.get("url") or item.get("expanded_url"),
                item.get("expanded_url") or item.get("expanded"),
            )
    for item in value.get("symbols") or []:
        add("symbol", item if isinstance(item, str) else item.get("text"))
    return entities


def _metrics(record: dict[str, Any], legacy: dict[str, Any]) -> dict[str, int | None]:
    value = record.get("metrics") if isinstance(record.get("metrics"), dict) else {}

    def pick(flat: str, raw: str) -> Any:
        if value.get(flat) is not None:
            return value.get(flat)
        return legacy.get(raw)

    views = value.get("views")
    if views is None:
        views = record.get("views") or legacy.get("views")
        if isinstance(views, dict):
            views = views.get("count")
    return {
        "favorite": _int_or_none(pick("favorite", "favorite_count")),
        "retweet": _int_or_none(pick("retweet", "retweet_count")),
        "reply": _int_or_none(pick("reply", "reply_count")),
        "quote": _int_or_none(pick("quote", "quote_count")),
        "bookmark": _int_or_none(pick("bookmark", "bookmark_count")),
        "views": _int_or_none(views),
    }


def _relations(record: dict[str, Any], legacy: dict[str, Any]) -> dict[str, str | None]:
    value = record.get("relations") if isinstance(record.get("relations"), dict) else {}

    def pick(flat: str, raw: str) -> str | None:
        text = value.get(flat) or legacy.get(raw)
        return str(text) if text else None

    return {
        "quoted_id": pick("quoted_id", "quoted_status_id_str"),
        "retweeted_id": pick("retweeted_id", "retweeted_status_id_str"),
        "in_reply_to_id": pick("in_reply_to_id", "in_reply_to_status_id_str"),
        "conversation_id": pick("conversation_id", "conversation_id_str"),
    }


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
    user_result = ((record.get("core") or {}).get("user_results") or {}).get("result") or {}

    tweet_id = str(_first(source, "rest_id", "id_str", "tweet_id", "id", default="")).strip()
    if not tweet_id:
        raise ValueError("tweet id is missing")
    if "://" in tweet_id:
        raise ValueError("tweet id looks like a URL")

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
    entities = _entities(record, legacy)
    metrics = _metrics(record, legacy)
    relations = _relations(record, legacy)

    user_legacy = user_result.get("legacy") if isinstance(user_result.get("legacy"), dict) else {}
    avatar = user_result.get("avatar")
    author_id = (
        str(_first(user_result, "rest_id", "id_str", default="")).strip()
        or str(_first(source, "author_id", default="")).strip()
        or None
    )
    author_followers = _int_or_none(
        _first(user_legacy, "followers_count", default=source.get("author_followers"))
    )
    author_verified = _bool_int(
        user_legacy.get("verified")
        or user_result.get("is_blue_verified")
        or source.get("author_verified")
    )
    author_avatar = (
        user_legacy.get("profile_image_url_https")
        or (avatar.get("image_url") if isinstance(avatar, dict) else None)
        or source.get("author_avatar")
    )
    lang = _first(source, "lang", default=None)
    source_client = _first(source, "source", default=None)
    status = str(record.get("status") or "available")

    url = _first(source, "url", "tweet_url", "permalink")
    if not url and username != "unknown" and tweet_id.isdigit():
        url = f"https://x.com/{username}/status/{tweet_id}"

    stable = {
        "id": tweet_id,
        "author_username": username,
        "author_name": author_name,
        "author_id": author_id,
        "text": text,
        "created_at": created_at,
        "url": str(url) if url else None,
        "lang": str(lang) if lang else None,
        "source": str(source_client) if source_client else None,
        "entities": entities,
        "relations": relations,
        "media": media,
        "status": status,
    }
    content_hash = hashlib.sha256(
        json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return {
        **stable,
        "author_followers": author_followers,
        "author_verified": author_verified,
        "author_avatar": str(author_avatar) if author_avatar else None,
        "metrics": metrics,
        "content_hash": content_hash,
        "raw_json": json.dumps(record, ensure_ascii=False, sort_keys=True),
    }


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
        """INSERT INTO tweet_media(
        tweet_id,media_url,media_type,media_id,width,height,duration_ms,alt_text,variants_json)
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(tweet_id,media_url) DO UPDATE SET
        media_type=excluded.media_type, media_id=excluded.media_id,
        width=excluded.width, height=excluded.height,
        duration_ms=excluded.duration_ms, alt_text=excluded.alt_text,
        variants_json=excluded.variants_json""",
        [
            (
                tweet["id"],
                item["url"],
                item["type"],
                item.get("media_id"),
                item.get("width"),
                item.get("height"),
                item.get("duration_ms"),
                item.get("alt_text"),
                item.get("variants"),
            )
            for item in media
        ],
    )


def _sync_entities(connection: sqlite3.Connection, tweet: dict[str, Any]) -> None:
    connection.execute("DELETE FROM tweet_entities WHERE tweet_id=?", (tweet["id"],))
    rows = [
        (tweet["id"], item["kind"], item["value"], item["expanded"]) for item in tweet["entities"]
    ]
    if rows:
        connection.executemany(
            "INSERT OR IGNORE INTO tweet_entities(tweet_id,kind,value,expanded) VALUES(?,?,?,?)",
            rows,
        )


def _sync_user(connection: sqlite3.Connection, tweet: dict[str, Any], now: str) -> None:
    if not tweet.get("author_id"):
        return
    connection.execute(
        """INSERT INTO users(user_id,handle,name,followers,verified,avatar_url,
        first_seen_at,updated_at) VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET
        handle=excluded.handle, name=excluded.name,
        followers=coalesce(excluded.followers,users.followers),
        verified=excluded.verified,
        avatar_url=coalesce(excluded.avatar_url,users.avatar_url),
        updated_at=excluded.updated_at""",
        (
            tweet["author_id"],
            tweet["author_username"],
            tweet["author_name"],
            tweet["author_followers"],
            tweet["author_verified"],
            tweet["author_avatar"],
            now,
            now,
        ),
    )


def _sync_metrics(connection: sqlite3.Connection, tweet: dict[str, Any], now: str) -> None:
    metrics = tweet["metrics"]
    values = (
        metrics["favorite"],
        metrics["retweet"],
        metrics["reply"],
        metrics["quote"],
        metrics["bookmark"],
        metrics["views"],
    )
    if all(value is None for value in values):
        return
    latest = connection.execute(
        """SELECT favorite_count,retweet_count,reply_count,quote_count,bookmark_count,view_count
        FROM tweet_metrics WHERE tweet_id=? ORDER BY captured_at DESC LIMIT 1""",
        (tweet["id"],),
    ).fetchone()
    if latest is not None and tuple(latest) == values:
        return
    connection.execute(
        """INSERT INTO tweet_metrics(tweet_id,captured_at,favorite_count,retweet_count,
        reply_count,quote_count,bookmark_count,view_count) VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(tweet_id,captured_at) DO UPDATE SET
        favorite_count=excluded.favorite_count, retweet_count=excluded.retweet_count,
        reply_count=excluded.reply_count, quote_count=excluded.quote_count,
        bookmark_count=excluded.bookmark_count, view_count=excluded.view_count""",
        (tweet["id"], now, *values),
    )


def _insert_tweet(connection: sqlite3.Connection, tweet: dict[str, Any], now: str) -> None:
    connection.execute(
        """INSERT INTO tweets(
        id,author_username,author_name,author_id,text,created_at,url,lang,source,
        conversation_id,in_reply_to_id,quoted_tweet_id,retweeted_tweet_id,
        status,last_checked_at,raw_json,content_hash,first_seen_at,updated_at,fts_text,fts_author)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            tweet["id"],
            tweet["author_username"],
            tweet["author_name"],
            tweet["author_id"],
            tweet["text"],
            tweet["created_at"],
            tweet["url"],
            tweet["lang"],
            tweet["source"],
            tweet["relations"]["conversation_id"],
            tweet["relations"]["in_reply_to_id"],
            tweet["relations"]["quoted_id"],
            tweet["relations"]["retweeted_id"],
            tweet["status"],
            now,
            tweet["raw_json"],
            tweet["content_hash"],
            now,
            now,
            to_index_text(tweet["text"]),
            to_index_text(tweet["author_name"]),
        ),
    )


def _update_tweet(connection: sqlite3.Connection, tweet: dict[str, Any], now: str) -> None:
    connection.execute(
        """UPDATE tweets SET author_username=?,author_name=?,author_id=?,text=?,created_at=?,
        url=?,lang=?,source=?,conversation_id=?,in_reply_to_id=?,quoted_tweet_id=?,
        retweeted_tweet_id=?,status=?,last_checked_at=?,raw_json=?,content_hash=?,
        updated_at=?,fts_text=?,fts_author=? WHERE id=?""",
        (
            tweet["author_username"],
            tweet["author_name"],
            tweet["author_id"],
            tweet["text"],
            tweet["created_at"],
            tweet["url"],
            tweet["lang"],
            tweet["source"],
            tweet["relations"]["conversation_id"],
            tweet["relations"]["in_reply_to_id"],
            tweet["relations"]["quoted_id"],
            tweet["relations"]["retweeted_id"],
            tweet["status"],
            now,
            tweet["raw_json"],
            tweet["content_hash"],
            now,
            to_index_text(tweet["text"]),
            to_index_text(tweet["author_name"]),
            tweet["id"],
        ),
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
    folder_id = metadata.get("folder_id")
    folder_name = metadata.get("folder_name")
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
            newest_id,total_tweets,source_sha256,folder_id) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                source_path.name,
                started_at,
                account,
                entry_type,
                exported_at,
                str(newest_id) if newest_id is not None else None,
                int(total_tweets) if isinstance(total_tweets, int) else None,
                source_sha256,
                str(folder_id) if folder_id else None,
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

        now = utc_now()
        if folder_id:
            connection.execute(
                """INSERT INTO bookmark_folders(folder_id,account_id,name,first_seen_at,updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(folder_id) DO UPDATE SET
                name=coalesce(excluded.name,bookmark_folders.name),
                updated_at=excluded.updated_at""",
                (str(folder_id), account_id, folder_name, now, now),
            )

        existing = _existing_hashes(connection, [tweet["id"] for tweet in normalized])
        for tweet in normalized:
            previous_hash = existing.get(tweet["id"])
            if previous_hash is None:
                _insert_tweet(connection, tweet, now)
                _sync_media(connection, tweet)
                _sync_entities(connection, tweet)
                inserted += 1
            elif previous_hash != tweet["content_hash"]:
                _update_tweet(connection, tweet, now)
                _sync_media(connection, tweet)
                _sync_entities(connection, tweet)
                updated += 1

            _sync_user(connection, tweet, now)
            _sync_metrics(connection, tweet, now)

            cursor = connection.execute(
                """INSERT INTO archive_entries(account_id,tweet_id,entry_type,archived_at,
                folder_id,run_id,read_status) VALUES(?,?,?,?,?,?, 'unread')
                ON CONFLICT(account_id,tweet_id,entry_type) DO NOTHING""",
                (account_id, tweet["id"], entry_type, now, folder_id, run_id),
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
    author: str | None = None,
    since: str | None = None,
    until: str | None = None,
    has_media: bool = False,
    folder: str | None = None,
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
        entry_columns = {row[1] for row in connection.execute("PRAGMA table_info(archive_entries)")}
        fts_columns = {row[1] for row in connection.execute("PRAGMA table_info(tweets_fts)")}
        if "pk" in tweet_columns and "tweet_id" not in fts_columns:
            join = "t.pk=tweets_fts.rowid"
        elif "tweet_id" in fts_columns:
            join = "t.id=tweets_fts.tweet_id"
        else:
            raise ValueError("unsupported database schema; run init to migrate")

        extra = ", (SELECT count(*) FROM tweet_media m WHERE m.tweet_id=t.id) AS media_count"
        if _table_exists(connection, "tweet_metrics"):
            extra += (
                ", (SELECT favorite_count FROM tweet_metrics m WHERE m.tweet_id=t.id"
                " ORDER BY captured_at DESC LIMIT 1) AS favorite_count"
            )
        sql = f"""SELECT t.id,t.author_username,t.author_name,t.text,t.created_at,t.url,
        bm25(tweets_fts) AS rank{extra} FROM tweets_fts JOIN tweets t ON {join}
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
        if author:
            handle = author.lstrip("@").strip()
            if "author_id" in tweet_columns:
                sql += " AND (lower(t.author_username)=lower(?) OR t.author_id=?)"
                params.extend([handle, handle])
            else:
                sql += " AND lower(t.author_username)=lower(?)"
                params.append(handle)
        if since:
            sql += " AND t.created_at >= ?"
            params.append(since)
        if until:
            sql += " AND t.created_at <= ?"
            params.append(until)
        if has_media:
            sql += " AND EXISTS (SELECT 1 FROM tweet_media m WHERE m.tweet_id=t.id)"
        if folder:
            if "folder_id" not in entry_columns:
                raise ValueError("folder filter requires schema v8; run init to migrate")
            sql += (
                " AND EXISTS (SELECT 1 FROM archive_entries e"
                " WHERE e.tweet_id=t.id AND e.folder_id=?)"
            )
            params.append(folder)
        sql += " ORDER BY rank,t.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = connection.execute(sql, params).fetchall()

    return [{**dict(row), "snippet": _snippet(row["text"], query)} for row in rows]


def list_tweets(
    database: str | Path,
    *,
    limit: int = 1000,
    offset: int = 0,
    entry_type: str | None = None,
    account: str | None = None,
    author: str | None = None,
    since: str | None = None,
    until: str | None = None,
    has_media: bool = False,
    folder: str | None = None,
    ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(limit, int) or not 1 <= limit <= 100000:
        raise ValueError("limit must be between 1 and 100000")
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if entry_type is not None and entry_type not in {"bookmark", "like"}:
        raise ValueError("entry_type must be bookmark or like")
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    if ids is not None and not ids:
        return []

    with closing(_connect_read(database)) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(tweets)")}
        entry_columns = {row[1] for row in connection.execute("PRAGMA table_info(archive_entries)")}
        selected = ["t.id", "t.author_username", "t.author_name", "t.text", "t.created_at", "t.url"]
        for optional in (
            "lang",
            "author_id",
            "conversation_id",
            "quoted_tweet_id",
            "retweeted_tweet_id",
            "in_reply_to_id",
            "status",
        ):
            if optional in columns:
                selected.append(f"t.{optional}")
        sql = f"SELECT {','.join(selected)} FROM tweets t WHERE 1=1"
        params: list[Any] = []
        if ids is not None:
            placeholders = ",".join("?" for _ in ids)
            sql += f" AND t.id IN ({placeholders})"
            params.extend(ids)
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
        if author:
            handle = author.lstrip("@").strip()
            if "author_id" in columns:
                sql += " AND (lower(t.author_username)=lower(?) OR t.author_id=?)"
                params.extend([handle, handle])
            else:
                sql += " AND lower(t.author_username)=lower(?)"
                params.append(handle)
        if since:
            sql += " AND t.created_at >= ?"
            params.append(since)
        if until:
            sql += " AND t.created_at <= ?"
            params.append(until)
        if has_media:
            sql += " AND EXISTS (SELECT 1 FROM tweet_media m WHERE m.tweet_id=t.id)"
        if folder:
            if "folder_id" not in entry_columns:
                raise ValueError("folder filter requires schema v8; run init to migrate")
            sql += (
                " AND EXISTS (SELECT 1 FROM archive_entries e"
                " WHERE e.tweet_id=t.id AND e.folder_id=?)"
            )
            params.append(folder)
        sql += " ORDER BY t.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = connection.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def doctor(database: str | Path, *, backup_dir: str | Path | None = None) -> dict[str, Any]:
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    verify = verify_database(database)
    issues: list[str] = []
    warnings: list[str] = []

    with closing(_connect_read(database)) as connection:

        def scalar(sql: str) -> int:
            return int(connection.execute(sql).fetchone()[0])

        schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        counts = {
            "tweets": scalar("SELECT count(*) FROM tweets"),
            "bookmarks": scalar("SELECT count(*) FROM archive_entries WHERE entry_type='bookmark'"),
            "likes": scalar("SELECT count(*) FROM archive_entries WHERE entry_type='like'"),
            "media": scalar("SELECT count(*) FROM tweet_media"),
            "empty_text": scalar("SELECT count(*) FROM tweets WHERE text=''"),
            "unknown_author": scalar(
                "SELECT count(*) FROM tweets WHERE author_username IN ('', 'unknown')"
            ),
            "orphan_tweets": scalar(
                """SELECT count(*) FROM tweets t
                WHERE NOT EXISTS (SELECT 1 FROM archive_entries e WHERE e.tweet_id=t.id)"""
            ),
            "orphan_media": scalar(
                """SELECT count(*) FROM tweet_media m
                WHERE NOT EXISTS (SELECT 1 FROM tweets t WHERE t.id=m.tweet_id)"""
            ),
        }
        if _table_exists(connection, "users"):
            counts["users"] = scalar("SELECT count(*) FROM users")
        if _table_exists(connection, "tweet_entities"):
            counts["entities"] = scalar("SELECT count(*) FROM tweet_entities")
            counts["orphan_entities"] = scalar(
                """SELECT count(*) FROM tweet_entities x
                WHERE NOT EXISTS (SELECT 1 FROM tweets t WHERE t.id=x.tweet_id)"""
            )
        if _table_exists(connection, "tweet_metrics"):
            counts["metrics"] = scalar("SELECT count(*) FROM tweet_metrics")
            counts["orphan_metrics"] = scalar(
                """SELECT count(*) FROM tweet_metrics x
                WHERE NOT EXISTS (SELECT 1 FROM tweets t WHERE t.id=x.tweet_id)"""
            )
        if _table_exists(connection, "tweets_fts"):
            counts["fts_docs"] = scalar("SELECT count(*) FROM tweets_fts")
            if counts["fts_docs"] != counts["tweets"]:
                issues.append(
                    f"FTS documents ({counts['fts_docs']}) do not match tweets ({counts['tweets']})"
                )

    for key, value in verify.items():
        if value != "ok":
            issues.append(f"verify.{key}: {value}")
    if counts["empty_text"]:
        issues.append(f"{counts['empty_text']} tweet(s) have empty text")
    if counts["unknown_author"]:
        issues.append(f"{counts['unknown_author']} tweet(s) have an unknown author")
    for key in ("orphan_tweets", "orphan_media", "orphan_entities", "orphan_metrics"):
        if counts.get(key):
            issues.append(f"{counts[key]} orphan {key.removeprefix('orphan_')} row(s)")
    if schema_version < LATEST_SCHEMA_VERSION:
        warnings.append(
            f"schema v{schema_version} is older than v{LATEST_SCHEMA_VERSION}; run init to migrate"
        )

    directory = Path(backup_dir) if backup_dir else database.parent.parent / "backups"
    backups = sorted(directory.glob("x-archive-*.sqlite3")) if directory.is_dir() else []
    last_backup = None
    if backups:
        newest = max(backups, key=lambda path: path.stat().st_mtime)
        age_days = (datetime.now(UTC).timestamp() - newest.stat().st_mtime) / 86400
        last_backup = {
            "path": str(newest),
            "age_days": round(age_days, 1),
            "count": len(backups),
        }
        if age_days > 7:
            warnings.append(f"last backup is {age_days:.1f} days old")
    else:
        warnings.append("no x-archive backup found")

    return {
        "database": str(database.resolve()),
        "schema_version": schema_version,
        "verify": verify,
        "counts": counts,
        "last_backup": last_backup,
        "issues": issues,
        "warnings": warnings,
    }


def undo_run(database: str | Path, run_id: int) -> dict[str, Any]:
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")
    with closing(connect(database)) as connection, connection:
        run = connection.execute("SELECT id FROM import_runs WHERE id=?", (run_id,)).fetchone()
        if run is None:
            raise ValueError(f"import run not found: {run_id}")
        entries = connection.execute(
            "DELETE FROM archive_entries WHERE run_id=?", (run_id,)
        ).rowcount
        tweets = connection.execute(
            "DELETE FROM tweets WHERE id NOT IN (SELECT tweet_id FROM archive_entries)"
        ).rowcount
        accounts = connection.execute(
            "DELETE FROM accounts WHERE id NOT IN (SELECT DISTINCT account_id FROM archive_entries)"
        ).rowcount
    return {
        "run_id": run_id,
        "entries_removed": entries,
        "orphan_tweets_removed": tweets,
        "orphan_accounts_removed": accounts,
        "note": None if entries else "run has no per-entry provenance (pre-v8 import)",
    }


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
