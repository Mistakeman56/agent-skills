# No-Agent Watchdog 监控模式

## 场景

定期检查某个值是否变化（余额、价格、状态等），仅**在变化时推送通知**给用户。零 LLM 成本，安静高效。

## 架构

```
┌─────────────────────┐
│  watchdog.py        │  ← 纯 Python/bash，零 LLM
│                     │
│  1. 查询目标 API    │
│  2. 读缓存文件      │
│  3. 比较新旧值      │
│  4. 变了？→输出+更新缓存 │
│     没变？→静默退出    │
└─────────┬───────────┘
          │ stdout
          ▼
┌─────────────────────┐
│  Cron (no_agent)    │  ← no_agent=true，不调 LLM
│                     │
│  脚本 stdout ≠ 空?  │──→ deliver to origin (微信)
│  脚本 stdout = 空?  │──→ 安静，不发送
└─────────────────────┘
```

## 步骤

### 1. 写监控脚本

```python
#!/usr/bin/env python3
"""看门狗：值变化才输出"""
import json, urllib.request, os, sys

CACHE = os.path.expanduser("~/.hermes/.last_value")

# 查目标值
value = query_api()  # 你的具体查询逻辑

# 读缓存
last = ""
if os.path.exists(CACHE):
    with open(CACHE) as f:
        last = f.read().strip()

# 没变就安静
if str(value) == last:
    sys.exit(0)

# 变了就更新缓存并输出
with open(CACHE, 'w') as f:
    f.write(str(value))

print(f"📊 值已变动: {value}")
print("---")
print("下次变化会自动提醒")
```

### 2. 放入 ~/.hermes/scripts/

```bash
cp watchdog.py ~/.hermes/scripts/
```

### 3. 创建 no_agent cron job

```bash
hermes cron create "监控名称" \
  --schedule "every 30m" \
  --script "watchdog.py" \
  --no-agent \
  --deliver origin
```

## 适用场景

| 场景 | 查询频率 | 缓存文件 |
|------|----------|----------|
| DeepSeek 余额 | 30min | `.last_balance` |
| 服务器磁盘使用率 | 1h | `.last_disk_usage` |
| 网站 SSL 证书到期 | 1d | `.last_ssl_expiry` |
| IP 地址变化 | 5min | `.last_public_ip` |
| 加密货币价格 | 10min | `.last_crypto_price` |

## 坑

- **no_agent=true** 是零成本关键——设成 false 每次都会跑 LLM
- 缓存文件路径用 `~/.hermes/` 下以 `.` 开头的隐藏文件，避免污染正常文件
- 首次运行没有缓存文件，一定会输出——这是预期的初始通知
- 脚本退出码可以是 0（无变化）或 0 + stdout（有变化）。不要用非零退出码表示"无变化"，cron 会误报失败
- Python 脚本比 bash 更健壮（JSON 解析、错误处理），推荐用 Python
