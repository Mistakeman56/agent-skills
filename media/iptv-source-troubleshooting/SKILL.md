---
name: iptv-source-troubleshooting
description: Use when 直播源在播放器里看不了/黑屏/全台同一画面。先查UA。
---

# IPTV 直播源排障

## 一、第一嫌疑人永远是 User-Agent

很多共享源（尤其 mursor 系）服务端**强制校验 UA**，UA 不对时**不报错**，而是 302 重定向到一段公开测试视频。表现：列表能加载、台标全有、但点开黑屏或所有台都是同一段画面。

**已知要求**：

| 源 | 必需 UA |
|---|---|
| mursor（`@mursorottiptv_bot`，`live.ottiptv.cc`） | `okHttp/Mod-1.5.0.0` |

大小写严格：是 `okHttp`（小写 o），不是 `OkHttp`/`okhttp`。

## 二、一条命令识别“假流”

对列表里的真实频道地址（不是 `.m3u` 列表本身，而是里面的 `live.xxx/` 流地址）：

```bash
curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}\n" \
  -A "VLC/3.0.20" "$CHANNEL_URL"
```

**重定向到下面这个域名 = UA 不对，实锤**：

```
cdn.jsdelivr.net/gh/feiyang666999/testvideo/
```

（社区公开的 IPTV 测试视频仓库，被当成“拒绝访问”的兑底内容。看到 `testvideo` 就不用再怀疑网络了。）

换正确 UA 对比：

```bash
curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}\n" \
  -A "okHttp/Mod-1.5.0.0" "$CHANNEL_URL"
```

拿到 `miguvideo.com` 这类真实 CDN 地址就说明 UA 对了。

## 三、播放器里填 UA 的位置（APTV）

- **APTV 1.5.9+**：设置 → 配置/订阅管理 → 编辑配置 → **User-Agent** 字段直接填。旧版没这个框，必须先更新。
- TiviMate / tvbox / DIYP / Kodi：在源（Playlist）的自定义 header / UA 设置里填。
- 部分 App 支持在订阅 URL 后追加 `?ua=okHttp/Mod-1.5.0.0`（easy_tv_live 等），或读取 m3u 里的 `#UA-Hint:` 行。

## 四、UA 对了还播不了 → 查地域

央视/卫视源很多是**咪咕（miguvideo.com）**，对境外 IP 直接拒。

- 播放设备（Apple TV / 盒子）**不能挂代理/机场**，必须家宽直连。
- 自己验：拿到真实 m3u8 后用 `-A "okHttp/Mod-1.5.0.0"` 下分片；`HTTP 000` = 连不上，`200` = 链路 OK。

## 五、别踩的坑

- **不要凭 M3U 里频道的 `userid` 跟列表 URL 的 `userid` 不一致就断定“账号不匹配”**。共享源里频道地址用公共账号签名是常态，跟能不能播无关。（我曾据此误判，实际是 UA 问题。）
- **列表能下载（HTTP 200）不代表频道能播**，必须逐个测流地址的 302 目标。
- `live.ottiptv.cc` 走 Cloudflare，国内访问本身时好时坏；UA 修好后如果仍然卡，再怀疑这层。
