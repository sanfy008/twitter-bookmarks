# Handover Book — X Local Archive

> **ReadMe 例外声明**：历次 project-save 均按用户明确要求，**不生成、不覆盖** 现有 `README.md`（该文件是项目产品文档，保留原样）。因此 project-save 的活性摘要由本文件的 Zone A 与 `docs/daily__pipeline_reviews/2026-10-21.md` 承担；`docs/project-state/RESUME.md` 提供下一会话的一分钟入口。`validate_closure.py` 的 ReadMe 契约检查在临时镜像中执行，真实工作区不改写 README。

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
- M6：借鉴 xarchive/scrollmark/dogsheep/prinsss 的高价值能力，落地采集器 v2.3.0 元数据、Schema v8、搜索过滤、JSON/CSV/MD/HTML 导出、`doctor`、`undo --run`；提交 `09651d0`。
- M7：复查用户 v2.2 导出，定位 104 条 t.co/card 伪记录与 `oldest_id` 污染；采集器 v2.3.1 / package 0.3.1 只接受数字 ID，导出/导入/`inspect` 同步收紧；提交 `5c74af9`。
- M8（2026-10-21 第二轮）：对立性审查发现并修复 6 项缺陷 —— 降级重导覆盖好数据（P0）、导入侧非数字 ID 未校验（P0）、`undo --run` 误删其他批次条目（P0，schema v9 `entry_runs`）、CI 分支名错误导致从未运行、同秒备份互相覆盖、导出默认截断到 1000 条；package 0.4.0，55 pytest 通过。

**🚧 Work In Progress**

- 用户需把 Violentmonkey 更新到 **v2.3.1**，重新导出 `/i/history` 与 `/i/history/likes`；当前 用户 Downloads 中的 `bookmarks_ethan151300_20261021-162308.json` 是 v2.2，含 104 条非数字 ID 且无元数据。
- `data/archive.sqlite3` 中 2,508 条历史推文的作者/媒体类型/URL 仍为 `unknown`，需重新导出才能补齐；新元数据表已就绪，等待导入。
- 媒体下载、标签/笔记/已读 UI、真实浏览器 E2E 尚未实现。
- 修复分支 `fix/import-safety-and-provenance`（提交 `55cf481`）已推送，PR 尚未创建 —— 本机无 `gh`，用户需通过 compare 链接手动创建。

**🧱 Active Blockers**

- 用户侧动作：更新到 v2.3.1 并重跑；否则 104 条伪记录与缺失元数据无法消除。
- 覆盖度不确定：v2.2 文件的 1,098 条有效推文中，997 条已在库、101 条新增，但库内 1,174 条书签不在该文件；无法仅凭文件判断是“已取消书签”还是“运行未到底”。
- CI：`.github/workflows/ci.yml` 原写 `branches: ["main"]`，而仓库默认分支是 `master`，因此五次推送**从未触发过 CI**；已改为 `["master","main"]`，但修正后的首次运行仍需推送后观察（`未执行/待确认`）。

**🗂️ Latest Daily Review**

- `docs/daily__pipeline_reviews/2026-10-21.md`（2026-10-21，第三轮更新）。

**🚀 Next Prompt Recommendations**

0. “用 https://github.com/sanfy008/twitter-bookmarks/compare/master...fix/import-safety-and-provenance?expand=1 创建 PR，正文用 `docs/project-state/PR-body.md`；合并后确认 GitHub Actions 首次运行结果（这是目前唯一没有证据的门禁）。”
1. “把 userscript 更新到 2.3.1，重新导出 `/i/history` 与 `/i/history/likes`，先运行 `uv run x-archive inspect <file>`，确认 `non_numeric_ids=0`、`empty_text=0`、`unknown_author=0`、`declared.newest_id/oldest_id == actual`，再运行 `scripts/sync.ps1`。”
2. “如果 `inspect` 仍报 `unknown_author` 或 `non_numeric_ids`，贴出输出与日志中的 `接受端点`/`忽略端点` 行；不要直接导入 v2.2 的 1,202 条文件。”
3. “若确认 v2.2 文件是完整书签列表（1,174 条差异是取消书签），再决定是否导入；否则先补一次完整 v2.3.1 全量导出。”

### A3. 🔍 Quality & Gap Analysis

- 优势：零运行时依赖；55 pytest + Node 行为测试；Schema v9 元数据模型与来源表；CJK 检索 + 过滤；备份/校验/doctor/undo 闭环；导入具备“不降级”语义；隐私边界清晰。
- 缺口：真实浏览器 E2E 缺失；2,508 条历史作者缺失；v2.2 文件含 104 条伪记录且无元数据；CI 修正后尚未观察到真实运行；无 `mypy`/覆盖率；媒体未下载；标签/笔记/已读 UI 未实现；只有本机备份。
- 技术债务见 B4。

### A4. 📊 Skill Dashboard

