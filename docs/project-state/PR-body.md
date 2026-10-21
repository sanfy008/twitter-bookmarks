# Fix import safety, undo provenance and silent truncation

## Why

An adversarial review of the 0.3.1 work found six defects that the existing 46 tests did not cover. Every one of them sits on the documented recovery path — re-export from the userscript, then import — so "tests are green" did not mean the path was safe.

## What changed

### Data safety (P0)

- **A thinner re-import overwrote good data.** `_update_tweet` assigned every column, so a record arriving without author, timestamp, or text blanked what was already stored, and the FTS copy was rebuilt from the empty text — which silently broke Chinese search. Reproduced: one rich import followed by a thin import left `media=0`, `entities=0`, `author_name=''`, and `search("价值投资")` returning nothing. Non-empty values now win, and media/entity rows are replaced only when the payload actually supplies them (an explicit `media: []` still clears).
- **The importer rejected only URL-shaped ids.** `abc123` and a GraphQL `User` node with a numeric `rest_id` were stored as tweets. Ids must now match `^[0-9]+$`, and profile-shaped nodes are rejected even when `__typename` is absent.
- **`undo --run` deleted entries another run still owned.** Provenance lived in `archive_entries.run_id`, which is not updated when a later import reuses an existing entry (`ON CONFLICT DO NOTHING`), so undoing the first run orphaned and deleted a row the second run was using. Schema v9 adds an `entry_runs` table; undo now only detaches entries no run still claims. Orphan detection switched from `NOT IN` to `NOT EXISTS` — `NOT IN` matches nothing when a `tweet_id` is NULL.

### Correctness

- **CI had never run.** The workflow triggered on `main`; the repository's default branch is `master`. Both names are now listed.
- **Backups overwrote each other** when two runs started in the same second (4 calls produced 1 file), and retention rotated backups belonging to *other* databases in a shared directory. Names now include the source database and a collision suffix; rotation is scoped per database.
- **`export` silently stopped at 1000 tweets** (2,508 stored). The default is now every matching row; `--limit` still caps explicitly.

### Smaller

- `import` reports `duplicate_of` and writes nothing when the same payload was already imported, so re-running `sync.ps1` cannot create a second run or backup.
- `doctor` derives the backup directory from the database path instead of assuming a `data/` layout.

## Verification

- `55 passed` (`uv run pytest`), up from 46; new tests cover each defect as a failure scenario.
- `ruff check` and `ruff format --check` clean.
- `node scripts/check-userscript.mjs` passes.
- `x-archive verify`: integrity / foreign_keys / fts all `ok`.
- Live database migrated v8 → v9 with unchanged counts (2,508 tweets, 2,171 bookmarks, 1,946 media); backup taken first.
- Original reproduction scripts re-run against the fixed code confirm each fix.

## Note for review

The existing `archive_entries.run_id` values in the user's database are all NULL, so `entry_runs` is legitimately empty after migration rather than back-filled with invented provenance. Imports from here on record it properly.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
