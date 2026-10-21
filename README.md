# X Local Archive

A Windows-native, local-first archive for exported X bookmarks and likes. Python 3.12,
uv, SQLite, and FTS5 provide offline JSON import, normalization, deduplication,
substring full-text search (including Chinese), and verified backups.

The project never reads browser cookies, never calls X on your behalf, and never
performs write actions. Import only reads a local JSON file that you explicitly pass in.

## Safety boundary

- Credentials, cookies, private exports, SQLite databases, and backups are excluded by `.gitignore`.
- The importer reads only a local JSON file supplied by the user.
- Original records remain available in the database as `raw_json`.
- SQLite uses foreign keys, WAL mode, and `synchronous=FULL`.
- Backups use the SQLite online backup API and must pass `PRAGMA integrity_check`.
- Never store `auth_token`, `ct0`, browser cookies, or private exports in source files, shell history, or Git.

### Bundled collector (opt-in)

`scripts/x-archive-sync.user.js` is a **manual, opt-in** userscript that observes the
GraphQL responses X already loaded while you browse your own bookmarks or likes pages.
It does not read cookies, does not send data anywhere, and only downloads a local JSON
file. It is deliberately scoped:

- It runs only on the bookmarks/likes surfaces: `x.com/i/history` (the current UI, where the
  default tab is Bookmarks), `x.com/i/history/likes`, `x.com/i/bookmarks*`, and
  `x.com/<handle>/likes*` (plus the twitter.com equivalents). Other History tabs
  (Videos, Articles) are ignored.
- It only accepts the `Bookmarks`, `BookmarkFolderTimeline`, `Likes`, and `UserLikes` endpoints.
- It captures author profile fields, hashtags/mentions/expanded URLs, engagement metrics,
  quote/reply/conversation ids, media dimensions/alt text/variants, and the bookmark
  folder id when X exposes one.
- It never auto-starts; you press **开始抓取** and can stop at any time.
- It keeps the first page X loaded before you pressed start; starting a run does not clear it.
- While X fetches the next page, the log reports `等待下一页` instead of a silent 0.
- It pauses while the tab is in the background, so it does not collect unattended.
- It stops on `HTTP 401`/`429`, on the configured scroll limit, or at the bottom of the timeline.
- It only reads the response bodies X itself requested; it does not issue its own API calls.

This is still automated scrolling of an authenticated page. Treat it as an experimental
convenience, not as a background service. See `CANDIDATE_AUDIT.md` for the review rules
that apply to third-party exporters.

## Requirements

- Windows PowerShell (the CLI also works anywhere Python runs)
- Python 3.12
- uv

The Python version is declared in `.python-version`; dependencies are locked in `uv.lock`.

## Setup

From the project root:

```powershell
.\scripts\setup.ps1
```

The default database is `data\archive.sqlite3`. Override it with `--database` or the
`X_ARCHIVE_DB` environment variable:

```powershell
$env:X_ARCHIVE_DB = "D:\Archive\archive.sqlite3"
```

Existing databases are migrated in place on `init`/`import`. The current schema
version is stored in `PRAGMA user_version`.

## Collecting bookmarks and likes

1. Install Violentmonkey or Tampermonkey.
2. Run the one-click installer:

   ```powershell
   .\scripts\install-userscript.ps1
   ```

   The installer serves **only** `x-archive-sync.user.js` on a random loopback port,
   validates the `Host` header, and shuts down after the download. It never exposes
   the project directory or the database.
3. Open `x.com/i/history` (Bookmarks tab), `x.com/i/history/likes`, or the legacy
   `x.com/i/bookmarks` / `x.com/<handle>/likes` page, click **开始抓取**, and let it
   scroll. Press **停止** at any time to export what has been captured.