| Skill 名称 | 累计触发 | 用户满意 | 用户纠正 | 效用评分 |
|---|---|---|---|---|
| project-save | 3 | 2 | 0 | ⭐⭐⭐⭐（第三次待确认） |
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
| — | n/a | v2.2 复合 ID 校验（id && legacy） | 104 条 t.co/card 伪记录；`oldest_id` 被污染 | N/A | N/A | discard |
| — | n/a | 数字 ID + 导出过滤 + 导入拒绝 URL ID | Node/Python 测试通过；`inspect` 报 `non_numeric_ids=104` | N/A | N/A | keep |
| — | n/a | 扁平推文模型（v0.2） | 无法保存作者资料/实体/指标/关系/文件夹 | N/A | N/A | discard |
| — | n/a | Schema v8 元数据模型 | 作者/实体/指标/关系/文件夹落库；46 tests | N/A | N/A | keep |
| — | n/a | 导出 JSON/CSV/MD/HTML | 四格式测试通过 | N/A | N/A | keep |
| — | n/a | 重新导入时按 `content_hash` 覆盖全部列 | 实测 thinner 记录清空作者/时间/正文/媒体，中文检索失效 | N/A | N/A | discard |
| — | n/a | 只覆盖非空字段 + 显式 media/entities 才替换 | 复现脚本：作者/正文/媒体/实体全保留，`search("价值投资")` 仍命中 | N/A | N/A | keep |
| — | n/a | `undo` 以 `run_id` + `NOT IN` 判孤儿 | 实测删掉其他批次仍在使用的推文 | N/A | N/A | discard |
| — | n/a | `entry_runs` 来源表（schema v9）+ `NOT EXISTS` | 共享条目保留，`entries_removed=0`；55 tests 通过 | N/A | N/A | keep |

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

- **[DEC-011] 推文 ID 只接受纯数字** | Session: S-20261021-1640 | 2026-10-21
  - 🔍 Context：v2.2 导出中 104 条 card/URL 实体的 `id` 是 t.co URL，被当成推文，且污染 `oldest_id`。
  - ✅ Decision：采集器 `extractTweetCandidate` 只接受 `/^\d+$/` 的 ID；导出前过滤非数字；导入拒绝 `://` 型 ID；`inspect` 输出 `non_numeric_ids`。
  - ❌ Alternatives：只靠 `__typename === 'Tweet'`（旧数据可能缺 typename）；在导入后 `prune`（会先写入垃圾）。
  - 📌 Status: `Active`

- **[DEC-012] 采用 Schema v8 元数据模型** | Session: S-20261021-1640 | 2026-10-21
  - 🔍 Context：旧模型只有推文 + 媒体 URL，无法支持作者筛选、指标、线程、文件夹与后续分析。
  - ✅ Decision：新增 `users`、`tweet_entities`、`tweet_metrics`、`bookmark_folders`；`tweets` 增加关系/语言/状态列；`archive_entries` 增加 folder/run/read_status；`tweet_media` 增加媒体元数据。
  - ❌ Alternatives：继续用 `raw_json` 存全部（查询难、无索引）；只在导出 JSON 里保留（无法 SQL 分析）。
  - 📌 Status: `Active`

- **[DEC-013] 导出作为只读投影，不引入新依赖** | Session: S-20261021-1640 | 2026-10-21
  - 🔍 Context：需要 CSV/Markdown/HTML 但不希望引入 pandas/Jinja2 等运行时依赖。
  - ✅ Decision：用标准库 `csv`/`json`/字符串模板实现四种格式；过滤条件与 `search` 一致；`--out` 支持文件或目录。
  - ❌ Alternatives：引入 pandas（重）；只在浏览器端导出（无法处理已入库数据）。
  - 📌 Status: `Active`

- **[DEC-014] doctor/undo 的安全语义** | Session: S-20261021-1640 | 2026-10-21
  - 🔍 Context：需要可诊断、可回滚，但不能误删与其他批次共享的条目。
  - ✅ Decision：`doctor` 只读检查并返回 issues/warnings；`undo --run` 只删除该 run 创建的 `archive_entries` 与因此产生的孤儿推文，共享条目保留。
  - ❌ Alternatives：按时间窗口删除（可能误删）；恢复整库备份（丢失后续导入）。
  - 📌 Status: `Active`

- **[DEC-015] 借鉴功能但保持边界** | Session: S-20261021-1640 | 2026-10-21
  - 🔍 Context：调研了 xarchive/scrollmark/dogsheep/prinsss/karakeep，功能很多，但项目定位是只读、手动、本地优先。
  - ✅ Decision：只借鉴元数据、导出、检索、doctor/undo 等离线能力；不引入 X API/OAuth、cookie 抓取、后台采集、云同步、回复流或重框架。
  - ❌ Alternatives：直接照搬 xarchive 的浏览器扩展/本地服务；引入 Next.js/Meilisearch（偏离零依赖）。
  - 📌 Status: `Active`

