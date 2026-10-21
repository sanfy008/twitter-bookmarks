# Handover Book — X Local Archive

> **ReadMe 例外声明**：本次 project-save 按用户明确要求，**不生成、不覆盖** 现有 `README.md`（该文件是项目产品文档，保留原样）。因此 project-save 的活性摘要由本文件的 Zone A 与 `docs/daily__pipeline_reviews/2026-10-21.md` 承担；`docs/project-state/RESUME.md` 提供下一会话的一分钟入口。`validate_closure.py` 的 ReadMe 契约检查在临时镜像中执行，真实工作区不改写 README。

## Zone A — Living Dashboard

### A1. 🎯 Core Intent Anchor

- 在本地（Windows + Python 3.12 + SQLite/FTS5）把 X 的书签/点赞沉淀为可离线检索、可验证备份、可长期维护的个人归档。
- 北极星：数据可信（作者、时间、媒体、链接正确）＋ 检索可用（中文任意子串、英文前缀）＋ 迁移与备份可验证。
- 明确不做：读取浏览器 cookie / 调用 X 写接口 / 无人值守高频抓取 / 上传数据到云端。

### A2. 📝 Active Handoff Status

**✅ Milestones Achieved**

- M1（2026-10-21）：完成全面审查与数据取证，定位采集器把 `User` 对象当推文、作者/媒体/时间丢失、CJK 检索失效等 P0 问题。
- M2：采集器 v2.0.0；导入器 GraphQL/时间/媒体归一化；连接关闭；CJK FTS；Schema v0→v7；备份保留；CLI stats/prune/forget；安装器收紧；测试/CI/文档；提交 `5f25334`。
- M3：支持 X History 路由 `/i/history` 与 `/i/history/likes`，保留旧路由；采集器 v2.1.0；提交 `a2b4a84`。
- M4：修复“开始抓取清空首屏”导致 11 屏 0、导出缺 26 条、`newest_id` 偏移；采集器 v2.2.0 / package 0.2.2；新增 `x-archive inspect`；提交 `477d9d2` 并推送。
- M5：真实库迁移 v0→v7，清理 1,189 条假记录与测试账号；当前 2,508 条推文、14.2 MB、`verify` 三项 ok。

**🚧 Work In Progress**

- `scripts/x-archive-sync.user.js` v2.2.0 尚未在真实浏览器会话中跑完整导出；用户需更新 Violentmonkey 后重跑。
- `data/archive.sqlite3` 中 2,508 条真实推文的作者/媒体类型/URL 仍为 `unknown`，需重新导出才能修复。

**🧱 Active Blockers**

- 用户侧动作：用 v2.2.0 重新导出 `/i/history` 与 `/i/history/likes`；否则作者/链接缺口无法本地恢复。
- CI：`.github/workflows/ci.yml` 已配置，但本次 push 后尚未观察到 GitHub Actions 运行结果（`[inferred]`，证据不足）。

**🗂️ Latest Daily Review**

- `docs/daily__pipeline_reviews/2026-10-21.md`（2026-10-21，首次建立）。

**🚀 Next Prompt Recommendations**

1. “把 v2.2.0 重新导出的 `bookmarks_*.json` / `likes_*.json` 放进 `inbox/`，先运行 `uv run x-archive inspect <file>`，确认 `empty_text=0`、`unknown_author=0`、`declared.newest_id == actual.newest_id`，再运行 `scripts/sync.ps1`。”
2. “如果 `inspect` 仍报 `unknown_author` 或 `empty_text`，贴出 `inspect` 输出与日志中的 `接受端点` / `忽略端点` 行，检查 X 是否改用了新的 GraphQL 操作名。”
3. “若要发布，先补真实浏览器 E2E（Playwright + 专用测试账号）与 `mypy`/coverage 门禁；不要修改 `README.md` 的产品定位。”

### A3. 🔍 Quality & Gap Analysis

- 优势：零运行时依赖；38 pytest + Node 行为测试；Schema 迁移、备份与校验闭环；隐私边界清晰；CLI 覆盖导入/检索/统计/清理/体检。
- 缺口：真实浏览器 E2E 缺失；作者恢复依赖用户重导出；CI 运行证据未观察；无 `mypy`/覆盖率门禁；只有本机备份；媒体只存 URL，不下载（有意为之）。
- 技术债务见 B4。

