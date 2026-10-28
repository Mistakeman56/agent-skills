# OpenClash 代理不工作 — 完整诊断路径（2026-06-05）

## 问题描述
OpenClash显示running，端口全部监听，但所有代理流量（包括国内直连的DIRECT流量）超时。

## 诊断步骤

### Step 1: 基础状态检查
```bash
/etc/init.d/openclash status  # → running ✅
ps | grep clash                # → PID 7434, 内存1.3GB ✅
netstat -tlnp | grep clash     # → 7890/7891/7892/7893/7895/9090 全部监听 ✅
```

### Step 2: nftables规则检查
```bash
nft list chain inet fw4 openclash          # TCP redirect → :7892 ✅
nft list chain inet fw4 openclash_mangle   # UDP tproxy → 7895 ✅
nft list chain inet fw4 openclash_output   # OUTPUT redirect → :7892 ✅
```

### Step 3: 代理端口测试
```bash
# 7890 (mixed-port): 返回407（需要认证）→ 端口在工作
# 7891 (socks): 返回000 → 连接失败
# 7892 (redir): 返回000 → 连接失败
# 7895 (tproxy): 未测试
```

### Step 4: 关键发现 — 配置文件不匹配
```bash
# 实际启动命令
cat /proc/7434/cmdline → /etc/openclash/clash -d /etc/openclash -f /etc/openclash/ddrdog.yaml

# 用户配置（config目录）
grep 'mixed-port' /etc/openclash/config/ddrdog.yaml → 7890
grep 'listen' /etc/openclash/config/ddrdog.yaml → 0.0.0.0:1053

# 实际运行配置（根目录）
grep 'mixed-port' /etc/openclash/ddrdog.yaml → 7893
grep 'listen' /etc/openclash/ddrdog.yaml → 0.0.0.0:7874
```

**端口对照表：**

| 组件 | 用户配置 | OpenClash实际 | nftables期望 |
|------|---------|-------------|-------------|
| mixed-port | 7890 | 7893 | — |
| redir-port | — | 7892 | redirect→7892 |
| tproxy-port | — | 7895 | tproxy→7895 |
| DNS listen | 1053 | 7874 | redirect→53 |

### Step 5: 网络本身正常
```bash
wget https://www.baidu.com  → 200 ✅
wget https://www.google.com → 超时 ❌（GFW封锁，需要代理）
ping 203.0.113.1                → 通 ✅（209ms）
```

### Step 6: 旧配置的rules对比
旧配置（ddrdog.yaml）包含新配置没有的重要规则：
- Tailscale直连（PROCESS-NAME tailscaled, IP-CIDR 100.64.0.1/10）
- 特定设备IP直连（192.0.2.10, 192.0.2.10）
- 端口配置（redir-port: 7892, tproxy-port: 7895, external-controller secret）
- MATCH兜底规则：旧配置 `MATCH,DIRECT` vs 新配置 `MATCH,SSRDOG`

**重要：** 不能简单删除旧配置，需要把旧配置的自定义规则同步到新配置，或者把旧配置的端口修改为正确值。

**⚠️ 用户明确教训（2026-06-05）：** "你确定这个旧配置是错的呗，我就怕旧配置是有用的你给删了还得重新配"、"要是我一开始同意让你把旧配置删了就大错特错了全乱了"。**在确认两个配置文件的差异之前，绝对不要删除任何一个。** 旧配置可能包含用户手动添加的重要规则（Tailscale直连、设备IP白名单等），删除后需要重新配置，且用户会非常不满。

### Step 7: SO_ORIGINAL_DST 故障检测（redir-port 特有）

当 nftables REDIRECT 到 redir-port (7892) 后，Clash 日志可能出现两种模式：

**正常模式**（SO_ORIGINAL_DST 工作）：
```
[TCP] 192.0.2.10:59006 --> comm.app.autohome.com.cn:443 match RuleSet(ChinaMax) using DIRECT
```
→ 目标地址被正确还原为真实域名，规则正常匹配。