- **[DEC-016] 导入采用“不降级”语义：非空值优先** | Session: S-20261021-1730 | 2026-10-21
  - 🔍 Context：`_update_tweet` 无条件 `SET` 全部列；实测 thin 记录（无作者/时间/正文）把已入库的好数据清空，FTS 也写入空文本，中文检索从此失效，且本地无法恢复。
  - ✅ Decision：`author_name/author_id/created_at/url/lang/source` 与四个关系列在新值为空时保留旧值；`text` 为空保留旧文本；`author_username` 为 `unknown`/空时保留旧作者；`fts_text/fts_author` 用**实际生效值**重建。media/entities 只在 payload 显式提供时替换（显式 `[]` 仍清空）。
  - ❌ Alternatives：整行覆盖（已证明丢数据）；跳过 content_hash 未变的记录（挡不住真的变化）；把空值当删除意图（用户无法区分）。
  - 📌 Status: `Active`

- **[DEC-017] 来源信息单独建表 `entry_runs`** | Session: S-20261021-1730 | 2026-10-21
  - 🔍 Context：`archive_entries.run_id` 只在插入行时写入；后一批次复用同一条目时 `ON CONFLICT DO NOTHING` 不更新它，导致 `undo --run` 把另一批次仍在使用的条目当孤儿删除。
  - ✅ Decision：Schema v9 新增 `entry_runs(account_id,tweet_id,entry_type,run_id,first_seen_at,last_seen_at)`；每次导入都写一条声明；undo 只删除无其他 run 声明的条目；孤儿判定统一用 `NOT EXISTS`（`NOT IN` 遇 NULL 静默返回空集）。
  - ❌ Alternatives：冲突时更新 `run_id`（等于丢掉上一批次的归属）；按时间窗口删除（会误删）；恢复整库备份（丢失后续导入）。
  - 📌 Status: `Active`

- **[DEC-018] 导出默认全量，不设隐式上限** | Session: S-20261021-1730 | 2026-10-21
  - 🔍 Context：`export --limit` 默认 1000，而库内 2,508 条；导出是“把归档带走”的手段，静默截断比慢更危险。FTS 搜索本身限制 1..1000。
  - ✅ Decision：`--limit` 默认 `None` 表示全部；有 query 时按 1000 一页循环取全；显式传 `--limit` 仍生效；`list_tweets` 仍保留自身 1..100000 的硬上限。
  - ❌ Alternatives：把默认值改大（仍是隐式上限）；导出时打印警告但照旧截断（用户仍可能漏读）。
  - 📌 Status: `Active`

- **[DEC-019] 备份文件名绑定数据库身份** | Session: S-20261021-1730 | 2026-10-21
  - 🔍 Context：文件名精度只到秒，`sync.ps1` 每次成功导入都备份，实测 4 次调用只剩 1 个文件；轮转还会删掉共享目录中其他数据库的备份。
  - ✅ Decision：命名改为 `x-archive-<源库名>-YYYYMMDD-HHMMSS[-n].sqlite3`，冲突自动加序号；轮转只清理同一 `stem` 的备份；无 stem 的旧命名视为本库，保证历史备份仍被轮转。
  - ❌ Alternatives：加毫秒（仍可能冲突且难读）；不轮转（磁盘无限增长）；按修改时间全局轮转（会删别人的）。
  - 📌 Status: `Active`

- **[DEC-020] 本地门禁全绿不等于安全，回归测试必须覆盖失败场景** | Session: S-20261021-1730 | 2026-10-21
  - 🔍 Context：第二轮声称“46 tests 全绿”，但对立性审查用复现脚本找出 6 项缺陷，全部落在旧测试覆盖之外；其中 3 项会让“重新导出并导入”这条关键路径反而降低数据质量。
  - ✅ Decision：修复每一项都先写复现脚本证明缺陷存在，修复后用同一脚本复验；新增测试针对“thin 记录、非数字 ID、共享条目 undo、重复导入、超 1000 条导出”等失败场景。
  - ❌ Alternatives：只补成功路径测试（本次缺陷正是这样漏掉的）；只靠代码审读下结论（无法证明行为）。
  - 📌 Status: `Active`

### B2. 🎨 Style DNA

- `[S-20261021]` 用户使用中文，偏好直接结论 + 可核对证据，不要空泛总结。
- `[S-20261021]` 用户会追问“有没有测试实际效果”，不接受只凭代码推断的“已完成”。
- `[S-20261021]` 用户会提供真实运行日志，期望 Agent 从日志定位根因，而不是泛泛而谈。
- `[S-20261021]` 用户要求把成果推送到 `https://github.com/sanfy008/twitter-bookmarks.git`，并关注提交是否成功。
- `[S-20261021]` 用户明确要求 project-save 保留现有 `README.md`，不生成/覆盖。
- `[S-20261021]` 用户授权“自行判断，然后执行优化”，但破坏性操作仍需有备份与可验证的恢复路径。

- `[S-20261021-1640]` 用户会把真实导出文件交给 Agent 复查，期望逐条/逐字段分析与明确结论。
- `[S-20261021-1640]` 用户再次强调 project-save 不覆盖 `README.md`；该约束长期有效。
- `[S-20261021-1640]` 用户接受“自行判断并实现”，但要求每一步有测试、可验证、并推送 Git。

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