### A4. 📊 Skill Dashboard

| Skill 名称 | 累计触发 | 用户满意 | 用户纠正 | 效用评分 |
|---|---|---|---|---|
| project-save | 1 | 0 | 0 | ⭐⭐⭐（待确认） |
| gov-doc-refine | 0 | 0 | 0 | — |
| mpa-thesis-review | 0 | 0 | 0 | — |
| mpa-thesis-writing | 0 | 0 | 0 | — |
| my-deep-research | 0 | 0 | 0 | — |
| cherry-browser | 0 | 0 | 0 | — |
| cherry-tool-guide | 0 | 0 | 0 | — |

### A5. 🧪 Experiment Log

| 时间 | Skill | 尝试 | 结果 | 尝试前评分 | 尝试后评分 | 保留? |
|---|---|---|---|---|---|---|
| — | n/a | FTS `unicode61` 直接索引中文 | `价值投资` 0 条；库 15.0 MB | N/A | N/A | discard |
| — | n/a | FTS `trigram` | 2 字中文查询不支持 | N/A | N/A | discard |
| — | n/a | CJK 逐字 + 短语 + contentless FTS | 中文子串可用；库 14.2 MB | N/A | N/A | keep |
| — | n/a | 开始抓取时清空采集器 | 首屏 26 条丢失；11 屏 0；导出 54/80 | N/A | N/A | discard |
| — | n/a | 保留首屏 + 按页面类型归属 | 首屏保留；书签/点赞不互串 | N/A | N/A | keep |
| — | n/a | 备份保留 WAL | 备份旁残留 `-wal/-shm` | N/A | N/A | discard |
| — | n/a | 备份落盘后 `journal_mode=DELETE` | 备份自包含、可立即删除 | N/A | N/A | keep |

## Zone B — Cumulative Knowledge Base

### B1. 🧠 Decision Ledger

- **[DEC-001] 保持零运行时依赖** | Session: S-20261021-1607 | 2026-10-21
  - 🔍 Context：项目是长期本地归档工具，依赖越少越易维护、越不易被供应链影响。
  - ✅ Decision：运行时只用 Python 标准库（`sqlite3`、`argparse`、`json`、`hashlib` 等）；开发依赖仅 pytest/ruff。
  - ❌ Alternatives：引入 ORM、Click、Pydantic；会增加升级与兼容成本。
  - 📌 Status: `Active`

- **[DEC-002] 中文检索采用 CJK 逐字索引 + 短语查询** | Session: S-20261021-1607 | 2026-10-21
  - 🔍 Context：`unicode61` 把连续中文当一个词，`价值投资` 无法命中；归档以中文为主。
  - ✅ Decision：索引前在每个 CJK 字符两侧插空格，查询时用短语（如 `"价 值 投 资"`）保证相邻与顺序；ASCII 用前缀 `"term"*`。
  - ❌ Alternatives：`trigram`（2 字查询不支持）、jieba 预分词（增加依赖且不支持任意子串）。
  - 📌 Status: `Active`

- **[DEC-003] FTS 使用 contentless 表 + 稳定整型主键** | Session: S-20261021-1607 | 2026-10-21
  - 🔍 Context：contentful FTS 复制正文，且 `tweets` 的 TEXT 主键在 VACUUM 后 rowid 可能变化，不能安全用作 FTS rowid。
  - ✅ Decision：`tweets` 增加 `pk INTEGER PRIMARY KEY`，FTS 使用 `content=''` 并以 `pk` 作为 rowid；迁移时重建表并重建索引。
  - ❌ Alternatives：保留 contentful FTS（体积大）；用 `tweets.rowid`（VACUUM 不安全）；用 `tweet_id` 文本（FTS rowid 必须是整数）。
  - 📌 Status: `Active`

- **[DEC-004] 同时支持 History 新路由与旧路由** | Session: S-20261021-1607 | 2026-10-21
  - 🔍 Context：X 已把书签入口改为 History；Web 端部分账号仍保留 `/i/bookmarks`。
  - ✅ Decision：识别 `/i/history`（bookmark）、`/i/history/likes`（like）、`/i/history/bookmarks`（bookmark）；保留 `/i/bookmarks*` 与 `/<handle>/likes`；Videos/Articles 明确忽略。
  - ❌ Alternatives：只支持新路由（破坏旧账号）；用 `/i/*` 全匹配（会把无关页面纳入）。
  - 📌 Status: `Active`

