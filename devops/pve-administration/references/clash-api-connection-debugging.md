# Clash API 实时连接排查

当用户反馈"某个App/网站走代理了导致慢"时，用 Clash API 抓实时连接数据分析。

## 前置信息

- Clash API: `http://192.0.2.10:9090`
- Secret: `<PASSWORD>`
- 路由器无 python3，但有 jq

## 三步排查

### Step 1: 抓连接数据

```bash
ssh root@192.0.2.10 "curl -s -H 'Authorization: Bearer <PASSWORD>' http://127.0.0.1:9090/connections" > /tmp/conns.json
```

### Step 2: 按设备IP过滤 + 按流量排序

```python
import json
with open('/tmp/conns.json') as f:
    data = json.load(f)
conns = data.get('connections', [])

# 指定设备IP
TARGET_IP = "192.0.2.10"  # PC

for c in conns:
    meta = c.get('metadata', {})
    src = meta.get('sourceIP', '')
    if TARGET_IP not in str(src):
        continue
    host = meta.get('host', '')
    up = c.get('upload', 0)
    dn = c.get('download', 0)
    chain = '→'.join(c.get('chains', []))
    rule = c.get('rulePayload', '')
    print(f"{host:50s} ↑{up:>10} ↓{dn:>10} {chain:20s} {rule}")
```

### Step 3: 按关键词过滤特定App

```python
# 过滤QQ音乐
keywords = ['qq', 'tencent', 'qqmusic', 'tencentmusic', 'bdycdn']
for c in pc_conns:
    host = c['host'].lower()
    if any(k in host for k in keywords):
        print(f"{c['host']} | {c['chain']} | ↑{c['upload']} ↓{c['download']}")
```

## 返回字段说明

| 字段 | 含义 |
|------|------|
| `metadata.host` | 目标域名 |
| `metadata.sourceIP` | 发起设备IP |
| `metadata.destinationIP` | 目标IP |
| `chains` | 走的代理链（`['DIRECT']` = 直连，`['SSRDOG']` = 走代理） |
| `rulePayload` | 命中的规则名 |
| `upload` / `download` | 累计上传/下载字节数 |

## 判断逻辑

- `chains=['DIRECT']` + `rulePayload='ChinaMax'` → 国内流量直连（正常）
- `chains=['DIRECT']` + `rulePayload=''` → 命中 GEOIP,CN 直连（正常）
- `chains=['SSRDOG']` 或含代理节点名 → 走了代理（需要确认是否预期）
- `chains=['DIRECT']` 但目标是国外IP → 可能是规则缺失

## 常见误判

用户说"某App慢"时，不要直接怀疑代理。**先抓连接看实际情况**：
1. 可能全走直连 → 问题在App本身或CDN节点
2. 部分走代理 → 找出哪些域名走了代理，加DIRECT规则
3. 全走代理 → 检查为什么没命中ChinaMax/GEOIP,CN

## 示例：QQ音乐慢排查结果

46条连接全部DIRECT，总下载仅8.8MB。流量不大，连接数太多（广告追踪、直播推送等杂请求拖慢主流程）。结论：App臃肿，非代理问题。
