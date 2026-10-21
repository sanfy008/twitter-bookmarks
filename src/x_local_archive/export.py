from __future__ import annotations

import csv
import html
import io
import json
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .db import _connect_read, _table_exists, list_tweets, search

_FORMATS = {"json", "csv", "md", "html"}


def _chunks(values: list[str], size: int = 500) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _details(
    connection: Any, ids: list[str]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    media: dict[str, list[dict[str, Any]]] = {}
    entities: dict[str, list[dict[str, Any]]] = {}
    metrics: dict[str, Any] = {}
    has_entities = _table_exists(connection, "tweet_entities")
    has_metrics = _table_exists(connection, "tweet_metrics")
    for chunk in _chunks(ids):
        placeholders = ",".join("?" for _ in chunk)
        for row in connection.execute(
            f"""SELECT tweet_id,media_url,media_type,alt_text FROM tweet_media
            WHERE tweet_id IN ({placeholders}) ORDER BY tweet_id,id""",
            chunk,
        ):
            media.setdefault(row["tweet_id"], []).append(
                {
                    "url": row["media_url"],
                    "type": row["media_type"],
                    "alt_text": row["alt_text"],
                }
            )
        if has_entities:
            for row in connection.execute(
                f"""SELECT tweet_id,kind,value,expanded FROM tweet_entities
                WHERE tweet_id IN ({placeholders}) ORDER BY tweet_id,kind,value""",
                chunk,
            ):
                entities.setdefault(row["tweet_id"], []).append(
                    {"kind": row["kind"], "value": row["value"], "expanded": row["expanded"]}
                )
        if has_metrics:
            for row in connection.execute(
                f"""SELECT m.tweet_id,m.favorite_count,m.retweet_count,m.reply_count,
                m.quote_count,m.bookmark_count,m.view_count
                FROM tweet_metrics m
                JOIN (
                    SELECT tweet_id,max(captured_at) AS captured_at FROM tweet_metrics
                    WHERE tweet_id IN ({placeholders}) GROUP BY tweet_id
                ) latest ON latest.tweet_id=m.tweet_id AND latest.captured_at=m.captured_at""",
                chunk,
            ):
                metrics[row["tweet_id"]] = {
                    "favorite": row["favorite_count"],
                    "retweet": row["retweet_count"],
                    "reply": row["reply_count"],
                    "quote": row["quote_count"],
                    "bookmark": row["bookmark_count"],
                    "views": row["view_count"],
                }
    return media, entities, metrics


def _render_json(records: list[dict[str, Any]]) -> str:
    return json.dumps(records, ensure_ascii=False, indent=2)


def _render_csv(records: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    fields = [
        "id",
        "created_at",
        "author_username",
        "author_name",
        "text",
        "url",
        "lang",
        "media_urls",
        "hashtags",
        "mentions",
        "favorite_count",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for record in records:
        writer.writerow(
            {
                "id": record.get("id"),
                "created_at": record.get("created_at"),
                "author_username": record.get("author_username"),
                "author_name": record.get("author_name"),
                "text": record.get("text"),
                "url": record.get("url"),
                "lang": record.get("lang"),
                "media_urls": " | ".join(item["url"] for item in record.get("media", [])),
                "hashtags": " ".join(
                    item["value"]
                    for item in record.get("entities", [])
                    if item["kind"] == "hashtag"
                ),
                "mentions": " ".join(
                    item["value"]
                    for item in record.get("entities", [])
                    if item["kind"] == "mention"
                ),
                "favorite_count": (record.get("metrics") or {}).get("favorite"),
            }
        )
    return output.getvalue()


def _render_markdown(records: list[dict[str, Any]]) -> str:
    lines = ["# X Archive Export", "", f"Generated: {datetime.now(UTC).isoformat()}", ""]
    for record in records:
        author = record.get("author_username") or "unknown"
        created = (record.get("created_at") or "")[:10]
        lines.append(f"## @{author} · {created}")
        if record.get("url"):
            lines.append(f"[{record['url']}]({record['url']})")
        lines.append("")
        lines.append(record.get("text") or "")
        lines.append("")
        for item in record.get("media", []):
            alt = item.get("alt_text") or item.get("type") or "media"
            lines.append(f"![{alt}]({item['url']})")
        hashtags = [
            item["value"] for item in record.get("entities", []) if item["kind"] == "hashtag"
        ]
        if hashtags:
            lines.append("")
            lines.append("Tags: " + " ".join(f"#{tag}" for tag in hashtags))
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def _render_html(records: list[dict[str, Any]]) -> str:
    parts = [
        "<!doctype html>",
        '<html lang="zh-CN"><head><meta charset="utf-8">',
        "<title>X Archive Export</title>",
        "<style>",
        "body{font-family:system-ui,sans-serif;max-width:46rem;",
        "margin:2rem auto;line-height:1.6;padding:0 1rem}",
        "article{border-bottom:1px solid #ddd;padding:1.5rem 0}",
        "h2{font-size:1rem;color:#555}",
        "img{max-width:100%;border-radius:8px;margin:.4rem .4rem 0 0}a{color:#0a7}",
        "blockquote{color:#555}",
        "</style>",
        "</head><body>",
        "<h1>X Archive Export</h1>",
    ]
    for record in records:
        author = html.escape(record.get("author_username") or "unknown")
        created = html.escape((record.get("created_at") or "")[:10])
        url = record.get("url")
        parts.append("<article>")
        parts.append(f"<h2>@{author} · {created}</h2>")
        if url:
            safe_url = html.escape(str(url), quote=True)
            parts.append(f'<p><a href="{safe_url}">{safe_url}</a></p>')
        parts.append(f"<p>{html.escape(record.get('text') or '').replace(chr(10), '<br>')}</p>")
        for item in record.get("media", []):
            safe_url = html.escape(str(item["url"]), quote=True)
            alt = html.escape(str(item.get("alt_text") or item.get("type") or "media"), quote=True)
            if item.get("type") == "photo":
                parts.append(f'<img src="{safe_url}" alt="{alt}">')
            else:
                parts.append(f'<p><a href="{safe_url}">{alt}</a></p>')
        hashtags = [
            item["value"] for item in record.get("entities", []) if item["kind"] == "hashtag"
        ]
        if hashtags:
            parts.append("<p>" + " ".join(f"#{html.escape(tag)}" for tag in hashtags) + "</p>")
        parts.append("</article>")
    parts.append("</body></html>")
    return "\n".join(parts)


def export_data(
    database: str | Path,
    destination: str | Path | None = None,
    *,
    fmt: str = "json",
    query: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    entry_type: str | None = None,
    account: str | None = None,
    author: str | None = None,
    since: str | None = None,
    until: str | None = None,
    has_media: bool = False,
    folder: str | None = None,
) -> str | Path:
    """Render matching tweets to *fmt*.

    `limit=None` exports every matching tweet. A default cap would silently
    truncate a full archive, which is exactly what an export is for.
    """
    fmt = fmt.lower()
    if fmt not in _FORMATS:
        raise ValueError(f"format must be one of {sorted(_FORMATS)}")
    database = Path(database)
    if not database.is_file():
        raise FileNotFoundError(f"database does not exist: {database}")

    filters = {
        "entry_type": entry_type,
        "account": account,
        "author": author,
        "since": since,
        "until": until,
        "has_media": has_media,
        "folder": folder,
    }
    if query:
        # FTS-backed search validates 1..1000, so walk it in pages instead of
        # raising the cap and risking an unbounded single query.
        rows = []
        page_size = min(limit or 1000, 1000)
        while limit is None or len(rows) < limit:
            page = search(database, query, limit=page_size, offset=offset + len(rows), **filters)
            rows.extend(page)
            if len(page) < page_size:
                break
        if limit is not None:
            rows = rows[:limit]
        for row in rows:
            row.pop("rank", None)
            row.pop("snippet", None)
    else:
        rows = list_tweets(
            database,
            limit=limit if limit is not None else 100000,
            offset=offset,
            **filters,
        )

    ids = [str(row["id"]) for row in rows]
    with closing(_connect_read(database)) as connection:
        media, entities, metrics = _details(connection, ids)

    records: list[dict[str, Any]] = []
    for row in rows:
        record = dict(row)
        record["media"] = media.get(record["id"], [])
        record["entities"] = entities.get(record["id"], [])
        record["metrics"] = metrics.get(record["id"])
        records.append(record)

    if fmt == "json":
        text = _render_json(records)
    elif fmt == "csv":
        text = _render_csv(records)
    elif fmt == "md":
        text = _render_markdown(records)
    else:
        text = _render_html(records)

    if destination is None:
        return text
    path = Path(destination)
    if path.is_dir() or not path.suffix:
        path.mkdir(parents=True, exist_ok=True)
        path = path / f"x-archive-export-{datetime.now():%Y%m%d-%H%M%S}.{fmt}"
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
