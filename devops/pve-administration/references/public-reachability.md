# 公网入口可达性排查（自建服务对外发布）

适用：域名/端口从外网打不开、同一台机器上子域名却正常、想做到「不带端口」、怀疑运营商封端口。

## 铁律：内网自测全是假阳性，只有外部 vantage point 算数

内网向公网 IP 发请求会被防火墙反射规则接回内网（走 LAN，不经过 WAN）。所以「内网测着好好的」和「外面进不来」**可以同时成立**。两个现象同时出现时，**不要怀疑服务，去怀疑入口**。
判定流量是否真从公网进来的硬证据只有两个：`tcpdump -i pppoe-wan` 抓到 SYN，或 DNAT 规则的 `counter packets N` 在涨。**没抓到就是没进来**，别再往下查反代。

## 外部 vantage point 工具箱（按可靠度）

1. **canyouseeme.org**（最可靠，Error/Success 明确）
   - 「Port to Check」填端口 → 提交 → 读结果行
   - `Error: I could not see your service on <IP> on port (N)` + `Reason: Connection timed out` = 不通
   - `Success: I can see your service on <IP> on port (N)` = 通
   - 页面顶部 `Your IP:` 要确认就是目标公网 IP（认错说明测的不是你家）
   - 逐个端口测，一次只能一个
2. **本机香港代理**（真外部视角，能测到 HTTP 层）
   - `curl -sv -x http://127.0.0.1:7899 https://域名:端口/ -o /dev/null`
   - 必须看到 `SSL certificate verify ok` + `HTTP/2 200` 才算通
   - 代理**不支持 IPv6 目标**
3. **手机流量实测**（关 WiFi）—— 最贴近真实场景。手机流量走 IPv4，443 被封时失败属预期。

**不可靠，别拿结论**：
- **itdog.cn**：数字常是上一条的缓存 —— 换端口/换目标重测而「最快/最慢/平均」完全相同就是没真跑；有无验证码随缘。
- **web_extract**：从境外取，国内家宽入站常不可达，失败不构成证据。
- **check-host.net**：不接受 IPv6 字面量（`invalid_url`）。
- **在目标机/路由器上 curl 自己的公网 IP**：会落进最后一跳 openclash `redirect to :7892`，恒 000，毫无意义。

## 自建入口的封锁矩阵（联通家宽实测）

| 入口 | 外网可达 |
|---|---|
| IPv4 :443 | ❌ 封（抓包无 SYN、DNAT counter 恒 0）|
| IPv4 :80 | ❌ 封 |
| IPv4 :18443 等高端口 | ✅ 通 |
| IPv6 :443 | 内部链路可用（**路由器必须显式放行，见下**）；**外网 v6 可达性没有可用工具能验证，只能让用户实测，不要声称已验通** |

**结论：不要承诺「裸域名 + IPv4」可达。** 外网也做到不带端口只有两条真路子：IPv6 入口，或套 CDN/隧道（Cloudflare Tunnel 需域名 NS 转过去、阿里云 DDNS 要改 CF API；国内 CDN 需域名已备案）。**都属大动作，先问用户。**

## 启用 IPv6 入口（IPv4:443 被封时的无端口方案）

1. 确认服务双栈监听：`ss -lnt | grep ':443'` 要看到 `*:443`（不是 `0.0.0.0:443`）。
2. 取主机全局 IPv6：`ip -6 addr show scope global | grep -oP 'inet6 \K2408:[\w:]+'`
3. **路由器显式放行端口（关键一步）**：IPv6 无 DNAT，`ct status dnat accept` 覆盖不到它，流量会掉进 `jump reject_from_wan`。症状是「**IPv6 能 ping 通，端口连不上**」。
   ```sh
   cp /etc/config/firewall /etc/config/firewall.bak.ipv6
   uci add firewall rule
   uci set firewall.@rule[-1].name='Allow-IPv6-HTTPS'
   uci set firewall.@rule[-1].src='wan'
   uci set firewall.@rule[-1].proto='tcp'
   uci set firewall.@rule[-1].dest_port='443'
   uci set firewall.@rule[-1].family='ipv6'
   uci set firewall.@rule[-1].target='ACCEPT'
   uci commit firewall && /etc/init.d/firewall reload
   ```
   验证：`nft list ruleset | grep 'Allow-IPv6'` → `meta nfproto ipv6 tcp dport 443 accept`
4. AAAA 指向该地址 + 用 `scripts/ddns-aaaa.py` 挂 cron 跟住前缀变化。
5. **前缀会变**：运营商重拨换 PD 前缀 → 地址变 → AAAA 成断头路。所以这个 cron 不是可选项。（本机 IPv6 是 EUI-64，前缀变地址跟着变：`20a1:5cf0` → `20a3:5570`。）
6. **别想用「只有 AAAA 的子域名」做 v6-only 探针**：泛解析 `*` 的 A 记录会一起返回，客户端仍走 v4。做不到，别在这耗时间。

