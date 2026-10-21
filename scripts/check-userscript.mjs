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
                    rest_id: `user-${handle}`,
                    core: { screen_name: handle, name },
                },
            },
        },
        legacy: {
            full_text: text,
            created_at: createdAt,
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
                                                    },
                                                    {
                                                        media_url_https:
                                                            "https://pbs.twimg.com/media/b.mp4",
                                                        type: "video",
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
assert.equal(first.text, "价值投资 hello");
assert.equal(first.created_at, "2024-04-21T17:46:07.000Z");
assert.equal(first.url, "https://x.com/alice/status/1782103537234973176");
assert.deepEqual(
    first.media.map(item => item.type),
    ["photo", "video"],
);
assert.equal(api.collector.get("1800000000000000002").author_username, "carol");
assert.equal(api.collector.get("1600000000000000003").text, "quoted body");

// A missing timestamp must stay null rather than being fabricated.
const noDate = api.extractTweetCandidate({
    __typename: "Tweet",
    rest_id: "1900000000000000004",
    legacy: { full_text: "no date" },
});
assert.equal(noDate.created_at, null);
assert.equal(noDate.url, null);

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
sandbox.location.pathname = "/Ethan151300/likes";
assert.equal(api.getPageType(), "like");
sandbox.location.pathname = "/home";
assert.equal(api.getPageType(), null);
sandbox.location.pathname = "/i/likes";
assert.equal(api.getPageType(), null);

console.log("userscript behaviour checks passed");