- **[DEC-005] 保留预加载首屏，并按页面类型维护成员关系** | Session: S-20261021-1607 | 2026-10-21
  - 🔍 Context：页面打开时 X 已加载第一页；开始抓取时清空会丢掉这批数据，且 Bookmarks/Likes 切换会互串。
  - ✅ Decision：`startSync()` 不清空采集器；每条推文记录 `_types` 集合；导出时按当前类型过滤并剔除内部字段；同一推文可同时属于书签和点赞。
  - ❌ Alternatives：开始清空（丢首屏）；切换页面时清空全部（丢新页面预加载）；只按 ID 去重不记类型（互串）。
  - 📌 Status: `Active`

- **[DEC-006] 备份落盘后切回 DELETE 日志模式** | Session: S-20261021-1607 | 2026-10-21
  - 🔍 Context：源库为 WAL，备份会继承 WAL 头；目标连接未关闭时残留 `-wal/-shm`。
  - ✅ Decision：目标连接用 `closing()` 显式关闭；备份完成后执行 `PRAGMA journal_mode=DELETE`，使备份自包含。
  - ❌ Alternatives：保留 WAL（备份不自包含）；只用 `wal_checkpoint`（仍有残留风险）。
  - 📌 Status: `Active`

- **[DEC-007] Schema 使用 `user_version` 迁移，而不是一次性建表** | Session: S-20261021-1607 | 2026-10-21
  - 🔍 Context：已有 v0 数据库需要原地升级，未来还会加列/改索引。
  - ✅ Decision：`SCHEMA` 保持 v0 基线，`migrate()` 按 `PRAGMA user_version` 逐版本执行；迁移后自动 FTS optimize + VACUUM。
  - ❌ Alternatives：删库重建（丢失历史）；`CREATE TABLE IF NOT EXISTS` 直接加列（无法演进）。
  - 📌 Status: `Active`

- **[DEC-008] 导入时记录元数据与逐条错误** | Session: S-20261021-1607 | 2026-10-21
  - 🔍 Context：旧导入只返回计数，无法定位坏记录，也无法核对导出声明。
  - ✅ Decision：`import_runs` 记录 `account`、`entry_type`、`exported_at`、`newest_id`、`total_tweets`、`source_sha256`；`import_errors` 记录 `record_index`、`reason`、`snippet`；`ImportStats` 返回前 5 条错误样本。
  - ❌ Alternatives：只打印总数（无法排错）；把错误写日志文件（不便查询）。
  - 📌 Status: `Active`

- **[DEC-009] 破坏性维护只走 CLI** | Session: S-20261021-1607 | 2026-10-21
  - 🔍 Context：本 Session 用裸 SQL 清理 e2e 数据，因 SQLite 默认 `foreign_keys=OFF` 造成 4 条外键悬挂并误删真实记录。
  - ✅ Decision：删除账号/空记录/孤儿推文只用 `x-archive forget` / `x-archive prune`；CLI 内部 `foreign_keys=ON` 并有级联。
  - ❌ Alternatives：裸 `DELETE`（已证明危险）；手写清理脚本（易漏级联）。
  - 📌 Status: `Active`

- **[DEC-010] project-save 不覆盖产品 README** | Session: S-20261021-1607 | 2026-10-21
  - 🔍 Context：用户明确要求保留现有 `README.md`，不生成 project-save 的 ReadMe。
  - ✅ Decision：本次 save 只写 `Handover Book.md`、日复盘与 `docs/project-state/RESUME.md`；README 契约检查在临时镜像执行，真实 README 不改写。
  - ❌ Alternatives：生成 `ReadMe.md`（Windows 大小写不敏感，会覆盖 README）；改名另存（偏离用户意图）。
  - 📌 Status: `Active`

### B2. 🎨 Style DNA

