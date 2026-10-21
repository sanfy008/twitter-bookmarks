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
                }
            }
        },
        "legacy": {
            "full_text": "价值投资 hello",
            "created_at": "Sun Apr 21 17:46:07 +0000 2024",
            "extended_entities": {
                "media": [
                    {"media_url_https": "https://pbs.twimg.com/media/a.jpg", "type": "photo"},
                    {"media_url_https": "https://pbs.twimg.com/media/a.jpg", "type": "photo"},
                    {"media_url_https": "https://pbs.twimg.com/media/b.mp4", "type": "video"},
                ]
            },
        },
    }


def test_graphql_tweet_is_normalized():
    tweet = _normalize(graphql_tweet())
    assert tweet["id"] == "1782103537234973176"
    assert tweet["author_username"] == "alice"
    assert tweet["author_name"] == "Alice"
    assert tweet["text"] == "价值投资 hello"
    assert tweet["created_at"] == "2024-04-21T17:46:07+00:00"
    assert tweet["url"] == "https://x.com/alice/status/1782103537234973176"
    assert tweet["media"] == [
        {"url": "https://pbs.twimg.com/media/a.jpg", "type": "photo"},
        {"url": "https://pbs.twimg.com/media/b.mp4", "type": "video"},
    ]


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
