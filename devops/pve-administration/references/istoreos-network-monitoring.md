# iStoreOS 网络设备监控

## 概述

在iStoreOS/OpenWrt路由器上部署设备流量监控系统，包括：
- nftables独立监控表（计数器统计每设备流量）
- 数据采集脚本（定时读取计数器+ping检测在线状态）
- LuCI兼容的Web监控页面（/www/目录，不修改LuCI核心）
- Hermes微信推送日报+异常告警

## 部署架构

```
iStoreOS路由器 (192.0.2.10:2222)
├── nftables表: inet devmon（独立于fw4防火墙）
│   ├── 计数器: c_XXX_up / c_XXX_down（每设备一对）
│   ├── input链: priority 0, policy accept（上行计数：设备→路由器）
│   └── postrouting_down链: priority -15, policy accept（下行计数：路由器→设备）
├── 脚本: /usr/bin/devmon.sh（数据采集）
├── Web页面: /www/devmon.html（静态HTML）
├── CGI接口: /www/cgi-bin/devmon.cgi（返回JSON）
└── cron: */5 * * * * /usr/bin/devmon.sh

Hermes Agent
├── 每日9:00 微信推送日报
└── 每30分钟 检查异常（设备离线告警）
```

## ⚠️ 关键Pitfall: nftables保留字

**`monitor` 是nftables的保留关键字！** 创建表时不能用 `monitor` 作为表名，否则报语法错误：

```
Error: syntax error, unexpected monitor, expecting string
```

**解决方案：** 使用其他名称，如 `devmon`、`netmon`、`devtrack`。

```bash
# ❌ 错误
nft add table inet monitor

# ✅ 正确
nft add table inet devmon
```

## 部署步骤

### 1. 备份当前nftables规则

```bash
ssh -p 2222 root@ROUTER "nft list ruleset" > backup-nftables-$(date +%Y%m%d).conf
```

### 2. 创建独立监控表

```bash
# 完全独立于fw4，不影响任何防火墙规则
nft add table inet devmon

# 为每设备创建命名计数器
nft add counter inet devmon c_130_up
nft add counter inet devmon c_130_down
# ... (每设备两个计数器)

# 创建input链（上行计数：设备→路由器）
nft add chain inet devmon input { type filter hook input priority 0 \; }

# 创建forward_lan链（下行计数：必须priority -10，在fw4之前处理！）
# ⚠️ 不要用 priority 0 或 -5，fw4会先处理完转发流量，自定义链抓不到
nft add chain inet devmon forward_lan "{ type filter hook forward priority -10 ; policy accept ; }"

# 添加计数规则（纯计数，不拦截）
# 上行：input链（设备发给路由器的包）
nft add rule inet devmon input ip saddr 192.0.2.10 counter name c_130_up
# 下行：forward_lan链（路由器转发给设备的包）
nft add rule inet devmon forward_lan ip daddr 192.0.2.10 counter name c_130_down
# ... (每设备两条规则)
```

**安全保证：**
- 新表完全独立于fw4
- 链的policy是accept，不会拦截任何流量
- 只添加计数器，不修改现有规则
- 随时可以 `nft delete table inet devmon` 完全删除

### 3. 部署数据采集脚本

脚本功能：
- 读取nftables计数器获取累计流量
- 与上次采集比较计算差值（本次增量）
- ping检测设备在线状态
- 输出JSON格式数据

```bash
# 部署到路由器
scp -P 2222 devmon.sh root@ROUTER:/usr/bin/devmon.sh
ssh -p 2222 root@ROUTER "chmod +x /usr/bin/devmon.sh"
```

### 4. 部署Web监控页面

**安全原则：** 只操作/www/目录，不修改LuCI核心文件。

```bash
# HTML页面 → /www/devmon.html
scp -P 2222 devmon.html root@ROUTER:/www/devmon.html

# CGI脚本 → /www/cgi-bin/devmon.cgi
scp -P 2222 devmon-cgi.sh root@ROUTER:/www/cgi-bin/devmon.cgi
ssh -p 2222 root@ROUTER "chmod +x /www/cgi-bin/devmon.cgi"
```

