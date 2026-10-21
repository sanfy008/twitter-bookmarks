import json
from pathlib import Path

from x_local_archive.db import import_json
from x_local_archive.export import export_data


def rich_payload():
    return {
        "account": "alice",
        "type": "bookmark",
        "exported_at": "2026-10-21T00:00:00Z",
        "folder_id": "f1",
        "folder_name": "AI",
        "tweets": [
            {
                "id": "1",
                "text": "投资 <AI> & 价值",
                "author_username": "alice",
                "author_name": "Alice",
                "author_id": "42",
                "created_at": "2024-01-01T00:00:00Z",
                "url": "https://x.com/alice/status/1",
                "lang": "zh",
                "entities": {
                    "hashtags": ["AI"],
                    "mentions": ["bob"],
                    "urls": [{"url": "https://t.co/x", "expanded": "https://example.com/a"}],
                },
                "metrics": {
                    "favorite": 12,
                    "retweet": 3,
                    "reply": 2,
                    "quote": 1,
                    "bookmark": 4,
                    "views": 1000,
                },
                "media": [
                    {
                        "url": "https://m/a.jpg",
                        "type": "photo",
                        "alt_text": "a photo",
                    }
                ],
            },
            {
                "id": "2",
                "text": "second",
                "author_username": "bob",
                "author_name": "Bob",
                "author_id": "43",
                "created_at": "2025-01-01T00:00:00Z",
                "url": "https://x.com/bob/status/2",
                "media": [],
            },
        ],
    }


def test_export_formats(write_json, database, tmp_path):
    source = write_json("export.json", rich_payload())
    import_json(database, source, "alice", "bookmark")

    data = json.loads(export_data(database, fmt="json"))
    assert len(data) == 2
    first = next(row for row in data if row["id"] == "1")
    assert first["media"][0]["url"] == "https://m/a.jpg"
    assert first["entities"][0]["kind"] == "hashtag"
    assert first["metrics"]["favorite"] == 12

    csv_text = export_data(database, fmt="csv")
    assert "media_urls" in csv_text
    assert "https://m/a.jpg" in csv_text
    assert "AI" in csv_text

    markdown = export_data(database, fmt="md")
    assert "## @alice" in markdown
    assert "![a photo](https://m/a.jpg)" in markdown
    assert "<AI>" in markdown

    html_text = export_data(database, fmt="html")
    assert "&lt;AI&gt;" in html_text
    assert "<img" in html_text

    target = tmp_path / "out.csv"
    result = export_data(database, target, fmt="csv")
    assert Path(result) == target
    assert target.exists()

    filtered = json.loads(export_data(database, fmt="json", query="投资"))
    assert len(filtered) == 1
    assert filtered[0]["id"] == "1"

    filtered = json.loads(export_data(database, fmt="json", author="bob"))
    assert [row["id"] for row in filtered] == ["2"]

    filtered = json.loads(export_data(database, fmt="json", folder="f1"))
    assert {row["id"] for row in filtered} == {"1", "2"}

    filtered = json.loads(export_data(database, fmt="json", has_media=True))
    assert [row["id"] for row in filtered] == ["1"]
