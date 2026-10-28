---
name: home-public-services
description: "Use when the user 发布内网服务到公网（加网站/映射MC/改端口/查访问故障）。"
version: 1.0.0
author: Hermes Agent
license: MIT
---

# 家里内网服务 → 公网发布（example.com 全家桶）

**the user authorizedassistant独立完成所有端口映射/网站发布类操作**（原话：「以后我如果要映射MC服务器出去这样的活就都由你来给我操作了」）。改前必须备份、只加不改、完成后验证连通性 + 报告。

## 现有架构（2026-09-22 跑通）

```
公网用户 → https://xxx.example.com:端口
   ↓ DNS A 记录（ddns-scripts_aliyun 自动更新，5分钟一查）
 203.0.113.1:端口   ← 联通 PPPoE 动态公网 IPv4
   ↓ 防火墙 DNAT（uci firewall redirect，持久化）
 内网机:端口
   ↓ （HTTP 服务再经 Caddy → 自动 HTTPS）
 后端服务
```

| 层 | 工具 | 配置文件（全是文本，assistant直接改）|
|---|---|---|
| DDNS | `ddns-scripts_aliyun`（路由器）| `/etc/config/ddns` |
| HTTPS + 反代 | Caddy（CT <ID> = 192.0.2.10）| `~/.hermes/caddy/Caddyfile` + `/etc/caddy/Caddyfile` |
| 端口映射 | uci firewall redirect | `/etc/config/firewall` |
| 泛域名证书 | acme.sh（DNS-01，阿里云）| `~/.acme.sh/*.example.com_ecc/` |
| 取 WAN IP | 自写脚本 | `~/.hermes/scripts/lucky_get_wan_ipv4.sh`（路由器：`/mnt/sata1-4/lucky/get_wan_ipv4.sh`）|

**证书**：`*.example.com` + `example.com`（EC-256，Let's Encrypt）→ **所有子域通用，不用逐个申请**。
续期 acme.sh cron 已装，续期后 `systemctl reload caddy`。
**阿里云凭据**：`~/.hermes/.aliyun.env`（600，仅 root）+ 路由器 `/etc/config/ddns`。**不落聊天/记忆**。

## 三个标准操作

### ① 发布一个 HTTP 网站（HTTPS 自动）
1. `Caddyfile` 追加一段（改完 `caddy fmt` + `caddy validate` + `systemctl reload caddy`）：
   ```
   https://新子域.example.com:端口 {
       tls /etc/caddy/certs/fullchain.pem /etc/caddy/certs/privkey.pem
       reverse_proxy 内网IP:端口
   }
   ```
2. 加一条 uci firewall redirect（外网端口 → 内网 IP:端口），见②。

### ② 映射任意 TCP/UDP 端口（MC、串流、SSH 都用这个）
```sh
uci add firewall redirect
uci set firewall.@redirect[-1].name="名字"
uci set firewall.@redirect[-1].src="wan"
uci set firewall.@redirect[-1].proto="tcp"      # 或 udp
uci set firewall.@redirect[-1].src_dport="外网端口"
uci set firewall.@redirect[-1].dest="lan"
uci set firewall.@redirect[-1].dest_ip="内网IP"
uci set firewall.@redirect[-1].dest_port="内网端口"
uci set firewall.@redirect[-1].target="DNAT"
uci commit firewall && /etc/init.d/firewall reload
```
**不要加 `reflection_src`**（坑1）。加完核对：`nft list ruleset | grep "端口"` 应出现 `dnat ip to ...`。

### ③ 加一条 DDNS 记录
`/etc/config/ddns` 里加 `config service`：`service_name 'aliyun.com'`、`domain '主机@域名'`（@ 分隔，**不写 @ 会把第一个 . 前的当主机名**）、`username`=AccessKeyId、`password`=AccessKeySecret、`use_ipv6 '0'`、`use_https '1'`、`ip_source 'network'`、`ip_network 'wan'`。`/etc/init.d/ddns restart`，日志 `/var/log/ddns/<name>.log`。

## ⚠️ 坑清单（每条都是真踩过的）