**⚠️ PITFALL: uhttpd 可能缺少 CGI 解释器配置！** 默认的 uhttpd 配置有 `cgi_prefix '/cgi-bin'` 但不一定有 `list interpreter` 行。如果 CGI 脚本直接访问返回空白，需要手动添加：

```bash
# 检查是否有 interpreter 配置
uci show uhttpd.main.interpreter 2>/dev/null
# 如果报错 → 需要添加

# 添加 CGI 解释器
uci add_list uhttpd.main.interpreter=".cgi=/bin/sh"
uci commit uhttpd
/etc/init.d/uhttpd restart
```

验证：`curl -s http://192.0.2.10/cgi-bin/devmon.cgi` 应返回 JSON 数据。

### 5. 设置路由器cron

```bash
ssh -p 2222 root@ROUTER "
crontab -l 2>/dev/null | grep -q 'devmon.sh' || \
  (crontab -l 2>/dev/null; echo '*/5 * * * * /usr/bin/devmon.sh >/dev/null 2>&1') | crontab -
/etc/init.d/cron start
/etc/init.d/cron enable
"
```

### 6. 设置Hermes微信推送

**日报任务（每天9:00）：**
```
prompt: SSH到路由器获取设备监控数据，格式化为中文日报
schedule: 0 9 * * *
```

**异常告警（每30分钟）：**
```
prompt: 检查设备状态，全部在线则回复"✅"，离线则详细报告
schedule: */30 * * * *
```

## 数据格式

### devmon.sh 输出JSON

```json
{
  "ts": 1782307619,
  "date": "2026-06-24",
  "time": "21:26:59",
  "devices": [
    {
      "ip": "192.0.2.10",
      "on": 1,           // 1=在线, 0=离线
      "tu": 1234567,     // 累计上传(bytes)
      "td": 8901234,     // 累计下载(bytes)
      "du": 12345,       // 本次上传增量(bytes)
      "dd": 56789        // 本次下载增量(bytes)
    }
  ]
}
```

### CGI端点

`GET http://192.0.2.10/cgi-bin/devmon.cgi` → 返回最新JSON数据

## 流量格式化

```bash
# bytes → 可读格式
fmt_bytes() {
    local b=$1
    if [ "$b" -eq 0 ]; then echo "0 B"; return; fi
    local units="B KB MB GB TB"
    local i=0
    while [ "$b" -ge 1024 ] && [ "$i" -lt 4 ]; do
        b=$((b / 1024))
        i=$((i + 1))
    done
    echo "$b ${units##* }"
}
```

## 清理/回滚

```bash
# 删除整个监控表（一键恢复原状）
ssh -p 2222 root@ROUTER "nft delete table inet devmon"

# 删除cron任务
ssh -p 2222 root@ROUTER "crontab -l | grep -v devmon | crontab -"

# 删除Web文件
ssh -p 2222 root@ROUTER "rm /www/devmon.html /www/cgi-bin/devmon.cgi"
```

## ⚠️ PITFALL: `ensure_rules()` 未确保表存在就创建链

**症状：** devmon.sh 运行报错 `Error: No such file or directory`，所有计数规则和链都未创建。首次部署或路由器重装后 nftables 表被清空时触发。

**根因：** `ensure_rules()` 函数只检查 chain 是否存在（`nft list chain`），但没有检查 table 是否存在。nftables 不允许向不存在的表添加链——必须先 `nft add table`。

**修复：** 在 `ensure_rules()` 开头加一行表存在检查：
```bash
ensure_rules() {
    # 先确保表存在（新增，关键！）
    nft list table inet devmon >/dev/null 2>&1 || nft add table inet devmon
    
    nft list chain inet devmon ingress_monitor >/dev/null 2>&1 || \
        nft add chain inet devmon ingress_monitor "{ type filter hook ingress priority -15 ; policy accept ; }"
    # ... 其余不变
```

**⚠️ 这是脚本自身的bug，不是部署步骤的问题。** 部署步骤（步骤2）已经创建了表，但路由器重启后如果表被清空（如持久化失败），脚本的自动恢复逻辑无法自愈。

## ⚠️ PITFALL: 路由器重启后 nftables 规则丢失（计数器归零）

**症状：** devmon.sh 输出所有设备流量为 0，但 ping 检测显示全部在线。

