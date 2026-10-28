# 把 OpenClash 从 redir-host 切到 fake-ip

## 为什么该切（用户会问「你说 host 好，到底哪个好」）

| | fake-ip | redir-host |
|---|---|---|
| 规则靠什么匹配 | **域名**（网关返回 198.18.x.x 假IP，Clash 反查回域名） | **真实 IP**（先解析再拿 IP 匹配） |
| 国内站误判 | 少 | **多**：CDN 域名几百个 IP 混着国内海外段 → 被判成国外 → 命中尾部 `MATCH,<分组>` → 绕代理 → 卡 |

**判据**：看配置里的规则尾部。若是 `RULE-SET,<国内域名集>,DIRECT` → `GEOIP,CN,DIRECT` → `MATCH,<代理组>`，那 redir-host 下所有 CDN 误判都会掉进最后的 MATCH。**这就是「开了 OpenClash 国内站变慢」的确切机制，答用户时就这么说。**

## 切换命令（三个 UCI 键，少一个都不行）

```sh
uci set openclash.config.en_mode='fake-ip'          # 上游配置文件的模式
uci set openclash.config.operation_mode='fake-ip'   # 运行时模式（两个都要改，别只改一个）
uci set openclash.config.enable_redirect_dns='1'    # fake-ip 必须靠 DNS 劫持把域名交给 Clash
u commit openclash
uci set openclash.config.enable='1'
uci commit openclash
/etc/init.d/openclash start        # 用 start，不要用 restart
```

`enable_redirect_dns` 原值 0（DNS 劫持关）在 redir-host 下能用，**fake-ip 下必须为 1**，否则客户端拿不到 198.18.x.x，fake-ip 形同没开。

## 坑 1：追加过滤列表不补换行 = 内核拒绝启动

`/etc/openclash/custom/openclash_custom_fake_filter.list` **最后一行没有换行符**。直接 `echo "*.foo.com" >>` 会拼成 `*.log.tailscale.io*.example.com`，内核报：

```
level=fatal msg="Parse config error: dns.fake-ip-filter[145]: invalid domain \"*.log.tailscale.io*.example.com\": \"*\" wildcard must occupy the entire label"
```

好在 OpenClash 会自己走完 Step1-5 回滚，**网络不受影响**（但用户会看到插件又关了）。修法：`sed -i 's|\(\*\.log\.tailscale\.io\)\*\.user\.top|\1|'`。以后追加前先 `tail -c1 file | od -c` 确认有换行。

## 坑 2：内核启动失败会把 enable 重置为 0

失败一次后 `/etc/init.d/openclash restart` 会输出 `[Warning] OpenClash Now Disabled, Need Start From Luci Page, Exit...`。**必须先 `uci set openclash.config.enable='1'` 再 `start`**（restart 的 start 分支会检查这个开关）。

## 坑 3：改 fake-ip 前必须把内网域名写进白名单

不写 → 内网域名也返回 198.18.x.x → **自建门户/HA/NAS 全被假 IP 劫持**。白名单文件同上，加 `example.com` 和 `*.example.com`。（`*.lan` / `*.local` 默认已有。）

## 坑 4：切完后全屋 DNS 只有 Clash 一个上游（安全网要确认在）

OpenClash 开 DNS 劫持时**直接改 UCI**（不是写 /tmp/dnsmasq.d/）：

```
dhcp.@dnsmasq[0].server='127.0.0.1#7874'
dhcp.@dnsmasq[0].noresolv='1'      # 不再读 resolv.conf.auto
dhcp.@dnsmasq[0].cachesize='0'     # 缓存交给 Clash 做
```

后果：**Clash 一挂全屋 DNS 就死**。两个安全网必须都在：

```sh
# 1. 看门狗（procd 实例，不要在 crontab 里找）
ubus call service list '{"name":"openclash"}'   # 应有 "openclash-watchdog": running: true
ps w | grep -i watchdogd                            # 应看到 openclash_watchdog.sh
# 2. 停插件自动还原上游：init 脚本的 save_dnsmasq_server() 在改之前把原 server
#    存进 openclash.config.dnsmasq_server，stop 时自动写回
uci -q get openclash.config.dnsmasq_server
```

**别因为「怕 Clash 挂了 DNS 也挂」而给 dnsmasq 多加一个公共上游** —— 那会造成两个默认上游，dnemasy 随机返回真实 IP 或假 IP，破坏 fake-ip 的域名匹配。用看门狗解决。

Clash 自己那侧的上游配置（`9.1.yaml` 的 `dns` 段）才是真正起作用的：`nameserver: [203.0.113.1, 203.0.113.1]` + `fallback: [203.0.113.1, 203.0.113.1]` + `fallback-filter: {geoip: true, geoip-code: CN}`。

## 坑 5：验完要清尾，别把节点密码打进对话

`grep` 代理配置时**会带出节点的 `password:`**。在拿到证据后立刻把密钥字段滤掉再输出（`sed -E 's/password: [^,}]+/password: <REDACTED>/'`）。订阅链接里的节点密码不该出现在会话记录里。

## 验证方法（别只看插件显示 running）

```sh
# 核心：国外域名应返回 198.18.x.x，国内/内网应返回真实 IP
nslookup www.google.com  127.0.0.1   # ⇒ 198.18.0.5      ✅ fake-ip 生效
nslookup www.baidu.com   127.0.0.1   # ⇒ 203.0.113.1   ✅ 国内直连
nslookup example.com    127.0.0.1   # ⇒ 203.0.113.1  ✅ 白名单保住门户
```

再从局域网客户端（不是路由器自身）验证实际吞吐与可达性。**已实测：国内 Tencent 镜像 61.5 MB/s、阿里 14.9 MB/s；google/github/youtube 全部 HTTP 200。**

---

# 路由器脚本铁律

**BusyBox 上没有 `timeout` 命令。** 写了 `timeout 4 nslookup ...` 会立刻 `ash: timeout: not found` 并以非零码退出 → 循环里每一项都显示 ❌，**看起来像「所有 DNS 服务器全挂了」，实际是测试脚本自己有 bug**。

**排查 DNS 时不要只在路由器上自测，务必从局域网客户端交叉验证一遍。** 真实案例：路由器上跑 7 个公共 DNS 全部报「不响应 ❌」，从容器测同一个解析器全部 12-27ms ✅。

路由器上要限时就用 `nslookup` 自己的参数或 `&`+`sleep`+`kill`，别指望 `timeout`。
