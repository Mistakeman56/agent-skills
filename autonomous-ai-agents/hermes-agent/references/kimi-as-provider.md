# Kimi & Kimi Code as Hermes Provider

两种不同的 Kimi 接入方式：常规 API (`api.moonshot.cn`) 和 Kimi Code 订阅 (`api.kimi.com/coding/v1`)。

文档来源: https://www.kimi.com/code/docs/

## 方式一：Kimi 常规 API（`api.moonshot.cn`）

```yaml
model:
  default: kimi-k2.6
  provider: custom
  base_url: https://api.moonshot.cn/v1
  api_key: <API_KEY>
```

KIMI_API_KEY 也可以放在 `.env` 文件中（Hermes 的 kimi/moonshot 内置 provider 会自动读取）。

## 方式二：Kimi Code 订阅（`api.kimi.com/coding/v1`）⭐推荐

Kimi Code 是 Kimi 会员权益中专为开发者提供的智能编程服务，基于 Kimi 最新旗舰模型。它**同时兼容 OpenAI 和 Anthropic 两种协议**。

| 协议 | Base URL | 完整 Endpoint |
|:---|:---------|:-------------|
| **OpenAI 兼容** | `https://api.kimi.com/coding/v1` | `https://api.kimi.com/coding/v1/chat/completions` |
| **Anthropic 兼容** | `https://api.kimi.com/coding/` | `https://api.kimi.com/coding/v1/messages` |

模型 ID 固定为 **`kimi-for-coding`**，后端会自动映射到最新旗舰模型。

```yaml
# 主模型配置（config.yaml）
model:
  default: kimi-for-coding
  provider: custom
  base_url: https://api.kimi.com/coding/v1
  api_key: ${KIMI_API_KEY}   # 从 .env 读取

# 辅助模型也同步配置
auxiliary:
  vision:
    api_key: ${KIMI_API_KEY}
    base_url: https://api.kimi.com/coding/v1
    model: kimi-for-coding
    provider: custom
    timeout: 120
```

### 📥 获取 API Key

Kimi 会员在 **Kimi Code 控制台** 创建和管理 API Key（最多 5 个，仅创建时显示一次，请妥善保存）。

### ⚠️ URL 区别
- ❌ `https://api.kimi.com/coding`（缺 `/v1` — 返回 404）
- ✅ `https://api.kimi.com/coding/v1`（正确，OpenAI 兼容）
- ✅ `https://api.kimi.com/coding/`（正确，Anthropic 兼容）

### 生效方式
修改 config.yaml + .env 后，**必须开新会话**（`/reset`）才能生效。当前进行中的会话仍使用旧模型。

## Kimi Code 的限制与配额

| 限制项 | 数值 |
|:---|:---|
| 请求窗口 | 每 **5 小时**约 300~1200 次请求 |
| 最高并发 | **30** |
| 输出速度 | 最高 **100 Tokens/s** |
| 额度刷新 | 每 **7 天**自动刷新，不累积 |
| 额度共享 | CLI/VS Code/API Key **共用同一配额** |
| 设备解绑 | 超 30 天未活跃自动解绑 |

**额度与 Kimi 会员套餐共享：** 如果 Kimi 会员月总额度达到上限，Kimi Code 额度会变为冻结状态，需等待月额度重置或升级订阅。

## 配置到第三方工具（如 Claude Code、Roo Code、OpenCode）

```bash
export KIMI_API_KEY="your-api-key-here"
export ANTHROPIC_BASE_URL="https://api.kimi.com/coding/"
export ANTHROPIC_API_KEY="$KIMI_API_KEY"
```

或在工具配置中将 Base URL 指向 `https://api.kimi.com/coding/v1`（OpenAI 兼容）或 `https://api.kimi.com/coding/`（Anthropic 兼容），模型名设为 `kimi-for-coding`。

## ⚠️ 关键坑

### 1. 256K 上下文限制（常规 API）
API 上的 kimi-k2.6 实际上下文为 **256K tokens**，而非 Kimi Code 产品宣传的 1M。对于 Hermes 的长对话（11+ 轮带工具调用），历史积累可能接近或触及上限。

**表现**：上下文压缩频繁触发，导致前后文丢失、指令遗忘。
**缓解**：定期 `/new` 新会话；使用轻量 profile（减少 MCP 工具数）；开启 context compression。

### 2. 会员积分 ≠ API 配额
- **Kimi Code 订阅**（api.kimi.com/coding/v1）：使用会员积分/Code 额度，按订阅计费
- **Kimi 开放平台 API**（api.moonshot.cn/v1）：走独立的 API 计费体系，按量付费
- 两种渠道的 API Key 都存储在 `KIMI_API_KEY` 环境变量中，容易混淆

### 3. 篡改 User-Agent 会被暂停权益
文档明确警告：使用时请保持工具的真实身份标识，**篡改客户端标识（User-Agent）将被视为违规**，可能导致会员权益暂停。

### 4. Claude Code 等工具集成时注意
如果使用 Anthropic 兼容协议，`base_url` 必须带末尾斜杠：`https://api.kimi.com/coding/`（不含 `/v1`），而 OpenAI 兼容协议需要带 `/v1`。两种协议互不通用。

## 切换回 DeepSeek

```bash
hermes config set model.default deepseek-v4-flash
hermes config set model.provider custom
hermes config set model.base_url https://api.deepseek.com/v1
# API key 在 .env 的 DEEPSEEK_API_KEY
```

## 验证

```bash
# OpenAI 兼容协议验证
curl -s https://api.kimi.com/coding/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KIMI_API_KEY" \
  -d '{"model":"kimi-for-coding","messages":[{"role":"user","content":"hi"}],"max_tokens":50}'

# Anthropic 兼容协议验证
curl -s https://api.kimi.com/coding/v1/messages \
  -H "Content-Type: application/json" \
  -H "x-api-key: $KIMI_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"kimi-for-coding","max_tokens":50,"messages":[{"role":"user","content":"hi"}]}'
```
