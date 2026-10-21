# Changelog

## 0.3.0 - 2026-10-21

### Added

- Collector v2.3.0 captures author profile fields (`author_id`, followers, verified,
  avatar), hashtags/mentions/expanded URLs, engagement metrics, quote/reply/conversation
  ids, media dimensions/alt text/variants, `lang`, `source`, and the bookmark folder id.
- Schema v8: `users`, `tweet_entities`, `tweet_metrics`, `bookmark_folders`; tweet
  relation/lang/source/status columns; archive folder/run/read-status columns; media
  metadata columns.
- Search filters: `--author`, `--since`, `--until`, `--has-media`, `--folder`.
- `x-archive export --format json|csv|md|html` with the same filters.
- `x-archive doctor` for integrity/orphan/backup checks and `x-archive undo --run`
  for per-run rollback.
- Import records `run_id` on archive entries and stores bookmark folder metadata.

### Changed

- Search results include `media_count` and the latest `favorite_count`.
- The userscript payload includes `oldest_id`, `folder_id`, and the metadata object.
- Test suite expanded to 44 tests, including metadata landing, filters, export,
  doctor, undo, and schema v8 migration.

## 0.2.2 - 2026-10-21

### Fixed

- Starting a capture no longer clears the tweets already captured from the first
  page. Previously the first page (often 20–30 posts) was discarded, the counter
  stayed at 0 for the first ~10 screens, and the exported JSON missed the newest
  page, so the saved `newest_id` breakpoint was wrong.
- The bottom-of-timeline timeout is now 40s instead of 24s. X bookmark pagination
  can take 20–30s, so the old timeout could stop a run between pages.
- While waiting for the next page the collector no longer keeps scrolling, and the
  log says `等待下一页` rather than showing an unexplained flat count.
- Bookmark and like membership is tracked per page type, so switching between the
  History tabs cannot mix the two lists; the same post can belong to both.

### Changed

- Logs include the GraphQL endpoint name and the exported `newest`/`oldest` IDs.
- Adaptive scroll step: traverse a loaded batch quickly, slow down near the bottom.
- The scroll limit now counts actual scroll steps; waiting for the next page no longer
  consumes the configured limit.

## 0.2.1 - 2026-10-21

### Fixed

- The userscript now recognises X's History routes. `x.com/i/history` is treated as
  Bookmarks and `x.com/i/history/likes` as Likes; the legacy `/i/bookmarks` and
  `/<handle>/likes` routes still work. The Videos and Articles tabs are ignored.
- On History routes the account is read from the profile link instead of the path, so
  `history` is never mistaken for a username.

### Added

- Userscript behaviour tests cover the History routes, trailing slashes, and account
  detection.

## 0.2.0 - 2026-10-21

### Fixed

- The userscript no longer treats GraphQL `User` objects as tweets. This removes the
  empty-text, `unknown`-author, fabricated-timestamp rows that polluted earlier archives.
- Author handles are read from the current X schema (`core.user_results.result.core`),
  with a corrected fallback path.
- Media is read from `legacy.extended_entities.media` (videos and multi-image posts),
  with types preserved.
- Timestamps are normalized to ISO 8601 UTC; missing timestamps are stored as `NULL`
  instead of the export time.
- URLs are no longer fabricated as `x.com/unknown/status/...`.
- SQLite connections are closed deterministically (fixes Windows file locks after import).
- Chinese full-text search now supports arbitrary substrings and enforces adjacency;
  ASCII search supports prefix matching.
- Search validates `limit`/`offset` and supports `--type`/`--account` filters and snippets.
- PowerShell wrappers now check native exit codes, so failed setup/verify/backup runs
  no longer report success.
- `sync.ps1` keeps files with record errors and writes an error report instead of
  silently discarding them.

### Added

- Automatic schema migrations (`PRAGMA user_version`, currently v7), including an
  in-place rebuild to a contentless FTS5 index with a stable integer key, timestamp
  normalization, and removal of absolute source paths.
- Indexes on `archive_entries(tweet_id)` and `tweets(created_at)`; `busy_timeout`.
- Import metadata (`account`, `entry_type`, `exported_at`, `newest_id`, `total_tweets`,
  `source_sha256`) and an `import_errors` table with per-record reasons.
- CLI: `stats`, `prune`, `forget`, `--version`, `--offset`, `--type`, `--account`,
  `X_ARCHIVE_DB`; `backup --keep`.
- `verify` now checks foreign keys and the FTS5 index.
- Case-insensitive account handles.
- Ruff configuration, MIT license, and a Windows/Ubuntu CI workflow.
- Collector: per-account breakpoints, numeric breakpoint comparison, endpoint filtering,
  export-on-stop, 401/429 handling, background-tab pause, and an explicit export button.

### Changed

- FTS indexing uses a contentless table, reducing a 2,508-tweet archive from ~19.5 MB
  to ~14.3 MB while keeping CJK substring search.
- README and `CANDIDATE_AUDIT.md` now document the bundled collector and its constraints.