- **[FAIL-004] t.co/card 对象被当作推文** | Session: S-20261021-1640 | 2026-10-21
  - 🔧 触发条件：v2.2 采集器在书签时间线中遇到 card/URL 实体，对象带 `id`（t.co URL）与 `legacy`。
  - 💥 错误表现：用户导出 1,202 条中 104 条 `id` 为 `https://t.co/...`，无文本/作者/时间；`oldest_id` 被算成 URL。
  - 💡 根因分析：`extractTweetCandidate` 只检查 `id` 与 `legacy/core/note_tweet`，未限制 ID 必须是数字；`exportData` 的 `BigInt` 转换把非数字 ID 变成 0。
  - ✅ 纠正措施：v2.3.1 只接受数字 ID；导出过滤非数字；导入拒绝 URL 型 ID；`inspect` 输出 `non_numeric_ids`；Node/Python 测试覆盖。

- **[FAIL-005] “46 tests 全绿”掩盖了 6 项真实缺陷** | Session: S-20261021-1730 | 2026-10-21
  - 🔧 触发条件：第二轮完成 0.3.1 后，以本地测试全绿作为“数据路径安全”的结论；用户随后要求做一轮对立性审查。
  - 💥 错误表现：复现脚本证明降级重导会清空已入库字段、非数字 ID 可入库、`undo --run` 会删掉其他批次条目、CI 因分支名错误从未运行、同秒备份互相覆盖、导出默认截断到 1000 条。
  - 💡 根因分析：测试只覆盖成功路径（导入有效数据后查询），没有覆盖“坏记录再次到达”“多批次共享条目”“同一秒连续备份”等失败与边界场景；验证被当成结论，而不是被当成待挑战的假设。
  - ✅ 纠正措施：为每项缺陷先写复现脚本再修；新增 5 个失败场景测试（thin 重导、非数字 ID、User 形状、共享条目 undo、超 1000 条导出）；DEC-020 固化“先复现再修、测试覆盖失败场景”。

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
  - ⚡ Impact: Medium（已修正根因：原 `branches: ["main"]` 与 `master` 不匹配，CI 从未触发）
  - 💡 Suggested Fix: 推送后打开 GitHub Actions 确认 Ubuntu/Windows 两条流水线首次真实运行结果；本地门禁通过不能替代 CI 证据。

- **[DEBT-009] 旧 `import_runs` 记录元数据为空** | Introduced: S-20261021-1607 | Status: `Open`
  - 📍 Location: `data/archive.sqlite3` 的 `import_runs`
  - ⚡ Impact: Low
  - 💡 Suggested Fix: 历史行无法补齐；新导入已写入 `account/entry_type/exported_at/newest_id/total_tweets/source_sha256`。

- **[DEBT-010] v2.2 导出未导入，覆盖度不确定** | Introduced: S-20261021-1640 | Status: `Open`
  - 📍 Location: 用户 Downloads 中的 `bookmarks_ethan151300_20261021-162308.json`（私有，Git 忽略）
  - ⚡ Impact: Medium
  - 💡 Suggested Fix: 先用 v2.3.1 全量重导；若确认 v2.2 是完整列表，再过滤 104 条非数字记录后导入。当前 1,174 条库内书签不在该文件，无法判定是取消书签还是未跑到底。

- **[DEBT-011] v2.3.1 真实浏览器 E2E 未执行** | Introduced: S-20261021-1640 | Status: `Open`
  - 📍 Location: `scripts/check-userscript.mjs`
  - ⚡ Impact: Medium
  - 💡 Suggested Fix: Playwright + 专用测试账号，验证数字 ID、history 路由、首屏保留、元数据字段与导出文件。

- **[DEBT-012] 媒体下载未实现** | Introduced: S-20261021-1640 | Status: `Open`
  - 📍 Location: `tweet_media.local_path/sha256/status`
  - ⚡ Impact: Medium（1,946 条媒体 URL 存在 link rot）
  - 💡 Suggested Fix: 可选 `media --download`，按 sha256 去重、限速、可中断；视频可调用 yt-dlp/gallery-dl。

- **[DEBT-013] 标签/笔记/已读 UI 未实现** | Introduced: S-20261021-1640 | Status: `Open`
  - 📍 Location: `archive_entries.read_status` 仅建列
  - ⚡ Impact: Low/Medium
  - 💡 Suggested Fix: 增加 `tags`/`tweet_tags`/`notes` 与 CLI，再考虑本地 UI。

- **[DEBT-014] 导出覆盖度元数据不足** | Introduced: S-20261021-1640 | Status: `Open`
  - 📍 Location: 采集器 payload / `import_runs`
  - ⚡ Impact: Medium
  - 💡 Suggested Fix: 记录 `mode`（full/quick）、`pages`、`completed`、`cursor`/`coverage_note`，让“是否跑到底”可判定。

- **[DEBT-015] PR 创建依赖用户手动操作** | Introduced: S-20261021-1730 | Status: `Open`
  - 📍 Location: 分支 `fix/import-safety-and-provenance`；`docs/project-state/PR-body.md`
  - ⚡ Impact: Low/Medium
  - 💡 Suggested Fix: 本机无 `gh`（GitHub CLI），无法用命令行建 PR；正文已写入 `docs/project-state/PR-body.md`，用 compare 链接手动创建即可。若希望以后自动化，需先安装并 `gh auth login`。

