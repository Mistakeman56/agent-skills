# Hermes 模型失败分类：谁触发降级、谁不触发

以 `agent/error_classifier.py` 的 `FailoverReason` 与 `agent/turn_truncation.py` 为准，
不要凭报错文案猜。下表是判类后的处置分界。

## 会触发降级（切 `fallback_providers` 下一条）

| 情形 | 触发时机 |
|---|---|
| HTTP 429 限流 | 重试次数用尽后 |
| HTTP 500 / 502 / 503 | 重试次数用尽后 |
| HTTP 401 / 403 认证失败 | **立即**，不重试 |
| HTTP 404 / 模型不存在 | **立即** |
| 返回体畸形/空（反复） | 计入无效响应 |
| **拒答 `finish_reason=content_filter`** | 有 fallback 就切；**没有就把错误发给用户** |
| `stop_reason: refusal`（Anthropic 原生线） | 同上，理由从 `stop_details` 读 |

**拒答是终态，不重试** —— 对未改动的 prompt 重发结果不变（源码注释：deterministic for the
unchanged prompt — never retried）。降级是唯一出路。

## 不触发降级

| 情形 | 应该做什么 |
|---|---|
| `context_overflow` | 压缩上下文，不是换模型 |
| `payload_too_large` (413) | 压缩 payload |
| 单张图过大 / 图片损坏 | 缩图 / 剥离图片后重试 |
| `format_error` (400) | 剥离可疑字段重试或中止 |
| 只有 reasoning 没有正文 | 同一轮内要求继续（最多 3 次），不降级 |
| `provider_policy_blocked` | 聚合商账号侧屏蔽，换路由 |

## 降级发生时的副作用

1. 重新解析凭证（含 `key_cmd` 动态凭证与自定义 provider）
2. 原地换 model / provider / client，**对话历史与工具调用保留**
3. 按新模型重新解析 reasoning effort
4. 重置重试计数
5. **prompt cache 被重置**（按模式分键）→ 切过去的那一轮明显变慢，属预期

## 生效范围

| 场景 | 支持降级 |
|---|---|
| CLI 交互 / `hermes -z` | ✔（启动时凭证失败、会话中、以及聊天打开期间新增的链） |
| 消息网关 | ✔ |
| 子 agent（delegate） | ✔（`delegation.fallback_providers`；未指定的子任务继承父链；`[]` 表示禁用） |
| cron 任务 | ✔（继承配置链，可按 job 覆盖） |
| 辅助任务（`provider: auto`） | ✔（先试各任务自己的链，再试主链，最后才内置发现） |

**改链/加链不需要重启**，从下一轮开始生效。