**根因：** iStoreOS 重启后，`inet devmon` 表中的**计数器定义保留了，但匹配规则（chains + rules）丢失**。计数器存在但没有任何规则引用它们，所以永远不增加。

**诊断：**
```bash
# 检查是否有 chain
nft list table inet devmon
# 如果只有 counter 定义没有 chain → 规则丢了

# 检查计数器是否在动
nft list table inet devmon | grep "packets [1-9]"
# 全部是 packets 0 → 确认规则丢失
```

**修复（添加匹配规则）：**
```bash
# 创建 input 链（上行）
nft add chain inet devmon input { type filter hook input priority 0 \; }

# 创建 forward_lan 链（下行，必须 priority -10！）
nft add chain inet devmon forward_lan "{ type filter hook forward priority -10 ; policy accept ; }"

# 给每个设备加规则
for ip in 130 148 184 159 198 113 109 169 238 167; do
  # 上行：设备→路由器（input chain）
  nft add rule inet devmon input ip saddr 192.0.2.$ip counter name c_${ip}_up
  # 下行：路由器→设备（forward_lan chain，priority -10 在 fw4 之前）
  nft add rule inet devmon forward_lan ip daddr 192.0.2.$ip counter name c_${ip}_down
done
```

**持久化（防止重启再丢）：**
```bash
# 1. 保存规则
nft list ruleset > /etc/nftables.conf

# 2. 加入启动脚本
echo "nft -f /etc/nftables.conf" >> /etc/rc.local
```

**验证：** 等 5 秒后检查计数器是否开始增长：
```bash
sleep 5 && nft list table inet devmon | grep "packets [1-9]"
```

## ⚠️ PITFALL: BusyBox grep 不支持 `-oP`（Perl 正则）和 `date -v-1d` 不兼容

**症状1：** devmon.sh 脚本运行报错 `grep: unrecognized option: P`，所有设备流量数据为 0。

**根因：** iStoreOS 使用 BusyBox 的精简版 grep，不支持 GNU grep 的 `-P`（Perl 正则）和 `-o`（只输出匹配部分）组合。

**修复：** 用 `grep + awk` 替代：
```bash
# ❌ BusyBox 不支持
nft list counter inet devmon "$1" 2>/dev/null | grep -oP 'bytes \K\d+'

# ✅ BusyBox 兼容
nft list counter inet devmon "$1" 2>/dev/null | grep "bytes" | awk '{print $2}'
```

**症状2：** devmon.sh 报错 `date: unrecognized option: v`，脚本中断。

**根因：** `date -v-1d` 是 macOS 语法（BSD date），BusyBox date 不支持 `-v`。devmon.sh 中的 fallback `date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d` 在 BusyBox 上两个都失败（BusyBox `-d yesterday` 需要特定编译选项）。

**修复：** 用 epoch 算术替代：
```bash
# ❌ macOS 语法，BusyBox 不支持
date -v-1d +%Y-%m-%d

# ✅ BusyBox 兼容（epoch 算术）
date -d "@$(($(date +%s)-86400))" +%Y-%m-%d
```

**⚠️ 注意：** `awk '{print $2}'` 中的 `$2` 在 shell 脚本中需要转义为 `\\$2` 或用单引号包裹整个 awk 表达式，否则 shell 会把 `$2` 当作变量展开。

## ⚠️ PITFALL: 下载计数（down）永远为 0 — fw4 转发链优先级问题

**症状：** 上行（up）计数器正常增长，但下行（down）计数器始终为 0。ping 检测在线，脚本无报错。

**根因：** 自定义 nftables 表的 forward 链（如 priority 0 或 -5）**不处理实际转发流量**。iStoreOS 的 fw4 防火墙在自己的 forward 链中处理转发，自定义表的 forward 链在 fw4 之后（或优先级不够低）执行，流量已经被 fw4 处理完毕不再经过自定义链。

**诊断：**
```bash
# 检查自定义forward链计数
nft list chain inet devmon forward | grep "packets [1-9]"
# 全部是 packets 0 → 链没抓到流量

# 检查fw4 forward链
nft list chain inet fw4 forward | head -5
# 如果有大量packets → 流量走的是fw4
```

**修复方案（三选一）：**

