# OpenClash 全屋网速慢 — 快速排查流程

当用户反馈"网线电脑测速只有 20-40M" / "看抖音一卡一卡" / "内网外网都不到 100M" / "百度都超时了" 时，不要怀疑宽带——**先查 OpenClash**。

## 三步排查（10 秒出结论）

### Step 1: 从路由器测真实宽带速度

```bash
ssh root@192.0.2.10 'speedtest -s 24447 --accept-license --accept-gdpr 2>&1 | grep -E "Download|Upload"'
```

**正常值**：几百 Mbps（用户宽带是千兆）
**如果 speedtest 也慢** → 宽带/光猫/线路问题（概率 <5%）

### Step 2: 查 `MATCH`（兜底规则）是否被改成 `DIRECT`

```bash
ssh root@192.0.2.10 'grep "MATCH" /etc/openclash/config/ddrdog.yaml'
```

**正常**: `MATCH,SSRDOG`（未匹配规则走代理）
**异常**: `MATCH,DIRECT` → **立即修复**

修复：
```bash
ssh root@192.0.2.10 "sed -i 's/MATCH,DIRECT/MATCH,SSRDOG/' /etc/openclash/config/ddrdog.yaml && /etc/init.d/openclash restart"
```

### Step 3: 对比 `speedtest` vs `curl 直连`

```bash
ssh root@192.0.2.10 '
speedtest -s 24447 --accept-license --accept-gdpr 2>&1 | grep Download
curl --noproxy "*" -s -o /dev/null -w "直连百度: %{speed_download}*8/1000000 Mbps\n" --max-time 5 https://www.baidu.com
'
```

**如果 speedtest 几百 Mbps 且 curl 直连也正常** → 问题在我方（Hermes/subagent 的网络环境），清理完了

**如果 speedtest 几百 Mbps 但 curl 直连只有几百 Byte/s** → 这是 Fake-IP 吞吐衰减（详见 `openclash-fakeip-throughput-penalty.md`）—— Clash 内核转发拖慢了国内直连流量，不是配置错误。这是 OpenClash Fake-IP 模式的架构性限制。

## 两种不同的"慢"——要区分

| 症状 | 根因 | 修复 |
|------|------|------|
| **外网也慢**（GitHub/Google 超时，梯子失效） | `MATCH,DIRECT` — 兜底规则被改成直连 | `sed` 改回 `MATCH,SSRDOG` + 重启 |
| **内网国内慢**（百度/抖音/腾讯云慢，但梯子能出国） | Fake-IP 吞吐衰减 — 正常架构限制 | 看国内内容时关 OpenClash，或双客户端策略 |

**验证方法**: 看 `/tmp/openclash.log` 里 PC 流量的规则匹配，`match Match using DIRECT` 说明外网流量也被直连了（异常）。`match RuleSet(ChinaMax) using DIRECT` 说明国内流量直连（正常架构限制）。

## 排障路径示意图

```
用户报"网速只有20-40M"
  │
  ├─ Step 1: speedtest 从路由测宽带
  │    ├─ 几百 Mbps ✅ → 宽带没问题
  │    └─ 几十 Mbps ❌ → 报运营商
  │
  ├─ Step 2: grep "MATCH" ddrdog.yaml
  │    ├─ MATCH,DIRECT ❌ → 修 MATCH 规则（本文 Step 2）
  │    └─ MATCH,SSRDOG ✅ → 检查下一层
  │
  └─ Step 3: curl 直连百度 vs speedtest
       ├─ 都正常 → 环境问题（查自己）
       └─ curl 慢但 speedtest 快 → Fake-IP 衰减（见 reference）
```

## Clash API 实时连接排查

如果用户说"某App/网站走代理了导致慢"，不要猜——用 Clash API 抓实时连接看实际流量。详见 `references/clash-api-connection-debugging.md`。

```bash
# 抓连接数据到本地处理
ssh root@192.0.2.10 "curl -s -H 'Authorization: Bearer <PASSWORD>' http://127.0.0.1:9090/connections" > /tmp/conns.json
# 然后用 execute_code 过滤特定设备IP + 关键词
```

## 常用命令速查

```bash
# 从路由测宽带
speedtest -s 24447 --accept-license --accept-gdpr

# 查看 PC 流量走什么规则
grep "192.0.2.10" /tmp/openclash.log | tail -10

# 查看当前规则文件
tail -5 /etc/openclash/config/ddrdog.yaml

# 重启 OpenClash
/etc/init.d/openclash restart

# 对比原始备份的 MATCH 规则
grep "MATCH" /etc/openclash/config/ddrdog.yaml.bak.permanent

# 查看 custom_rules.list
cat /etc/openclash/custom/openclash_custom_rules.list
```

## 此用户环境特有问题（历史记录）

- OpenClash **config/ddrdog.yaml** 已被确认至少一次被改写成 `MATCH,DIRECT`（永久备份 `/etc/openclash/config/ddrdog.yaml.bak.permanent` 记录为 `MATCH,SSRDOG`）
- custom_rules.list 已被清理到仅含 Tailscale + NAS 直连的干净版本
- 路由器 SSH: `root@192.0.2.10` / `<PASSWORD>!`
- OpenClash Dashboard: `http://192.0.2.10:9090` / Secret: `<PASSWORD>`

## SSH 暴力破解攻击快速检查

网络排查过程中**顺便看一眼**路由器的 SSH 日志——如果被暴力破解扫满了，也会间接影响路由性能。

```bash
# 查最近攻击
logread -l 500 | grep -c "Bad password"

# 查攻击来源 IP
logread -l 500 | grep "Bad password\|Exit before auth" | grep -o "from [0-9.]*" | sort | uniq -c | sort -rn | head -5

# 如果有攻击，快速封禁（iptables + iptables-save 持久化）
logread -l 2000 | grep "Bad password\|Exit before auth" | grep -o "from [0-9.]*" | sort -u | grep -v "192.0.2" | while read ip; do
  ip=$(echo $ip | sed 's/from //')
  iptables -I INPUT -s $ip -j DROP 2>/dev/null && echo "封禁: $ip"
done
iptables-save > /etc/iptables.rules
```

详见 `devops/router-ssh-security` skill。网络排查完毕后顺手把封了的 IP 写入 memory 备忘。
