# 动态公网 IP + DDNS + 反向代理：把内网服务暴露到公网

目标：`https://你的域名:端口` → 任何人任何网络可访问家里的服务，IP 变了自动跟上。
四步链路，缺一不通：**取 IP → DDNS 写 A 记录 → 反向代理 → 端口可达**。

## 0. 先判定到底有没有「真公网 IPv4」

别信客服口径，用三条硬指标实测：

| 检查 | 命令 | 判定 |
|---|---|---|
| WAN 口地址 vs 出口地址 | `ip -4 addr show pppoe-wan` 对比 `curl -s http://ip.3322.net` | **两者一致 = 无二次 NAT** |
| 是否落在私网/CGN 段 | 看 WAN IP 是否在 `10/8`、`172.16-31/12`、`192.168/16`、`100.64.0.1/10` | 落在里面 = **没公网 IP**（CGN 是最常见的"假公网"） |
| 拨号方式 | `ip -4 addr show pppoe-wan` 看 `peer <运营商BNG>` | **PPPoE 直拨 = 光猫已桥接**，中间没有一层 NAT |

分档结论：
- **真·动态公网 IPv4**（PPPoE 直拨 + 真公网段）→ 本文件整套可用。
- **CGNAT / 二次 NAT** → 端口转发无效，别折腾 DDNS，直接用 Tailscale/内网穿透。
- **固定公网 IP** → 少了 DDNS 那步，其余相同。

**⚠️ 入站是否真可达，看 nftables 计数器，不要靠外部探测站。** 外部端口探测服务常超时/无结果，
而自家已有的转发规则自带计数器，`counter packets N bytes M` 里 N>0 就是铁证（有外部包进来了）：
```bash
ssh -p 2222 root@ROUTER "nft list ruleset | grep -E 'dnat ip to|accept' | grep -v 'saddr 192.168'"
```

**⚠️ 用户会误以为"只有 IPv6 能公网访问"。** 家宽普遍默认分配公网 IPv6（AAAA 这半边容易配），
而 IPv4 那半边（A 记录 + DDNS）往往**根本没配**。先查 DNS 有无 A 记录再下结论：
```bash
curl -s "https://203.0.113.1/resolve?name=HOST&type=A"    # 无 Answer = IPv4 那半边没配
curl -s "https://203.0.113.1/resolve?name=HOST&type=AAAA"
```

## 1. DDNS 取 IP：给 Lucky 一个「变量命令」

Lucky 的动态域名里有个变量（如 `{ipv4Addr}`），取值方式选**指令**。命令必须**只输出 IP + 一个换行**。

**取值优先级（前两个都是本地读取，亚毫秒返回；不要把外网回显放第一位）：**
```sh
# ① 逻辑接口（接口改名也不受影响，最稳）
ubus call network.interface.wan status | jsonfilter -e '@["ipv4-address"][0].address'

# ② PPPoE 网卡直读
ip -4 addr show pppoe-wan | awk '/inet /{sub(/\/.*/,"",$2); print $2; exit}'

# ③ 兜底：外网回显
```

**⚠️ PITFALL: 路由器上国外 IP 回显站常常不通。** `api.ipify.org` / `ifconfig.me` 在国内软路由上经常返回空，
而**国内的 `http://ip.3322.net` 可用**。兜底列表把国内站放前面，并且对返回值做格式校验（非 IP 就跳过下一个），
否则会把空字符串写进 DNS 记录。

**⚠️ PITFALL: 变量命令必须做「拒绝内网地址」保护。** 拨号空窗期/接口 down 时会读到 `10.x` 之类，
一旦写进公网 DNS 就是长时间故障（TTL 600 起）。脚本里必须拒绝 `10/8`、`172.16-31/12`、`192.168/16`、
`100.64-127/10`（CGN）、`127/8`、`169.254/16`，并校验每个 octet ≤ 255；校验不过就 `exit 1`（宁可不更新也不写错）。

**⚠️ PITFALL: 同步间隔别设几十秒。** IP 变化频率很低（PPPoE 可能几周不变），而 DNS 服务商 API 有限频。
设 **300–600 秒**即可。TTL 建议 600；要更快收敛可设 60。

部署位置放 **SATA/数据分区**（如 `/mnt/sata1-4/lucky/`），别放 `/usr/bin`——固件升级会冲掉。

**验证写入外部 DNS 后必须从公网侧读回**（多家公共解析器交叉，不能只看本机）：
```bash
for r in "https://203.0.113.1/resolve" "https://doh.pub/dns-query"; do
  curl -s -H 'accept: application/dns-json' "$r?name=HOST&type=A"
done
# 比对解析结果 == 路由器当前 WAN IP
```

## 2. 反向代理：前端/后端字段方向（最常填反）

| 字段 | 填什么 |
|---|---|
| **前端地址** | **匹配的域名**，如 `test.example.com` —— **不带 `http://`** |
| **后端地址** | **内网服务**，如 `http://192.0.2.10:18080` —— **要带协议头** |