**方案A（推荐）：用 priority -10 的新链，比 fw4 先处理**
```bash
# 删除旧的forward链
nft delete chain inet devmon forward 2>/dev/null

# 创建priority -10的链（在fw4之前处理）
nft add chain inet devmon forward_lan "{ type filter hook forward priority -10 ; policy accept ; }"

# 添加下行计数规则
for ip in 130 148 184 159 198 113 109 169 238 167; do
  nft add rule inet devmon forward_lan ip daddr 192.0.2.$ip counter name "c_${ip}_down"
done
```

**方案B：在 fw4 表中直接添加规则（但重启后可能被 fw4 覆盖）**
```bash
# ⚠️ fw4 不认识自定义表的命名计数器，会报 "No such file or directory"
# 需要在 fw4 表中重新定义计数器，或使用无名计数器
nft add rule inet fw4 forward ip daddr 192.0.2.10 counter
```

**方案C：用 ip saddr 双向计数（不区分 up/down，只统计总量）**
```bash
# 在 input 链同时统计上行和下行（简化方案）
nft add rule inet devmon input ip saddr 192.0.2.$ip counter name c_${ip}_up
nft add rule inet devmon input ip daddr 192.0.2.$ip counter name c_${ip}_down
```

**⚠️ fw4 表的命名计数器不兼容问题：** 尝试在 fw4 表中引用 devmon 表的命名计数器会报 `Error: Could not process rule: No such file or directory`。nftables 命名计数器是表作用域的，fw4 无法识别 devmon 表中的计数器。解决方案是在 fw4 表中重新定义计数器，或使用方案A/B的无名计数器。

**验证：** 等 5 秒后检查 down 计数器：
```bash
sleep 5 && nft list table inet devmon | grep "packets [1-9]"
# 应该同时看到 up 和 down 计数器在增长
```

## ⚠️ PITFALL: IoT 设备下载计数为 0（forward_lan 方案失效）

**症状：** 即使用了 priority -10 的 `forward_lan` 链，IoT 设备（摄像头、传感器）的 down 计数器仍然为 0。上行正常。

**根因：** IoT 设备的特点是**几乎不接收外部数据**——它们主要往外推流（摄像头推视频、传感器上报数据）。fw4 的 `ct state established : accept` 会直接放行已建立连接的回包，不经过自定义链。而且这些设备确实很少收到从互联网到设备的转发流量。

**诊断：**
```bash
# 确认是真没流量还是链没抓到
# 用 postrouting 链测试（比 forward 链更靠后）
nft add chain inet devmon postrouting_test "{ type filter hook postrouting priority -15 ; policy accept ; }"
for ip in 130 148 184; do
  nft add rule inet devmon postrouting_test ip daddr 192.0.2.$ip counter name "c_${ip}_down"
done
sleep 5 && for ip in 130 148 184; do
  echo -n "c_${ip}_down: "
  nft list counter inet devmon "c_${ip}_down" 2>&1 | grep packets
done
```

**结论：** 如果 postrouting 有少量数据（如 2-3 个包）但 forward_lan 为 0，说明 IoT 设备确实很少收数据，这是**正常行为不是 bug**。

**最终方案：用 postrouting 链替代 forward_lan 做下行计数**
```bash
# 删除无效的 forward_lan 链
nft delete chain inet devmon forward_lan 2>/dev/null

# 用 postrouting 链（priority -15，比大多数链先处理）
nft add chain inet devmon postrouting_down "{ type filter hook postrouting priority -15 ; policy accept ; }"

for ip in 130 148 184 159 198 113 109 169 238 167; do
  nft add rule inet devmon postrouting_down ip daddr 192.0.2.$ip counter name "c_${ip}_down"
done
```

**⚠️ 重要：IoT 设备下载量天生很少。** 页面上"下载"列可能长期为 0 或个位数，这不是监控系统的问题，而是设备本身的特性。用户看到下载为 0 时不要误以为系统坏了。

## ⚠️ PITFALL: ingress hook 只能抓上行，不能抓下行

**症状：** 在 br-lan 接口用 `type filter hook ingress` 创建的链只能统计设备→路由器的上行流量，下行（路由器→设备）为 0。

**根因：** nftables 的 `ingress` hook 只捕获**进入**网桥接口的流量（设备发出来的）。发给设备的流量是**离开**网桥的（egress），但 `inet` family 不支持 `egress` hook。

