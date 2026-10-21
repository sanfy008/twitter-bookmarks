# Changelog

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
