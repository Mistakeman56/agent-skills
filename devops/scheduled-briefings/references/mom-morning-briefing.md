# 妈妈早安日报 — 实作案例

用户user为母亲设置的每日工作日早安推送。

## 当前内容规则（2026-05-12 更新）

```
✅ 大连今日天气（气温 + 晴/雨）
✅ 早高峰路况/通勤情况
✅ 一句暖心漂亮话
❌ 不算八字，不算命，不写运势
❌ 不搜新闻
✅ 控制在200字以内，简短温馨
```

## Cron Job 配置

```yaml
name: 妈妈早安日报
schedule: 0 23 * * 0-4          # UTC 周日~周四 23:00 = 北京 周一~周五 7:00
skills: [mom-memory]             # 加载妈妈记忆以了解她的偏好
deliver: origin                  # 交付到创建此 cron 的会话
repeat: forever
```

## Prompt 模板（当前版本）

```markdown
## 任务：给妈妈发送早安日报

现在是北京时间 **早上7:00**（UTC 23:00），请给妈妈发一份早安日报。

**第1步：查大连天气**
使用 `mcp_amap_maps_weather` city="大连" 获取今日天气

**第2步：查路况**
使用相关工具查路况

**第3步：生成早安日报并发给妈妈**

将完整消息写入 SQLite send_queue：

```python
python3 -c "
from mom_bot_db import *
from datetime import datetime
db = get_db()
db.execute('INSERT INTO send_queue (text, created_at) VALUES (?, ?)',
  ('早安消息正文', datetime.now().isoformat()))
db.commit()
db.close()
"
```

**早安消息格式：**
📅 今天日期
🌤 天气（气温X~X°C，天气状况）
🚗 路况（简短）
💕 [一句暖心漂亮话]

**重要规则：**
- ❌ 不算八字，不算命，不写运势
- ❌ 不搜新闻
- ✅ 只报天气、路况、暖心话
- ✅ 简短温馨，控制在200字以内
- ✅ 写入 SQLite send_queue，由 mom_bot_relay.py 自动发送
```

## 架构

```
cron job (0 23 * * 0-4)
  | 加载 mom-memory skill
  | 查天气 (Amap MCP)
  | 查路况
  | 生成问候
  v
写入 SQLite send_queue 表
  |
  v
mom_bot_relay.py 消费队列 (每3秒轮询)
  |
  v
妈妈微信收到消息
```

### 注意：必须用 SQLite，不是 JSONL

V3 架构改用 SQLite 后，旧版 JSONL 队列 (mom_send_queue.jsonl) 已废弃。确保：
- 使用 `mom_bot_db.get_db()` 获取数据库连接
- 写入 `send_queue` 表，字段：`text, created_at`
- relay 进程仅消费 SQLite 队列

## 用户要求变更历史

| 日期 | 变更 | 原因 |
|------|------|------|
| 初始 | 天气 + 通勤 + 八字 + 新闻 | 原始设计 |
| 2026-05-12 | ❌ 去掉八字 ❌ 去掉新闻 ✅ 只留天气+路况+漂亮话 | 用户嫌内容冗余，八字不适合日报场景 |

## 涉及的 MCP 工具

| 工具 | 用途 |
|------|------|
| `mcp_amap_maps_weather` | 大连天气预报 |

## 注意

- **发送目标不是本会话用户（是妈妈）**，所以 prompt 中必须指导 agent 写入 SQLite send_queue
- `deliver: origin` 只保证 cron 执行结果回传到对话，不保证发到妈妈
- 如实时 API 查询失败，简单降级（"今日天气查询暂时不可用"）
- 通勤时间不要写坐标，写自然语言
- **Token 控制**：只查天气1个工具 + 简短文案，比原来省一半 token
