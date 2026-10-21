// ==UserScript==
// @name         X/Twitter Bookmarks & Likes Incremental Syncer
// @namespace    https://github.com/x-local-archive/x-local-archive
// @version      2.3.1
// @description  手动触发、低频率地抓取 X 书签/点赞时间线并导出为 JSON，供本地 x-archive 导入。支持 History 新路由与旧书签/点赞路由。
// @author       x-local-archive
// @match        https://x.com/i/history*
// @match        https://x.com/i/bookmarks*
// @match        https://x.com/*/likes*
// @match        https://twitter.com/i/history*
// @match        https://twitter.com/i/bookmarks*
// @match        https://twitter.com/*/likes*
// @grant        none
// @inject-into  page
// @run-at       document-start
// @noframes
// ==/UserScript==

(function () {
    'use strict';

    const VERSION = '2.3.1';
    const SCROLL_INTERVAL_MS = 2000;
    const STALL_LIMIT = 20; // 40s: X bookmark pagination can take 20-30s per page.
    const MAX_LOGS = 200;

    // 只接受与当前页面类型匹配的 GraphQL 端点，避免把主时间线、推文详情、
    // 用户资料等无关数据混进书签/点赞导出。
    const ENDPOINTS_BY_TYPE = {
        bookmark: ['Bookmarks', 'BookmarkFolderTimeline'],
        like: ['Likes', 'UserLikes'],
    };

    const tweetCollector = new Map();
    let isScrolling = false;
    let scrollTimer = null;
    let scrollCount = 0;
    let stallCount = 0;
    let activeContext = null; // {type, account} captured when a run starts
    let currentFolderId = null;

    const config = {
        mode: localStorage.getItem('x_archive_cfg_mode') || 'incremental',
        maxScrolls: parseInt(localStorage.getItem('x_archive_cfg_max_scrolls') || '30', 10),
    };

    const logger = {
        logs: [],
        renderQueued: false,
        add(level, msg) {
            const time = new Date().toTimeString().split(' ')[0];
            this.logs.push({ time, level, msg });
            if (this.logs.length > MAX_LOGS) this.logs.shift();
            console.log(`[X-Archive][${level}] ${msg}`);
            this.render();
        },
        render() {
            const container = document.getElementById('x-archive-log-content');
            if (!container || container.offsetParent === null) return;
            if (this.renderQueued) return;
            this.renderQueued = true;
            requestAnimationFrame(() => {
                this.renderQueued = false;
                const target = document.getElementById('x-archive-log-content');
                if (!target || target.offsetParent === null) return;
                target.innerHTML = this.logs.map(entry => {
                    let color = '#8b98a5';
                    if (entry.level === 'ERROR') color = '#f4212e';
                    else if (entry.level === 'SUCCESS') color = '#00ba7c';
                    else if (entry.level === 'NET') color = '#1d9bf0';
                    else if (entry.level === 'WARN') color = '#ffd400';
                    return `<div style="margin-bottom:3px;word-break:break-all;"><span style="color:#6e767d;">[${entry.time}]</span> <span style="color:${color};font-weight:600;">[${entry.level}]</span> ${escapeHtml(entry.msg)}</div>`;
                }).join('');
                target.scrollTop = target.scrollHeight;
            });
        },
        copyAll() {
            const text = this.logs.map(entry => `[${entry.time}][${entry.level}] ${entry.msg}`).join('\n');
            if (navigator.clipboard) {
                navigator.clipboard.writeText(text).catch(() => {});
            }
        },
    };

    function escapeHtml(value) {
        return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function getPageType() {
        const path = window.location.pathname.toLowerCase().replace(/\/+$/, '');

        // Legacy bookmarks route.
        if (path === '/i/bookmarks' || path.startsWith('/i/bookmarks/')) return 'bookmark';

        // History tab: /i/history defaults to Bookmarks; Likes has its own tab.
        // Videos and Articles are intentionally ignored.
        if (path === '/i/history' || path === '/i/history/bookmarks') return 'bookmark';
        if (path === '/i/history/likes') return 'like';
        if (path.startsWith('/i/history/')) return null;

        // Legacy profile likes route: /<handle>/likes.
        const parts = path.split('/').filter(Boolean);
        if (parts.length >= 2 && parts[0] !== 'i' && parts[1] === 'likes') return 'like';
        return null;
    }

    function getCurrentAccount() {
        const parts = window.location.pathname.split('/').filter(Boolean);
        // Only /<handle>/likes carries the handle in the path. History routes
        // (/i/history, /i/history/likes) do not, so fall back to the profile link.
        if (parts.length >= 2 && parts[0] !== 'i' && parts[1].toLowerCase() === 'likes') {
            return parts[0].replace('@', '').toLowerCase();
        }
        const userLink = document.querySelector('a[data-testid="AppTabBar_Profile_Link"]');
        const href = userLink ? userLink.getAttribute('href') || '' : '';
        const handle = href.replace(/^\//, '').split('/')[0].trim();
        return (handle || 'owner').toLowerCase();
    }

    function endpointName(url) {
        try {
            const path = new URL(url, window.location.href).pathname;
            return path.split('/').filter(Boolean).pop() || '';
        } catch (error) {
            return '';
        }
    }

    function endpointMatchesPage(url, pageType) {
        const name = endpointName(url);
        return (ENDPOINTS_BY_TYPE[pageType] || []).some(endpoint => name === endpoint);
    }

    function toBigInt(value) {
        return /^\d+$/.test(String(value)) ? BigInt(value) : null;
    }

    // 只接受真正的 Tweet 节点。旧版本会把 user_results 里的 User 对象
    // （同样带 rest_id）当成推文，造成大量空文本记录。
    function toInt(value) {
        if (value === null || value === undefined || value === '') return null;
        const number = Number(value);
        return Number.isFinite(number) ? Math.trunc(number) : null;
    }

    function collectEntities(legacy) {
        const source = legacy.entities || {};
        const entities = { hashtags: [], mentions: [], urls: [], symbols: [] };
        for (const item of source.hashtags || []) {
            const text = typeof item === 'string' ? item : item?.text;
            if (text) entities.hashtags.push(text);
        }
        for (const item of source.user_mentions || []) {
            const text = typeof item === 'string' ? item : item?.screen_name;
            if (text) entities.mentions.push(text);
        }
        for (const item of source.urls || []) {
            if (typeof item === 'string') entities.urls.push({ url: item, expanded: null });
            else if (item?.url) entities.urls.push({ url: item.url, expanded: item.expanded_url || null });
        }
        for (const item of source.symbols || []) {
            const text = typeof item === 'string' ? item : item?.text;
            if (text) entities.symbols.push(text);
        }
        return entities;
    }

    function collectMetrics(tweet, legacy) {
        return {
            favorite: toInt(legacy.favorite_count),
            retweet: toInt(legacy.retweet_count),
            reply: toInt(legacy.reply_count),
            quote: toInt(legacy.quote_count),
            bookmark: toInt(legacy.bookmark_count),
            views: toInt(tweet.views?.count ?? legacy.views?.count),
        };
    }

    function collectRelations(legacy) {
        return {
            quoted_id: legacy.quoted_status_id_str || null,
            retweeted_id: legacy.retweeted_status_id_str || null,
            in_reply_to_id: legacy.in_reply_to_status_id_str || null,
            conversation_id: legacy.conversation_id_str || null,
        };
    }

    function collectMedia(legacy) {
        const list = legacy.extended_entities?.media || legacy.entities?.media || [];
        return list
            .filter(item => item && (item.media_url_https || item.media_url))
            .map(item => ({
                url: item.media_url_https || item.media_url,
                type: item.type || 'unknown',
                media_id: item.media_key || item.id_str || null,
                width: toInt(item.original_info?.width),
                height: toInt(item.original_info?.height),
                duration_ms: toInt(item.video_info?.duration_millis),
                alt_text: item.ext_alt_text || null,
                variants: Array.isArray(item.video_info?.variants) ? item.video_info.variants : null,
            }));
    }

    function extractFolderId(url) {
        let parsed = null;
        try {
            parsed = new URL(url, window.location.href);
            const variables = parsed.searchParams.get('variables');
            if (variables) {
                const data = JSON.parse(variables);
                const folderId = data.bookmark_collection_id || data.bookmarkCollectionId;
                if (folderId) return String(folderId);
            }
        } catch (error) {
            // ignore malformed variables
        }
        const pathname = parsed ? parsed.pathname : window.location.pathname;
        const match = pathname.match(/\/i\/bookmarks\/([^/]+)/);
        return match ? decodeURIComponent(match[1]) : null;
    }

    function extractTweetCandidate(node) {
        if (!node || typeof node !== 'object') return null;
        let tweet = node;
        if (node.__typename === 'TweetWithVisibilityResults' && node.tweet) {
            tweet = node.tweet;
        }
        if (tweet.__typename && tweet.__typename !== 'Tweet') return null;
        if (!tweet.legacy && !tweet.core && !tweet.note_tweet) return null;

        const id = tweet.rest_id || tweet.id_str || tweet.id;
        if (!id) return null;
        // Real X tweet ids are numeric. Cards and URL entities can carry
        // id-like values (often a t.co URL); reject them explicitly.
        if (!/^\d+$/.test(String(id))) return null;

        const legacy = tweet.legacy || {};
        const userResult = tweet.core?.user_results?.result || {};
        const userCore = userResult.core || {};
        const userLegacy = userResult.legacy || {};

        const username = userCore.screen_name || userLegacy.screen_name || tweet.author_username || '';
        const authorName = userCore.name || userLegacy.name || tweet.author_name || '';
        const noteText = tweet.note_tweet?.note_tweet_results?.result?.text;
        const text = noteText ?? legacy.full_text ?? legacy.text ?? tweet.text ?? '';
        const createdAt = legacy.created_at ? new Date(legacy.created_at) : null;

        return {
            id: String(id),
            author_username: username || null,
            author_name: authorName,
            author_id: userResult.rest_id || userLegacy.id_str || null,
            author_followers: toInt(userLegacy.followers_count),
            author_verified: Boolean(userLegacy.verified || userResult.is_blue_verified),
            author_avatar: userLegacy.profile_image_url_https || userResult.avatar?.image_url || null,
            text: text,
            created_at: createdAt && !Number.isNaN(createdAt.getTime()) ? createdAt.toISOString() : null,
            url: username ? `https://x.com/${username}/status/${id}` : null,
            lang: legacy.lang || tweet.lang || null,
            source: legacy.source || null,
            entities: collectEntities(legacy),
            metrics: collectMetrics(tweet, legacy),
            relations: collectRelations(legacy),
            media: collectMedia(legacy),
            status: 'available',
        };
    }

    function extractTweetsFromData(root, pageType = getPageType()) {
        const type = pageType || 'unknown';
        let added = 0;
        const stack = [root];
        while (stack.length) {
            const node = stack.pop();
            if (!node || typeof node !== 'object') continue;

            const candidate = extractTweetCandidate(node);
            if (candidate) {
                const existing = tweetCollector.get(candidate.id);
                if (!existing) {
                    tweetCollector.set(candidate.id, { ...candidate, _types: new Set([type]) });
                    added++;
                } else if (!existing._types.has(type)) {
                    // The same post can be both bookmarked and liked.
                    existing._types.add(type);
                    added++;
                }
            }

            for (const key of Object.keys(node)) {
                // legacy/entities/note_tweet 已在 candidate 中处理；user_results 里
                // 全是 User 对象，继续遍历既无意义也容易误判。
                if (key === 'legacy' || key === 'entities' || key === 'note_tweet' || key === 'user_results') continue;
                const child = node[key];
                if (child && typeof child === 'object') stack.push(child);
            }
        }
        return added;
    }

    function handleAuthFailure(status) {
        logger.add('ERROR', `收到 HTTP ${status}，已停止抓取（登录失效或被限流）`);
        if (isScrolling) stopSync(`HTTP ${status}，已停止`);
    }

    function handleNetworkPayload(url, rawText, source) {
        const pageType = getPageType();
        if (!pageType || !endpointMatchesPage(url, pageType)) return;
        if (/BookmarkFolderTimeline/i.test(endpointName(url))) {
            const folderId = extractFolderId(url);
            if (folderId) currentFolderId = folderId;
        }
        if (!rawText || !rawText.trim()) return;

        let data;
        try {
            data = JSON.parse(rawText);
        } catch (error) {
            logger.add('WARN', `解析响应失败: ${error.message}`);
            return;
        }

        const added = extractTweetsFromData(data, pageType);
        if (added > 0) {
            stallCount = 0;
            logger.add('SUCCESS', `[${source}:${endpointName(url)}] +${added} 条，累计 ${collectedCount(pageType)} 条`);
            updateUIStatus();
        }
    }

    function installHooks() {
        const originalOpen = window.XMLHttpRequest.prototype.open;
        window.XMLHttpRequest.prototype.open = function (method, url) {
            this.__xArchiveUrl = String(url || '');
            this.addEventListener('load', () => {
                try {
                    if (this.responseType && this.responseType !== 'text') return;
                    if (this.status === 429 || this.status === 401) {
                        handleAuthFailure(this.status);
                        return;
                    }
                    handleNetworkPayload(this.__xArchiveUrl, this.responseText, 'XHR');
                } catch (error) {
                    logger.add('ERROR', `XHR 处理异常: ${error.message}`);
                }
            });
            return originalOpen.apply(this, arguments);
        };

        const originalFetch = window.fetch;
        window.fetch = async function (...args) {
            const response = await originalFetch.apply(this, args);
            try {
                const rawUrl = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
                const pageType = getPageType();
                if (pageType && rawUrl && endpointMatchesPage(rawUrl, pageType)) {
                    if (response.status === 429 || response.status === 401) {
                        handleAuthFailure(response.status);
                    } else {
                        response.clone().text()
                            .then(text => handleNetworkPayload(rawUrl, text, 'Fetch'))
                            .catch(() => {});
                    }
                }
            } catch (error) {
                // 网络钩子不能影响 X 自身请求。
            }
            return response;
        };

        logger.add('INIT', '网络拦截层就绪（仅处理当前页面对应的端点）');
    }

    function breakpointKey(type, account) {
        return `x_archive_last_${type}_${account}`;
    }

    function getBreakpoint(type, account) {
        return localStorage.getItem(breakpointKey(type, account)) || '';
    }

    function setBreakpoint(type, account, id) {
        localStorage.setItem(breakpointKey(type, account), String(id));
    }

    function currentTweets(type = getPageType()) {
        if (!type) return [];
        return Array.from(tweetCollector.values()).filter(tweet => tweet._types.has(type));
    }

    function collectedCount(type = getPageType()) {
        return currentTweets(type).length;
    }

    function reachedBreakpoint(lastSeenId) {
        const limit = toBigInt(lastSeenId);
        if (limit === null) return false;
        for (const tweet of currentTweets()) {
            const value = toBigInt(tweet.id);
            if (value !== null && value <= limit) return true;
        }
        return false;
    }

    function setupFloatingWidget() {
        if (document.getElementById('x-archive-widget') || !document.body) return;

        const widget = document.createElement('div');
        widget.id = 'x-archive-widget';
        widget.style.cssText = `
            position: fixed; bottom: 24px; right: 24px; z-index: 999999;
            background: rgba(15, 20, 25, 0.95); color: #fff; border: 1px solid #38444d;
            border-radius: 14px; padding: 14px 16px; font-size: 13px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            box-shadow: 0 4px 24px rgba(0,0,0,0.5); display: flex; flex-direction: column;
            gap: 9px; min-width: 280px; backdrop-filter: blur(10px);
        `;

        widget.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="font-weight:700;color:#1d9bf0;">⚡ X 归档助手 v${VERSION}</span>
                <span id="x-archive-type" style="font-size:11px;background:#273340;padding:2px 6px;border-radius:4px;color:#8b98a5;">--</span>
            </div>
            <div id="x-archive-info" style="color:#8b98a5;font-size:12px;line-height:1.5;">
                账号: <b id="x-archive-account" style="color:#fff;">--</b><br>
                已捕获: <b id="x-archive-count" style="color:#fff;font-size:14px;">0</b> 条<br>
                断点: <span id="x-archive-last" style="color:#1d9bf0;font-family:monospace;">未设定</span>
            </div>
            <div style="background:#16181c;padding:6px 8px;border-radius:8px;display:flex;flex-direction:column;gap:6px;font-size:11px;border:1px solid #2f3336;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="color:#8b98a5;">抓取模式:</span>
                    <select id="x-archive-sel-mode" style="background:#202327;color:#fff;border:1px solid #38444d;border-radius:4px;padding:2px 4px;font-size:11px;">
                        <option value="incremental" ${config.mode === 'incremental' ? 'selected' : ''}>⚡ 增量（遇到断点即停）</option>
                        <option value="deep" ${config.mode === 'deep' ? 'selected' : ''}>📚 全量（忽略断点）</option>
                    </select>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="color:#8b98a5;">滚动上限:</span>
                    <select id="x-archive-sel-limit" style="background:#202327;color:#fff;border:1px solid #38444d;border-radius:4px;padding:2px 4px;font-size:11px;">
                        <option value="30" ${config.maxScrolls === 30 ? 'selected' : ''}>30 屏</option>
                        <option value="100" ${config.maxScrolls === 100 ? 'selected' : ''}>100 屏</option>
                        <option value="300" ${config.maxScrolls === 300 ? 'selected' : ''}>300 屏</option>
                        <option value="0" ${config.maxScrolls === 0 ? 'selected' : ''}>无限制</option>
                    </select>
                </div>
            </div>
            <div style="display:flex;gap:6px;">
                <button id="x-archive-btn-sync" style="flex:1;background:#1d9bf0;color:#fff;border:none;border-radius:18px;padding:7px 10px;font-weight:700;cursor:pointer;font-size:12px;">开始抓取</button>
                <button id="x-archive-btn-export" title="导出当前已捕获的数据" style="background:#273340;color:#8b98a5;border:none;border-radius:18px;padding:6px 10px;cursor:pointer;font-size:11px;">导出</button>
                <button id="x-archive-btn-toggle-log" style="background:#273340;color:#8b98a5;border:none;border-radius:18px;padding:6px 10px;cursor:pointer;font-size:11px;">日志</button>
                <button id="x-archive-btn-clear" title="清空当前账号/类型的断点" style="background:#273340;color:#8b98a5;border:none;border-radius:18px;padding:6px 10px;cursor:pointer;font-size:11px;">重置</button>
            </div>
            <div id="x-archive-msg" style="font-size:11px;color:#00ba7c;display:none;line-height:1.3;"></div>
            <div id="x-archive-log-panel" style="display:none;margin-top:8px;border-top:1px solid #38444d;padding-top:8px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">
                    <span style="font-size:11px;color:#6e767d;font-weight:600;">实时调试日志</span>
                    <button id="x-archive-btn-copy-log" style="background:none;border:none;color:#1d9bf0;cursor:pointer;font-size:11px;padding:0;">复制全部</button>
                </div>
                <div id="x-archive-log-content" style="background:#000;color:#8b98a5;font-family:Consolas,monospace;font-size:11px;padding:6px;border-radius:6px;height:150px;overflow-y:auto;line-height:1.3;"></div>
            </div>
        `;

        document.body.appendChild(widget);

        document.getElementById('x-archive-btn-sync').addEventListener('click', toggleSync);
        document.getElementById('x-archive-btn-export').addEventListener('click', exportData);
        document.getElementById('x-archive-btn-clear').addEventListener('click', resetBreakpoint);
        document.getElementById('x-archive-btn-toggle-log').addEventListener('click', toggleLogPanel);
        document.getElementById('x-archive-btn-copy-log').addEventListener('click', () => {
            logger.copyAll();
            showMessage('日志已复制到剪贴板！', '#00ba7c');
        });
        document.getElementById('x-archive-sel-mode').addEventListener('change', event => {
            config.mode = event.target.value;
            localStorage.setItem('x_archive_cfg_mode', config.mode);
            logger.add('INFO', `模式切换为 ${config.mode === 'incremental' ? '增量' : '全量'}`);
        });
        document.getElementById('x-archive-sel-limit').addEventListener('change', event => {
            config.maxScrolls = parseInt(event.target.value, 10);
            localStorage.setItem('x_archive_cfg_max_scrolls', String(config.maxScrolls));
            logger.add('INFO', `滚动上限设为 ${config.maxScrolls === 0 ? '不限' : config.maxScrolls + ' 屏'}`);
        });

        logger.add('INIT', `界面挂载完成（v${VERSION}），模式 ${config.mode}，上限 ${config.maxScrolls} 屏`);
        updateUIStatus();
    }

    function toggleLogPanel() {
        const panel = document.getElementById('x-archive-log-panel');
        if (!panel) return;
        const isHidden = panel.style.display === 'none';
        panel.style.display = isHidden ? 'block' : 'none';
        if (isHidden) logger.render();
    }

    function updateUIStatus() {
        const type = getPageType();
        const account = getCurrentAccount();
        const typeEl = document.getElementById('x-archive-type');
        const accountEl = document.getElementById('x-archive-account');
        const countEl = document.getElementById('x-archive-count');
        const lastEl = document.getElementById('x-archive-last');

        if (typeEl) typeEl.textContent = type === 'like' ? 'Likes' : type === 'bookmark' ? 'Bookmarks' : '--';
        if (accountEl) accountEl.textContent = account;
        if (countEl) countEl.textContent = collectedCount();
        const lastSeen = type ? getBreakpoint(type, account) : '';
        if (lastEl) {
            lastEl.textContent = lastSeen ? lastSeen.slice(-8) + '…' : '未设定';
            lastEl.title = lastSeen || '未记录断点';
        }
    }

    function showMessage(message, color = '#00ba7c') {
        const element = document.getElementById('x-archive-msg');
        if (!element) return;
        element.textContent = message;
        element.style.color = color;
        element.style.display = 'block';
        window.clearTimeout(showMessage.timer);
        showMessage.timer = window.setTimeout(() => {
            element.style.display = 'none';
        }, 8000);
    }

    function resetBreakpoint() {
        const type = getPageType();
        if (!type) return;
        const account = getCurrentAccount();
        localStorage.removeItem(breakpointKey(type, account));
        updateUIStatus();
        logger.add('WARN', `已清空 ${type}/${account} 的断点`);
        showMessage('已重置断点，下次将从头抓取。', '#ffd400');
    }

    function scrollDown() {
        const viewport = window.innerHeight || 900;
        const remaining = document.documentElement.scrollHeight - (window.scrollY + viewport);
        // Traverse a large loaded batch quickly, then approach the bottom gently so
        // X's IntersectionObserver still fires the next-page request.
        const step = remaining > viewport * 2 ? viewport * 1.4 : viewport * 0.8;
        const distance = Math.round(step) + Math.floor(Math.random() * 120);
        window.scrollBy({ top: distance, behavior: 'smooth' });
    }

    function tick() {
        if (!isScrolling) return;
        if (document.hidden) return; // 后台标签页暂停，避免无人值守抓取
        const type = getPageType();
        if (!type) {
            stopSync('已离开书签/点赞页面');
            return;
        }
        const account = getCurrentAccount();

        if (config.mode === 'incremental') {
            const lastSeenId = getBreakpoint(type, account);
            if (lastSeenId && reachedBreakpoint(lastSeenId)) {
                stopSync(`已到达上次断点 ${lastSeenId.slice(-6)}，增量同步完成`);
                return;
            }
        }
        if (config.maxScrolls > 0 && scrollCount >= config.maxScrolls) {
            stopSync(`已达到滚动上限 ${config.maxScrolls} 屏`);
            return;
        }

        const height = document.documentElement.scrollHeight;
        const atBottom = window.innerHeight + window.scrollY >= height - 200;
        if (atBottom) {
            stallCount++;
            if (stallCount === 2) {
                logger.add('WARN', '当前已加载内容已滚到底，等待 X 返回下一页…');
            }
            if (stallCount === 4 || stallCount === 8) {
                logger.add('WARN', '等待下一页响应，执行回弹重试');
                window.scrollBy(0, -350);
                window.setTimeout(() => {
                    window.scrollBy(0, 400);
                    window.dispatchEvent(new Event('scroll'));
                }, 400);
            } else if (stallCount >= STALL_LIMIT) {
                stopSync(`已到达时间线底部，共 ${collectedCount()} 条`);
                return;
            }
            // Do not keep scrolling while the next page is in flight.
            logger.add('INFO', `已滚动 ${scrollCount}${config.maxScrolls > 0 ? '/' + config.maxScrolls : ''} 屏（等待下一页，已捕获 ${collectedCount()} 条）`);
            return;
        }
        stallCount = 0;

        scrollDown();
        scrollCount++;
        logger.add('INFO', `第 ${scrollCount}${config.maxScrolls > 0 ? '/' + config.maxScrolls : ''} 屏，已捕获 ${collectedCount()} 条`);
    }

    function startSync() {
        const type = getPageType();
        if (!type) {
            showMessage('当前页面不是书签或点赞页。', '#f4212e');
            return;
        }

        // Do NOT clear tweetCollector. X loads the first page as soon as the page
        // opens, before the user presses start; clearing it discarded that page
        // and the run appeared stuck at 0 until the second page arrived.
        isScrolling = true;
        scrollCount = 0;
        stallCount = 0;
        currentFolderId = extractFolderId(window.location.href);

        const button = document.getElementById('x-archive-btn-sync');
        if (button) {
            button.textContent = '⏹ 停止';
            button.style.background = '#f4212e';
        }

        const account = getCurrentAccount();
        activeContext = { type, account };
        const lastSeenId = getBreakpoint(type, account);
        const carried = collectedCount(type);
        logger.add('INFO', `开始抓取 ${type}/${account}（${config.mode === 'incremental' ? '增量' : '全量'}，上限 ${config.maxScrolls === 0 ? '不限' : config.maxScrolls + ' 屏'}）${carried ? `；页面预捕获 ${carried} 条，将一并导出` : ''}`);
        if (config.mode === 'incremental' && lastSeenId) {
            logger.add('INFO', `断点守护已启用: ${lastSeenId}`);
        }
        showMessage('正在抓取，可随时点击“停止”导出已捕获数据。', '#1d9bf0');
        updateUIStatus();
        scrollTimer = window.setInterval(tick, SCROLL_INTERVAL_MS);
    }

    function toggleSync() {
        if (isScrolling) {
            stopSync('用户手动停止');
            return;
        }
        startSync();
    }

    function stopCapture() {
        isScrolling = false;
        if (scrollTimer) {
            window.clearInterval(scrollTimer);
            scrollTimer = null;
        }
    }

    function stopSync(reason = '') {
        stopCapture();
        const button = document.getElementById('x-archive-btn-sync');
        if (button) {
            button.textContent = '开始抓取';
            button.style.background = '#1d9bf0';
        }
        if (reason) {
            logger.add('INFO', `停止: ${reason}`);
            showMessage(reason, '#ffd400');
        }
        const type = getPageType() || activeContext?.type;
        if (type && currentTweets(type).length > 0) exportData();
    }

    function exportData() {
        const currentType = getPageType();
        const type = currentType || activeContext?.type;
        if (!type) {
            showMessage('当前页面不是书签或点赞页。', '#f4212e');
            return;
        }
        const account = currentType ? getCurrentAccount() : activeContext?.account || 'owner';
        const collected = currentTweets(type);
        const tweets = collected
            .filter(tweet => /^\d+$/.test(String(tweet.id)))
            .map(({ _types, ...tweet }) => tweet);
        const skipped = collected.length - tweets.length;
        if (skipped > 0) {
            logger.add('WARN', `跳过 ${skipped} 条无效记录（id 不是数字）`);
        }
        if (tweets.length === 0) {
            logger.add('WARN', '没有可导出的数据');
            showMessage('尚未捕获到推文。', '#f4212e');
            return;
        }

        const newest = tweets.reduce((a, b) => ((toBigInt(b.id) ?? 0n) > (toBigInt(a.id) ?? 0n) ? b : a));
        const oldest = tweets.reduce((a, b) => ((toBigInt(b.id) ?? 0n) < (toBigInt(a.id) ?? 0n) ? b : a));
        setBreakpoint(type, account, newest.id);
        updateUIStatus();

        const payload = {
            account,
            type,
            exported_at: new Date().toISOString(),
            newest_id: newest.id,
            oldest_id: oldest.id,
            total_tweets: tweets.length,
            folder_id: currentFolderId,
            folder_name: null,
            tweets,
        };

        const now = new Date();
        const datePart = now.toISOString().slice(0, 10).replace(/-/g, '');
        const timePart = now.toTimeString().slice(0, 8).replace(/:/g, '');
        const filename = `${type}s_${account}_${datePart}-${timePart}.json`;

        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(url);

        logger.add('SUCCESS', `已导出 ${tweets.length} 条（newest=${newest.id}，oldest=${oldest.id}）到 ${filename}`);
        showMessage(`已导出 ${tweets.length} 条到 ${filename}`, '#00ba7c');
    }

    installHooks();

    // Exposed only when the test harness opts in; production pages never see this.
    if (window.__X_ARCHIVE_TEST__) {
        window.__xArchiveTest = {
            extractTweetCandidate,
            extractTweetsFromData,
            collector: tweetCollector,
            reset: () => tweetCollector.clear(),
            getPageType,
            getCurrentAccount,
            endpointMatchesPage,
            extractFolderId,
            currentTweets,
            startSync,
            stopCapture,
        };
    }

    let widgetAttempts = 0;
    function ensureWidget() {
        setupFloatingWidget();
    }
    window.addEventListener('DOMContentLoaded', ensureWidget);
    window.addEventListener('load', ensureWidget);
    const widgetTimer = window.setInterval(() => {
        ensureWidget();
        widgetAttempts++;
        if (document.getElementById('x-archive-widget') || widgetAttempts > 15) {
            window.clearInterval(widgetTimer);
        }
    }, 1000);
})();
