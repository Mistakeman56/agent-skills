# 微信/iLink 会话过期：「绑定过一段时间就失效」的真相与排查

适用症状：第三方（妈妈等）**扫码绑定成功、用一阵子后 Hermes 发不出去也收不到**，观感像"绑定失效了、要重扫码"。

## 0. 三种错码，必须分开看（这是本节的核心）

| 错码 | errmsg | 真实含义 | 能否自愈 |
|---|---|---|---|
| `errcode=-14` | `session timeout` | iLink 服务端会话**真过期** | ❌ 必须重新扫码 |
| `ret=-2` | `unknown error`（**或空**） | **stale-session 信号，等同 -14** | ✅ 官方适配器可自愈 |
| `ret=-2` | `rate limited` | 真·限流（时间窗机制） | ✅ 等几分钟 |

上游判定逻辑（`gateway/platforms/weixin.py`）：

```python
def _is_stale_session_ret(ret, errcode, errmsg) -> bool:
    return (ret == -2 or errcode == -2) and (errmsg or "").lower() == "unknown error"

def _is_session_expired(resp, ret, errcode) -> bool:
    return -14 in (ret, errcode) or _is_stale_session_ret(ret, errcode, resp.get("errmsg"))
```

⚠️ 注意匹配条件是 **errmsg 小写后精确等于 `'unknown error'`**。历史上自建中继的日志里出现过 `ret=-2 errcode=None errmsg=`（**空串**）的发送失败，
按上面的实现空串**不**算 stale-session —— 拿不准时不要靠 typo 猜，直接跑 §1 的探活脚本。

## 1. 只读探活：某个 bot 的凭证还活着吗

用 `scripts/ilink_bot_probe.py`（本 skill 自带，见 SKILL.md 的 References）：

```bash
python3 scripts/ilink_bot_probe.py 71195dda53c8@im.example 683b90c609da@im.example
# 不传参数则自动扫描 ~/.hermes/weixin/accounts/*.json
```

判读：

- `ret=None errcode=None` ⇒ ✅ **凭证有效，会话正常**
- `errcode=-14 'session timeout'` ⇒ ❌ 已死，只能重新扫码

脚本要点（自己手写时照抄这个姿势）：走 `ilink/bot/getupdates`，带上磁盘上现存的 `get_updates_buf`，
**把原始响应原样落盘 `/tmp/ilink_probe_<bot_id>.json` 且不推进 sync 游标** —— 这样既拿到结论又不会吞掉待收消息。
请求头需要 `AuthorizationType: ilink_bot_token` + `iLink-App-Id: bot` + `iLink-App-ClientVersion` + 随机 `X-WECHAT-UIN`。

## 2. 实测数据（2026-09-11）

- `71195dda53c8@im.example`（妈妈，2026-05-11 扫的）→ **4 个月后仍然 `ret=None errcode=None`** ✅
  ⇒ **绑定本身是长期有效的，"过一段时间必然失效"这个前提是错的。**
- `683b90c609da@im.example`（更早那个）→ `errcode=-14 session timeout` ❌ 已死。

也就是说：失效是**事件**（会话被服务端掐掉），不是**到期**。而它之所以"看起来必然会失效"，
是因为当时跑的那套中继**没有自愈能力**（见 §3）。

## 3. 病根：自建中继只认 `-14`，`-2` 会永久卡死

`~/.hermes/mom_bot_relay.py`（V3，2026-05-11 上线）轮询循环里只处理了 -14：

```python
ret, errcode = resp.get("ret",0), resp.get("errcode",0)
if ret not in (0,None) or errcode not in (0,None):
    if ret==-14 or errcode==-14:
        logger.error("Session过期，等待重试")
        await asyncio.sleep(30); continue
    await asyncio.sleep(2); continue        # ← ret=-2 掉这里，无限重试
```

后果实录（`~/.hermes/logs/mom_relay.log`）：从 5/12 23:01 起 `发送失败: ret=-2 errcode=None errmsg=`
每 ~40 秒一条、**连刷 3 天**，脚本 5/14 11:35 后彻底停摆。**用户感受到的"绑定失效"就是这么来的。**

上游在 **2026-04-29 `e9b96fd050`** 才把 `ret=-2` 认成 stale-session（本机 v0.20.3 已含，
`_is_stale_session_ret` 在 `weixin.py:118`）。所以：**用官方适配器 = 自动获得这条修复；用自己写的轮询 = 自己背这个 bug。**

## 4. 官方适配器的自愈路径（为什么"现在不会了"）

1. session-expired ⇒ **去掉 `context_token` 重试一次**（iLink 常常直接就发出去了）
2. 仍失败 ⇒ 判定会话过期，**暂停 10 分钟**等对方开口，自动恢复 —— **不用重扫码**
3. typing ticket 过期自动刷新（`09a5548628`）

日志里的标志串：`Session expired; pausing for 10 minutes` / `session expired for <uid>; retrying without context_token`。

## 5. 判断"某个上游修复我本机有没有"

```bash
cd ~/.hermes/hermes-agent
git log -1 --format='%h %ad %s' --date=short <sha>          # 这个 sha 是什么、哪天下的
git merge-base --is-ancestor <sha> HEAD && echo 本地已含 ✅ || echo 本地未含 ❌
git log origin/main --grep='weixin' -i --oneline | head -30 # 找相关 sha
git log origin/main --since=2026-06-01 --oneline -- gateway/platforms/weixin.py
```

`--grep` 找不到就换关键词：`expir` / `token` / `refresh` / `ilink` / `stale`。
**先查本机再下结论** —— 很多"上游修了"的修复其实早就在你现在的版本里了。

## 6. PITFALL：一个 iLink bot 只能有一个 poller

同一个 bot 被两个进程同时 `getupdates` 会**互相抢消息**（不是广播）。因此：

> 每个 profile 的 `.env` 里 `WEIXIN_ACCOUNT_ID` **必须指向该 profile 自己的 bot**。

实测踩到过：`~/.hermes/profiles/mom/.env` 被配成**主账号的 bot**（`<PASSWORD>`）
外加主账号的 `WEIXIN_HOME_CHANNEL` —— 这个 profile 一旦启动就会把assistant的消息抢走。
**改凭证、开 multiplex、或让一个二级 profile 跑起来之前，先逐个 profile 核对它指向哪个 bot：**

```bash
for f in ~/.hermes/.env ~/.hermes/profiles/*/.env; do
  echo "--- $f"; grep -E '^WEIXIN_ACCOUNT_ID|^WEIXIN_HOME_CHANNEL' "$f" 2>/dev/null
done
```

另外：iLink bot 的**身份在扫码那一刻就和扫码人绑死**，所以 bot 的 `user_id` 就是"谁扫的码"，
一眼就能看出这个凭证是谁的 —— 这是最快的归属核对方式。
