# 绿联 NAS 官方远程连接（UGREENlink）掉线排查

2026-08 实测：用户报告"绿联官方连接一直掉线，昨天下午5点开始"。排查结论：**NAS/网络/绿联服务器全都没问题，是 P2P 隧道会话失效**（客户端↔协调服务器↔NAS 的打洞通道断了）。

## 排查顺序（从"变化的东西"入手）

### 1. NAS 本机健康（局域网视角）
```bash
ping -c 4 -W 2 192.0.2.10          # 0丢包 = 活着
for p in 22 80 443 9999 8080 3000 445 139 111 2049; do
  timeout 2 bash -c "echo >/dev/tcp/192.0.2.10/$p" 2>/dev/null && echo "$p open"
done
curl -sk --noproxy '*' -I "https://192.0.2.10:9443/" | head -3   # 绿联 UGOS Pro Web（9999→307→9443）
```
- 全通 → NAS 没病，别折腾它；问题在"远程链路"
- 指纹确认：`/desktop/?os=ugospro` 返回 200 = UGOS Pro（绿联 DXP4800）

### 2. ⚠️ 域名陷阱：别测错域名
| 域名 | 解析到 | 是不是绿联远程服务 |
|---|---|---|
| `web.ugnas.com` | Cloudflare CDN | ✅ 绿联云真正的网页端 |
| `ug.link` | 203.0.113.1 | ✅ UGREENlink 远程访问入口 |
| `link.ugreen.com` | 203.0.113.1 (**SAP Emarsys**) | ❌ 营销邮件域名，不是远程服务！ |
| `cloud.ugreen.com` | 203.0.113.1 (阿里云) | ⚠️ 疑似旧版/废弃服务 |

**教训：** `link.ugreen.com` 解析到 SAP Emarsys（德国邮件营销平台）——测它失败不代表绿联挂了。判断绿联服务是否正常，测 `web.ugnas.com`（200）和 `ug.link`（301 跳转正常）即可。

### 3. ⚠️ WAN6 显示 pending ≠ IPv6 坏了
路由器 `ubus call network.interface.wan6 status` 可能显示 `up:false, pending:true`，**但 LAN 实际 IPv6 完全正常**：
```bash
# 看邻居表是否有 2408: 公网 IPv6 前缀（联通）分配给 NAS
ip -6 neigh show | grep -i '6c:1f:f7'    # NAS MAC → 有 2408:822f:...::c7b REACHABLE = IPv6 通
ping6 -c 3 -W 2 "2408:822f:20a2:e2c0::c7b"  # 0丢包 = 公网 IPv6 可达
```
绿联 P2P 打洞强依赖公网 IPv6——**先确认 IPv6 前缀真的在工作再怀疑它**，别被 WAN6 接口状态误导。

### 4. 绿联服务端状态
```bash
for d in web.ugnas.com ug.link; do
  timeout 8 curl -s --noproxy '*' -o /dev/null -w "$d: %{http_code}\n" --connect-timeout 6 "https://$d"
done
# web.ugnas.com=200 + ug.link=301 → 绿联服务器活着，问题不在服务端
```

### 5. 路由器侧确认没有重启/重拨
```bash
ssh -p 2222 root@192.0.2.10 "uptime -s"          # 启动时间——排除路由器重启
ssh -p 2222 root@192.0.2.10 "ubus call network.interface.wan status"  # PPPoE 正常、公网IP在
```

## 结论模式

**NAS 本地全通 + 绿联服务端正常 + 网页端能开 + 但 App/客户端连不上**
= P2P 打洞隧道失效（典型触发：IPv6 前缀刷新、NAT 会话超时、客户端切换网络、路由/NAS 状态变化）

**修复（30秒）：**
1. 首选：绿联 App/网页端 → 控制面板 → 设备连接 → 远程访问 → **关闭再开启 UGREENlink**（重建 P2P 通道，90% 恢复）
2. 备选：完全退出客户端重新登录（清缓存旧会话）
3. 社区同类症状确认过：重启 NAS / 重启路由器 / 重开服务后恢复；也有人遇到"文件上传一半被暂停"导致远程异常，清空任务列表恢复

## 长期方案：Tailscale 直连（用户已有 tailnet）

绿联官方 P2P 依赖协调服务器，官方服务抽风就掉线。**NAS 装 Tailscale 后走 WireGuard 直连**，官方服务器挂不挂都不影响。DXP4800 是 x86，支持安装。用户明确说过"我其实不用这个官方连接我有tailscale"——排查完主动提议帮装。

## 环境速查（2026-08）

- NAS：绿联 DXP4800，192.0.2.10，UGOS Pro，**未装 Tailscale**
- UGREEN SSH 用户是 `user`（非 root，root SSH 默认禁用）
- 绿联官方网页端：https://web.ugnas.com
- UGREENlink 网页端：https://ug.link/<自定义ID>