- **[DEBT-016] `_connect_read` 回退到读写连接** | Introduced: S-20261021-1730 | Status: `Open`
  - 📍 Location: `src/x_local_archive/db.py::_connect_read`
  - ⚡ Impact: Low（只读命令在 WAL 边缘情况下会打开读写连接，可能创建 `-wal`/`-shm`）
  - 💡 Suggested Fix: 已是既有行为，仅补了注释说明调用方不能假设文件未被触碰；若要彻底只读，可在 WAL 场景改用 `immutable=1` 或先做 checkpoint。

## Zone C — Session Archive

### Session Snapshot: S-20261021-1730 | v1.2 | 2026-10-21 17:32

**Session Summary**: 用户要求“阅读项目文件后做一轮对立性审查”。Agent 不采信上一轮“46 tests 全绿”的结论，用复现脚本逐条验证，定位 6 项缺陷并全部修复：降级重导覆盖好数据、导入侧非数字 ID 未校验、`undo --run` 误删其他批次条目、CI 因分支名错误从未运行、同秒备份互相覆盖、导出默认截断到 1000 条。Schema v8→v9（`entry_runs` 来源表），package 0.3.1→0.4.0，55 pytest 通过，真实库已迁移；提交 `55cf481` 推送至分支 `fix/import-safety-and-provenance`，PR 因本机无 `gh` 待用户手动创建。

**Delta from Previous Save (增量变化)**:

- 📁 New files：`docs/project-state/PR-body.md`。
- ✏️ Modified files：`src/x_local_archive/{db.py,cli.py,export.py,__init__.py}`、`tests/{test_archive,test_doctor,test_export,test_normalize,test_search}.py`、`CHANGELOG.md`、`pyproject.toml`、`uv.lock`、`.github/workflows/ci.yml`。
- 🗑️ Deleted files：无。
- 🔑 Key changes：导入“不降级”语义、数字 ID + User 形状校验、`entry_runs` 来源表与 undo 语义、备份命名/轮转隔离、导出全量默认、重复导入短路、doctor 备份目录推导。

**Decisions Made This Session**: DEC-016、DEC-017、DEC-018、DEC-019、DEC-020。

**Failed Attempts This Session**: FAIL-005。

**Pending FAIL Items**: 无。

**Structured Retention（正向结构化保留）**:

- **Decisions**: 见 DEC-016..DEC-020；核心是“导入不降级”“来源单独建表”“导出无隐式上限”“备份绑定数据库身份”“先复现再修”。
- **Constraints**: 用户要求保留 `README.md`（本次 save 同样不生成/不覆盖）；不读 cookie/不调用 X 写接口；手动、低频、可停止；Python 3.12 + uv；Windows PowerShell 5.1；SQLite FTS5；GitHub 仓库 `sanfy008/twitter-bookmarks`；`data/`、`backups/`、`inbox/` 私有且 Git 忽略；默认分支为 `master`；本机无 `gh`。
- **Verified Facts**: `pytest` 55 passed；`ruff check` 与 `ruff format --check` 通过（23 files）；`node scripts/check-userscript.mjs` passed；`x-archive verify` 三项 ok；`data/archive.sqlite3` 为 schema 9、2,508 tweets、2,171 bookmarks、804 likes、1,946 media、14,376,960 bytes；迁移前备份 `backups/x-archive-archive-20261021-171044.sqlite3`；`git ls-remote --symref origin HEAD` 证实远端只有 `master`；提交 `55cf481` 已推送到 `origin/fix/import-safety-and-provenance`。
- **Files & Paths**: `src/x_local_archive/{db.py,cli.py,export.py,inspect.py}`；`scripts/x-archive-sync.user.js`；`scripts/check-userscript.mjs`；`tests/{test_archive,test_doctor,test_export,test_normalize,test_search}.py`；`docs/daily__pipeline_reviews/2026-10-21.md`；`docs/project-state/{RESUME.md,PR-body.md}`；`backups/x-archive-archive-20261021-171044.sqlite3`。
- **Reusable Commands**: `uv run pytest`；`uv run ruff check .`；`uv run ruff format --check .`；`node scripts/check-userscript.mjs`；`uv run x-archive init`；`uv run x-archive verify`；`uv run x-archive doctor`；`uv run x-archive backup backups --keep 10`；`uv run x-archive export --format csv --out exports\`；`uv run x-archive undo --run <id>`；`git ls-remote --symref origin HEAD`。
- **Interface Contracts**: CLI 不变（`init|import|search|export|backup|verify|stats|prune|forget|doctor|undo|inspect`）；`export --limit` 默认 `None`（全量）；`ImportStats` 新增 `duplicate_of`；`undo` 结果新增 `entries_kept_shared`；Schema v9 新增 `entry_runs(account_id,tweet_id,entry_type,run_id,first_seen_at,last_seen_at)`；备份命名 `x-archive-<源库名>-YYYYMMDD-HHMMSS[-n].sqlite3`。
- **Rejected Approaches**: 整行覆盖（丢数据）；`undo` 用 `run_id` + `NOT IN`（误删）；导出默认 1000 条（静默截断）；按修改时间全局轮转备份（删别人的）；伪造迁移前的 `entry_runs` 来源。
- **Test Results**: Windows + Python 3.12 + SQLite + PowerShell 5.1 + Node v22.13.0；55 pytest passed；ruff clean；Node 行为检查 passed；`verify` 三项 ok；真实库 v8→v9 迁移后条目数不变。真实浏览器 E2E 未执行（`未执行/待用户确认`）；CI 修正后首跑未观察（`未执行/待用户确认`）；PR 未创建（`未执行/待用户确认`）。
- **Open Issues**: 需用 v2.3.1 重导；2,508 条历史作者仍缺失；v2.2 文件 1,174 条差异无法判定；媒体未下载；标签/笔记/已读 UI 未实现；CI 未观察；无异地备份；PR 待手动创建。
- **Next Actions**: 1) 用 compare 链接创建 PR 并合并；2) 观察 CI 首跑；3) 更新 userscript 到 2.3.1 重导；4) `inspect` 确认后 `sync.ps1`；5) 评估媒体下载与覆盖度元数据。

**Cognitive State at Close (会话关闭时的思维状态)**:

- “本地测试全绿”只证明已写的用例通过，不证明关键路径安全。这 6 项缺陷全部落在旧测试覆盖之外，且 3 项会让“重新导出并导入”这条官方恢复路径反而降低数据质量。
- 来源/血缘信息必须单独建表：塞进主表的 `run_id` 在冲突复用场景下必然失真。
- 修复与验证要成对：每项缺陷都先有复现脚本，修复后用同一脚本复验，否则无法区分“看起来对了”和“真的对了”。

**Context Window Highlights (上下文要点)**:

- 用户先要求“阅读项目文件，掌握今天优化的历程，然后做一轮对立性审查”。
- 审查结论给出 3 个 P0、4 个 P1 与文档层面的 3 处不实；用户逐项要求先修 P0-1/P0-2，再“继续完成你认为必要的优化”。
- 用户要求“测试无误后提交 PR，然后执行 /project-save”，并强调不得生成/覆盖 README。
- 本机无 `gh`，用户选择“给 compare 链接手动创建 PR”。

**Session Reflect Report**:

- **R1 — 成功模式**：坚持用复现脚本而不是代码审读下结论，使每条发现都有可重放的证据；修复后重跑同一脚本，直接证明缺陷消失（例如 `media rows 0 → 1`、`entries_removed 1 → 0`）。迁移真实库前先备份并在副本上试跑，避免了不可逆操作。
- **R2 — 边界案例**：① `undo` 修复涉及语义变化（从“删该 run 创建的”到“删无其他声明的”），需改动 schema 才能正确表达，属于“小 bug 牵出模型缺陷”；② 旧测试用 `"s1"`、`"media-1"` 这类合成 ID，被新的数字校验正确拒绝，属于“测试夹具本身不合规”而非功能回归；③ 真实库旧 entry 无 `run_id`，`entry_runs` 迁移后为空 —— 选择如实为空，不伪造来源。
- **R3 — 改进信号**：

| 规则 | 本 Session 是否应触发 | 是否实际执行 |
|---|---|---|
| A1 先述计划 | Y | Y |
| A4 先问后做 | Y | Y（迁移前备份；PR 方式先询问） |
| B1 强制核查 | Y | Y |

- 说明：改进方向是把“先复现再修”写进常规流程（已固化为 DEC-020），避免下次仍以测试全绿代替安全结论。

**Compact File Tree Snapshot (精简文件树)**:

```text
12-Twitter_Bookmarks/
├── README.md                         # 产品说明（历次 save 均保留，不改写）
├── CANDIDATE_AUDIT.md                # 第三方导出器审计（v2.3.1）
├── CHANGELOG.md                      # 0.4.0 变更
├── LICENSE
├── pyproject.toml                    # 0.4.0
├── uv.lock
├── .github/workflows/ci.yml          # master + main 触发
├── Handover Book.md                  # 本文件
├── Handover Book - Archive.md        # 归档占位（暂无归档快照）
├── docs/
│   ├── daily__pipeline_reviews/{_TEMPLATE.md,2026-10-21.md}
│   └── project-state/{RESUME.md,PR-body.md}
├── src/x_local_archive/
│   ├── __init__.py                   # 0.4.0
│   ├── cli.py                        # export --limit 默认全量
│   ├── db.py                         # schema v9/entry_runs/导入不降级/undo
│   ├── export.py                     # 全量导出
│   ├── inspect.py                    # 导出 JSON 体检
│   └── py.typed
├── scripts/
│   ├── x-archive-sync.user.js        # 采集器 v2.3.1
│   ├── check-userscript.mjs          # Node 行为测试
│   ├── install_userscript.py
│   └── *.ps1
├── tests/                            # 55 pytest
├── data/.gitkeep                     # 私有 DB（Git 忽略）
├── backups/.gitkeep                  # 私有备份（Git 忽略）
└── inbox/{.gitkeep, failed/.gitkeep} # 私有导出（Git 忽略）
```


### Session Snapshot: S-20261021-1640 | v1.1 | 2026-10-21 16:40

**Session Summary**: 在 v0.2.2 基础上落地一轮借鉴优化：采集器 v2.3.0 捕获作者资料、entities、metrics、relations、媒体元数据与文件夹；Schema v8；搜索过滤；JSON/CSV/MD/HTML 导出；`doctor`/`undo`。随后复查用户 v2.2 导出，定位 104 条 t.co/card 伪记录与 `oldest_id` 污染，修复为 v2.3.1 / v0.3.1。真实库迁移 v8，46 pytest + Node 检查通过，提交 `09651d0`、`5c74af9` 已推送。

**Delta from Previous Save (增量变化)**:

- 📁 New files：`src/x_local_archive/export.py`、`tests/test_export.py`、`tests/test_doctor.py`。
- ✏️ Modified files：`src/x_local_archive/{db.py,cli.py,inspect.py}`、`scripts/x-archive-sync.user.js`、`scripts/check-userscript.mjs`、`scripts/search.ps1`、`README.md`、`CHANGELOG.md`、`CANDIDATE_AUDIT.md`、`pyproject.toml`、`uv.lock`、`tests/{test_migration,test_normalize,test_pipeline,test_search}.py`。
- 🗑️ Deleted files：无。
- 🔑 Key changes：元数据模型 v8、四格式导出、doctor/undo、数字 ID 校验、用户 v2.2 导出复查、真实库 v7→v8 迁移。

**Decisions Made This Session**: DEC-011、DEC-012、DEC-013、DEC-014、DEC-015。

**Failed Attempts This Session**: FAIL-004。

**Pending FAIL Items**: 无。

**Structured Retention（正向结构化保留）**:

- **Decisions**: 见 DEC-011..DEC-015；数字 ID 校验、Schema v8 元数据模型、导出只读投影、doctor/undo 安全语义、借鉴但保持边界。
- **Constraints**: 用户要求保留 `README.md`；不读 cookie/不调用 X 写接口；手动、低频、可停止；Python 3.12 + uv；Windows PowerShell 5.1；SQLite FTS5；GitHub 仓库 `sanfy008/twitter-bookmarks`；`data/`、`backups/`、`inbox/` 私有且 Git 忽略；元数据导入需 v2.3.1。
- **Verified Facts**: `pytest` 46 passed；`node scripts/check-userscript.mjs` passed；`x-archive verify` 三项 ok；`data/archive.sqlite3` 为 schema 8、2,508 tweets、2,171 bookmarks、804 likes、1,946 media、14,331,904 bytes；`master` 与 `origin/master` 均在 `5c74af9`；迁移前备份 `backups/x-archive-20261021-163228.sqlite3`；用户 v2.2 文件 1,202 条中 1,098 条有效、104 条非数字 ID、552 作者、608 条带媒体、857 个媒体项；997 条已在库、101 条新增、库内 1,174 条书签不在文件。
- **Files & Paths**: `src/x_local_archive/{db.py,cli.py,inspect.py,export.py}`；`scripts/x-archive-sync.user.js`；`scripts/check-userscript.mjs`；`tests/{test_archive,test_cli,test_doctor,test_export,test_migration,test_normalize,test_pipeline,test_search}.py`；`docs/daily__pipeline_reviews/2026-10-21.md`；`docs/project-state/RESUME.md`；`backups/x-archive-20261021-163228.sqlite3`。
- **Reusable Commands**: `uv run pytest`；`node scripts/check-userscript.mjs`；`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1`；`uv run x-archive stats`；`uv run x-archive verify`；`uv run x-archive inspect <export.json>`；`uv run x-archive search "投资" --author alice --has-media`；`uv run x-archive export --format md --out exports\`；`uv run x-archive doctor`；`uv run x-archive undo --run <id>`；`git log --oneline -5`。
- **Interface Contracts**: CLI `x-archive init|import|search|export|backup|verify|stats|prune|forget|doctor|undo|inspect`，全局 `--database` 与 `X_ARCHIVE_DB`；Schema v8（users/tweet_entities/tweet_metrics/bookmark_folders；tweets author_id/conversation/quoted/retweeted/in_reply/lang/source/status；archive_entries folder_id/run_id/read_status；tweet_media media_id/width/height/duration/alt/variants/sha256/status）；导出 JSON 字段含 `account/type/exported_at/newest_id/oldest_id/total_tweets/folder_id/tweets[]`，tweet 含 `author_id/followers/verified/avatar/entities/metrics/relations/media/status`；History 路由 `/i/history`（bookmark）、`/i/history/likes`（like）、`/i/history/bookmarks`（bookmark）；GraphQL 端点 `Bookmarks`、`BookmarkFolderTimeline`、`Likes`、`UserLikes`；备份命名 `x-archive-YYYYMMDD-HHMMSS.sqlite3`。
- **Rejected Approaches**: 接受非数字 ID（t.co/card 伪记录）；扁平推文模型（无法存元数据）；直接导入 v2.2 文件（104 条错误 + 无元数据）；引入 X API/OAuth、cookie 抓取、后台采集、云同步、重框架；本轮实现媒体下载/标签 UI（范围过大）。
- **Test Results**: Windows + Python 3.12 + SQLite 3.45.3 + PowerShell 5.1 + Node v22.13.0；46 pytest passed；Node 行为检查 passed；ruff check/format passed；`x-archive verify` 三项 ok；真实库 v8 迁移通过。真实浏览器 E2E 未执行（`未执行/待用户确认`）；GitHub Actions 运行结果仍未观察（`[inferred]`）；用户 v2.2 文件已复查但未导入。
- **Open Issues**: 需用 v2.3.1 重导；2,508 条历史作者仍缺失；v2.2 文件 1,174 条差异无法判定；媒体未下载；标签/笔记/已读 UI 未实现；CI 未观察；无异地备份。
- **Next Actions**: 1) 更新到 v2.3.1；2) 重导 `/i/history` 与 `/i/history/likes`；3) `inspect` 确认 `non_numeric_ids=0`、`empty_text=0`、`unknown_author=0`、`declared==actual`；4) `sync.ps1`；5) 评估媒体下载与覆盖度元数据。

**Cognitive State at Close (会话关闭时的思维状态)**:

- v2.2 文件是有价值的诊断样本，但不是可导入的最终产物：104 条 t.co/card 伪记录、无元数据、`oldest_id` 被污染。
- 1,202 与库内 2,171 的差异无法仅凭文件判定；需要 v2.3.1 的完整运行与覆盖度元数据。
- 边界保持：只做离线归档/检索/导出，不引入 X API、cookie、后台采集或云同步。

**Context Window Highlights (上下文要点)**:

- 用户要求调研 GitHub 同类项目，并把有价值的功能落到当前项目。
- 用户随后指定复查 `bookmarks_ethan151300_20261021-162308.json`；Agent 从中定位 104 条伪记录与 `oldest_id` 问题。
- 用户再次要求 project-save，并明确保持 README 不覆盖。

**Session Reflect Report**:

- **R1 — 成功模式**：先用 `inspect` + 逐条字段分析 + 数据库交集/差集，再决定修复点；数字 ID 校验同时修掉采集、导出、导入三个入口；迁移先在副本验证，再备份并迁移真实库。
- **R2 — 边界案例**：① 1,202 与 2,171 的差异无法判定是取消书签还是未跑到底，未强行下结论；② 决定不直接导入 v2.2 文件，避免 104 条错误与无元数据；③ project-save 仍要求 ReadMe，但用户明确禁止覆盖 README，继续用临时镜像验证。
- **R3 — 改进信号**：

| 规则 | 本 Session 是否应触发 | 是否实际执行 |
|---|---|---|
| A1 先述计划 | Y | Y |
| A4 先问后做 | Y | Y（用户已授权；迁移前先备份） |
| B1 强制核查 | Y | Y |

- 说明：工作区无 `AGENTS.md`/`GEMINI.md`，以上按 project-save Skill 内置规则自评。改进方向：导出/采集 payload 增加覆盖度元数据（mode/pages/completed/cursor），避免再次出现“是否跑到底”不可判定。

**Compact File Tree Snapshot (精简文件树)**:

```text
12-Twitter_Bookmarks/
├── README.md                         # 产品说明（本次 save 保留，不改写）
├── CANDIDATE_AUDIT.md                # 第三方导出器审计（v2.3.1）
├── CHANGELOG.md                      # 0.3.0 / 0.3.1 变更
├── LICENSE
├── pyproject.toml                    # 0.3.1
├── uv.lock
├── .github/workflows/ci.yml
├── Handover Book.md                  # 本文件
├── Handover Book - Archive.md        # 归档占位（暂无归档快照）
├── docs/
│   ├── daily__pipeline_reviews/{_TEMPLATE.md,2026-10-21.md}
│   └── project-state/RESUME.md
├── src/x_local_archive/
│   ├── __init__.py                   # 0.3.1
│   ├── cli.py                        # init/import/search/export/backup/verify/stats/prune/forget/doctor/undo/inspect
│   ├── db.py                         # schema v8/migrations/import/search/list/doctor/undo
│   ├── export.py                     # JSON/CSV/MD/HTML
│   ├── inspect.py                    # 导出 JSON 体检
│   └── py.typed
├── scripts/
│   ├── x-archive-sync.user.js        # 采集器 v2.3.1
│   ├── check-userscript.mjs          # Node 行为测试
│   ├── install_userscript.py
│   └── *.ps1
├── tests/
│   ├── conftest.py
│   ├── test_archive.py / test_cli.py / test_doctor.py / test_export.py
│   ├── test_migration.py / test_normalize.py / test_pipeline.py / test_search.py
│   └── fixtures/sample_export.json
├── data/.gitkeep                     # 私有 DB（Git 忽略）
├── backups/.gitkeep                  # 私有备份（Git 忽略）
└── inbox/{.gitkeep, failed/.gitkeep} # 私有导出（Git 忽略）
```

---

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