前端 = 客户端输入的地址（匹配条件）；后端 = 转发目标。

**⚠️ PITFALL: 两个字段填反会形成自指循环，症状极具迷惑性。** 后端填成域名时，Lucky 会去请求那个域名
→ 解析到自家公网 IP → 命中自家的端口转发 → 落到**另一个完全不相关的服务**。
表面看"反代在工作（返回 200）"，实际返回的是别人家服务的页面。
**判据：拿目标服务的特征串去 grep 反代返回的 HTML**，没命中就是没转发到目标。
```bash
ssh -p 2222 root@ROUTER 'curl -s -H "Host: test.example.com" http://127.0.0.1:5001/ | grep -o "特征串"'
```
**⚠️ 同一个匹配条件有两条规则时先怀疑「掉到默认规则」**——域名带了协议头、目标多写了端口（如 `http://IP:18080:5001`，
一个 URL 不能有两个端口）都会让规则失效而落入默认规则。用 `curl -H "Host: ..."` 精确测每条规则。

## 3. ⚠️ 端口可能已被 DNAT 劫持（Lucky 永远收不到外部流量）

如果防火墙里已有端口转发：
```
meta nfproto ipv4 tcp dport 5001 dnat ip to 192.0.2.10:5001  comment "!fw4: talent"
```
那么**所有进 5001 的流量（含到路由器本机的）都会被 DNAT 送走**，Lucky 在 5001 上的反代**从外部永远不可达**。

**排查顺序（反代"配好了却打不开"必做）：**
1. `nft list ruleset | grep "dport <PORT>"` —— 有 `dnat ... to` 就是被劫持，**换端口**，别试图改这条规则
2. `curl -H "Host: <域名>" http://127.0.0.1:<PORT>/` 从路由器本机测（走 OUTPUT 链，不经 prerouting DNAT）
   - 本机能拿到目标页 → 反代没问题，问题在端口/防火墙
   - 本机拿到的是别的服务 → 见第 2 节，字段填反或掉默认规则

**建议给测试/新服务单独开一个高位端口**（如 18088），不要挤在已有服务的端口上。

## 4. 防火墙：Lucky 的「防火墙自动放行」会自己加规则

**先查再动手。** Web 服务设置里的「防火墙自动放行」开着时，Lucky 会自己写入 nftables：
```bash
nft list ruleset | grep -E "tcp dport <PORT> accept"
```
有这条就**不需要人工改防火墙**——这遵守"不碰 OpenClash/nftables 自建表"的铁律。
若必须手动加，走 **uci firewall**（写 `/etc/config/firewall`，重启后仍有效，且与现有转发规则同一套机制），
**不要 `nft add rule`**（fw4 reload 就丢）。改前全量备份 `/etc/config/firewall` + `nft list ruleset`。

另外：fw4 的 `ct status dnat accept` 会让 **DNAT 转发自动放行**，不用再改 input 链——需要"能进但不改防火墙"时，
用一条 DNAT 转发规则是风险最低的做法。

## 5. 80/443 被运营商封 → 非标端口 + SSL 走 DNS-01

家宽 80/443 入站普遍被封，所以：
- 访问地址必须**带端口**（`http://host:18088`）。用户说"域名打不开"时，第一件事是确认**他有没有带端口**。
- HTTPS 证书不能用 HTTP-01（需要 80 端口），改用 **DNS-01 验证**（TXT 记录，完全不碰 80/443）。
  Lucky 的 SSL 模块支持 DNS 服务商 API（阿里云等），前提是有 DNS 的 API 密钥。

**⚠️ PITFALL: "端口被占用" ≠ "运营商封锁"，两件事必须分清。** 用户把监听端口改成 443 报"被占用"，
那是**本地监听冲突**（软件没抢到端口），不是包进不来。封锁与否只能在端口有人监听之后才测得出来。
**80/443 默认被路由器自带的 LuCI 管理界面（`uhttpd`）占着**（`uci show uhttpd` 看 `listen_http`/`listen_https`）。
要用 443 就先把它挪走（如 `uci set uhttpd.main.listen_https='0.0.0.0:9443' && uci commit uhttpd && /etc/init.d/uhttpd restart`），
后台的 HTTP 入口（80）不受影响。**这是改路由器管理入口，动之前先备份 `/etc/config/uhttpd` 并告知用户后台 HTTPS 地址会变。**

**⭐ 泛域名证书是 DNS-01 独有的红利，能吃就吃。** HTTP-01 不支持通配符，DNS-01 支持。
域名列表一次填 `*.example.com,example.com`（通配符**不覆盖裸域**，所以两个一起填），
以后任意子域都自动被同一张证书覆盖并自动续期，不用逐个申请。