1. **`reflection_src` 不能填网段**！填 `192.0.2.10/24` → fw4 报 `option 'reflection_src' specifies invalid value` → **整条 redirect 被静默跳过**，nft 里看不到规则还以为配好了。要么不填（默认就反射），要么填接口名。
2. **curl 在 CT <ID> 容器里默认走 Clash 代理**（`HTTPS_PROXY=http://Clash:***@192.0.2.10:7890`）→ 测自己的服务会被误判「打不开」（SSL_ERROR_SYSCALL）。**一律加 `--noproxy '*'`**。用 `-x` 测 Clash 必须带账号密码，否则 407（不是网络坏了）。
3. **80/443 被 iStoreOS 后台 uhttpd 占用**（`0.0.0.0:80/443`）→ 想不带端口号必须先把 uhttpd 的 `listen_https` 挪到别的端口（如 9443）。**80 不动，后台照常能进**。
4. **Lucky 的配置 `*.lkcf` 是加密二进制**，不能直接改。API 是 `POST /api/login`（**JSON，字段大写 `Account`/`Password`/`TwoFA`**）+ `PUT /api/lucky/service?option=...`。连续错 10 次锁后台（要重启 Lucky）。
5. **Lucky 的「防火墙自动放行」是 nft 直加的 `accept`（非持久）**，`firewall reload` / 重启就没了。真正持久的是 uci firewall redirect（DNAT 流量由 `ct status dnat accept` 放行，**不需要额外 input 规则**）。
6. **关 Lucky 前必须盘点它管的端口转发**！MC 25565 原本是 `lucky_portforward.lkcf` 在管、uci 里没有 → 直接关会断。要把每个转发都补成 uci redirect 再关。
7. **acme.sh 的 `Ali_Key`/`Ali_Secret` 必须 `export`**（它是子进程，读不到 shell 变量），否则报 `You don't specify aliyun api key and secret yet`。
8. **诊断页的「来源判定」会误导**：内网反射把源 SNAT 成 `192.0.2.10`，手机运营商 CGN 可能给 `10.x`/`100.64.x` → 都像「内网」。**判定是否真从公网进来，必须手机关 WiFi（信号显示 4G/5G）再看**。
9. **每次 `firewall reload` 后必须验证 OpenClash 还活着**：`curl -s --max-time 8 $HTTPS_PROXY https://api.github.com/zen` 有输出 = 正常。`pgrep openclash` 恒为 0（进程名叫 `clash`），别当故障。
10. **ddns-scripts_aliyun 的 `check_interval` 单位是分钟**；日志 `/var/log/ddns/<服务名>.log`，看到 `Forced update successful` / `Registered IP '...' detected` = 正常。
11. **Caddy 里设了 `admin off` 就不能用 `systemctl reload caddy`**！它走 `POST localhost:2019/load`，admin 关了就 `connection refused` → reload 失败。**改用 `systemctl restart caddy`**。或者把 `admin off` 改成 `admin localhost:2019`。
12. **不要靠「诊断页显示的来源 IP」判断是否从公网进来**！这个环境里防火墙有大量 `snat ip to 192.0.2.10`（反射规则）+ `lan` 区 `masq=1` → **源地址被统一改写成路由器 LAN IP**，页面永远显示「内网」。**正确判据是防火墙 DNAT 计数器**（`nft list ruleset | grep "端口"` 看 `counter packets N bytes M`，公网专用那条），或 `tcpdump -i any -n "port X"` 抓真实源 IP。the user 曾因这个误判被冤枉（他是 30 公里外用流量，却被说成「没关 WiFi」）。
13. **改 Caddyfile 必须 `caddy validate` 通过再 restart**（顺序反了会把全部站点一起打挂）。**指令层级错位 = 整个服务起不来**：`flush_interval` 是 `reverse_proxy` 的**子指令**，放在 site 块顶层会报 `unrecognized directive: flush_interval` → Caddy 起不来 → **七站全断**（2026-09-23 接 HA 时实际踩过）。
14. **Home Assistant 反代必 400 Bad Request** —— 精确定位法：逐个头做对照实验，**只要 `X-Forwarded-For` 有值就 400**（其它头全部正常）。根因：HA 默认不信任任何代理，收到 XFF 就拒。**正确修法不是 strip 掉 XFF**（否则 HA 把所有客户端都看成反代 IP，IP 封禁会误伤自己），而是让 HA 信任反代：
    ```yaml
    http:
      use_x_forwarded_for: true
      trusted_proxies:
        - 192.0.2.10/32   # Caddy 所在容器 CT <ID>
        - 127.0.0.1/32
    ```
15. **HA 装在 CT <ID> 的 Docker 容器 `homeassistant` 里** —— 配置在宿主 `/opt/ha-config/configuration.yaml`（映射进容器的 `/config`）。**CT <ID> 根本没有 `/config`**，直接 `pct exec 201 -- cat /config/...` 必报 No such file。改配置：先 `cp` 备份，再 `pct exec 201 -- printf "%b" "..." >> /opt/ha-config/configuration.yaml`，然后 `pct exec 201 -- docker restart homeassistant`（约 35 秒起）。**别用 `yaml.safe_load` 当重启卡点**——HA 的 `!include` 自定义标签会让标准解析器报 `ConstructorError`，但 HA 本身认。
16. **反代目标是 DHCP 的会自己变，必须先钉静态租约**（`uci add dhcp host` + MAC）。2026-09-23 实测：HA 的 CT <ID>（MAC `00:00:00:00:00:00`）IP 从 `.172` 漂到 `.175`，用户照旧地址填就 `No route to host`。**拿到旧 IP 先查路由器 `/tmp/dhcp.leases` 按 MAC 对齐**，对不上再全网段扫端口验证（`192.0.2.10/24` 扫 8123 找到 `.175` 和 `.219` 两台）。

