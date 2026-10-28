# Hermes Agent 成本分析方法

准确计算 Hermes Agent 的 API token 使用成本，避免被 `hermes insights` 的"Input tokens"字段误导。

## 关键认识

### "Total tokens" 才是账单数字

`hermes insights` 输出中的三个数字含义不同：

| 字段 | 含义 | 是否用于计价 |
|:--|:--|:--:|
| `Input tokens` | 每轮**新增**的用户/上下文 tokens | ❌ 仅参考 |
| `Output tokens` | 每轮生成的 tokens | ✅ 部分计入 |
| `Total tokens` | 全周期所有 API 请求累计 tokens **总量** | ✅ **实际账单** |

**为什么 Input vs Total 差100倍？**
每次 API 调用，Hermes 都会重发完整的系统提示词（系统人格 + 用户记忆 + 技能内容 + 所有 MCP 工具 schema）。即使内容不变，每次调用仍会计量这些 tokens。20 轮对话 = 20 次重发，累计量远大于"新增"量。

### 系统提示词的构成（按大小排序）

```
┌─────────────────────────────────────┐
│ MCP 工具描述（21个服务器 ≈ 50K）      │ ← 最大头，可压缩
├─────────────────────────────────────┤
│ Agent Persona（人格设定 ≈ 5K）        │ ← 固定
├─────────────────────────────────────┤
│ Memory + User Profile（≈ 3K）        │ ← 固定
├─────────────────────────────────────┤
│ Skills 内容（加载的技能 ≈ 2-10K）     │ ← 技能加载决定
├─────────────────────────────────────┤
│ 对话历史（随轮次增长）                 │ ← 不可避免
└─────────────────────────────────────┘
总计每轮：~4-5M tokens（含历史累积）
```

## 成本计算公式

### DeepSeek V4 Flash（精确版）

```python
cache_hit_rate = 0.86  # 典型值，根据实际经验

input_cost = total_tokens * (
    cache_hit_rate * 0.02 / 1_000_000 +     # 缓存命中
    (1 - cache_hit_rate) * 1 / 1_000_000     # 缓存未命中
)
output_cost = output_tokens * 2 / 1_000_000
total_cost = input_cost + output_cost
```

### 快速估算（粗略版）

```python
# 假设 ~80% 缓存命中，混合输入单价约 ¥1.2/M
total_cost ≈ total_tokens * 1.2 / 1_000_000 + output_tokens * 2 / 1_000_000
```

### 典型场景成本对比

| 场景 | 轮次 | 总 Tokens | MCP 状态 | 预估成本 |
|:--|:--:|:--:|:--|:--:|
| 简单问答（1-2轮）| 2 | ~8M | 21个未压缩 | ¥1.20 |
| 技术探讨（10轮）| 10 | ~42M | 21个未压缩 | ¥6.50 |
| 同上 + compressor | 10 | ~10M | 21个已压缩 | ¥1.60 |
| 精简 profile（8个MCP）| 10 | ~4M | 8个已压缩 | ¥0.65 |
| cron 早报 | 1 | ~0.3M | 同上 | ¥0.05 |

## 优化手段优先级

| 手段 | 节省幅度 | 难度 | 说明 |
|:--|:--:|:--:|:--|
| **1. 装 mcp-compressor** | ↓75% | ⭐ | 一行命令，最大回报 |
| **2. 建轻量 profile** | 额外 ↓60% | ⭐⭐ | 只保留必需的 MCP |
| 3. 增加对话压缩频率 | ↓20-30% | ⭐ | 减少历史累积 |
| 4. 缩短对话轮次 | 线性 | — | 少聊就省😅 |
| 5. 本地模型机械任务 | ↓15-25% | ⭐⭐⭐ | 需 RTX 4080S + Ollama |

## 检查当前系统状态

```bash
# 1. mcp-compressor 是否安装？
which mcp-compressor && mcp-compressor --version

# 2. 系统提示词中 MCP 工具是否已压缩？
# 查看 gateway 启动日志
journalctl -u hermes-gateway --since "10 min ago" --no-pager | grep -i "tools.*schema\|MCP.*tools" | tail -5

# 3. 当前 MCP 服务器数量和压缩状态
python3 -c "
import yaml
with open('~/.hermes/config.yaml') as f:
    cfg = yaml.safe_load(f)
mcp = cfg.get('mcp_servers', {})
compressed = sum(1 for s in mcp.values() if 'mcp-compressor' in str(s.get('command','')))
print(f'总MCP服务器: {len(mcp)}')
print(f'已压缩: {compressed}')
print(f'未压缩: {len(mcp)-compressed}')
print(f'建议: {\"✅ 已全部压缩\" if compressed==len(mcp) else f\"⚠️ 还有{len(mcp)-compressed}个未压缩\"} 'if mcp else '无MCP服务器')
"

# 4. 今日 token 消耗
hermes insights --days 1

# 5. 账户余额（DeepSeek 等）
# 从余额变化反算实际成本
```