**⚠️ PITFALL: 证书绑定入口是条件渲染的，TLS 开关不开就看不见。** Lucky 的 Web 服务弹窗里只有一个「TLS」
开关（当前多为"禁用"），**证书下拉框只在 TLS 打开后才出现**。用户问"找不到绑定证书的地方"时，答案永远是
**先把 TLS 开关打开**，而不是去找别的菜单。若打开后仍无证书框，把「操作模式」从"简易模式"切成"定制模式"
——证书、强制 HTTPS 等高级项通常只在定制模式里露出。绑定后提醒用户访问时**必须写 `https://`**。
用完的测试服务及时下线，每条转发/放行规则都是公网入口。

## 6. 链路验证用「来源判定」测试页，别用空白页

测试页必须能让用户一眼看出流量从哪来，否则"打不开"和"从内网打开"无法区分。必备字段：
- **服务端看到的客户端 IP**（大字）+ 自动判定：私网段/CGN/Tailscale → 内网；真公网 → **链路已打通**
- `Host`、`X-Forwarded-For`、`X-Real-IP`、`User-Agent`（验证反代有没有传对头）
- 端点：`/`（诊断页）、`/health`（返回 OK）、`/ip`（纯文本 IP，给脚本校验）

部署为 **systemd 服务**（不是 nohup/后台 job）——否则会随宿主进程 cgroup 一起死。
**用户最终验证要用手机关 WiFi 开数据流量**，在家用 WiFi 上永远显示"内网访问"。

## 7. Lucky 无界面自动化（只有 Web 登录、没有 SSH 可改配置时）

配置文件 `/etc/config/lucky.daji/*.lkcf` 是**加密二进制，不可直接改**，只能走 HTTP API：

| 用途 | 接口 |
|---|---|
| 登录 | `POST /api/login`，**body 必须是 JSON**（表单会回 `Error parsing login request`） |
| 业务操作 | `PUT /api/lucky/service?option=<模块>` |
| 模块列表 | `GET /api/modules/list` |

未登录统一回 `{"msg":"login invalid","ret":-1}`。
**登录 body 的字段名是大写首字母**：`{"Account":"...","Password":"...","TwoFA":""}`。用小写 `username`/`password` 会一律回 `IncorrectAccountOrPassword`，看起来像密码错，其实只是字段名错。
**⚠️ 排查顺序：先确认是 JSON、再确认字段名是 Account/Password，最后才怀疑密码**（表单回"解析错误"、JSON 回 `IncorrectAccountOrPassword` = 格式对、字段对，才轮到凭据错）。另外面板设置页显示的密码可能是**未保存的表单值**，不等于已生效的密码。

**⚠️ 登录试错有代价**：「登录连续错误最大次数」默认 10 次，超了**必须重启 Lucky 才能再登**（会中断它承载的反代）。凭据不对就**立刻停手问用户**，绝不换着法子猜。

接口清单可从 Web UI 的主 JS 里挖（`curl $BASE/static/js/lucky_index-*.js | grep -oE '"/api/[a-zA-Z0-9_/-]+"'`）；但**载荷字段名要去懒加载 chunk 里找**——主 JS 只有 `function qJ(e){return An({url:"/api/login",method:"post",data:e})}` 这种转发壳，真正的 `{Account,Password,TwoFA}` 构造在 `static/js/lucky_Login-*.js`。先零风险摸清协议，再花一次登录配额，比盲试 5 次省事。

## 8. 决策表：用反代还是用 DNAT

| 需求 | 用什么 |
|---|---|
| 只想快点验证链路通不通 | **DNAT 端口转发**（不需 Lucky 登录，且自动放行） |
| 一个端口按域名分流多个服务 | **Lucky 反向代理** |
| 要 HTTPS 证书 | **Lucky 反代 + DNS-01**（80/443 被封时唯一可行） |
| 只给自己/家人访问 | **Tailscale**（零防火墙改动、零暴露面） |
| 要**长期由 agent 用命令行维护**（不想点界面）| **`ddns-scripts_aliyun`**（OpenWrt 官方 DDNS，`/etc/config/ddns` 是明文 UCI，`uci` 一条命令增删改查） |

**⚠️ DDNSTO ≠ DDNS，别给已经有公网 IP 的用户推它。** 它是**内网穿透**：流量走第三方中转服务器，
慢、依赖对方、数据过别人手。真·公网 IPv4 下直连更快更安全，DDNSTO 只在 CGN/无法入站时才有意义。
它的配置虽是明文 UCI（`/etc/config/ddnsto`）可脚本化，但**不要因为它"好改"就选它**——先看它解决的是不是同一个问题。
同理，判断一款 DDNS 工具值不值得用，看**它的配置是不是文本/UCI**：加密私有格式（如 Lucky 的 `*.lkcf`）
只能靠 HTTP API 驱动，明文 UCI 才是 agent 能长期无痛维护的形态。

**暴露面提醒：** 每条转发/放行规则都是公网入口。远程桌面、下载器这类高危服务建议改走 Tailscale，
不要挂端口转发。给用户列一份端口暴露面清单并标注风险等级。