- `[S-20261021]` 用户使用中文，偏好直接结论 + 可核对证据，不要空泛总结。
- `[S-20261021]` 用户会追问“有没有测试实际效果”，不接受只凭代码推断的“已完成”。
- `[S-20261021]` 用户会提供真实运行日志，期望 Agent 从日志定位根因，而不是泛泛而谈。
- `[S-20261021]` 用户要求把成果推送到 `https://github.com/sanfy008/twitter-bookmarks.git`，并关注提交是否成功。
- `[S-20261021]` 用户明确要求 project-save 保留现有 `README.md`，不生成/覆盖。
- `[S-20261021]` 用户授权“自行判断，然后执行优化”，但破坏性操作仍需有备份与可验证的恢复路径。

### B3. ❌ Failed Attempts Archive

- **[FAIL-001] History 路由遗漏** | Session: S-20261021-1607 | 2026-10-21
  - 🔧 触发条件：用户实际使用 `/i/history` 与 `/i/history/likes`，而脚本只匹配 `/i/bookmarks*` 与 `/*/likes*`。
  - 💥 错误表现：脚本在新页面完全不注入；`/i/history/likes` 即使被 `/*/likes*` 命中，`getPageType()` 也返回 `null`。
  - 💡 根因分析：以旧路由为默认假设，未先核对用户真实 URL；页面类型判断只覆盖旧路径。
  - ✅ 纠正措施：userscript v2.1.0 增加 History 路由与账号识别；Node 行为测试覆盖 `/i/history`、`/i/history/likes`、`/i/history/videos`、`/i/history/articles`。

- **[FAIL-002] 开始抓取清空首屏** | Session: S-20261021-1607 | 2026-10-21
  - 🔧 触发条件：页面打开后 X 先加载第一页（26 条），用户随后点击“开始抓取”。
  - 💥 错误表现：`startSync()` 的 `tweetCollector.clear()` 丢掉 26 条；前 11 屏显示 0；最终导出 54 = 25 + 29；`newest_id` 取到第二页。
  - 💡 根因分析：为避免重复导出而在开始清空，未考虑“首屏在开始前已被捕获且不会重新请求”。
  - ✅ 纠正措施：v2.2.0 移除清空；按页面类型维护成员关系；`startSync` 行为测试断言采集器不被清空；`newest_id` 用 `BigInt` 最大值。

- **[FAIL-003] 裸 SQL 清理导致外键悬挂与误删** | Session: S-20261021-1607 | 2026-10-21
  - 🔧 触发条件：为清理 e2e 测试数据，直接用 `sqlite3.connect()` 执行 `DELETE FROM tweets`。
  - 💥 错误表现：`verify` 报 `foreign_keys: 4 violation(s)`；同时删除了一条原本存在的真实推文。
  - 💡 根因分析：Python `sqlite3` 默认 `foreign_keys=OFF`，未触发 `ON DELETE CASCADE`；绕过 CLI 也绕过了既有保护。
  - ✅ 纠正措施：从 `backups/x-archive-20261021-150015.sqlite3` 恢复并重跑 `init → prune → forget → verify`；DEC-009 固化“破坏性维护只走 CLI”。

### B4. 🏗️ Technical Debt Register

- **[DEBT-001] 2,508 条历史推文作者/媒体类型/URL 缺失** | Introduced: S-20261021-1607 | Status: `Open`
  - 📍 Location: `data/archive.sqlite3`（私有，Git 忽略）
  - ⚡ Impact: High
  - 💡 Suggested Fix: 用 userscript v2.2.0 重新导出并导入；旧 JSON 已丢失作者，无法本地恢复。

- **[DEBT-002] 无真实浏览器 E2E** | Introduced: S-20261021-1607 | Status: `Open`
  - 📍 Location: `scripts/check-userscript.mjs`
  - ⚡ Impact: Medium
  - 💡 Suggested Fix: Playwright + 专用测试账号，覆盖 401/429、分页等待、首屏保留、Bookmarks/Likes 切换。

- **[DEBT-003] 无 mypy/覆盖率门禁** | Introduced: S-20261021-1607 | Status: `Open`
  - 📍 Location: `.github/workflows/ci.yml`、`pyproject.toml`
  - ⚡ Impact: Low/Medium
  - 💡 Suggested Fix: 增加 `mypy` 严格检查与 `pytest-cov` 阈值；先修 `sqlite3.Row` 与私有函数类型。

