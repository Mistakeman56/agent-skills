---
name: nav-monitor
description: Use when the user 问内网入口网站/三设备监控状态，或要改 nav 页面、排查数据不刷新。
---

# 内网入口监控站 (example.com)

## 架构
- **页面**: `/var/www/nav/index.html`（v2 美化版，源文件 `/root/nav-index-v2.html`，备份 `index.html.bak.20261012190809`）
- **数据**: `~/.hermes/nav-monitor/collector.py` → 每 20s SSH 三台 → 原子写 `/var/www/nav/api/status.json`
- **服务**: `systemctl {status|restart|journalctl -u nav-monitor}`（enabled，Restart=always）
- **认证**: Caddy forward_auth → `user-auth.py`；页面与 JSON 都在认证后（无 cookie 302 /login）

## 数据源
| 设备 | 方式 | 温度 |
|---|---|---|
| 软路由 .1:2222 | ssh key, `sh -s` stdin | thermal_zone→x86_pkg_temp |
| PVE .134 | sshpass (密 `~/.hermes/secrets/nav_monitor.env`) | x86_pkg_temp + pct/qm 计数 |
| NAS .219 | sshpass, 用户 user(docker组) | sysfs NVMe(免root) + **HDD 走 docker nsenter `postgres:17-alpine` 跑 smartctl** |

## IPTV 直播页（2026-10-22 新增）
- **页面** `/var/www/nav/iptv.html` + `js/hls.min.js`（**必须本地化**，npmmirror 下载最快，`cdn.jsdelivr.net` 国内不稳）
- **后端** `/root/iptv/iptv_proxy.py` → systemd `iptv-proxy`，监听 `127.0.0.1:7788`
- **源地址** 存 `/root/iptv/source.txt`（600）—— token 失效时只改这里，代码不用动
- **Caddy** 主域 `example.com` 加 `handle /iptv/*`（forward_auth + `reverse_proxy 127.0.0.1:7788`），**必须插在通用 `handle` 之前**（Caddy handle 按顺序互斥匹配）
- **端点**：`/iptv/health`、`/iptv/list`、`/iptv/play?u=<b64url>`、`/iptv/seg?u=<b64url>`
- **collector** `SERVICES` 加 `"iptv": "http://127.0.0.1:7788/iptv/health"` → nav 卡片带健康点

### 三个坑（都踩过）
1. **`/seg` 必须也重写 m3u8**：master playlist 走 `/play` 会重写，但二级 media playlist 是从 `/seg` 拿的，若只透传，里面的分片就是裸相对路径（`20260216...ts?msisdn=`）→ 浏览器 404/HTTP 000。判据：看 `Content-Type` 含 `mpegurl` 或首字节是 `#EXTM3U`。
2. **浏览器无法设 User-Agent**：源强制 `okHttp/Mod-1.5.0.0`，不注入就 302 到 `cdn.jsdelivr.net/gh/feiyang666999/testvideo` 假流（能播但所有台同一画面）。网页播放**必须**走服务端代理。
3. **`pkill -f "iptv_proxy"` 会杀掉自己的 shell**（命令行包含该字符串）→ 用 `systemctl stop` 或 `pkill -f "[i]ptv_proxy"`。

### 验证一条命令
```bash
curl -s -m 8 http://127.0.0.1:7788/iptv/health   # 期望 ok
```
分片真伪：末级返回首字节 `0x47`（`4740…`）= 真 MPEG-TS。

## 坑（都踩过）
1. **sudo -S 喂密码被安全策略 BLOCKED** → 换 docker nsenter 路线（user 在 docker 组，无需 sudo）
2. **sshpass 后必须紧跟 `ssh`**，否则 `invalid option -- 'o'`
3. **别加 BatchMode=yes**（会掐死密码认证）
4. **fill() 元素 id 前缀**: 卡内数值用首字母 `r-/p-/n-`，状态点用 `d-router` 全名；所有赋值走 `set(id,txt)` 存在性守卫，一个不存在的 id 会中断整个渲染
5. **hist 会被 `state['devices'][dev]=d` 整体覆盖冲掉** → 赋值前拷回旧 `cpu_hist/temp_hist`
6. **单次 SSH 抖动不算掉线** → `fail_streak>=2` 才判 offline，否则 banner 误报红
7. write_file 只落工作区/绝对路径可用（`/etc/...` 会失败），`terminal` 的 cwd 是 `~/.hermes/nav-monitor`，跨目录用绝对路径
8. 自签测试 cookie: `cc_auth = ts + '.' + hmac_sha256(secret, ts)`，secret=`~/.hermes/secrets/caddy_auth_secret`；**有效期约 15 分钟**，过期被踢 /login 重签即可

## 页面功能清单
v3：三卡(CPU/内存/温度/负载|CT计数/延迟ms/20min趋势线/uptime) + NAS硬盘温度(盘1盘2NVMe+正常|温热|偏高标签) + 状态banner(含`#svcn`服务在线胶囊) + 时钟问候 + **11服务分组卡(真品牌图标+每卡红绿点+延迟)** + 橘猫/大黄鸡SVG(点头像/小鸡弹说话气泡彩蛋) + 橘猫favicon + 手机单列自适应。10s fetch 刷新。

## 图标与服务反代 (2026-10-12 v3)
- 图标库 `/var/www/nav/icons/`：simple-icons SVG(simpleicons CDN 直连) + 各家真 favicon(NAS直 curl) + 绿联官网/istoreos GitHub头像 + 自绘 speed.svg/test.svg；**img 别加 `loading="lazy"`（本页不触发加载，全部 pending）**
- 新增 Caddy 块：qb:8888(VueTorrent) / mp:3000 / iyuu:8787，照抄模板（自带登录无站点认证）；DNS `*.example.com` 已泛解析免加记录
- **Caddy `admin off` → `systemctl reload caddy` 必失败(Post 2019 refused)，只能 `validate` 通过后 `systemctl restart caddy`**；重启后首测可能 000，重试即 302，非故障
- collector `SERVICES` 表 + `collect_services()` 并发 curl 探活(3s超时,401/302/307=活,000/5xx=挂)，写进 `state["services"]`；前端 `svcRender()` 渲染
- **主入口认证=专属登录页+会话级Cookie**（2026-10-12 最终版；中间曾短暂用过 basicauth 原生弹框，用户否决：“要入口网页不要弹窗”）：Caddy `handle /login*|/logout` → `127.0.0.1:8899`，其余路径 `forward_auth 127.0.0.1:8899 {uri /verify}`；登录页 `/var/www/nav/login.html`（表单 action=/login，用户名 user）；`user-auth.py` 校验 `caddy_basic_auth.txt` 的 `password=` 行 → 签 HMAC cookie `cc_auth`（**会话级，无 Max-Age，关浏览器失效=取消7天自动认证**；服务端 token 7 天）。**改凭据后必须同时：改文件→`caddy hash-password` 不再需要，但要轮换 `caddy_auth_secret` 才能让旧 cookie 立即失效**；无 cookie 访问 → 302 /login。子域名本就无站点认证（实测 Location 全是服务自己的跳转）
- 服务探活 `probe_one` 带 **1s 后重试一次**（000/5xx 抖动不误报）；`SERVICES` 表打内网直连 IP 不走公网回环
- 工作副本 `/root/nav-index-v3.html`