**异常模式**（SO_ORIGINAL_DST 失败）：
```
[TCP] 127.0.0.1:35802 --> 127.0.0.1:7892 match IPCIDR(127.0.0.0/8) using DIRECT
```
→ 目标地址未被还原，Clash 看到的是 127.0.0.1（REDIRECT 改写后的地址），匹配了 127.0.0.0/8 规则走 DIRECT。

**诊断方法：**
```bash
# 查看 Clash 日志中 redir-port 连接的目标地址
grep '7892' /tmp/openclash.log | tail -20
# 如果全部是 127.0.0.1:7892 → SO_ORIGINAL_DST 失败
# 如果有真实域名/IP → SO_ORIGINAL_DST 正常，问题在别处
```

**可能原因（按实测概率排序）：**

1. **🔴 Sniffer 未配置 redir 端口（2026-06-05 实测根因）**
   - Clash 的 sniffer 只处理配置中指定端口的流量（默认 80, 443, 8080-8880）
   - redir-port (7892) 不在 sniffer 端口列表中
   - 因此 sniffer 无法对 7892 端口的流量执行 `override-destination`，Clash 看到的仍是 127.0.0.1
   - **验证方法**：检查 conntrack 表，如果 conntrack 记录了原始目标地址但 Clash 日志仍显示 127.0.0.1，则确认是 sniffer 问题
   ```bash
   # conntrack 应该记录了原始目标地址（如 203.0.113.1:443）
   cat /proc/net/nf_conntrack | grep 7892 | grep -v 127.0.0.1
   # 如果有非 127.0.0.1 的记录 → conntrack 正常，问题在 Clash sniffer
   ```
   - **修复方案 A（改 sniffer 配置）**：在 sniffer.sniff.HTTP.ports 中添加 7892
   ```yaml
   sniffer:
     enable: true
     override-destination: true
     sniff:
       HTTP:
         ports:
         - 80
         - 7892  # ← 添加
         - 8080-8880
   ```
   - **修复方案 B（切换 tproxy 模式，推荐）**：tproxy 不修改目标地址，不需要 sniffer 获取原始目标。UDP 已在用 tproxy 且工作正常。

2. **内核 conntrack 模块未加载**（REDIRECT 依赖 conntrack 保存原始目标地址）
3. **nftables 规则顺序问题**（REDIRECT 在 conntrack 之前执行）
4. **Clash 版本不支持该平台的 SO_ORIGINAL_DST**

**注意区分：** 日志中 `127.0.0.1:xxxxx --> 127.0.0.1:7892` 的连接是**从路由器本机发起的**（如 curl 测试），不是 LAN 设备流量。LAN 设备流量应该显示源 IP 为 192.0.2.X。

## 教训
1. **不要假设哪个配置文件是"正确的"** — 两个都可能有用户需要的内容
2. **先对比rules差异再决定修复方案** — 旧配置可能有用户手动添加的重要规则
3. **端口不匹配是最隐蔽的代理故障** — 所有端口都在监听但就是不工作
4. **Clash 日志中的 127.0.0.1 目标地址 = SO_ORIGINAL_DST 故障** — 与端口不匹配是不同的故障模式
5. **排查要刨根问底，不要急于修复** — 用户说"你继续排查吧"，深度诊断（conntrack、sniffer配置、nftables链分析）比直接动手改规则更有价值
6. **不要直接修改nftables规则** — OpenClash管理的链（openclash、openclash_mangle等）应该通过OpenClash配置修改，直接nft操作会破坏状态
7. **修改前先备份** — `nft list ruleset > /tmp/nftables-backup.txt`，但备份nftables规则不够，还需要确认OpenClash的运行时状态
8. **用户说"只看不改"时严格遵守** — 即使你发现了问题根因，也先报告再等用户决定
