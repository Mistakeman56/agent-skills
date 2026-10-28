# iLink Bot 中继 V3 架构（SQLite + 事件驱动 + 告警）

替代 V2 的 JSONL + cron 轮询方案。适用于需要中继 iLink Bot 消息的多用户场景。

## V3 相比 V2 的改进

| 维度 | V2 (JSONL + cron) | V3 (SQLite + 事件驱动) |
|:----|:-----------------:|:---------------------:|
| 存储 | 4个JSONL文件 | 1个SQLite数据库 |
| 回复延迟 | 最多5分钟（cron轮询） | 秒级（事件触发） |
| 每次回复token | ~42K（全MCP工具） | ~500（直接调API） |
| cron心跳消耗 | ¥0.4+/天 | ¥0 |
| 余额告警 | ❌ | ✅ 自动通知 |
| 发送失败通知 | ❌ | ✅ |

## 架构

```
iLink Bot API
  ↓ getupdates 长轮询 (35s)
mom_bot_relay.py (持久 aiohttp 会话)
  ├── 收到消息 → SQLite messages表
  │       └── spawn mom_processor.py (子进程)
  │               ├── 读SQLite → 调DeepSeek API
  │               └── 写回复到 send_queue 表
  ├── 消费 send_queue (每3秒) → sendmessage
  │       └── 记录发送日志
  └── 告警检查 (每60秒)
          ├── 余额 < ¥3 → 告警推送
          └── 发送失败 → 告警推送
```

## SQLite 表结构

```sql
messages   (id, ts, from_user, text, message_id, context_token, processed)
send_queue (id, text, status, created_at, sent_at, error_msg)
send_log   (id, queue_id, text, success, ts, error_msg)
kv_store   (key, value)  -- 缓存 context_token 等
```

## 告警规则

- DeepSeek 余额 < ¥3 → 推送到用户微信
- 过去1小时内发送失败 > 0 → 推送到用户微信
