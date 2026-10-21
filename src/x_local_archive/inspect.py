from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .db import _first, _iso_utc, _records


def inspect_export(source: str | Path) -> dict[str, Any]:
    """Report the metadata and data quality of a userscript export without importing it."""
    source_path = Path(source)
    payload = json.loads(source_path.read_text(encoding="utf-8-sig"))
    records = _records(payload)
    metadata = payload if isinstance(payload, dict) else {}

    ids: list[str] = []
    dates: list[str] = []
    empty_text = unknown_author = media = invalid = 0
    for record in records:
        if not isinstance(record, dict):
            invalid += 1
            continue
        tweet_id = str(_first(record, "rest_id", "id", "id_str", "tweet_id", default="")).strip()
        if tweet_id:
            ids.append(tweet_id)
        if not str(_first(record, "text", "full_text", "content", default="")).strip():
            empty_text += 1
        author = str(
            _first(record, "author_username", "username", "screen_name", default="unknown")
        ).lower()
        if author in ("", "unknown"):
            unknown_author += 1
        media_value = record.get("media") or record.get("media_urls") or []
        if isinstance(media_value, list):
            media += len(media_value)
        created = _iso_utc(_first(record, "created_at", "createdAt", "date"))
        if created:
            dates.append(created)

    numeric = [int(value) for value in ids if value.isdigit()]
    actual_newest = str(max(numeric)) if numeric else None
    actual_oldest = str(min(numeric)) if numeric else None
    declared = {
        "account": metadata.get("account"),
        "type": metadata.get("type"),
        "exported_at": metadata.get("exported_at"),
        "total_tweets": metadata.get("total_tweets"),
        "newest_id": metadata.get("newest_id"),
        "oldest_id": metadata.get("oldest_id"),
    }
    actual = {
        "records": len(records),
        "unique_ids": len(set(ids)),
        "duplicate_ids": len(ids) - len(set(ids)),
        "non_numeric_ids": sum(1 for value in ids if not value.isdigit()),
        "invalid_records": invalid,
        "empty_text": empty_text,
        "unknown_author": unknown_author,
        "media": media,
        "newest_id": actual_newest,
        "oldest_id": actual_oldest,
        "date_range": {
            "oldest": min(dates) if dates else None,
            "newest": max(dates) if dates else None,
        },
    }

    warnings: list[str] = []
    if declared["total_tweets"] is not None and declared["total_tweets"] != actual["records"]:
        warnings.append(
            f"declared total_tweets={declared['total_tweets']} "
            f"but file has {actual['records']} records"
        )
    if declared["newest_id"] and actual_newest and str(declared["newest_id"]) != actual_newest:
        warnings.append("declared newest_id is not the maximum tweet id in the file")
    if declared["oldest_id"] and actual_oldest and str(declared["oldest_id"]) != actual_oldest:
        warnings.append("declared oldest_id is not the minimum tweet id in the file")
    if actual["duplicate_ids"]:
        warnings.append(f"{actual['duplicate_ids']} duplicate tweet id(s)")
    if actual["non_numeric_ids"]:
        warnings.append(f"{actual['non_numeric_ids']} record(s) have a non-numeric tweet id")
    if invalid:
        warnings.append(f"{invalid} non-object record(s)")
    if empty_text:
        warnings.append(f"{empty_text} record(s) have empty text")
    if unknown_author:
        warnings.append(f"{unknown_author} record(s) have an unknown author")
    if ids and not numeric:
        warnings.append("no numeric tweet ids; the file may not be a valid export")

    return {
        "file": str(source_path),
        "declared": declared,
        "actual": actual,
        "warnings": warnings,
    }
