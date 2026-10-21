---
updated: 2026-10-21T17:32:57+08:00
session: S-20261021-1730
project_version: v1.2
status: active
evidence_level: mixed
---

# Resume Card

## Current Contract

- Goal: 在本地把 X 书签/点赞沉淀为可离线检索、可验证备份、可长期维护的归档；数据可信、中文可检索、迁移可验证。
- Scope / non-goals: 只读采集（不读 cookie、不调用 X 写接口）；手动、低频、可停止；不下载媒体、不做无人值守后台抓取、不上传数据。
- Constraints: Python 3.12 + uv；Windows PowerShell 5.1；SQLite FTS5；`data/`、`backups/`、`inbox/` 私有且 Git 忽略；用户要求保留现有 `README.md`，不改写。
- Acceptance check: `pytest` 全绿、`node scripts/check-userscript.mjs` 通过、`x-archive verify` 三项 `ok`；新导出经 `x-archive inspect` 后 `non_numeric_ids=0`、`empty_text=0`、`unknown_author=0`、`declared.newest_id/oldest_id == actual`，且至少部分记录带 `author_id/entities/metrics`。

## Verified State

- [verified] 55 个 Python 测试通过 — `uv run pytest`，2026-10-21（第二轮审查后由 51 增至 55）。
- [verified] 采集器行为测试通过 — `node scripts/check-userscript.mjs`。
- [verified] `ruff check` 与 `ruff format --check` 均通过（23 files）。
- [verified] 真实库已迁移到 schema 9，数据量不变 — `x-archive init` + `stats`：2,508 tweets / 2,171 bookmarks / 804 likes / 1,946 media / 14,376,960 bytes。
- [verified] 迁移前备份 — `backups/x-archive-archive-20261021-171044.sqlite3`（新命名含库名）。
- [verified] `verify` 三项 ok；`doctor` 仅剩 `2508 tweet(s) have an unknown author`。
- [verified] 修复项均有复现脚本证据：降级重导保留字段、非数字 ID 拒绝、`undo` 保留共享条目、备份不再同秒覆盖、导出 2,508 条全量。
- [verified] CI 原配置 `branches: ["main"]` 与仓库默认分支 `master` 不符，从未触发 — `git ls-remote --symref origin HEAD` 确认只有 `master`。
- [verified] 修复已提交 `55cf481` 并推送到 `origin/fix/import-safety-and-provenance`；本机无 `gh`，PR 未创建。
- [inferred] 修正分支名后的 CI 首次运行仍未观察，需要推送并合并后确认。

## Blockers and Do-Not-Repeat

- 不要直接导入 v2.2 的 1,202 条文件：104 条 `id` 是 t.co URL，且没有 v2.3 元数据。
- 只有在 `inspect` 显示 `non_numeric_ids=0` 后才导入。
- 1,174 条库内书签不在 v2.2 文件中，无法判定是取消书签还是运行未到底。
- 2,508 条历史推文的作者/媒体类型/URL 仍为 `unknown`；必须由用户重新导出。
- 不要裸 SQL 删除 `tweets`/`accounts`；只用 `x-archive prune` / `forget` / `undo`。
- 不要改写 `README.md`。
- 不要假设 `archive_entries.run_id` 能表达“谁还拥有这条目” —— 第二批次复用已有 entry 时不会更新它；来源信息在 `entry_runs`（schema 9）。
- 不要再给导入加“整行覆盖”语义：thin 记录会清空已捕获的作者/时间/正文，而本地无法恢复。

## One Next Action

- action: 用 https://github.com/sanfy008/twitter-bookmarks/compare/master...fix/import-safety-and-provenance?expand=1 创建 PR（正文见 `docs/project-state/PR-body.md`），合并后查看 GitHub Actions 首次运行。
- completion check: PR 显示 55 tests 在 Ubuntu + Windows 两条流水线通过；`master` 包含提交 `55cf481`。完成后下一动作才转到「更新 userscript 2.3.1 并重导」。

## Read First

- `README.md`（产品文档，不改写）
- `Handover Book.md`
- `docs/daily__pipeline_reviews/2026-10-21.md`
- `scripts/x-archive-sync.user.js`
- `src/x_local_archive/db.py`（`_update_tweet`、`undo_run`、`backup`）
- `src/x_local_archive/export.py`
