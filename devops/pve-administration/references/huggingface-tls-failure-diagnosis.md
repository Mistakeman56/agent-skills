# HuggingFace TLS 握手失败诊断 (2026-05-19)

## 问题现象

从 Hermes LXC 202 (192.0.2.10) 无法访问 HuggingFace：
- `curl https://huggingface.co/api/models?search=qwen&limit=1` → HTTP 000 超时
- `curl -x http://Clash:hrFM183F@192.0.2.10:7890` → 同样超时
- 错误：`SSL_ERROR_SYSCALL`、`unexpected eof while reading`

## 排障过程

### 1️⃣ 网络层检查（一切正常）
```
Google 直连: 200 ✓
OpenClash 代理: 200 ✓
软路由 (192.0.2.10) ping: 0.1ms ✓
LXC 200 (192.0.2.10) ping: 0.06ms ✓
203.0.113.1 ping: 190ms ✓
```

### 2️⃣ SSL 握手追踪（发现关键线索）
```
CONNECT tunnel established, response 200
TLSv1.3 (OUT), Client hello (1):
OpenSSL SSL_connect: SSL_ERROR_SYSCALL
```
CONNECT 建隧道成功，ClientHello 发出后无响应。

### 3️⃣ DNS 检查（找到根因）
```
getent hosts huggingface.co
→ 203.0.113.1    ← Clash Fake IP!
```
DNS 返回了 `203.0.113.1`（Clash fake-ip 池 `198.18.0.1/16`），这表示 Clash 劫持了 DNS。

### 4️⃣ SSH 进软路由查 Clash 规则
```bash
sshpass -p '<PASSWORD>' ssh root@192.0.2.10
```
查到：
- OpenClash **已开启** (`enable=1`)
- 模式：`mode: rule`
- 默认规则：`MATCH,DIRECT` ← 匹配不到的域名全部直连
- 规则配置：`/etc/openclash/config/ddrdog.yaml`
- 自定义规则：`/etc/openclash/custom/openclash_custom_rules.list`
- 无任何 `huggingface` 或 `brightdata` 规则

## 根因

**Clash Fake-IP 模式 + 规则缺失**：

1. LXC 202 请求 `huggingface.co` DNS
2. DNS 被劫持到 Clash → 返回 Fake IP `203.0.113.1`
3. Clash 规则列表中没有 HuggingFace → 命中 `MATCH,DIRECT`
4. DIRECT = 直连 → 流量直接发往 `203.0.113.1:443`
5. 此 IP 是 Clash 虚拟分配的，**没有真实服务器在此监听**
6. 发送 ClientHello 后永远收不到 ServerHello → 超时 → `SSL_ERROR_SYSCALL`

**即使走代理也一样**：代理建立了 CONNECT 隧道到 `203.0.113.1:443`，但目标仍然是这个虚拟 IP。

## 修复方案

在 OpenClash 自定义规则文件添加 HuggingFace 走代理：

```yaml
# 添加到 /etc/openclash/custom/openclash_custom_rules.list
- DOMAIN-SUFFIX,huggingface.co,SSRDOG
- DOMAIN-SUFFIX,brightdata.com,SSRDOG
```

OpenClash 会定期重载，或 `service openclash restart` 强制生效。

## 类似问题的诊断口诀

**"DNS 给 Fake IP + 代理也超时 = 规则缺失"**

### 快速诊断命令

```bash
# 第1步：查 DNS 是否被 Clash 劫持
getent hosts <domain>                 # 返回 198.18.x.x → 被劫持

# 第2步：查当前 Clash 规则
ssh root@192.0.2.10 \
  "grep -i '<domain>' /etc/openclash/config/ddrdog.yaml"   # 无结果 → 规则缺失
ssh root@192.0.2.10 \
  "cat /etc/openclash/custom/openclash_custom_rules.list"   # 查自定义规则

# 第3步：确认 MATCH 规则（默认兜底）
ssh root@192.0.2.10 \
  "grep MATCH /etc/openclash/config/ddrdog.yaml"           # 如果是 DIRECT → 需要加规则

# 第4步：加规则（如果需要）
ssh root@192.0.2.10 \
  "echo '  - DOMAIN-SUFFIX,<domain>,SSRDOG' >> /etc/openclash/custom/openclash_custom_rules.list"
```

### 区分 Fake-IP 的两种失败模式

| 特征 | 模式A：工具拒绝 Fake IP | 模式B：MATCH,DIRECT 静默失败 |
|------|----------------------|--------------------------|
| 报错 | "blocked address"、"internal IP" | `SSL_ERROR_SYSCALL`、`HTTP 000` |
| DNS | 198.18.x.x | 198.18.x.x |
| curl -x 代理 | ✅ 可通（代理建 HTTP 隧道） | ❌ 也超时（目标 IP 不存在） |
| 修复 | 换工具 / 加代理 env | 加 Clash 规则走代理 |
| 典型受害者 | webclaw (Rust CLI) | HuggingFace、无代理规则的境外站 |