4. Move the downloaded JSON into `inbox\`.
5. Run:

   ```powershell
   .\scripts\sync.ps1
   ```

`sync.ps1` reads `account`/`type` from the JSON metadata, falls back to the filename,
imports each file, and moves it to `inbox\processed\`. Files with record-level errors
are moved to `inbox\failed\` with an `.error.txt` report so they can be reviewed.

## Supported JSON forms

The importer accepts:

- An array of tweet objects
- A single tweet object
- An object containing a `tweets`, `bookmarks`, `likes`, `items`, or `data` array
- The userscript payload (`account`, `type`, `exported_at`, `newest_id`, `oldest_id`,
  `total_tweets`, optional `folder_id`/`folder_name`, `tweets`)

Recognized common fields include:

- ID: `rest_id`, `id`, `id_str`, `tweet_id`
- Text: `note_tweet...text`, `text`, `full_text`, `content`
- Author: `core.user_results.result.core.screen_name`, `author`, `user`, or flat fields;
  optional `author_id`, `author_followers`, `author_verified`, `author_avatar`
- Time: `created_at`, `createdAt`, `date` (ISO 8601 and RFC 2822 are normalized to UTC)
- Media: `media`, `media_urls`, `legacy.extended_entities.media`, `legacy.entities.media`;
  optional `media_id`, `width`, `height`, `duration_ms`, `alt_text`, `variants`
- Entities: `entities.hashtags`, `entities.mentions` / `user_mentions`, `entities.urls`
  (`url` + `expanded`), `entities.symbols`
- Metrics: `metrics.favorite/retweet/reply/quote/bookmark/views` or the raw
  `legacy.favorite_count` etc.
- Relations: `relations.quoted_id/retweeted_id/in_reply_to_id/conversation_id` or the
  raw `legacy.*_status_id_str` fields
- `lang`, `source`, `status`

Imports are idempotent. Tweets are deduplicated globally by tweet ID; bookmark and
like membership is stored independently per account. Account handles are
case-insensitive.

If the payload contains `type` or `account`, they must match `--type`/`--account`;
otherwise the import is rejected to prevent mislabeled data.

## Import

```powershell
.\scripts\import.ps1 -Source D:\Private\bookmarks.json -Account your_username -Type bookmark
.\scripts\import.ps1 -Source D:\Private\likes.json -Account your_username -Type like
```

A record without a tweet ID (or a non-tweet GraphQL object such as a `User`) is counted
in `errors`; valid records in the same import are still processed. The CLI returns a
nonzero exit code when record errors occur and prints up to five error samples.
Detailed errors are stored in `import_errors`.

## Full-text search

```powershell
.\scripts\search.ps1 -Query "SQLite"
.\scripts\search.ps1 -Query "价值投资" -Limit 10
.\scripts\search.ps1 -Query "投资" -Type bookmark -Account your_username
```

Search uses SQLite FTS5 with BM25 relevance ranking and returns a `snippet` field.

- ASCII terms use prefix matching (`sqlit` matches `SQLite`).
- Chinese queries match arbitrary substrings; adjacency and order are enforced
  (`价值投资` matches, `资投` does not).
- `--type` and `--account` filter by archive membership.
- `--author` matches a handle or numeric author id; `--since` / `--until` filter the
  normalized `created_at`; `--has-media` requires at least one media row; `--folder`
  filters by bookmark folder id.
- `--offset` paginates.

```powershell
.\scripts\search.ps1 -Query "投资" -Author alice -Since 2024-01-01 -HasMedia
.\scripts\search.ps1 -Query "AI" -Folder f1
```

Indexing notes: CJK characters are indexed as single-character tokens with positions,
which makes substring search possible without a segmentation dependency. The trade-off
is a somewhat larger FTS index; `prune` and `VACUUM` keep it compact.

## Export

```powershell
uv run x-archive export --format csv --out exports\
uv run x-archive export --format md --query "投资" --author alice
uv run x-archive export --format html --out exports\archive.html
uv run x-archive export --format json --type bookmark --has-media --out exports\
```

Formats: `json`, `csv`, `md` (Markdown for Obsidian/notes), `html` (static page).
The export accepts the same filters as search; `--out` may be a directory (timestamped
filename) or a file path. Media URLs, hashtags, mentions, and the latest engagement
metrics are included.

## Statistics and maintenance

```powershell
uv run x-archive stats
uv run x-archive prune --dry-run
uv run x-archive prune
uv run x-archive forget --account old_account
uv run x-archive inspect D:\Downloads\bookmarks_ethan151300_20261021-155610.json
uv run x-archive doctor
uv run x-archive undo --run 6
```

- `stats` reports counts, date range, accounts, schema version, and the last import.
- `prune` removes empty/unknown rows and tweets with no archive membership, then vacuums.
- `forget` removes one account, its archive entries, and any tweets left orphaned.
- `inspect` checks an export before importing it: declared vs actual counts, duplicate
  ids, empty text, unknown authors, media, date range, and whether `newest_id` /
  `oldest_id` match the file.
- `doctor` checks integrity, foreign keys, FTS, orphans, empty text, unknown authors,
  and the age of the newest backup; exits nonzero when issues are found.
- `undo --run` removes the archive entries created by one import run and any tweets
  left orphaned (shared entries from earlier runs are preserved).

## Backup and verification

```powershell
.\scripts\backup.ps1
```

The script verifies the source database, creates a timestamped file under `backups\`,
retains the newest 10 timestamped backups, and keeps a backup only after it passes
`PRAGMA integrity_check`.

`verify` now checks three things:

```json
{
  "integrity": "ok",
  "foreign_keys": "ok",
  "fts": "ok"
}
```

`fts` runs the FTS5 `integrity-check` command, which requires a writable handle even
though it does not modify data.

## Recovery procedure

1. Stop commands or applications using the archive database.
2. Verify the selected backup:

   ```powershell
   uv run x-archive --database backups\x-archive-YYYYMMDD-HHMMSS.sqlite3 verify
   ```

3. Rename the current `data\archive.sqlite3` instead of deleting it.
4. Copy the verified backup to `data\archive.sqlite3`.
5. Run `uv run x-archive verify` again.
6. Search for a known term to confirm that both content and the FTS index are readable.

## Direct CLI usage

Global options must appear before the subcommand.

```powershell
uv run x-archive init
uv run x-archive import D:\Private\bookmarks.json --account your_username --type bookmark
uv run x-archive search "SQLite" --limit 20 --offset 0
uv run x-archive search "投资" --type bookmark --account your_username
uv run x-archive search "投资" --author alice --since 2024-01-01 --has-media
uv run x-archive export --format md --query "投资" --out exports\
uv run x-archive backup backups --keep 10
uv run x-archive verify
uv run x-archive stats
uv run x-archive doctor
uv run x-archive prune --dry-run
uv run x-archive forget --account old_account
uv run x-archive undo --run 6
uv run x-archive inspect D:\Downloads\bookmarks_ethan151300_20261021-155610.json
uv run x-archive --database D:\Private\archive.sqlite3 verify
uv run x-archive --version
```

## Collector troubleshooting

- **Progress stays flat for several screens.** X has already rendered the current
  batch and is waiting to be scrolled to the bottom before it requests the next one.
  The log shows `等待下一页`. The run only declares the bottom after ~40 seconds
  without page growth, because bookmark pagination can take 20–30 seconds.
- **The exported JSON is missing the newest page.** Userscript v2.1.0 and earlier
  cleared the collector when 开始抓取 was pressed, discarding the page X had already
  loaded. Update to v2.2.0; the export now includes it and `newest_id` is correct.
- **The account shows `owner`.** The profile link was not found. Pass `-Account`
  to `sync.ps1`, or use the legacy `/<handle>/likes` page for likes.
- **No data at all.** Open 日志 and check the `接受端点` / `忽略端点` lines. The
  bookmarks endpoint is `Bookmarks` and the likes endpoint is `Likes`; if X changes
  them, the log will show the new name.

## Data quality note

Versions before the collector fix stored author objects as if they were tweets: a large
share of rows had empty text, `author_username = 'unknown'`, fabricated timestamps, and
broken `x.com/unknown/status/...` URLs. The importer now rejects non-tweet GraphQL
objects, and `prune` removes the old junk rows. Author names and media types that were
lost in those exports cannot be recovered locally; re-export with the current userscript
to rebuild the archive with correct authors and links.

## Tests and CI

```powershell
.\scripts\verify.ps1
```

This runs `ruff check`, `ruff format --check`, `pytest`, and `x-archive verify`.
The suite covers:

- Idempotent import, independent bookmark/like membership, tweet updates, FTS triggers
- GraphQL normalization (author, note tweets, media, timestamps, non-tweet rejection)
- Author profile, entities, metrics, relations, media metadata, and bookmark folders
- Chinese substring search, ASCII prefix search, filters, snippets
- Schema migration (v0 -> v8) and the new users/entities/metrics/folders tables
- Export to JSON, CSV, Markdown, and HTML
- Doctor diagnostics and undo-by-run
- Backup retention, integrity verification, and search from a backup
- CLI exit codes, statistics, pruning, and account removal

CI runs the same checks on Ubuntu and Windows (see `.github/workflows/ci.yml`).

## Open-source exporter review gate

Before allowing any third-party X exporter to access an authenticated browser session, review:

1. Source availability and license.
2. Maintenance status and compatibility with the current X interface.
3. Requested browser or operating-system permissions.
4. Network destinations for cookies, tokens, telemetry, and exported content.
5. Remote execution, automatic updates, or closed-source binary components.
6. Incremental export, resumability, and raw-response preservation.
7. Coverage of tweet ID, text, author, timestamp, URL, and media metadata.
8. Whether it can operate read-only without uploading session credentials.

Do not run unaudited binaries or extensions with access to an authenticated session.
Any collector must remain read-only and low-frequency, stop on authentication failures,
back off on rate limits, preserve raw responses, and persist its cursor.

The evidence-based review of three third-party candidates is recorded in
`CANDIDATE_AUDIT.md`, together with the constraints applied to the bundled userscript.

## License

MIT. See `LICENSE`.
