import json

import pytest

from x_local_archive.db import _normalize


def graphql_tweet():
    return {
        "__typename": "Tweet",
        "rest_id": "1782103537234973176",
        "core": {
            "user_results": {
                "result": {
                    "__typename": "User",
                    "rest_id": "42",
                    "core": {"screen_name": "alice", "name": "Alice"},
                    "legacy": {
                        "followers_count": 1234,
                        "verified": True,
                        "profile_image_url_https": "https://pbs.twimg.com/avatar.jpg",
                    },
                }
            }
        },
        "legacy": {
            "full_text": "价值投资 hello",
            "created_at": "Sun Apr 21 17:46:07 +0000 2024",
            "lang": "zh",
            "favorite_count": 12,
            "retweet_count": 3,
            "reply_count": 2,
            "quote_count": 1,
            "bookmark_count": 4,
            "views": {"count": "1000"},
            "quoted_status_id_str": "99",
            "in_reply_to_status_id_str": "88",
            "conversation_id_str": "77",
            "entities": {
                "hashtags": [{"text": "AI"}],
                "user_mentions": [{"screen_name": "bob"}],
                "urls": [{"url": "https://t.co/x", "expanded_url": "https://example.com/a"}],
            },
            "extended_entities": {
                "media": [
                    {
                        "media_url_https": "https://pbs.twimg.com/media/a.jpg",
                        "type": "photo",
                        "media_key": "3_1",
                        "original_info": {"width": 1200, "height": 800},
                        "ext_alt_text": "a photo",
                    },
                    {
                        "media_url_https": "https://pbs.twimg.com/media/a.jpg",
                        "type": "photo",
                    },
                    {
                        "media_url_https": "https://pbs.twimg.com/media/b.mp4",
                        "type": "video",
                        "media_key": "7_2",
                        "video_info": {
                            "duration_millis": 30000,
                            "variants": [
                                {
                                    "bitrate": 832000,
                                    "content_type": "video/mp4",
                                    "url": "https://v/b.mp4",
                                }
                            ],
                        },
                    },
                ]
            },
        },
    }


def test_graphql_tweet_is_normalized():
    tweet = _normalize(graphql_tweet())
    assert tweet["id"] == "1782103537234973176"
    assert tweet["author_username"] == "alice"
    assert tweet["author_name"] == "Alice"
    assert tweet["author_id"] == "42"
    assert tweet["author_followers"] == 1234
    assert tweet["author_verified"] == 1
    assert tweet["author_avatar"] == "https://pbs.twimg.com/avatar.jpg"
    assert tweet["text"] == "价值投资 hello"
    assert tweet["created_at"] == "2024-04-21T17:46:07+00:00"
    assert tweet["url"] == "https://x.com/alice/status/1782103537234973176"
    assert tweet["lang"] == "zh"
    assert [(item["url"], item["type"]) for item in tweet["media"]] == [
        ("https://pbs.twimg.com/media/a.jpg", "photo"),
        ("https://pbs.twimg.com/media/b.mp4", "video"),
    ]
    assert tweet["media"][0]["media_id"] == "3_1"
    assert tweet["media"][0]["width"] == 1200
    assert tweet["media"][0]["height"] == 800
    assert tweet["media"][0]["alt_text"] == "a photo"
    assert tweet["media"][1]["duration_ms"] == 30000
    assert json.loads(tweet["media"][1]["variants"])[0]["bitrate"] == 832000
    assert tweet["entities"] == [
        {"kind": "hashtag", "value": "AI", "expanded": None},
        {"kind": "mention", "value": "bob", "expanded": None},
        {
            "kind": "url",
            "value": "https://t.co/x",
            "expanded": "https://example.com/a",
        },
    ]
    assert tweet["metrics"] == {
        "favorite": 12,
        "retweet": 3,
        "reply": 2,
        "quote": 1,
        "bookmark": 4,
        "views": 1000,
    }
    assert tweet["relations"] == {
        "quoted_id": "99",
        "retweeted_id": None,
        "in_reply_to_id": "88",
        "conversation_id": "77",
    }


def test_userscript_flat_metadata_is_normalized():
    record = {
        "id": "1",
        "text": "flat",
        "author_username": "alice",
        "author_id": "42",
        "author_followers": 10,
        "author_verified": True,
        "author_avatar": "https://a/avatar.jpg",
        "entities": {
            "hashtags": ["AI"],
            "mentions": ["bob"],
            "urls": [{"url": "https://t.co/x", "expanded": "https://example.com/a"}],
            "symbols": ["BTC"],
        },
        "metrics": {
            "favorite": 5,
            "retweet": 2,
            "reply": 1,
            "quote": 0,
            "bookmark": 3,
            "views": 100,
        },
        "relations": {
            "quoted_id": "9",
            "retweeted_id": None,
            "in_reply_to_id": "8",
            "conversation_id": "7",
        },
        "media": [
            {
                "url": "https://m/a.jpg",
                "type": "photo",
                "media_id": "m1",
                "width": 100,
                "height": 200,
                "alt_text": "alt",
            }
        ],
    }
    tweet = _normalize(record)
    assert tweet["author_id"] == "42"
    assert tweet["author_followers"] == 10
    assert tweet["author_verified"] == 1
    assert tweet["entities"][3] == {"kind": "symbol", "value": "BTC", "expanded": None}
    assert tweet["metrics"]["favorite"] == 5
    assert tweet["relations"]["quoted_id"] == "9"
    assert tweet["media"][0]["width"] == 100
    assert tweet["media"][0]["alt_text"] == "alt"


def test_visibility_wrapper_is_unwrapped():
    tweet = _normalize({"__typename": "TweetWithVisibilityResults", "tweet": graphql_tweet()})
    assert tweet["id"] == "1782103537234973176"


def test_user_objects_are_rejected():
    with pytest.raises(ValueError, match="not a tweet object"):
        _normalize({"__typename": "User", "rest_id": "42", "legacy": {}})


def test_note_tweet_text_wins():
    record = graphql_tweet()
    record["legacy"]["full_text"] = "truncated…"
    record["note_tweet"] = {"note_tweet_results": {"result": {"text": "完整长文"}}}
    assert _normalize(record)["text"] == "完整长文"


def test_url_like_tweet_ids_are_rejected():
    with pytest.raises(ValueError, match="URL"):
        _normalize({"id": "https://t.co/x", "text": "", "legacy": {}})


def test_missing_timestamp_is_not_fabricated():
    record = {"id": "1", "text": "no date"}
    assert _normalize(record)["created_at"] is None


def test_unknown_author_does_not_produce_a_fake_url():
    record = {"id": "1", "text": "no author"}
    tweet = _normalize(record)
    assert tweet["author_username"] == "unknown"
    assert tweet["url"] is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-09-24T00:00:00Z", "2026-09-24T00:00:00+00:00"),
        ("2026-09-24T08:00:00+08:00", "2026-09-24T00:00:00+00:00"),
        ("Sun Apr 21 17:46:07 +0000 2024", "2024-04-21T17:46:07+00:00"),
        ("not a date", None),
        (None, None),
    ],
)
def test_timestamp_normalization(value, expected):
    record = {"id": "1", "text": "x", "created_at": value}
    assert _normalize(record)["created_at"] == expected
