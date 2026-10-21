# Candidate Exporter Audit

Audit date: 2026-09-25 (updated 2026-10-21)

## Scope and safety boundary

This project does not bundle, install, or automatically run any X collector. Candidate exporters are considered only as optional, manually operated sources of JSON. They must not receive access to this project's databases, backups, credentials, or unrelated browser accounts.

## prinsss/twitter-web-exporter

Evidence reviewed:

- Public MIT-licensed TypeScript userscript project.
- Captures GraphQL responses initiated by the X web application through a network interceptor instead of issuing its own X API requests.
- Export coverage depends on data loaded through manual scrolling.
- The project states that processing remains in the local browser and archive data is not uploaded to a cloud service.
- The repository does not contain a root `manifest.json`; the exact generated userscript and its metadata must be reviewed before installation.
- The repository does not contain a tracked `dist` directory, so repository source and an installed release artifact must not be assumed to be identical without comparison.

Decision: **conditional candidate**. It is the least invasive candidate reviewed for a manual, observable, low-frequency export. Inspect the exact release userscript before use. Do not add auto-scroll or unattended automation.

## sytelus/xarchive

Evidence reviewed:

- Public MIT-licensed Chrome Manifest V3 extension.
- Uses X's internal GraphQL API and maintains a cumulative archive per account.
- Requests `storage`, `unlimitedStorage`, `cookies`, `webRequest`, `declarativeNetRequestWithHostAccess`, and `downloads` permissions.
- Requests host access to `x.com`, `twitter.com`, and `abs.twimg.com` and injects a content script at `document_start`.
- Its service worker captures `authorization`, `x-csrf-token`, client identifiers, GraphQL query IDs, and feature flags from X requests and stores captured values in extension-local storage.
- It registers a rule that adds X Origin and Referer headers to extension-originated GraphQL requests.
- The content script reads the `twid` cookie and the profile handle to label stored account data.
- The project states that archives remain local, credentials are not exported, and it adds no analytics or telemetry.
- Browser extension storage is explicitly not a backup; downloaded JSON backups remain necessary.

Decision: **high-risk conditional candidate**. Its cookie and request-header access is broader than required by this local importer. Do not install it in the primary browser profile. If evaluated, use a disposable profile, review `background.js`, `content.js`, and identity/storage code first, disable the extension after export, and import only the resulting JSON.

## 0x1b2c/twitter-bookmarks-downloader

Evidence reviewed:

- Public MIT-licensed Go 1.25 application with a browser userscript and local HTTP daemon.
- The userscript explicitly implements auto-scroll and unattended periodic synchronization.
- It uses `unsafeWindow` and `GM_xmlhttpRequest` and posts captured responses to `http://localhost:41008/api/sync-raw`.
- The daemon starts a background media-download worker and listens on port `41008`.
- The documented implementation uses SQLite and automatically downloads media.
- No `docker-compose.yml` exists at the checked repository path; the documented setup builds a Go executable directly.
- The README clone example references a different repository owner, which is an additional documentation-integrity concern.

Decision: **rejected for current scope**. Although Docker was not demonstrated as required, automatic scrolling, unattended reloads, persistent synchronization, a local daemon, and automatic media downloads conflict with this project's explicit low-frequency, import-only boundary.

## Bundled collector in this repository

`scripts/x-archive-sync.user.js` (v2.3.0) is maintained by this project. It is not a
third-party exporter, but it is subject to the same constraints:

- Opt-in and manually started from the floating widget; it never runs on page load.
- Runs only on `x.com/i/history` (default Bookmarks tab), `x.com/i/history/likes`,
  `x.com/i/bookmarks*`, and `x.com/<handle>/likes*`. The Videos and Articles tabs of
  History are ignored.
- Accepts only the `Bookmarks`, `BookmarkFolderTimeline`, `Likes`, and `UserLikes`
  GraphQL endpoints. Home timelines, tweet detail, and profile timelines are ignored.
- Reads responses X already fetched; it never issues its own API requests.
- Does not read cookies, tokens, or authorization headers, and sends nothing off-device.
- Pauses while the tab is hidden; it does not perform unattended background collection.
- Stops on `HTTP 401`/`429`, on the configured scroll limit, at the bottom of the
  timeline, or when the user presses stop.
- Writes a single JSON file to the browser's download directory.

The installer exposes only the userscript file on a loopback port with a random port
number, validates the `Host` header, and never serves the project directory, database,
or inbox.

Decision: **included, opt-in, manual**. It remains subject to the rules below.

## Selection outcome

No exporter is automatically trusted or included.

For a one-time export, `prinsss/twitter-web-exporter` is the least invasive candidate found, subject to exact release-artifact inspection. `sytelus/xarchive` requires a disposable browser profile and deeper source review because it captures credentials and requests cookie and network-interception permissions. `0x1b2c/twitter-bookmarks-downloader` is excluded from the current implementation.

## Mandatory operating rules

1. Use a separate browser profile containing no unrelated accounts.
2. Review the exact installed source or release artifact, not only its repository README.
3. Never copy `auth_token`, `ct0`, cookies, authorization headers, or session data into this repository.
4. Operate manually and at low frequency. Do not add unattended scrolling, periodic
   reloads, background-tab collection, or polling. Automated scrolling is acceptable
   only when the user starts it explicitly and can observe it.
5. Stop on authentication errors, rate limits, unexpected network destinations, or permission changes.
6. Export JSON to a private path excluded from Git.
7. Verify record counts and sample tweet IDs before importing.
8. Disable or remove the exporter after use when continued access is unnecessary.