**解决方案：** 不要用 ingress/egress hook，改用：
- **上行：** `input` hook（设备→路由器）
- **下行：** `postrouting` hook（路由器→设备，priority -15）

## ⚠️ PITFALL: ping在线检测不可靠——设备物理断电后仍显示在线

**症状：** 用户拔掉设备电源，devmon.sh仍报告 `"on":1`（全部在线），但用户明确知道设备已断电。

**根因：** devmon.sh用 `ping -c 1 -W 1` 判定在线状态。设备断电后：
1. **DHCP租约未过期**（`/tmp/dhcp.leases` 中的 expiry 时间戳仍然有效，默认租约1-24小时）
2. **ARP缓存保持 STALE/REACHABLE 状态**（`ip neigh show` 仍显示MAC映射）
3. **ping触发ARP重激活**：即使设备不在了，路由器的ARP缓存条目在STALE状态收到ping时会尝试刷新，如果缓存未过期就直接回复

**验证方法（对比nftables计数器差值）：**
```bash
# 第一次读计数器
nft list counter inet devmon "c_130_up" | grep bytes
# → bytes 60134

# 等30秒再读
sleep 30 && nft list counter inet devmon "c_130_up" | grep bytes
# → bytes 60134（没变）

# devmon.sh输出中的 du/dd 字段
# → "du":0, "dd":0, "su":0, "sd":0
# 结论：bytes没变 = 设备没有实际通信 = 已断电（即使ping通）
```

**判断逻辑：**
| ping结果 | 流量差值(du/dd) | 实际状态 |
|----------|----------------|----------|
| ✅ 通 | > 0 | **真在线** |
| ✅ 通 | = 0 | **假在线**（DHCP/ARP缓存，设备已断电） |
| ❌ 不通 | 任意 | **真离线** |

**改进方案（如果需要更准确的在线检测）：**
1. **nftables计数器差值法**（推荐）：对比前后两次采集的 `bytes` 值，连续2次 `du=0 && dd=0` 且 `su=0 && sd=0` 判定为离线
2. **DHCP租约过期时间检查**：读 `/tmp/dhcp.leases` 的 `ts`（expiry epoch），如果过期时间到了但设备没续租 → 离线
3. **ARP状态检查**：`ip neigh show | grep MAC | grep -v REACHABLE` → 非REACHABLE状态的设备可能已离线

**当前脚本设计：** devmon.sh只用ping判定在线，这是**已知的简化设计**。对于"设备管理日报"这种场景够用（第二天设备肯定已续租），但对于"实时离线告警"场景会误报。

**快速诊断脚本：** `scripts/check_device_online.sh` — 对比两次nftables计数器差值，准确判断设备是否真正在线。用法：在路由器上运行或通过SSH远程执行。

## 已知限制

1. **路由器重启后 nftables 规则可能丢失** — 见上方修复步骤，需持久化到 `/etc/nftables.conf` + `rc.local`
2. **无法看到具体访问了什么网站** — 需要DNS日志，更复杂
3. **conntrack表有大小限制** — 高并发时可能溢出，但不影响nftables计数器
4. **J4125 CPU性能有限** — 每5分钟ping10台设备+读计数器，CPU占用极低（<1%）

## ⚠️ PITFALL: DHCP 重新分配 IP 导致监控失效（MAC 自动发现方案）

**症状：** 路由器重启或 DHCP 租约过期后，部分设备变 `OFFLINE`，脚本报错找不到设备。

**根因：** devmon.sh 里 IP 是硬编码的（`IPS="130 148 184..."`），DHCP 重新分配后设备 IP 变了，脚本还在查旧 IP。

**最佳方案：MAC 地址自动发现。** MAC 是硬件固定的，不会变。

### 步骤 1：记录设备 MAC 地址

```bash
# 从 DHCP 租约表查 MAC
cat /tmp/dhcp.leases | grep -E "192.0.2\.(130|148|184)"
# 格式: <expiry> <MAC> <IP> <hostname> <client-id>
```

### 步骤 2：改写 devmon.sh 为 MAC 自动发现版

