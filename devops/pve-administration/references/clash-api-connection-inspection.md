# Clash API 连接检查 — "这个流量走代理了吗？"

## 场景
用户反馈某个应用慢，怀疑是 OpenClash 代理导致的。需要确认该应用的流量是走 DIRECT 还是走了代理。

## 快速连接

```bash
# Clash API 地址和密钥
API="http://127.0.0.1:9090"
SECRET="<PASSWORD>"  # 在 /etc/openclash/ddrdog.yaml 的 secret 字段

# SSH 到路由器获取连接数据
ssh -o StrictHostKeyChecking=no -p 2222 root@192.0.2.10 \
  "curl -s -H 'Authorization: Bearer <PASSWORD>' 'http://127.0.0.1:9090/connections'" > /tmp/conns.json
```

### 密钥位置
- API secret: `/etc/openclash/ddrdog.yaml` → `secret:` 字段（值: `<PASSWORD>`）
- Dashboard密码: `/etc/config/openclash` → `dashboard_password`（值: `<PASSWORD>`，可能相同也可能不同）
- ⚠️ 不要混淆 dashboard password 和 API secret

### 注意事项
- 路由器没有 python3，不能在路由器上跑 python 解析 JSON
- JSON 输出可能包含控制字符，本地解析时需要用 `re.sub(rb'[\x00-\x1f]', b' ', raw)` 清理，或用 `json_parse()`
- 连接数据较大（100-200KB），建议保存到文件后本地处理

## 诊断流程

### 1. 获取连接数据
```bash
ssh -p 2222 root@192.0.2.10 \
  "curl -s -H 'Authorization: Bearer <PASSWORD>' 'http://127.0.0.1:9090/connections'" > /tmp/conns.json
```

### 2. 按设备过滤（关键：识别是哪台设备的问题）
用户设备 IP 对照：
| 设备 | IP | 说明 |
|------|-----|------|
| PC (4080 Super) | 192.0.2.10 | SSH <PASSWORD> |
| MacBook Air | 192.0.2.10 | SSH 22 |
| iPhone | 192.0.2.10 | |
| PVE | 192.0.2.10 | |
| NAS (DSM) | 192.0.2.10 | |

### 3. 按目标域名过滤
根据用户反馈的应用，搜索相关域名关键字。

### 4. 判断结果
- **CHAIN=['DIRECT']** → 流量直连，代理没问题
- **CHAIN=['🇯🇵 Japan丨01', '🇯🇵 Japan', 'OpenAI']** → 走了代理，检查节点状态
- **RULE=[]** → 规则未匹配（可能走兜底 MATCH 规则）

### 5. 如果确认走代理且有问题
```bash
# 检查代理组状态
curl -s -H 'Authorization: Bearer <PASSWORD>' 'http://127.0.0.1:9090/proxies/OpenAI'

# 检查节点延迟
curl -s -H 'Authorization: Bearer <PASSWORD>' 'http://127.0.0.1:9090/proxies/🇯🇵 Japan丨01'
```

## 常见应用域名速查

| 应用 | 关键域名 | 规则 | 说明 |
|------|----------|------|------|
| Minecraft/PCL2 | `curseforge.com`, `forgecdn.net`, `mojang.com`, `minecraft.net` | 无规则→MATCH→SSRDOG | mod下载走 CurseForge CDN，实际检测走 DIRECT（GEOIP?） |
| PCL2 镜像 | `bmclapi2.bangbang93.com` | 中国IP→DIRECT | BMCLAPI 国内镜像，速度快 |
| QQ音乐 | `y.qq.com`, `music-file*.y.qq.com`, `tencentmusic.com`, `bdycdn.cn` | ChinaMax→DIRECT | 全部直连，慢是客户端臃肿 |
| ChatGPT | `chatgpt.com`, `openai.com`, `oaistatic.com` | OpenAI规则→代理 | 正常走日本节点 |
| Grok/xAI | `grok.com`, `x.ai` | ⚠️ 无规则→MATCH→SSRDOG | **不在任何规则提供者中**，需手动添加 |
| Claude | `anthropic.com`, `claude.ai` | AI Suite→代理 | |
| Steam | `steampowered.com`, `steamcontent.com`, `steamstatic.com` | SteamCN→DIRECT | 中国区直连 |
| Google | `google.com`, `googleapis.com`, `gvt2.com` | Google规则→代理 | |
| GitHub | `github.com`, `github.io`, `githubusercontent.com` | 自定义规则→SSRDOG | |

### 检查域名是否在规则提供者中

```bash
# 搜索所有规则提供者文件
ssh -p 2222 root@192.0.2.10 \
  "grep -i '关键词' /etc/openclash/rule_provider/OpenAI.yml /etc/openclash/rule_provider/Reject /etc/openclash/rule_provider/ChinaMax.yml /etc/openclash/rule_provider/Proxy /etc/openclash/rule_provider/Special /etc/openclash/rule_provider/Domestic 2>/dev/null"

# 也检查自定义规则
ssh -p 2222 root@192.0.2.10 \
  "cat /etc/openclash/custom/openclash_custom_rules.list | grep -i '关键词'"

# 检查 AI Suite（包含主流AI服务）
ssh -p 2222 root@192.0.2.10 \
  "cat '/etc/openclash/rule_provider/AI Suite'"
```

⚠️ **Grok 缺失案例**：2026-06-19 发现 Grok (grok.com, x.ai) 不在任何规则提供者中。虽然兜底 MATCH→SSRDOG 会让它走代理，但建议显式添加到 custom_rules.list 以确保稳定。

## 规则链路（当前 ddrdog.yaml）

```
自定义规则 → Adobe REJECT → SteamCN DIRECT → Google/G YouTube → ChinaMax DIRECT → 
私网 DIRECT → GEOIP,CN,DIRECT → GEOIP,LAN,DIRECT → MATCH,SSRDOG（兜底）
```

⚠️ **兜底规则是 MATCH → SSRDOG**，所有未被前面规则命中的流量都会走代理。中国 IP 被 GEOIP,CN 拦截直连，但国外 IP（如 Mojang、CurseForge CDN）会走代理。
