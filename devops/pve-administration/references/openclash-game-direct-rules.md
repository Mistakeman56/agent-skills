# OpenClash 游戏直连规则（LOL/腾讯游戏掉线修复，2026-08 实测）

用户打 LOL 疯狂掉线（一局重连十几次），根因是**游戏流量走了代理**（订阅节点全在香港/日本 anytls）。修复=在 OpenClash 配置 rules 顶部加游戏直连规则。

## 症状与诊断

**症状：** 游戏疯狂掉线/卡顿，但网页、视频正常（代理能通，只是游戏流量不该走代理）。

**诊断三步（30秒内）：**

```bash
# 1. 看目标设备（打游戏那台，如 192.0.2.10）的 UDP 游戏连接是否 UNREPLIED
cat /proc/net/nf_conntrack | grep "192.0.2.10" | grep udp | grep -vE 'dport=53|dport=1900'
# UNREPLIED = 发了包没收到回复；ASSURED+大流量 = 连接在跑但可能绕路

# 2. 测腾讯游戏服务器延迟（区分"某个节点线路断" vs "全走代理绕路"）
for ip in 203.0.113.1 203.0.113.1 203.0.113.1 203.0.113.1; do
  echo -n "$ip: "; ping -c 2 -W 1 $ip 2>&1 | grep -oE '[0-9]+% packet loss|[0-9.]+ ms' | tr '\n' ' '; echo
done
# 203.0.113.1(腾讯云)=18ms 但 203.0.113.1(山东联通LOL服务器)=100%丢包 → 要么该节点线路断，要么走代理

# 3. 确认代理在劫持游戏流量：看 Clash 监听端口
netstat -tulnp | grep -E '789[0-9]|clash'
# 7890=http, 7891=socks, 7892=proxy(mixed), 7893=mixed, 7895=tproxy
# 如果 conntrack 里游戏设备流量 src=192.0.2.10 sport=7892 → 走了代理
```

**判断逻辑：**
- 游戏设备流量走 `192.0.2.10:7892`（Clash proxy_port）→ 被代理了
- 腾讯云 IP 18ms 正常 + 特定游戏服务器丢包 → 该服务器节点线路问题（重排一局换服务器可能就好）
- **但根本问题是代理规则没把游戏流量直连** → 加直连规则一劳永逸

## 修复：在 rules: 顶部加游戏直连规则

**⚠️ iStoreOS 路由器没有 python3！** 用 sed 插入，不能用 python 脚本。

```bash
# 1. 备份
cp /etc/openclash/config/7.16.yaml /etc/openclash/config/7.16.yaml.bak.$(date +%Y%m%d%H%M%S)

# 2. 找到 rules: 行号（先确认，通常是 92 附近）
grep -n '^rules:' /etc/openclash/config/7.16.yaml

# 3. 用 sed 在 rules: 后插入游戏直连规则（92 是 rules: 行号，按实际替换）
sed -i '92a\
    - '"'"'DOMAIN-SUFFIX,qq.com,DIRECT'"'"'\
    - '"'"'DOMAIN-SUFFIX,qq.net,DIRECT'"'"'\
    - '"'"'DOMAIN-SUFFIX,tencent.com,DIRECT'"'"'\
    - '"'"'DOMAIN-SUFFIX,wegame.com,DIRECT'"'"'\
    - '"'"'DOMAIN-KEYWORD,leagueoflegends,DIRECT'"'"'\
    - '"'"'DOMAIN-KEYWORD,lol,DIRECT'"'"'\
    - '"'"'IP-CIDR,112.224.0.0/12,DIRECT,no-resolve'"'"'\
    - '"'"'IP-CIDR,60.29.0.0/16,DIRECT,no-resolve'"'"'\
    - '"'"'IP-CIDR,122.224.0.0/12,DIRECT,no-resolve'"'"'\
    - '"'"'IP-CIDR,27.221.0.0/16,DIRECT,no-resolve'"'"'\
    - '"'"'IP-CIDR,43.140.0.0/16,DIRECT,no-resolve'"'"'\
    - '"'"'IP-CIDR,119.28.0.0/16,DIRECT,no-resolve'"'"' /etc/openclash/config/7.16.yaml

# 4. 验证插入
sed -n '92,110p' /etc/openclash/config/7.16.yaml

# 5. 重启 OpenClash
/etc/init.d/openclash restart

# 6. 验证生效
ping -c 3 -W 1 203.0.113.1   # 应 0% 丢包 + 16ms 左右
```

**规则放最前面的原因：** Clash 规则从上到下匹配，命中即停。游戏域名/IP 规则必须放在 MATCH 兜底规则之前，否则被 `MATCH,SSRDOG`（全代理）截胡。

## 覆盖的 IP 段（腾讯/LOL 常用服务器）

| IP段 | 归属 |
|---|---|
| 112.224.0.0/12 | 山东联通（LOL 对战服务器，用户实测丢包节点） |
| 60.29.0.0/16 | 天津联通（对战服务器） |
| 122.224.0.0/12 | 腾讯游戏节点 |
| 27.221.0.0/16 | 腾讯游戏节点 |
| 43.140.0.0/16 | 腾讯云 |
| 119.28.0.0/16 | 腾讯云 |

## 关联

- 同思路已有 Steam 直连规则修复（见 SKILL.md "MATCH catch-all规则把游戏/Steam流量走代理" pitfall）——Steam 用 `DOMAIN-SUFFIX,steampowered.com/steamcontent.com/steamgames.com/steamstatic.com,DIRECT`
- 订阅更新会改变 MATCH 行为：旧订阅 `MATCH,DIRECT`（全直连），新订阅 `MATCH,SSRDOG`（全代理）。用户更新订阅后掉线/变慢，先查 MATCH 行。
- ICMP 正常 ≠ 游戏不卡：游戏用 UDP，ping 用 ICMP，两条路径。完整 UDP 丢包排查见 SKILL.md 对应小节。
