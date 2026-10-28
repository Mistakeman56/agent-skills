# 一个 Hermes 接多个微信号：现状、multiplex、以及上游进度

快照日期 **2026-09-11**。这类信息会过期——**用前先按下面的命令重新测一遍**，不要照抄结论。

## 0. 先测本机 vs 上游（3 条命令）

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY CLASH_PROXY
hermes --version                     # 本机版本 + install dir
cd ~/.hermes/hermes-agent
git fetch --all -q
git rev-list --count HEAD..origin/main          # 落后多少个提交
git tag --sort=-creatordate | head -8           # 上游最新发布 tag
git log origin/main --oneline --since='<date>' -- gateway/platforms/weixin.py | head -40
git log origin/main --oneline --since='<date>' --grep='weixin\|multiplex' -i | head -30
```

2026-09-11 实测：本机 `v0.20.3 (2026.8.16.2)`，commit 停在 2026-08-17；上游最新 tag `v2026.9.7`；
**落后 origin/main 9,937 个提交**。所以"有没有更新"这类问题，答案几乎总是"有，而且积压很多"。

### 查上游相关 issue / PR（无 jq 也能用）

```python
import json, urllib.request, urllib.parse
def api(q):
    url = 'https://api.github.com/search/issues?q=' + urllib.parse.quote(q) + '&sort=updated&order=desc&per_page=10'
    req = urllib.request.Request(url, headers={'User-Agent': 'hermes', 'Accept': 'application/vnd.github+json'})
    return json.load(urllib.request.urlopen(req, timeout=45))
for it in api('repo:NousResearch/hermes-agent weixin account in:title')['items']:
    print(it['number'], it['state'], it['title'], it['updated_at'][:10])