## 实用经验

1. **会话中间 `/compress` 可以大幅降低历史累积** —— 在长对话中主动使用
2. **cron 任务记得设 `enabled_toolsets`** —— 否则加载全部 MCP 工具描述，成本翻倍
3. **高频 cron（≤5min）不用 agent 模式** —— 用 `no_agent: true` 脚本，零 LLM 成本
4. **Token 计数 ≠ 字符数** —— 中文约 1.5-2 tokens/字，代码约 1 token/2-3 chars
5. **缓存命中率波动大** —— 新话题首轮总是 cache miss，后续同话题命中率高

## 实战案例：2026-05-16 重度日

### 会话概况
- 平台：Weixin | 22 条消息（11 轮对话）
- 总 Tokens：**46,077,956**（含系统提示词重复发送）
- 输出 tokens：76,198
- 工具调用：22 次（terminal）
- DeepSeek 余额变化：¥19.10 → ¥11.90（花费 **¥7.20**）

### 成本反算

```
输出费用 = 76,198 × ¥2/百万 = ¥0.15
输入费用 = ¥7.20 - ¥0.15 = ¥7.05

缓存命中率反推：
  46.08M × (hit_rate × 0.02 + (1-hit_rate) × 1) = ¥7.05
  → hit_rate ≈ 86.3%
```

### 主要成本驱动因素
1. **21 个 MCP 服务器**（即使已用 compressor 压缩，描述仍占 ~10K）
2. **对话历史累积** — 11 轮后上下文大幅增长
3. **大工具输出回吐** — 如 `hermes insights` 返回表格等大段数据被重新送入上下文

## 订阅制方案对比（2026年5月）

当按量计费日费达到 ¥3-7（月费 ¥90-210）时，订阅制值得考虑：

| 方案 | 月费 | 模型 | 长上下文惩罚 | 刷新机制 | 适合 Hermes？ |
|:--|:--:|:--|:--:|:--|:--|
| **DeepSeek V4 Flash**（当前） | ¥90-210 浮动 | 很强 | 无 | 按量 | ✅ 灵活 |
| **Kimi Code ¥99** | ¥99 固定 | Kimi K2.6（1T MoE） | 无（1M 上下文） | 每周+5h 双刷新 | ✅ **推荐** |
| **GLM ¥49/¥149** | ¥49-149 | GLM-5.1 | 无 | 每5h 80/400次 prompt | ⚠️ 高峰期 3 倍扣 |
| **MiMo ¥39 Lite** | ¥39 固定 | MiMo-V2-Pro | **4 倍扣** ❌ | 月度固定 | ❌ 长上下文场景杀手 |

### Kimi ¥99 的优势
- 固定成本 ¥99/月，对比 DeepSeek 平均月费 **立省 30-50%**
- Kimi K2.6 模型质量不输 DeepSeek V4 Flash，甚至更强
- 1M 上下文无惩罚（Hermes 每次请求带 ~4M+，但 Kimi 足以覆盖单次）
- Hermes 原生支持 `provider: kimi` + `KIMI_API_KEY`

### MiMo ¥39 的陷阱
- 每次 Hermes 调用都在长上下文区间（>100K），触发 **4 倍 credit 惩罚**
- 实际可用额度 ≈ 其他家 ¥10 以下水平
- **不推荐**用于 Hermes

## "双 AI" 架构参考（Codex + Hermes 分工）

在本会话中用户确立的分工模式：

```
assistant（决策）
  ├→ Hermes（DeepSeek V4 Flash）— 日常助手
  │   • 微信聊天、行情查询、PPT 制作、班级事务
  │   • 省 token、够用就行、性价比优先
  │   • 遇到技术难题时调 Codex
  │
  └→ Codex CLI（GPT-5.5）— 技术攻坚
      • 编程难题、架构设计、复杂算法
      • 智商更高但框架偏编程，不适合日常
      • 由 Hermes 调度，结果翻译后转给用户
```

Hermes 接入 Codex 的方式：
- PVE 服务器安装 `npm install -g @openai/codex`
- 通过 `codex login --device-auth` 绑定 ChatGPT Plus/Pro 账户
- Hermes 的 terminal 工具可直接调用 `codex` CLI
