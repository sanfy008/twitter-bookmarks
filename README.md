# X Local Archive

A Windows-native, local-first archive for exported X bookmarks and likes. The project uses Python 3.12, uv, SQLite, and FTS5 for offline JSON import, normalization, deduplication, full-text search, and verified backups.

This project does not read browser cookies, call X, perform write actions, or implement high-frequency scraping.

## Safety boundary

- Credentials, cookies, private exports, SQLite databases, and backups are excluded by `.gitignore`.
- Import only reads a local JSON file explicitly supplied by the user.
- Original records remain available in the local database as `raw_json`.
- SQLite uses foreign keys, WAL mode, and `synchronous=FULL`.
- Backups use the SQLite online backup API and must pass `PRAGMA integrity_check`.
- Never store `auth_token`, `ct0`, browser cookies, or private exports in source files, shell history, or Git.

## Requirements

- Windows PowerShell
- Python 3.12
- uv

The Python version is declared in `.python-version`, and dependencies are locked in `uv.lock`.

## Setup

From the project root:

```powershell
.\scripts\setup.ps1
```

The default database is `data\archive.sqlite3`.

## Supported JSON forms

The importer accepts:

- An array of tweet objects
- A single tweet object
- An object containing a `tweets`, `bookmarks`, `likes`, `items`, or `data` array

Recognized common fields include:

- ID: `id`, `id_str`, `tweet_id`, `rest_id`
- Text: `text`, `full_text`, `content`
- Author: top-level fields, an `author` object, or a `user` object
- Time: `created_at`, `createdAt`, `date`
- Media: `media`, `media_urls`

Imports are idempotent. Tweets are deduplicated globally by tweet ID, while bookmark and like membership is stored independently for each account.

## Import bookmarks and likes

```powershell
.\scripts\import.ps1 -Source D:\Private\bookmarks.json -Account your_username -Type bookmark
.\scripts\import.ps1 -Source D:\Private\likes.json -Account your_username -Type like
```

A record without a tweet ID is counted in `errors`; valid records in the same import are still processed. The CLI returns a nonzero exit code when record errors occur.

## Full-text search

```powershell
.\scripts\search.ps1 -Query "SQLite"
.\scripts\search.ps1 -Query "local archive" -Limit 10
```

Search uses SQLite FTS5 and BM25 relevance ranking.

## Backup and verification

```powershell
.\scripts\backup.ps1
.\scripts\verify.ps1
```

The backup script verifies the source database, creates a timestamped file under `backups\`, and retains it only after the backup passes `PRAGMA integrity_check`.

## Recovery procedure

1. Stop commands or applications using the archive database.
2. Verify the selected backup:

   ```powershell
   uv run x-archive --database backups\x-archive-YYYYMMDD-HHMMSS.sqlite3 verify
   ```

3. Rename the current `data\archive.sqlite3` instead of deleting it.
4. Copy the verified backup to `data\archive.sqlite3`.
5. Run `uv run x-archive verify` again.
6. Search for a known term to confirm that both content and the FTS5 index are readable.

## Direct CLI usage

Global options must appear before the subcommand.

```powershell
uv run x-archive init
uv run x-archive import D:\Private\bookmarks.json --account your_username --type bookmark
uv run x-archive search "SQLite" --limit 20
uv run x-archive backup backups
uv run x-archive verify
uv run x-archive --database D:\Private\archive.sqlite3 verify
```

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

Do not run unaudited binaries or extensions with access to an authenticated session. Automated GraphQL collection is intentionally outside this project. Any future collector must remain read-only and low-frequency, stop on authentication failures, back off on rate limits, preserve raw responses, and persist its cursor after every successful page.

The evidence-based review of three current candidates is recorded in
CANDIDATE_AUDIT.md. No exporter is bundled or
automatically trusted.

## Tests

The test suite covers:

- Initial and repeated import idempotency
- Independent bookmark and like membership
- Tweet updates and FTS5 trigger synchronization
- English and exact-phrase Chinese full-text search
- Invalid-record accounting
- SQLite online backup, integrity verification, and search from the backup

Run:

```powershell
uv run pytest
```

## Candidate exporter audit

See `CANDIDATE_AUDIT.md` for the evidence-based candidate review and operating restrictions. No exporter is bundled or automatically trusted.