17. **80/443 被联通封死入站 = 「必须带端口」的唯一原因**（2026-10-07 三重实证）：家宽入站 80/443 全部超时，18443/18088 等非标端口秒通；uci 规则 `user-https`(443)/`user-http`(80) 存在且正确，但 nft 计数器长期 `packets 0 bytes 0`——包根本没到路由器，18443 同期几百个包。**在内网测不能证明对外通**：fw4 会生成 `192.0.2.10/24 → WAN IP` 的 reflection 规则，家里访问 443 走反射秒开，极易误判 443 是好的（the user 就这么被误导：家里能开、外面开不了）。对外只能用非标端口，或 ICP 备案后找运营商开白（家宽基本无望）。
18. **外部视角的两个可用探测法**（不用等 the user 手动试）：`curl "https://r.jina.ai/https://域名:端口/"` 用对方云端浏览器真访问——200/正文=外部可达，`TimeoutError: page.goto 15000ms`=不可达；`curl -x http://127.0.0.1:7899 …`（本机 mihomo 境外出口，先用 `ip-api.com/line?fields=query` 确认出口 IP 不是你家 WAN IP）。最后回 `nft list ruleset | grep 'dnat ip to'` 看计数器涨没涨，形成「外部打 → 路由器收没收到」的闭环。
19. **登录页 `/var/www/nav/login.html` 的 CSS 泄漏坑**：通用 `button{width:100%}` 会撑爆绝对定位的小按钮——`.eye` 没写 `width:auto` → 眼睛图标渲染到密码框正中、还透明盖住整行抢点击。同款页面只要还有裸 `button{…}` 全局选择器，新加的小按钮都必须显式 `width:auto`。加载点 `.dots` 原来常驻且紧贴按钮，已改默认 `display:none`、提交时加 `.show`。改这个文件不用重启服务（`user-auth` 每次请求 `open(LOGIN_PAGE)` 重读）。

## 排障顺序（从外到内）

1. DNS：`curl 'https://203.0.113.1/resolve?name=X&type=A'` → 应返回当前 WAN IP
2. 端口可达：手机流量实测（关 WiFi）
3. 防火墙：`nft list ruleset | grep "端口"` 看有没有 `dnat ip to`
4. 反代：`curl --noproxy '*' https://域名:端口/health`
5. 后端：`curl --noproxy '*' http://内网IP:端口/`

## 已在跑的服务（改前先看）

| 对外 | 后端 | 备注 |
|---|---|---|
| `nas.example.com:18443` | 192.0.2.10:**9443** | **绿联 DXP4800 / UGOS Pro 桌面**（Caddy 反代，跳过后端自签证书）|
| `firefox.example.com:18443` | 192.0.2.10:**5888** | **NAS Docker 云端 Firefox**（`ugreen/firefox:v2`，容器 5800→宿主 5888；Caddy 块含 `flush_interval -1` 支持流式/noVNC；导航页已加卡片，探活 200）|
| `https://test.example.com:18088` | CT <ID> 127.0.0.1:18080 测试页 | Caddy |
| `tcp+udp 25565` | 192.0.2.10:25565 | **MC 服务器**（CT100，平时封存）|
| `tcp 5001` | 192.0.2.10:5001 | talent-app（DNAT 直转，不经 Caddy）|
| `tcp 47984/47989/47990/48010` + `udp 47998/47999/48000/48002/48010` | 192.0.2.X123** | **Moonlight/Sunshine 串流**（9 条规则 `pc-tcp`/`pc-udp`，**非 HTTP 不走 Caddy**，直 DNAT）|
| `51413 / 56881 / 8800 / 38944 / 41641 / 41643` | NAS / TV-Proxy / Sunshine / Tailscale | the user 自己加的 |

**HTTP 服务全部走 Caddy 一个公网端口 `18443`，按域名分流**（`home/pve/nas/jellyfin/transmission`）；**非 HTTP 服务（游戏串流、MC）只能直 DNAT**，一个服务一组端口映射。
**`home` + `pve` 已加 Caddy Basic Auth**（用户名 `user`，凭据存 `~/.hermes/secrets/basicauth.txt` 600；浏览器会记住，体验是每浏览器输一次）。
**`<PASSWORD>`（PC）已加静态 DHCP 租约**：`00:00:00:00:00:00` → `192.0.2.10`（**端口映射前必须钉死 IP**，否则 DHCP 一变规则全废）。

**UGOS Pro 端口拓扑（查了才找到正门）**：`:80` → 307 → `:9999` → 307 → **`:9443`**（真入口，HTTP/2）；`:443` → 307 → `:9443`；`:9443/` → 307 **相对路径** → `/desktop/?os=ugospro`（反代会自动跟随，不用改）。
NAS 同机还跑着：22 SSH、111 rpcbind、139/445 SMB、2049 NFS、**8080 qBittorrent WebUI**、**8096 Jellyfin**。**默认只暴露 9443（桌面），其余全不透出**，要开哪个需逐个加映射。

**为什么公网直连比 Tailscale 打洞稳（the user 实测后原话「比 tailscale 打洞稳定多了」）**：Tailscale 在对称 NAT（学校）下打洞失败会退到 **DERP 中继**，绕远路、限速、换网络要重建；公网域名是**端到端直连**，无中继无打洞，能跑满 2000M 宽带，且**不用装客户端、能发链接给别人**。Tailscale 留着用于 SSH/内部管理/不暴露端口的场景。
