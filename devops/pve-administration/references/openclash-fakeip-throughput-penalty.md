# OpenClash Fake-IP 吞吐量衰减（直连流量性能诊断）

## 问题现象

千兆宽带（Speedtest 实测 878Mbps 下载），OpenClash 开着的状态下：
- **内网设备直连国内网站**（百度、腾讯云、阿里云、抖音视频）只有 **几十 Kbps ~ 几 Mbps**
- **同一设备关掉 OpenClash 后**，百度秒开、速度正常
- **Speedtest 不走 OpenClash**（作为独立二进制直接连网）→ 878Mbps ✅
- **curl --noproxy "*"** 从路由器自身测百度也极慢（几百 Byte/s）

## 根因：Fake-IP 模式的架构性吞吐衰减

OpenClash 在 **Fake-IP 模式**下，即使流量匹配 `RuleSet(ChinaMax) → DIRECT`，**仍然要经过 Clash 内核的 TUN/TPROXY 层**。具体说：

1. DNS 被劫持 → 域名解析返回 `198.18.x.x`（Fake IP）
2. 客户端发 TCP SYN 到 Fake IP
3. Clash 内核收到包，查规则 → 匹配 DIRECT
4. Clash **仍要代理这个连接**——它在本地开一个 TCP socket 连接到真实目标 IP
5. 流量路径变为：**App → Clash TUN/TPROXY → Clash DIRECT forward → 真实服务器**
6. 这个 TPROXY + socket 转发增加了延迟开销和吞吐衰减

**关键认知**：OpenClash 的 `DIRECT` 不是"不经过 Clash"，而是"Clash 帮你直连"。流量仍然在用户态经过 Clash 核心的 TCP 协议栈，对于高吞吐应用（视频流、大文件下载），这个用户态转发层是瓶颈。

## 与 Redir-Host 模式对比

| 模式 | 直连流量路径 | 直连性能影响 |
|------|:-----------:|:----------:|
| **Fake-IP** (默认) | App → TUN/TPROXY → Clash DIRECT → 真实IP | **严重衰减**（用户态转发） |
| **Redir-Host** | App → NAT REDIR → Clash DIRECT → 真实IP | 中度衰减 |
| **无代理** | App → 网卡 → 真实服务器 | **无衰减 ✅** |

## 诊断方法

### 1. 确认衰减存在

```bash
# 路由器自身测速（走 Clash DIRECT）
curl --noproxy "*" -s -o /dev/null -w "百度: %{speed_download} B/s\n" --max-time 5 https://www.baidu.com
# → 几百 Byte/s（异常）

# 同机器 speedtest 客户端（不走 Clash）
speedtest -s 24447 --accept-license --accept-gdpr | grep Download
# → 878 Mbps（正常）

# 对比结论：Clash 内核转发拖慢了直连
```

### 2. 临时关 Clash 验证

```bash
/etc/init.d/openclash stop
# 再测国内网站 → 速度恢复正常
/etc/init.d/openclash start
```

## 解决方案

### 方案 A：看国内内容时关 OpenClash（最快）

```bash
ssh root@192.0.2.10 '/etc/init.d/openclash stop'
```

### 方案 B：双客户端策略

在 iStoreOS 上给指定设备（如你的电脑）设 DHCP option 排除代理，让这些设备不经过 Clash 内核处理。其他走代理的设备（盒子、NAS）正常走 Clash。

### 方案 C：买独立串流盒子

苹果 TV / 安卓盒子接电视，这些盒子只走代理看外网内容。你的电脑不走代理，国内体验完全不受影响。

## 排障误区（不要浪费时间）

❌ 怀疑网线/交换机问题（eth2 2.5Gbps 协商正常，Speedtest 878Mbps）
❌ 怀疑宽带本身问题（Speedtest 确认带宽充足）
❌ 反复修改 OpenClash 规则文件（规则文件不是问题根因）
❌ 用 curl 测小文件判断带宽（被 HTTP 连接握手时间主导，测不出真实带宽）
❌ 用 fast.com / fastnet 测速（这些走的 CDN 域名可能被 OpenClash 规则匹配到代理，导致误判）