核心改动：
1. **MAC 列表替代 IP 列表**（MAC 硬编码，IP 从 DHCP 表动态查）
2. **`find_ip_by_mac()` 函数**：从 `/tmp/dhcp.leases` 按 MAC 查当前 IP
3. **`ensure_rules()` 函数**：每次运行前检查 nftables 规则是否匹配当前 IP，不匹配就自动更新
4. **JSON 输出包含 MAC 字段**：方便前端显示

**⚠️ DHCP 租约表字段顺序：** `$1=expiry, $2=MAC, $3=IP, $4=hostname, $5=client-id`

```bash
# ✅ 正确：MAC 是 $2，IP 是 $3
mac=$(echo "$line" | awk '{print tolower($2)}')
ip=$(echo "$line" | awk '{print $3}')

# ❌ 常见错误：MAC 和 IP 写反
mac=$(echo "$line" | awk '{print $3}')  # 这是 IP！
```

### 步骤 3：nftables 规则动态更新

```bash
ensure_rules() {
    # 确保链存在
    nft list chain inet devmon ingress_monitor >/dev/null 2>&1 || \
        nft add chain inet devmon ingress_monitor "{ type filter hook ingress priority -15 ; policy accept ; }"
    nft list chain inet devmon postrouting_monitor >/dev/null 2>&1 || \
        nft add chain inet devmon postrouting_monitor "{ type filter hook postrouting priority -15 ; policy accept ; }"
    
    for mac in $MACS; do
        ip=$(find_ip_by_mac "$mac")
        [ -z "$ip" ] && continue
        ip_last=$(echo "$ip" | cut -d. -f4)
        
        # 创建计数器（如果不存在）
        nft list counter inet devmon "c_${ip_last}_up" >/dev/null 2>&1 || \
            nft add counter inet devmon "c_${ip_last}_up" 2>/dev/null
        
        # 检查规则是否存在，不存在就添加
        nft list chain inet devmon ingress_monitor 2>/dev/null | grep -q "192.0.2.$ip_last" || \
            nft add rule inet devmon ingress_monitor ip saddr 192.0.2.$ip_last counter name "c_${ip_last}_up" 2>/dev/null
    done
}
```

**⚠️ `ether saddr/daddr` MAC 匹配在 BusyBox/OpenWrt nftables 上不可靠。** 尝试用 MAC 直接匹配会报 `Could not process rule: No such file or directory`。不要用 MAC 匹配 nftables 规则，而是让脚本从 DHCP 表查 IP 后用 IP 匹配。

### 验证

```bash
# 运行脚本，确认输出包含 MAC 和正确 IP
/usr/bin/devmon.sh | python3 -m json.tool
# 期望：每个设备都有 "mac": "xx:xx:xx:xx:xx:xx" 和正确的 "ip"
```

## ⚠️ PITFALL: CGI 端点读取旧数据（必须执行脚本而非读文件）

**症状：** Web 页面能打开但数据不更新，速率全为 0，累积流量不变。

**根因：** CGI 脚本只是 `cat /tmp/devmon/latest.json`，读取的是上次 cron 运行时写入的静态文件。浏览器每次请求 CGI 都拿到同一份旧数据，没有触发新的数据采集。

**修复：** CGI 端点必须执行采集脚本，不能只读文件：

```bash
# ❌ 错误：读旧文件
cat /tmp/devmon/latest.json

# ✅ 正确：执行脚本获取实时数据
/usr/bin/devmon.sh 2>/dev/null
```

CGI 脚本内容：
```bash
#!/bin/sh
echo "Content-Type: application/json"
echo "Access-Control-Allow-Origin: *"
echo ""
/usr/bin/devmon.sh 2>/dev/null
```

**注意：** 这意味着每次页面刷新都会触发一次数据采集（ping + 读 nftables 计数器）。对于 10 台设备来说开销极低（<0.1秒），但如果设备数量很多（50+），可以考虑加缓存（如 3 秒内重复请求返回缓存）。

## 相关文件

- 路由器备份: `~/.hermes/router-backup-nftables-YYYYMMDD.conf`
- 采集脚本: `/usr/bin/devmon.sh`（路由器上）
- Web页面: `/www/devmon.html`（路由器上）
- CGI接口: `/www/cgi-bin/devmon.cgi`（路由器上）
