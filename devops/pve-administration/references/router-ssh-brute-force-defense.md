# Router SSH Brute-Force Defense (OpenWrt/iStoreOS Dropbear)

## Detection

### 查攻击记录
```bash
# 最近的认证失败
logread | grep "dropbear.*Bad password"

# 统计攻击来源 IP（BusyBox 兼容写法）
logread -l 5000 | grep "Bad password\|Exit before auth" | grep -o "from [0-9.]*" | sort | uniq -c | sort -rn
```

### 查当前 ESTABLISHED SSH 连接
```bash
netstat -tnp | grep ":22" | grep -v "192.0.2"
```

**关键判断：** `ESTABLISHED` 只是 TCP 三次握手完成，认证还没通过。查 `authpriv.notice` 确认有无成功登录：
```bash
logread | grep "authpriv.notice" | grep "succeeded\|Password auth" | grep -v "192.0.2"
```

### IP 归属查询
```bash
curl -s --noproxy "*" "http://ip-api.com/json/IP?fields=country,regionName,city,isp,org,as" --max-time 5
```

## ⚠️ CRITICAL: fw3 vs fw4 Detection

**Before running any mitigation, check what firewall system the router uses!**

```bash
which fw4 && echo "fw4 (nftables)" || echo "fw4 not found"
which fw3 && echo "fw3 (iptables)" || echo "fw3 not found"
nft list tables 2>/dev/null | head -3
```

- **iStoreOS 24+ / OpenWrt 23.05+** → **fw4/nftables** — DO NOT use `iptables` commands
- **Old OpenWrt (<23.05)** → fw3/iptables

**On fw4/nftables systems, these commands are DANGEROUS:**
- `iptables -I INPUT -s IP -j DROP` — works temporarily but conflicts with nftables
- `iptables-save > /etc/iptables.rules` — may corrupt nftables state
- `fw3 flush` — **will wipe OpenClash TProxy/DNS/nftables rules, crashing all proxy traffic**
- `nft flush ruleset` — completely destroys all firewall rules

## Mitigation

### Step 1: 踢掉当前攻击连接
```bash
NETSTAT_OUTPUT=$(netstat -tnp 2>/dev/null)
FOREIGN_PID=$(echo "$NETSTAT_OUTPUT" | grep "ATTACK_IP" | grep "ESTAB" | awk "{print \$NF}" | cut -d"/" -f1)
kill $FOREIGN_PID
```

### Step 2: 封禁 IP（nftables method — safe for fw4 systems ✅）
```bash
cat >> /etc/nftables.d/99-custom-blocklist.nft << 'EOF'
define blocklist = {
    203.0.113.1,
    203.0.113.1,
}
chain input_blocklist {
    type filter hook input priority 0; policy accept;
    ip saddr $blocklist drop
}
EOF
/etc/init.d/firewall restart
```

### Step 3: 防火墙规则（UCI 持久化）
```bash
# 允许内网访问 SSH
uci add firewall rule
uci set firewall.@rule[-1].name="Allow-SSH-LAN"
uci set firewall.@rule[-1].src="lan"
uci set firewall.@rule[-1].dest_port="2222"
uci set firewall.@rule[-1].proto="tcp"
uci set firewall.@rule[-1].target="ACCEPT"

# 拒绝外网访问 SSH
uci add firewall rule
uci set firewall.@rule[-1].name="Deny-SSH-WAN"
uci set firewall.@rule[-1].src="wan"
uci set firewall.@rule[-1].dest_port="2222"
uci set firewall.@rule[-1].proto="tcp"
uci set firewall.@rule[-1].target="REJECT"

uci commit firewall
/etc/init.d/firewall reload
```

### Step 4（可选）：改 SSH 端口
```bash
uci set dropbear.main.Port='2222'
uci commit dropbear
/etc/init.d/dropbear restart
```

## fw3 Flush Recovery (iStoreOS 24+)

If `fw3 flush` was accidentally executed:

```bash
# 1. SSH 应该还能进（INPUT 默认 ACCEPT）
ssh -p 2222 root@192.0.2.10

# 2. 重启 OpenClash（重建 nftables 规则链）
/etc/init.d/openclash restart

# 3. 重启防火墙
/etc/init.d/firewall restart

# 4. 等待 10s 后检查
nft list ruleset | grep -i clash | wc -l   # 应 > 0
nslookup google.com 127.0.0.1              # 应返回 198.18.x.x
```

### Recovery 后必须做三件事
1. **修正 WAN 安全基线**: `uci set firewall.@zone[1].input='REJECT'` + `forward='REJECT'`
2. **配置快照**: `sysupgrade -b /root/backup-$(date +%F).tar.gz`
3. **检查公网暴露面**: `netstat -tulpen | grep "0.0.0.0:"`

## Agent 防火墙操作纪律

**永远不要直接执行:** `fw3 flush`, `fw4 flush`, `nft flush ruleset`, `iptables -F`, `uci commit firewall` + restart, `/etc/init.d/openclash restart`

**正确模式:** agent 生成命令 → 发给用户审核 → 用户手动执行。

## 实际攻击数据（2026-05-25 实测）

| IP | 归属 | 主机商 | 频率 | 特点 |
|----|------|--------|:----:|------|
| 203.0.113.1 | 贵州贵阳 | 华为云 | ~5次/秒 | 主力攻击者 |
| 203.0.113.1 | 北京 | 腾讯云 | 单次 | 扫描型 |
| 203.0.113.1 | 广东广州 | 腾讯云 | 单次 | 扫描型 |
| 203.0.113.1 | 波兰华沙 | 私人 AS200730 | 持续 | 晚间活跃 |

## 为什么 OpenWrt 容易被扫
- SSH 端口 22（公网扫描器最优先扫的端口）
- 允许 root 直接登录（默认配置）
- 无 fail2ban/rate-limit 机制
- 公网 IP 直接暴露无保护

## Pitfalls
- `logread` 重启后清空
- `ESTABLISHED` ≠ 已认证
- UCI 规则比 iptables-save 持久
- 改端口后先测试再断开
- OpenWrt 用 dropbear 非 openssh，用 `logread` 而非 `journalctl`
- BusyBox grep 不支持 `-P`