## DNS 记录：A / AAAA 一起查，并且查**权威**那台

**症状「域名打不开但子域名正常」有两个常见根因，两个都要查：**

1. **AAAA 指错机器**（最常见）：浏览器 Happy Eyeballs 优先 IPv6，AAAA 指向只有自签证书的机器（例如某台 NAS）就整体失败，而 A 记录看着完全正常。修法两条一起做：**AAAA 改指正确主机 + 放行 IPv6 入站**。
2. **主域名 A 记录自己过期了**：路由器上 `ddns-scripts_aliyun` 的每条 service 都是**逐个主机名**配的，只覆盖当初列进去的那批子域，**`@` 和 `*` 通常不在里面**。公网 IP 一变，子域自动跟上、主域名和泛解析还指着旧 IP → 表现就是「子域名能开、裸域名不能开」。

**判据**：`dig +short @dns29.hichina.com 域名 A`（权威）对比 `dig +short @203.0.113.1 域名 A`（公共）以及路由器 `dnsmasq`。

**TTL 缓存会骗人**：改完 A 记录后权威和路由器立刻是新值，但 203.0.113.1 / 203.0.113.1 / 114 会继续返旧值直到 TTL 到期。**阿里云免费版 TTL 最低 600 秒**（`UpdateDomainRecord` 传 60 直接 HTTP 400，降不下来）。改完 10 分钟内不要下结论；家里设备走路由器 DNS，通常已经能用了。

**还有一层最容易忽略：发查机器自己的 dnsmasq 也会缓存。** 典型现场是「`--resolve 新IP` 直连 200、直连内网机 200，但拿域名 `curl` 恒 000」——服务和入口都是好的，是本机解析器还返旧地址。判据：`dig @127.0.0.1 域名 A` 与 `dig @203.0.113.1 域名 A` 对比，不一致就是本机缓存。修：`systemctl restart dnsmasq`（`kill -HUP` 有时不够），顺手把走代理的那条也重启（mihomo 的 DNS 缓存同样会返旧值）。**排查「改完 DNS 还是不通」时，三层（本机解析器 / 公共 DNS / 权威）要逐层 `dig` 确认，别只看权威。**

详见 `references/ddns-and-apex-coverage.md`。

## 反代层（Caddy）配置坑 —— 每一条都真金白银踩过

1. **改工作副本 = 改了等于没改**。服务实际读的是 `/etc/caddy/Caddyfile`；在 `~/.hermes/caddy/Caddyfile` 上改完不 `cp` 过去，会得到一个很坏的假象：语法校验通过、旧进程还活着、测试「都通」，其实跑的是旧配置（真路径从 `systemctl status caddy` / journal 里看）。**改完就 `cp`，再 restart。**
2. **全局选项块 `{}` 必须在文件最前面**。站点块写在它前面 → `server block without any key is global configuration, and if used, it must be first` → 服务起不来。新增 http→https 跳转之类的块要放在全局块**之后**。
3. **Caddy 以 `caddy` 用户运行，读不了 `/root/**`**。静态页放 `/root/` 下时，认证过了也只会得到 **403 + `content-length: 0`**（很容易误判成认证失败）。放 `/var/www/`，属主 `caddy:caddy`。
4. **设了 `admin off` 就不能 `reload`** —— reload 走 `POST localhost:2019/load`，admin 关了必然 `connection refused`。改用 `systemctl restart caddy`（service 会报 failed 而旧进程还活着，别被 `is-active` 骗）。
5. **顺序永远是：改文件 → 语法校验 → restart**。反了会把所有站点一起打挂。
6. **测 Caddy 必须带域名 + `--resolve`，不能拿 IP 当 Host** —— SNI=IP 时报 `alert internal error`，会误判成服务挂了：
   `curl -sv --noproxy '*' --resolve 域名:端口:127.0.0.1 https://域名:端口/`
7. **`forward_auth` 未登录时必须返 `302 → /login`，不能返 401** —— 401 在浏览器上是一张白屏错误页，不会跳登录页。同时 `/login`、`/logout` 要用 `handle` 互斥块直接 `reverse_proxy` 给认证服务，否则认证会把登录页本身也拦了。
8. `curl` 在本机/容器里默认会走 Clash 代理，测自己的服务会被误判「打不开」（`SSL_ERROR_SYSCALL`）→ **一律加 `--noproxy '*'`**。
9. **`curl -x` 打印的 `HTTP/1.1 200 Connection established` 是代理自己的应答，不代表目标可达** —— 一个根本不存在的端口也照返 200 CONNECT。必须看后面那行 `SSL_connect` / `HTTP/2`。
10. **一个 site 块可以挂多个地址**：`https://a.b, https://a.b:18443 { ... }` —— 这就是「443 留给内网/将来 CDN，18443 给外网」同时可用的写法，不用复制两份配置。
11. **裸域名走 80 要两样都给**：路由器加一条 80 的 DNAT **且** Caddy 加 `http://域名, http://*.域名 { redir https://{host}{uri} 301 }`。只做一半的话，用户输裸域名会落到路由器 uhttpd 或一个 `307 → http://域名:9999/`（nginx）——那就是「打不开」的现场。
12. **别为了腾 443 去动 uhttpd，代价不值**：uhttpd 占的是路由器**本机**的 80/443，与公网 DNAT 并不冲突（`ct status dnat accept` 会让 DNAT 流量照过）。把它的 `listen_https` 删掉后，**反代 LuCI 的站点立刻 502**（它的上游就是 `https://192.0.2.10:443`）—— 要么让 uhttpd 继续听 443，要么把上游改到 `:80`。而且腾出来也没用：外网 443 本来就被运营商封着。

