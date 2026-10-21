// Behavioural tests for scripts/x-archive-sync.user.js using a realistic GraphQL
// response shape. Run with: node scripts/check-userscript.mjs
//
// The userscript is evaluated in a minimal VM sandbox. The harness opts into the
// script's test API (`window.__X_ARCHIVE_TEST__`), feeds a bookmark timeline
// payload, and asserts that only real tweets are collected.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("./x-archive-sync.user.js", import.meta.url), "utf8");

function createSandbox() {
    const store = new Map();
    const sandbox = {
        console: { log() {} },
        JSON,
        BigInt,
        URL,
        Date,
        Map,
        Set,
        Math,
        RegExp,
        Error,
        setTimeout: () => 0,
        clearTimeout: () => {},
        setInterval: () => 0,
        clearInterval: () => {},
        requestAnimationFrame: () => 0,
        localStorage: {
            getItem: key => (store.has(key) ? store.get(key) : null),
            setItem: (key, value) => store.set(key, String(value)),
            removeItem: key => store.delete(key),
        },
        document: {
            getElementById: () => null,
            querySelector: () => null,
            createElement: () => ({ style: {}, addEventListener() {}, appendChild() {} }),
            body: null,
            hidden: false,
            documentElement: { scrollHeight: 0 },
        },
        navigator: { clipboard: null },
        location: { pathname: "/i/bookmarks", href: "https://x.com/i/bookmarks" },
    };
    sandbox.window = sandbox;
    sandbox.globalThis = sandbox;
    sandbox.window.addEventListener = () => {};
    sandbox.window.__X_ARCHIVE_TEST__ = true;
    sandbox.window.XMLHttpRequest = class {
        open() {}
        addEventListener() {}
    };
    sandbox.window.fetch = async () => ({
        status: 200,
        clone: () => ({ text: async () => "{}" }),
    });
    return sandbox;
}

function tweet(id, handle, name, text, createdAt, media = []) {
    return {
        __typename: "Tweet",
        rest_id: id,
        core: {
            user_results: {
                result: {
                    __typename: "User",
                    rest_id: `u-${handle}`,
                    core: { screen_name: handle, name },
                    legacy: {
                        followers_count: 1234,
                        verified: true,
                        profile_image_url_https: "https://a/avatar.jpg",
                    },
                },
            },
        },
        legacy: {
            full_text: text,
            created_at: createdAt,
            lang: "zh",
            favorite_count: 12,
            retweet_count: 3,
            reply_count: 2,
            quote_count: 1,
            bookmark_count: 4,
            views: { count: "1000" },
            quoted_status_id_str: "99",
            conversation_id_str: "77",
            entities: {
                hashtags: [{ text: "AI" }],
                user_mentions: [{ screen_name: "bob" }],
                urls: [{ url: "https://t.co/x", expanded_url: "https://example.com/a" }],
                symbols: [{ text: "BTC" }],
            },
            ...(media.length ? { extended_entities: { media } } : {}),
        },
    };
}