```

单个 issue 的判定价值在于 **labels + milestone + 最新评论**：
`labels` 里有 `needs-decision` / `P3` 且 `milestone` 为 `None` ⇒ **没有承诺的版本和日期**，别给用户报时间表。

## 1. 三种拓扑，别混为一谈

| 想要的效果 | 现状 | 实现方式 |
|---|---|---|
| 一个**进程**服务多个微信号 | ✅ 支持（本机 v0.20.3 就有） | `multiplex_profiles`（见 §2） |
| 一个 **agent/profile** 挂多个微信号 | ❌ 上游未合并 | 等 issue（见 §3），或继续用自建 iLink 中继 |
| 多个用户共用**同一个 bot** | ✅ 可用 | 让其他人直接给这个 iLink bot 发消息，把 openid 加进 `WEIXIN_ALLOWED_USERS` |

⚠️ multiplex ≠ 同一个 agent。**每个微信号仍是一个独立 agent**（独立 memory / skills / sessions / provider keys）。
用户如果问的是"我一句话同时发给两个人"，multiplex 满足不了，要等 §3。

## 2. multiplex（多路复用）怎么开

让**默认 profile** 的网关进程同时服务机器上所有 profile，各 profile 用**自己的**平台凭证。

```bash
hermes config set gateway.multiplex_profiles true   # 或 config.yaml: gateway.multiplex_profiles: true
hermes gateway restart
```

打开后的行为变化（关掉即全部还原）：

- 二级 profile **不能再自己 `hermes gateway start`** —— 会硬报错（"The default gateway is running as a profile multiplexer and already serves profile 'X'"）。multiplexer 是唯一入站进程。
- HTTP 入站的平台（webhook 等）走 **`/p/<profile>/` 路径前缀**，不是第二个端口；未知/未配置的 profile 前缀返回 404。
- 二级 profile **不得自己启用绑定端口的平台**（配置错误会整段跳过该 profile）。
- 二级 profile 的 `send_message` / 通知 / `/loop` 唤醒走**它自己的 bot**（上游专门修过这条，见 `45a6101f36`）。
- 凭证严格按 profile 隔离：provider keys / vault secrets / MCP 子进程都不跨 profile 串。

代码层证据（本机已具备）：`gateway/config.py` 里的 `multiplex_profiles: bool = False`、`multiplex_profile_allowlist`；`hermes_cli/config.py` 接受顶层 `multiplex_profiles` 写法；文档 `website/docs/user-guide/multi-profile-gateways.md`。

## 3. 「单个 agent 多个微信号」上游进度

| Issue | 内容 | 状态（2026-09-11） |
|---|---|---|
| **#47129** | `gateway/platforms/weixin_multi.py`：启动时扫 `~/.hermes/weixin/accounts/*.json`，每个账号注册一个独立适配器；支持 `deliver="weixin:<account>"` 路由 | **open**，已 rebase 待审，7 月起挂在 review；作者提议拆成 PR-A(inbound)/PR-B |
| **#89290** | 多账号 + **共享同一个 DM 会话**；配置 `platforms.weixin.extra.accounts: [...]`，支持 `shared_dm_session` / `shared_dm_users` / `shared_dm_sender_name`（可打 `[大哥]` 这类标签）；歧义发送直接拒绝 | **open**（2026-08-18 提） |
| #29144 / #41286 | 更早的同类需求 | open |
| ~~#25660~~ | single gateway, multiple agents | **closed = 已合并**（就是 multiplex） |

有价值的旁证：issue #47129 评论区有生产用户（@aleck31）报告**用本地补丁跑了 3 个 iLink bot 三个多月**，
并指出 iLink 的 1:1 特性：**bot token 在扫码那一刻就和扫码人的身份绑死**，所以同一 profile 内不同 bot 的
入站 openid 全局唯一，**不需要按账号做 session 命名空间**。⇒ 技术上通，卡在 review 人力。

## 4. iLink 身份与凭证落盘

- QR 登录拿到的是 **iLink bot 身份**（形如 `a5ace6fd482e@im.example`），**不是**可自由脚本化的普通个人微信号。
- 一般**不能**像普通联系人那样被拉进普通微信群；iLink 通常也**不投递普通微信群事件**（`WEIXIN_GROUP_POLICY` 因此默认 `disabled`）。
- `@` 个人号 ≠ `@` iLink bot —— 是两个身份。
- 凭证目录：`~/.hermes/weixin/accounts/<ilink_bot_id>.json`（含 `token` / `base_url` / `user_id`），
  外加 `<bot_id>.context-tokens.json`（按 `account_id:user_id` 存回复上下文）和 `<bot_id>.sync.json`（长轮询游标）。
- 排查时看 `~/.hermes/.env` 的 `WEIXIN_ACCOUNT_ID` / `WEIXIN_TOKEN` / `WEIXIN_HOME_CHANNEL` 指向哪个 bot。

```bash
ls -la ~/.hermes/weixin/accounts/          # 已登录的 bot 身份
python3 -c "
import json,glob,os
for f in sorted(glob.glob('~/.hermes/weixin/accounts/*.json')):
    try:
        d=json.load(open(f)); print(os.path.basename(f), '->', d.get('user_id','?'))
    except Exception as e: print(os.path.basename(f), '读不了', e)"
```

⚠️ **有乱码文件名的 bot json 说明当年写盘时文件名被污染**（见过一个 `\x11\x08…json`）——它会进发现逻辑，
该删就删，别留着当"幽灵账号"。

## 5. 相关但不属于本节的功能

- **跨 bot 给第三方（如妈妈）推送**：multiplex 之外还有"SQLite 发送队列 + 独立 relay 进程"的老方案，
  见 `scheduled-briefings` 的「Delivery to Third Party」一节和 mom-memory 的 V3 架构说明。
- **限流**：`iLink sendmessage rate limited: ret=-2 ... errmsg=rate limited` 是时间窗口机制，等几分钟自恢复；
  上游已有 `honor server retry_after for flood-capped sends` 的修复（本机是否包含需先按 §0 核对）。