- **[DEBT-004] GraphQL 端点白名单是硬编码** | Introduced: S-20261021-1607 | Status: `Open`
  - 📍 Location: `scripts/x-archive-sync.user.js` 的 `ENDPOINTS_BY_TYPE`
  - ⚡ Impact: Medium
  - 💡 Suggested Fix: 已加 `接受端点/忽略端点` 日志；若 X 改名，按日志补充别名并加测试。

- **[DEBT-005] 只有本机备份** | Introduced: S-20261021-1607 | Status: `Open`
  - 📍 Location: `backups/`（Git 忽略）
  - ⚡ Impact: Medium
  - 💡 Suggested Fix: 增加异地/离线备份（加密后放到用户指定目录或对象存储）。

- **[DEBT-006] `tweet_media.local_path` 为空置字段** | Introduced: S-20261021-1607 | Status: `Open`
  - 📍 Location: `src/x_local_archive/db.py`
  - ⚡ Impact: Low（有意不下载媒体）
  - 💡 Suggested Fix: 保留字段并在文档中说明；如未来实现下载，需单独的权限与存储设计。

- **[DEBT-007] 安装器启动本地 HTTP 服务** | Introduced: S-20261021-1607 | Status: `Open`
  - 📍 Location: `scripts/install_userscript.py`
  - ⚡ Impact: Low
  - 💡 Suggested Fix: 已限制为单文件、随机端口、Host 校验；可进一步改为直接打开本地文件或加一次性 token。

- **[DEBT-008] CI 运行结果未观察** | Introduced: S-20261021-1607 | Status: `Open`
  - 📍 Location: `.github/workflows/ci.yml`
  - ⚡ Impact: Low
  - 💡 Suggested Fix: 打开 GitHub Actions 确认 Ubuntu/Windows 两条流水线首次运行结果。

- **[DEBT-009] 旧 `import_runs` 记录元数据为空** | Introduced: S-20261021-1607 | Status: `Open`
  - 📍 Location: `data/archive.sqlite3` 的 `import_runs`
  - ⚡ Impact: Low
  - 💡 Suggested Fix: 历史行无法补齐；新导入已写入 `account/entry_type/exported_at/newest_id/total_tweets/source_sha256`。

## Zone C — Session Archive

### Session Snapshot: S-20261021-1607 | v1.0 | 2026-10-21 16:07

**Session Summary**: 完成 X Local Archive 的全面审查、数据取证与三轮修复；采集器从 v2.0.0 迭代到 v2.2.0，Python 包从 0.1.0 到 0.2.2；真实库迁移到 schema v7 并清理 1,189 条假记录；三次提交已推送到 `sanfy008/twitter-bookmarks`。最终本地验证为 38 pytest passed、Node 行为检查 passed、`x-archive verify` 三项 ok。

**Delta from Previous Save (增量变化)**:

- 📁 New files（本次存档新增）：`Handover Book.md`、`docs/daily__pipeline_reviews/_TEMPLATE.md`、`docs/daily__pipeline_reviews/2026-10-21.md`、`docs/project-state/RESUME.md`。
- ✏️ Modified files（本 Session 代码变更，已提交）：`src/x_local_archive/db.py`、`cli.py`、`inspect.py`、`scripts/x-archive-sync.user.js`、`scripts/check-userscript.mjs`、`scripts/install_userscript.py`、`scripts/*.ps1`、`tests/*`、`README.md`（产品文档，已在 `5f25334` 更新；本次 save 不再改写）、`CANDIDATE_AUDIT.md`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`。
- 🗑️ Deleted files：无（Git 层面）。
- 🔑 Key changes：采集器严格识别 Tweet、作者/媒体/时间修复、History 路由、首屏保留、按类型归属、40s 触底、`inspect` 命令；导入器迁移/索引/中文检索/备份收紧。

**Decisions Made This Session**: DEC-001、DEC-002、DEC-003、DEC-004、DEC-005、DEC-006、DEC-007、DEC-008、DEC-009、DEC-010。

**Failed Attempts This Session**: FAIL-001、FAIL-002、FAIL-003。

**Pending FAIL Items**: 无（首次存档；三条 FAIL 已直接归档到 B3）。

**Structured Retention（正向结构化保留）**:

- **Decisions**: 见 DEC-001..DEC-010；核心是零依赖、CJK 逐字短语检索、contentless FTS + 整型主键、History+旧路由兼容、保留首屏并按类型归属、备份 DELETE 模式、`user_version` 迁移、导入元数据/错误、破坏性维护只走 CLI、README 不改写。
- **Constraints**: 用户要求保留 `README.md`；不读 cookie/不调用 X 写接口；采集为手动、低频、可停止；Python 3.12 + uv；Windows PowerShell 5.1；SQLite FTS5；GitHub 仓库 `sanfy008/twitter-bookmarks`；`data/`、`backups/`、`inbox/` 私有且 Git 忽略。
- **Verified Facts**: `pytest` 38 passed；`node scripts/check-userscript.mjs` passed；`x-archive verify` 为 `integrity/foreign_keys/fts = ok`；`data/archive.sqlite3` 为 schema 7、2,508 tweets、2,171 bookmarks、804 likes、1,946 media、14,188,544 bytes；`master` 与 `origin/master` 均在 `477d9d2`；迁移前备份 `backups/x-archive-20261021-150015.sqlite3` 可恢复且已用于修复。
- **Files & Paths**: `src/x_local_archive/{db.py,cli.py,inspect.py}`；`scripts/x-archive-sync.user.js`；`scripts/check-userscript.mjs`；`tests/{test_archive,test_cli,test_migration,test_normalize,test_pipeline,test_search}.py`；`docs/daily__pipeline_reviews/2026-10-21.md`；`docs/project-state/RESUME.md`；`backups/x-archive-20261021-150015.sqlite3`。
- **Reusable Commands**: `uv run pytest`；`node scripts/check-userscript.mjs`；`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1`；`uv run x-archive stats`；`uv run x-archive verify`；`uv run x-archive inspect <export.json>`；`uv run x-archive prune --dry-run`；`uv run x-archive forget --account <name>`；`git log --oneline -5`。
- **Interface Contracts**: CLI `x-archive init|import|search|backup|verify|stats|prune|forget|inspect`，全局 `--database` 与 `X_ARCHIVE_DB`；Schema v7；FTS contentless + `pk` rowid；导出 JSON 字段 `account/type/exported_at/newest_id/oldest_id/total_tweets/tweets[]`，tweet 字段 `id/author_username/author_name/text/created_at/url/media[]`；History 路由 `/i/history`（bookmark）、`/i/history/likes`（like）、`/i/history/bookmarks`（bookmark）；GraphQL 端点 `Bookmarks`、`BookmarkFolderTimeline`、`Likes`、`UserLikes`；备份命名 `x-archive-YYYYMMDD-HHMMSS.sqlite3`。
- **Rejected Approaches**: FTS `unicode61` 直索引（CJK 不可用）；`trigram`（2 字不支持）；jieba（依赖 + 非任意子串）；contentful FTS（体积大）；开始清空采集器（丢首屏）；`newest_id=allTweets[0]`（插入顺序错误）；裸 SQL 删除（FK 悬挂）；安装器暴露项目根目录（安全问题）。
- **Test Results**: Windows + Python 3.12 + SQLite 3.45.3 + PowerShell 5.1 + Node v22.13.0；38 pytest passed；Node 行为检查 passed；ruff check/format passed；`x-archive verify` 三项 ok。真实浏览器 E2E 未执行（`未执行/待用户确认`）；GitHub Actions 运行结果未观察（`[inferred]`）。`validate_closure.py`：临时镜像 **37 passed / 0 failures**；真实工作区仅 3 项 ReadMe 契约失败（README 保留例外）。
- **Open Issues**: 2,508 条历史推文作者/媒体类型/URL 仍为 `unknown`；CI 未观察；无真实浏览器 E2E；仅本机备份；旧 `import_runs` 元数据为空；GraphQL 端点白名单需随 X 变更维护。
- **Next Actions**: 1) 用 v2.2.0 重新导出并 `inspect`；2) 放入 `inbox/` 后 `sync.ps1`；3) `verify` 与 `stats` 复核；4) 打开 GitHub Actions 确认 CI；5) 规划真实浏览器 E2E 与异地备份。

**Cognitive State at Close (会话关闭时的思维状态)**:

- 已确认“11 屏空档”不是滚动速度问题，而是开始抓取清空首屏 + 分页延迟共同造成；修复已落到 v2.2.0 与测试。
- 仍有一个未闭环的外部依赖：用户必须用新版采集器重新导出，才能补齐作者/链接；本地无法恢复。
- 对“真实效果”的判断保持分层：本地静态/运行时验证已过，真实浏览器会话与大归档长跑仍是 `未执行/待用户确认`。

**Context Window Highlights (上下文要点)**:

- 用户先要求“全面审查 + 优化建议”，随后要求“自行判断并执行优化”，再要求推送 GitHub。
- 用户指出实际地址是 `/i/history` 与 `/i/history/likes`，推翻旧路由假设。
- 用户提供真实运行日志，暴露“开始抓取清空首屏”回归；Agent 据此定位 26 条丢失与 `newest_id` 偏移。
- 用户明确要求本次 project-save **不要生成 README**，保留现有 README。

**Session Reflect Report**:

- **R1 — 成功模式**：以证据驱动的审查（数据库统计、旧导出取证、Node 新旧逻辑对照、迁移先在副本验证）显著提升了定位质量；测试门禁（38 pytest + Node + PowerShell + `verify`）让每轮修复都有可复核结果。
- **R2 — 边界案例**：① 旧路由假设导致 History 页面完全漏抓；② 为避免重复导出而清空采集器，反而丢掉首屏；③ 为清 e2e 数据绕过 CLI 用裸 SQL，触发 FK 悬挂并误删真实记录；④ project-save 默认要求 ReadMe，但用户明确禁止改写 README，需在“遵循 Skill”与“遵循用户”之间选择后者，并用临时镜像完成结构校验。
- **R3 — 改进信号**：

| 规则 | 本 Session 是否应触发 | 是否实际执行 |
|---|---|---|
| A1 先述计划 | Y | Y |
| A4 先问后做 | Y | N（裸 SQL 清理与备份恢复未先确认） |
| B1 强制核查 | Y | Y |

- 说明：工作区无 `AGENTS.md`/`GEMINI.md`，以上按 project-save Skill 内置规则自评。改进方向：破坏性操作先备份、先说明、优先走 CLI；采集器类改动先核对真实 URL/端点日志。

**Compact File Tree Snapshot (精简文件树)**:

```text
12-Twitter_Bookmarks/
├── README.md                         # 产品说明（本次 save 保留，不改写）
├── CANDIDATE_AUDIT.md                # 第三方导出器审计
├── CHANGELOG.md                      # 0.2.0 → 0.2.2 变更
├── LICENSE                           # MIT
├── pyproject.toml                    # 包元数据 / ruff / pytest
├── uv.lock
├── .github/workflows/ci.yml          # Ubuntu + Windows CI
├── .gitattributes / .gitignore
├── Handover Book.md                  # 本文件（project-save 存档）
├── docs/
│   ├── daily__pipeline_reviews/
│   │   ├── _TEMPLATE.md
│   │   └── 2026-10-21.md
│   └── project-state/
│       └── RESUME.md
├── src/x_local_archive/
│   ├── __init__.py                   # 0.2.2
│   ├── cli.py                        # init/import/search/backup/verify/stats/prune/forget/inspect
│   ├── db.py                         # schema/migrations/import/search/backup/prune
│   ├── inspect.py                    # 导出 JSON 体检
│   └── py.typed
├── scripts/
│   ├── x-archive-sync.user.js        # 采集器 v2.2.0
│   ├── check-userscript.mjs          # Node 行为测试
│   ├── install_userscript.py         # 单文件安装器
│   ├── install-userscript.ps1
│   ├── sync.ps1 / import.ps1 / search.ps1 / backup.ps1 / verify.ps1 / setup.ps1
├── tests/
│   ├── conftest.py
│   ├── test_archive.py
│   ├── test_cli.py
│   ├── test_migration.py
│   ├── test_normalize.py
│   ├── test_pipeline.py
│   ├── test_search.py
│   └── fixtures/sample_export.json
├── data/.gitkeep                     # 私有 DB（Git 忽略）
├── backups/.gitkeep                  # 私有备份（Git 忽略）
└── inbox/{.gitkeep, failed/.gitkeep} # 私有导出（Git 忽略）
```