## 自写脚本（DDNS / DNS API）的坑

1. **Python 会读 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` 环境变量**。本机这些变量指向 Clash，于是 `urllib` 调外部 API 报 `Connection refused`，而**同一时刻 `curl --noproxy '*'` 完全正常** —— 极易误判成「阿里云挂了」。所有自写脚本一律：
   ```python
   opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
   with opener.open(url, timeout=20) as r: ...
   ```
   **代价**：DDNS 脚本曾因此静默失败（cron 里只留一行 traceback），公网 IP 变了主域名没跟上，整站打不开一整夜。
2. **公网 IPv4 从路由器取，不要调外部 API**：
   `ssh root@192.0.2.10 "ifconfig pppoe-wan | grep -o 'inet addr:[0-9.]*'"` —— 稳定、快、天然不受本机代理影响。
3. **DDNS 要覆盖 `@` 和 `*`**，别只依赖路由器的子域列表（见上文 DNS 段）。
4. cron 里跑的自愈脚本要**把输出落盘**（`>> /var/log/xxx.log 2>&1`），否则失败无人知晓；顺手查一眼日志尾部有没有 traceback。

## 门户与认证分工（用户既定偏好，别自行改）

- **只给入口门户做认证，子域名一律不加**。用户原话：「后面的那些跳转的网页你就别设密码了，你就给这个前端设的坚固点就行了…他比如说 iStore，他都自己有那个登录，你就不用再整个还整一套登录密码了，不然太麻烦了」。LuCI / NAS / HA / PVE / Jellyfin 各自有登录，再套一层只会添乱；无登录的服务（如测速页）直接开放，不要自行加壳。
- **不要用浏览器原生 Basic Auth 弹窗做主入口**（用户嫌「太简陋」）。正确形态：**自定义登录页 + Cookie + `forward_auth`** —— 一个常驻小认证服务（systemd，监听 `127.0.0.1:8899`），Caddy `forward_auth` 调它的 `/verify`；Cookie `Domain=<主域>`（跨子域共享）、`HttpOnly`、`Secure`、7 天；token 用 HMAC(密码, 服务端 secret) 做无状态校验。
- 导航页卡片与登录页放 `/var/www/`；主页未登录时返 302 → `/login`，登录成功后回主页。

## 变更后核对清单

- `ss -lnt` 目标端口在听；相关 systemd 服务 `is-active`
- 配置里的站点地址确实带上目标端口；**跳转/导航页里的链接要指到外网真能用的那个入口**（链接写裸域名的话，外网 IPv4 用户点了就是死链）
- 改完配置：**先确认服务实际读的是哪个文件**（从 `systemctl status` / journal 看路径，改工作副本不生效会造出「测试都通其实跑旧配置」的假象）→ `cp` 到位 → 语法校验 → 重启
- 备份到手再改防火墙；`reload` 不 `flush`
- **收尾必须做一次外部验证**（canyouseeme + 香港代理），别只报内网结果

## 附：交付运维大图（拓扑图/长截图）

可复用链路：写自包含 HTML（固定宽 1500px + 深色主题 + 分层卡片，卡片塞 IP/端口/容器名/运行状态）→
`Emulation.setDeviceMetricsOverride(width=1500, height=页面高, deviceScaleFactor=2)` →
`Page.captureScreenshot(captureBeyondViewport=True)` 取全页 →
PIL 转 JPEG（quality 88、宽降到 2400）压进 1MB 内再发（原 PNG 常 3~4MB）。
`capture_screenshot()` 不支持 `full_page`，全页必须走 CDP。发图前用 `vision_analyze` 复查排版（文字截断/重叠）。

**图上标什么（the user explicitly要求，别回退）**：**不要写公网 IP** —— PPPoE 断电重拨就换，图当天就作废。写**域名**（永不变，DDNS 自动跟随）+ **不变的内网 IP**（已钉静态租约的那批），动态地址一律标 `动态`。同理，任何要留存的文档/配置/清单都别写死公网地址。