const bookmarkResponse = {
    data: {
        bookmark_timeline_v2: {
            timeline: {
                instructions: [
                    {
                        type: "TimelineAddEntries",
                        entries: [
                            {
                                entryId: "tweet-1",
                                content: {
                                    itemContent: {
                                        tweet_results: {
                                            result: tweet(
                                                "1782103537234973176",
                                                "alice",
                                                "Alice",
                                                "价值投资 hello",
                                                "Sun Apr 21 17:46:07 +0000 2024",
                                                [
                                                    {
                                                        media_url_https:
                                                            "https://pbs.twimg.com/media/a.jpg",
                                                        type: "photo",
                                                        media_key: "3_1",
                                                        original_info: { width: 1200, height: 800 },
                                                        ext_alt_text: "a photo",
                                                    },
                                                    {
                                                        media_url_https:
                                                            "https://pbs.twimg.com/media/b.mp4",
                                                        type: "video",
                                                        media_key: "7_2",
                                                        video_info: {
                                                            duration_millis: 30000,
                                                            variants: [
                                                                {
                                                                    bitrate: 832000,
                                                                    content_type: "video/mp4",
                                                                    url: "https://v/b.mp4",
                                                                },
                                                            ],
                                                        },
                                                    },
                                                ],
                                            ),
                                        },
                                    },
                                },
                            },
                            {
                                entryId: "tweet-2",
                                content: {
                                    itemContent: {
                                        tweet_results: {
                                            result: {
                                                __typename: "TweetWithVisibilityResults",
                                                tweet: tweet(
                                                    "1800000000000000002",
                                                    "carol",
                                                    "Carol",
                                                    "wrapped",
                                                    "Tue Apr 23 00:00:00 +0000 2024",
                                                ),
                                            },
                                        },
                                    },
                                },
                            },
                            {
                                entryId: "quoted",
                                content: {
                                    itemContent: {
                                        tweet_results: {
                                            result: {
                                                ...tweet(
                                                    "1700000000000000001",
                                                    "bob",
                                                    "Bob",
                                                    "quoted tweet",
                                                    "Mon Apr 22 00:00:00 +0000 2024",
                                                ),
                                                quoted_status_result: {
                                                    result: tweet(
                                                        "1600000000000000003",
                                                        "dave",
                                                        "Dave",
                                                        "quoted body",
                                                        "Wed Apr 24 00:00:00 +0000 2024",
                                                    ),
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                            // A card/URL entity can carry an id-like t.co URL; it must be rejected.
                            {
                                entryId: "card-object",
                                content: {
                                    itemContent: {
                                        card: {
                                            id: "https://t.co/card",
                                            legacy: { card_url: "https://t.co/card" },
                                        },
                                    },
                                },
                            },
                            // The old collector treated this User object as a tweet.
                            {
                                entryId: "user-object",
                                content: {
                                    itemContent: {
                                        user_results: {
                                            result: {
                                                __typename: "User",
                                                rest_id: "42",
                                                core: { screen_name: "alice", name: "Alice" },
                                                legacy: {},
                                            },
                                        },
                                    },
                                },
                            },
                            {
                                entryId: "tombstone",
                                content: {
                                    itemContent: {
                                        tweet_results: {
                                            result: { __typename: "TweetTombstone" },
                                        },
                                    },
                                },
                            },
                        ],
                    },
                ],
            },
        },
    },
};

const sandbox = createSandbox();
vm.createContext(sandbox);
vm.runInContext(source, sandbox, { filename: "x-archive-sync.user.js" });

const api = sandbox.window.__xArchiveTest;
assert.ok(api, "test API was not exposed");

// --- collection -----------------------------------------------------------
api.reset();
const added = api.extractTweetsFromData(bookmarkResponse);
assert.equal(added, 4, `expected 4 real tweets, got ${added}`);
assert.equal(api.collector.size, 4);

const ids = [...api.collector.keys()].sort();
assert.deepEqual(
    ids,
    [
        "1600000000000000003",
        "1700000000000000001",
        "1782103537234973176",
        "1800000000000000002",
    ],
    "only Tweet / TweetWithVisibilityResults nodes should be collected",
);
assert.ok(!api.collector.has("42"), "User objects must not be collected");
assert.ok(!api.collector.has("user-alice"), "User rest_ids must not be collected");

const first = api.collector.get("1782103537234973176");
assert.equal(first.author_username, "alice");
assert.equal(first.author_name, "Alice");
assert.equal(first.author_id, "u-alice");
assert.equal(first.author_followers, 1234);
assert.equal(first.author_verified, true);
assert.equal(first.author_avatar, "https://a/avatar.jpg");
assert.equal(first.text, "价值投资 hello");
assert.equal(first.created_at, "2024-04-21T17:46:07.000Z");
assert.equal(first.url, "https://x.com/alice/status/1782103537234973176");
assert.equal(first.lang, "zh");
assert.equal(first.entities.hashtags.join(","), "AI");
assert.equal(first.entities.mentions.join(","), "bob");
assert.equal(first.entities.urls[0].expanded, "https://example.com/a");
assert.equal(first.metrics.favorite, 12);
assert.equal(first.metrics.views, 1000);
assert.equal(first.relations.quoted_id, "99");
assert.equal(first.relations.conversation_id, "77");
assert.deepEqual(
    first.media.map(item => item.type),
    ["photo", "video"],
);
assert.equal(first.media[0].width, 1200);
assert.equal(first.media[0].height, 800);
assert.equal(first.media[0].alt_text, "a photo");
assert.equal(first.media[1].duration_ms, 30000);
assert.equal(api.collector.get("1800000000000000002").author_username, "carol");
assert.equal(api.collector.get("1600000000000000003").text, "quoted body");
assert.equal(
    api.extractTweetCandidate({ id: "https://t.co/x", legacy: {} }),
    null,
    "t.co/card ids must not be treated as tweets",
);

// A missing timestamp must stay null rather than being fabricated.
const noDate = api.extractTweetCandidate({
    __typename: "Tweet",
    rest_id: "1900000000000000004",
    legacy: { full_text: "no date" },
});
assert.equal(noDate.created_at, null);
assert.equal(noDate.url, null);

// --- starting a run must keep the page captured before the click -----------
api.reset();
api.extractTweetsFromData(bookmarkResponse);
assert.equal(api.collector.size, 4);
api.startSync();
assert.equal(
    api.collector.size,
    4,
    "startSync must not discard the first page captured before the user pressed start",
);
api.stopCapture();

// --- bookmark and like membership are independent -------------------------
const likesOnlyResponse = {
    data: {
        user: {
            result: {
                __typename: "User",
                timeline: {
                    timeline: {
                        instructions: [
                            {
                                entries: [
                                    {
                                        content: {
                                            itemContent: {
                                                tweet_results: {
                                                    result: tweet(
                                                        "1900000000000000009",
                                                        "erin",
                                                        "Erin",
                                                        "liked only",
                                                        "Thu Apr 25 00:00:00 +0000 2024",
                                                    ),
                                                },
                                            },
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                },
            },
        },
    },
};

api.reset();
sandbox.location.pathname = "/i/history";
api.extractTweetsFromData(bookmarkResponse);
assert.equal(api.currentTweets().length, 4);

sandbox.location.pathname = "/i/history/likes";
assert.equal(api.currentTweets().length, 0);
api.extractTweetsFromData(likesOnlyResponse);
assert.equal(api.currentTweets().length, 1);
assert.equal(api.collector.size, 5);

// The same posts can be in both lists; membership is added, not replaced.
api.extractTweetsFromData(bookmarkResponse);
assert.equal(api.currentTweets().length, 5);
sandbox.location.pathname = "/i/history";
assert.equal(api.currentTweets().length, 4);

// --- endpoint scoping -----------------------------------------------------
assert.equal(
    api.endpointMatchesPage("https://x.com/i/api/graphql/abc/Bookmarks?variables=1", "bookmark"),
    true,
);
assert.equal(
    api.endpointMatchesPage("https://x.com/i/api/graphql/abc/BookmarkFolderTimeline", "bookmark"),
    true,
);
assert.equal(
    api.endpointMatchesPage("https://x.com/i/api/graphql/abc/HomeTimeline", "bookmark"),
    false,
);
assert.equal(api.endpointMatchesPage("https://x.com/i/api/graphql/abc/Likes", "bookmark"), false);
assert.equal(api.endpointMatchesPage("https://x.com/i/api/graphql/abc/Likes", "like"), true);
assert.equal(api.endpointMatchesPage("https://x.com/i/api/graphql/abc/TweetDetail", "like"), false);

// --- page detection -------------------------------------------------------
sandbox.location.pathname = "/i/bookmarks";
assert.equal(api.getPageType(), "bookmark");
sandbox.location.pathname = "/i/bookmarks/folder-123";
assert.equal(api.getPageType(), "bookmark");

// History tab (the current UI): /i/history is Bookmarks, /i/history/likes is Likes.
sandbox.location.pathname = "/i/history";
assert.equal(api.getPageType(), "bookmark");
sandbox.location.pathname = "/i/history/";
assert.equal(api.getPageType(), "bookmark");
sandbox.location.pathname = "/i/history/bookmarks";
assert.equal(api.getPageType(), "bookmark");
sandbox.location.pathname = "/i/history/likes";
assert.equal(api.getPageType(), "like");
sandbox.location.pathname = "/i/history/videos";
assert.equal(api.getPageType(), null);
sandbox.location.pathname = "/i/history/articles";
assert.equal(api.getPageType(), null);

sandbox.location.pathname = "/Ethan151300/likes";
assert.equal(api.getPageType(), "like");
assert.equal(api.getCurrentAccount(), "ethan151300");
sandbox.location.pathname = "/home";
assert.equal(api.getPageType(), null);
sandbox.location.pathname = "/i/likes";
assert.equal(api.getPageType(), null);

// History routes do not contain the handle; the profile link is used instead.
sandbox.location.pathname = "/i/history/likes";
assert.equal(api.getCurrentAccount(), "owner");
sandbox.document.querySelector = () => ({ getAttribute: () => "/Ethan151300" });
assert.equal(api.getCurrentAccount(), "ethan151300");

// --- folder extraction ----------------------------------------------------
assert.equal(
    api.extractFolderId(
        "https://x.com/i/api/graphql/abc/BookmarkFolderTimeline?variables=%7B%22bookmark_collection_id%22%3A%22f1%22%7D",
    ),
    "f1",
);
assert.equal(api.extractFolderId("https://x.com/i/bookmarks/f1"), "f1");
assert.equal(api.extractFolderId("https://x.com/i/bookmarks"), null);

console.log("userscript behaviour checks passed");
