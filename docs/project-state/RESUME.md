---
updated: 2026-10-21T16:07:58+08:00
session: S-20261021-1607
project_version: v1.0
status: active
evidence_level: mixed
---

# Resume Card

## Current Contract

- Goal: 在本地把 X 书签/点赞沉淀为可离线检索、可验证备份、可长期维护的归档；数据可信、中文可检索、迁移可验证。
- Scope / non-goals: 只读采集（不读 cookie、不调用 X 写接口）；手动、低频、可停止；不下载媒体、不做无人值守后台抓取、不上传数据。
- Constraints: Python 3.12 + uv；Windows PowerShell 5.1；SQLite FTS5；`data/`、`backups/`、`inbox/` 私有且 Git 忽略；用户要求保留现有 `README.md`，本次 save 不改写。
- Acceptance check: `pytest` 全绿、`node scripts/check-userscript.mjs` 通过、`x-archive verify` 三项 `ok`；新导出经 `x-archive inspect` 后 `empty_text=0`、`unknown_author=0`、`declared.newest_id == actual.newest_id`。

## Verified State

- [verified] 38 个 Python 测试通过 — `uv run pytest`，`tests/`，2026-10-21。
- [verified] 采集器行为测试通过（History 路由、首屏保留、书签/点赞独立归属、账号识别）— `node scripts/check-userscript.mjs`。
- [verified] 数据库完整性与 FTS 正常 — `uv run x-archive verify` 返回 `integrity/foreign_keys/fts = ok`。
- [verified] 当前库为 schema 7、2,508 tweets、2,171 bookmarks、804 likes、1,946 media、14,188,544 bytes — `uv run x-archive stats`。
- [verified] 三次提交已推送，`master` 与 `origin/master` 均在 `477d9d2` — `git log --oneline -3`、`git status -sb`。
- [verified] `README.md` 保持产品文档原样，本次 save 未生成/覆盖 — 用户指令；`git status` 无 README 变更。
- [inferred] CI 已配置 Ubuntu/Windows 两条流水线，但本次 push 后尚未观察到运行结果 — `.github/workflows/ci.yml`，证据不足。
- [proposed] 用 v2.2.0 重新导出可补齐作者/媒体类型/URL — 旧 JSON 已丢失这些字段，本地无法恢复。

## Blockers and Do-Not-Repeat

- 2,508 条历史推文的作者/媒体类型/URL 仍为 `unknown`；必须由用户用 v2.2.0 重新导出，不能用本地数据恢复。
- 不要裸 SQL 删除 `tweets`/`accounts`：SQLite 默认 `foreign_keys=OFF`，会留下 `archive_entries`/`tweet_media` 孤儿并可能误删真实记录；只用 `x-archive prune` / `x-archive forget`。
- 不要在 `startSync()` 清空采集器：首屏在点击开始前已加载，清空会丢 26 条左右并让 `newest_id` 偏移。
- 不要假设只有 `/i/bookmarks`：必须同时支持 `/i/history`、`/i/history/likes` 与旧路由。
- 不要改写 `README.md`：本次 project-save 的 ReadMe 契约由临时镜像验证，真实 README 保留。

## One Next Action

- action: 用 userscript v2.2.0 重新导出 `/i/history`（书签）与 `/i/history/likes`（点赞），把 JSON 放入 `inbox/`，先运行 `uv run x-archive inspect <file>`，确认无误后运行 `scripts/sync.ps1`。
- completion check: `inspect` 显示 `empty_text=0`、`unknown_author=0`、`declared.newest_id == actual.newest_id`；`sync.ps1` 成功备份并 `verify` 三项 `ok`；`stats` 的 tweets/bookmarks/likes 按预期增加。

## Read First

- `README.md`（产品文档，本次 save 未改写）
- `Handover Book.md`
- `docs/daily__pipeline_reviews/2026-10-21.md`
- `scripts/x-archive-sync.user.js`
- `src/x_local_archive/db.py`
