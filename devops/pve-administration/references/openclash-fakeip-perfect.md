# OpenClash fake-ip 做到「完美」—— 配置 + 五个坑

## 目标状态（逐项验收，全部要满足）

| 检查项 | 期望值 |
|---|---|
| 国内域名 | **真 IP**，首次 ~20ms、缓存 <1ms |
| 国外域名 | **假 IP `198.18.x.x`**，<1ms 秒回 |
| 自己的域名（白名单/内网） | **真 IP** 且走 DIRECT |
| 兜底规则 | `MATCH,<代理组>` —— **绝不能是 DIRECT** |
| 内核 | running |

## 3 个 UCI 键必须一起改

```sh
uci set openclash.config.en_mode='fake-ip'
uci set openclash.config.operation_mode='fake-ip'
uci set openclash.config.enable_redirect_dns='1'
uci commit openclash && /etc/init.d/openclash restart
```

只改其中一个 → OpenClash 拒绝启动并**自安全回滚**（网络不受影响，但白忙）。

## 必开：假 IP 持久化（不开客户端必卡）

```sh
uci set openclash.config.store_fakeip='1'
```

**为什么**：假 IP 映射默认只在内存。OpenClash 一重启映射表重建，但**客户端还缓存着旧假 IP** → 连到没人认领的 `198.18.x.x` → 死等。（这就是 the user said 的「手机一动不动」「一卡一卡」。）

> **判定特征**：`curl -w` 报 `连=0.000000s` + `总=20.00s`，且 Clash 日志里**完全没有这条连接**（域名都映射不出来）。对比「快速失败（0.1s）」就说明连接到了 Clash、是上游/节点问题，不是假 IP 问题。
>
> **修**：开 `store_fakeip` + 让客户端**断开 WiFi 重连**（或杀掉 App 重开）以清掉旧假 IP。

## DNS：只留国内，清掉被墙的 fallback

`openclash.config.enable_custom_dns='1'`，然后遍历 `openclash.@dns_servers[N]`：
- `group='nameserver'` / `'default'` → **全开**（203.0.113.1 / 203.0.113.1 / 203.0.113.1 / doh.pub / dns.alidns.com 都是国内的）
- `group='fallback'` → **全关**。默认开着的 `dns.google/dns-query` 与 `dns.cloudflare.com/dns-query` 在国内基本连不上，配合 `fallback-filter:{geoip:true}` 会让非国内解析干等超时 → 整屋「一卡一卡」。

**用 UCI 改，不要改 yaml** —— 订阅一更新 yaml 就被覆盖，UCI 不会。

---

## ⚠️ 坑 1：兜底被改成 `MATCH,DIRECT` → 谷歌/油管全挂

**症状**：国内全快、`gstatic`/`github` 能通，但 `google.com`/`youtube.com`/`wikipedia.org` 死等或快速失败。

**第一步：看真正在跑的配置，不是源配置**

```sh
ps w | grep clash | grep -v grep      # 找 -f 指向的路径，通常是 /etc/openclash/<name>.yaml
grep -nE '^- (MATCH|FINAL)' /etc/openclash/<name>.yaml
```

`/etc/openclash/config/<name>.yaml` 是**源**，`/etc/openclash/<name>.yaml` 才是**运行时**，两者可能不一样！

**常见元凶**：`/etc/openclash/custom/openclash_custom_overwrite.sh`（OpenClash 官方「自定义覆写」钩子，**每次生成配置都会执行**）。查里面有没有：

```sh
grep -rn 'MATCH' /etc/openclash/custom/
```

用 `ls --time-style=full-iso` 看 **Birth**（创建时间）能定位是哪次操作留下的。

**别搞错开关**：`/usr/share/openclash/yml_rules_change.sh` 里也有 `.gsub(match_pattern,'MATCH,DIRECT')`，但它在 `enable_rule_proxy=1` 时才跑（默认 0，`$3` 是 shell 展开进去的）。**不要为了修这个把 `enable_custom_clash_rules` 关掉** —— 那会连带废掉用户的自定义规则文件（Tailscale 直连、指定域名走代理等）。

## ⚠️ 坑 2：从路由器自己测代理，永远失败

`openclash.config.router_self_proxy='0'` 时，路由器自身流量**不走代理**，但它拿到的仍是**假 IP** → 连 `198.18.x.x` 无人接管 → 死等。

> **结论：所有「能不能翻墙」的验收必须在局域网客户端上做**（容器 / PC / 手机）。在路由器上 `ssh` 跑 curl 只会得出假结论，而且会让人误判成「配置又坏了」。

## ⚠️ 坑 3：重启后有 1~2 分钟收敛期

实测：重启刚完 16 并发只有 **152 Mbps**，收敛后 **1153 Mbps**。
**「开完 OpenClash 网变慢」这个观察，先排除收敛期再下结论**，也别在收敛窗口里做验收/测速。

## 事实：OpenClash 不吃吞吐（A/B 实测）

同一秒、同一源、16 并发：Clash **开 1153 Mbps** vs **关 1080 / 1122 Mbps** → 无差异。
多流吞吐的天花板在**服务器/CDN 侧**，不是 Clash、也不是 J4125（load 0.27）。别把「下载跑不满」赖到代理头上。

---

## 附带：iStore 自带测速「恒 1M」的真相

```
/usr/share/systools/speedtest.run  →  /usr/bin/speedtest [-s $SERVER]     # Ookla CLI
```

Ookla 服务器列表里**国内只剩一台**：`Duke Kunshan University - Kunshan (id 30852)`。它现在是坏的：

```
Idle Latency: 62.53 ms
Download:     1.07 Mbps   (data used: 1.2 MB)
Download:     FAILED
[error] Cannot open socket
```

**用户说的「一直 1M」就是它 —— 服务器侧挂了，与线路无关。**

`Cannot open socket` **不是本机资源耗尽**（同机实测：conntrack 1033/1638400 = 0.1%、file-max 121794、内存剩 5.2GB、进程 260）。

> **任何基于 Ookla 的测速（含 iStore 自带的）都测不出 2000M** —— 国内节点没了，只能跨境。要测国内线路请用多线程国内 CDN 拉取，见 `references/router-throughput-diagnosis.md`。

---

## 改动铁律

1. 备份：`/etc/config/openclash` + `/etc/openclash/<name>.yaml` + `/etc/openclash/history/<name>.db`
2. 改完**实测验收**：国内→真 IP、国外→假 IP、自建→直连、谷歌/油管 200、吞吐不掉
3. 输出任何 yaml/日志前先过滤：`sed -E 's/(password|uuid|psk|secret|token|Clash):[^ ]*/\1:<REDACTED>/g'`
4. 重启只能用 `/etc/init.d/openclash restart`；`uci commit` 不会自动重载
5. 路由器 BusyBox 无 `base64`、无 `timeout` → 脚本一律本地 `write_file` + `scp`，别在路由器上拼长命令
