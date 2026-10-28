# 改完 Hermes 配置：不用重启也能验证是否生效

## 铁律：别让用户白等一次 /restart —— 先从日志里找证据

改完 `config.yaml` 后，`agent.log` 会自己暴露新值。**先查日志，再决定要不要叫用户重启。**

```bash
grep -aE "Compression budget rearmed|compression done|stale for|API call #" ~/.hermes/logs/agent.log | tail -20
```

关键证据行：

```
Compression budget rearmed after provider-confirmed recovery: prompt=75,130 < threshold=157,286
```

**日志里印的 `threshold=` 就是运行时装载的值。** 它是新值 → 配置已生效，**不需要 /restart**（网关会自动重载配置并重建 agent）。旧值是 524,288、新值是 157,286，一眼可辨。

同理验证 stale 超时：`errors.log` 里 `Stream stale for 240s (threshold 240s)` —— 括号里的秒数就是实际生效值。

## 坑：`providers.custom.stale_timeout_seconds` 只管名字叫 custom 的 provider

fallback_providers 里写 `provider: custom` 的条目会继承 `providers.custom`；主模型用的 `provider: deepseek` 只认 `providers.deepseek`。**两个都要单独设，别只设一个。**

## 坑：`fallback_providers` 全是同一个厂商+同一个 key = 假容灾

```yaml
# ❌ 假的：DeepSeek 一挂（402 Insufficient Balance / 502），两个兜底一起挂 → 整个链路死 → 用户看到 No reply
fallback_providers:
  - {provider: custom, base_url: https://api.deepseek.com, key_env: DEEPSEEK_API_KEY, model: deepseek-flash}
  - {provider: custom, base_url: https://api.deepseek.com, key_env: DEEPSEEK_API_KEY, model: deepseek-chat}
```

**判定规则：看 `base_url` 域名 + `key_env` 是否重复。重复 = 不是容灾，只是重试。**
至少要有一个**不同厂商**的尾部兜底：

```yaml
  - {provider: custom, base_url: https://api.xiaomimimo.com/v1, key_env: MIMO_API_KEY, model: mimo-v2.6-flash}
```

改法（列表类用 JSON 传给 CLI，比手改 YAML 安全）：

```bash
hermes config set fallback_providers '[{"provider":"custom","base_url":"...","key_env":"...","model":"..."}]'
```

## 诊断顺序：用户报「no reply / 没反应」时

1. **先看 `errors.log` 最后 10 行** —— 90% 的答案是现成的错误码
   - `402 Insufficient Balance` → 余额问题，直接查 `/user/balance`，不是网络
   - `Stream stale for Ns ... context=~M tokens` → 上下文过大或 provider 慢，看 M 与阈值
   - `APIConnectionError ... base_url=...` → 网络/代理问题，查那个 base_url 通不通
2. **再看 `agent.log` 的 API call 行**，确认当前到底在跑哪个模型：
   ```
   API call #32: model=deepseek-v4-flash-vision-exp provider=deepseek in=155207 out=1921 cache=152960/155207 (99%)
   ```
3. **余额/配额**：`curl -s https://api.deepseek.com/user/balance -H "Authorization: Bearer $KEY"`
4. **最后才怀疑网络**。

## 上下文构成的正确拆法（别猜）

`state.db` 是 SQLite。活动上下文的真实构成：

```sql
-- 消息本体（注意 reasoning 与 reasoning_content 是双份存储，占很大一块）
SELECT COUNT(*), SUM(LENGTH(content)), SUM(LENGTH(tool_calls)),
       SUM(LENGTH(reasoning)), SUM(LENGTH(reasoning_content)) FROM messages WHERE ...;
-- 系统提示词在独立表，通常很小（几千 token），别把它当成大头
SELECT SUM(LENGTH(content)) FROM system_prompts;
```

典型误判：以为是 MCP 工具描述撑大了上下文。实测 238 条消息 ≈ 774K 字符 ≈ 193K token（其中 reasoning 两份就占 278K 字符），系统提示词只 7.2K token。**该压的是消息历史，不是 MCP 工具。**

## 压缩阈值的算术坑

触发线 = `model.context_length × compression.threshold`。模型声明 1M 上下文时，`0.5` 就是 524K —— 而实际上下文只有 244K，**永远够不到，等于压缩从未生效**，直到 provider 端因 context 过大把流卡死。

修法用 per-model 覆盖，别动全局 `threshold`：

```bash
hermes config set compression.model_thresholds.<model-id> 0.15
```
