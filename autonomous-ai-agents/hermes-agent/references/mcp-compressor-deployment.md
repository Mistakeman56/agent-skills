# mcp-compressor: MCP 工具描述压缩部署指南

mcp-compressor 是一个 HTTP → stdio 传输层包装器，在 MCP 服务器的 `tools/list` 响应到达 LLM 前压缩工具描述的冗长字段（`description`、`properties.description` 等），大幅减少系统提示词中的 MCP 工具描述 token 开销。

**实测效果：** 19 个 MCP 服务器从 ~42K tokens 降至 ~10K tokens（省 ~75%）

## 安装

```bash
uv tool install mcp-compressor
# 验证
mcp-compressor --version   # v0.13.0+
```

## 配置格式

在 `config.yaml` 的 `mcp_servers` 段，将原 MCP 服务器的 `command` 和 `args` 用 mcp-compressor 包装：

```yaml
mcp_servers:
  filesystem:
    command: mcp-compressor
    args:
    - --compression-level
    - max               # max = 最激进压缩
    - --server-name
    - filesystem        # 保留原服务器名（用于日志/调试）
    - --                # 分隔符，后面是原始命令
    - ssh
    - -o
    - StrictHostKeyChecking=no
    - root@192.0.2.10
    - /opt/mcp-start.sh
    - filesystem
    timeout: 60
```

## 批量处理所有 MCP 服务器

### 方式一：手动配置（推荐）

对每个 MCP 服务器，在 `command` 和 `args` 前插入：

```yaml
command: mcp-compressor
args:
- --compression-level
- max
- --server-name
- <server_name>
- --
```

后面的 `args` 保持原样（原 `command` 变成 `args` 的第一个元素）。

### 方式二：Python 脚本批量改写

```python
import yaml, copy

with open("config.yaml") as f:
    cfg = yaml.safe_load(f)

for name, server in cfg["mcp_servers"].items():
    orig_cmd = server["command"]
    orig_args = server.get("args", [])
    server["command"] = "mcp-compressor"
    server["args"] = [
        "--compression-level", "max",
        "--server-name", name,
        "--",
        orig_cmd,
    ] + orig_args

with open("config.yaml", "w") as f:
    yaml.dump(cfg, f, default_flow_style=False)
```

### 验证部署

检查进程树确认所有 MCP 服务器都通过 mcp-compressor 运行：

```bash
ps aux | grep mcp-compressor | grep -v grep
# 应看到每个服务器一行：
# /root/.local/share/uv/tools/mcp-compressor/bin/python /root/.local/bin/mcp-compressor --compression-level max --server-name filesystem -- ssh ...
```

也可查看 systemd 服务状态：

```bash
systemctl status hermes-gateway --no-pager
# 应在 CGroup 树中看到每个 mcp-compressor 进程
```

## reload 注意点

修改 config.yaml 后需重载 MCP 服务器：

```bash
# 在运行中的 Hermes 会话内输入：
/reload-mcp
# 或重启 gateway：
systemctl restart hermes-gateway   # 注意：不要从 gateway 进程内执行
```

### 与 profiles 配合使用

mcp-compressor 可以和 Hermes profiles 叠加使用以达到最大效果：

- **default profile**：所有 MCP 服务器 + mcp-compressor（全量压缩）
- **mom profile**：仅保留 mom 需要的服务器 + mcp-compressor（最小化 + 压缩）

```bash
hermes profile create mom --clone-from default
# 然后编辑 ~/.hermes/profiles/mom/config.yaml，移除不需要的服务器
```

#### 实战案例：mom profile（从19个→8个服务器，再加压缩）

目标：只保留 mom 日常需要的 MCP 服务（天气/通勤、八字、基础工具），砍掉开发/调试/智能家居等不相关的服务器。

**保留的服务器（8个）：** filesystem, fetch, time, memory, amap, zhipu, bazi, engram  
**砍掉的服务器（11个）：** git, sequentialthinking, everything, homeassistant, github, openwebsearch, brightdata, context7, playwright, excel, xiaomi-home

每个保留的服务器同时用 `mcp-compressor --compression-level max` 包装，形成双重压缩。效果：

| 场景 | 工具描述大小 | 对比原始 |
|------|------------|---------|
| 原始（19个未压缩） | ~42K tokens | — |
| 默认 profile（19个压缩） | ~10K tokens | 省76% |
| **mom profile（8个压缩）** | **~4K tokens** | **省90%** |

配置示例（每个服务器都用 mcp-compressor 包裹）：

```yaml
mcp_servers:
  filesystem:
    command: mcp-compressor
    args:
    - --compression-level
    - max
    - --server-name
    - filesystem
    - --
    - ssh
    - -o StrictHostKeyChecking=no
    - root@192.0.2.10
    - /opt/mcp-start.sh
    - filesystem
    timeout: 60
  # ... 其他服务器同样格式
  amap:
    command: mcp-compressor
    args:
    - --compression-level
    - max
    - --server-name
    - amap
    - --
    - ssh
    - -o StrictHostKeyChecking=no
    - root@192.0.2.10
    - /opt/mcp-start-amap.sh
    timeout: 30
```

### 实际部署案例（2026-05-12）

对这位用户的 mom profile，最终保留了以下 8 个服务器（从 19 个中精简）：
- **保留**：filesystem, fetch, time, memory, amap, zhipu, bazi, engram
- **移除**：github, git, playwright, brightdata, context7, excel, everything, openwebsearch, sequentialthinking, homeassistant, xiaomi-home
- 保留的 8 个也全部用 mcp-compressor --compression-level max 包装
- mom profile 下 token 开销：~4K tokens/次（默认 ~10K，原始 ~42K）

### Mom profile 实操示例

在 `~/.hermes/profiles/mom/config.yaml` 中只保留 8 个服务器：

**保留：** `filesystem`, `fetch`, `time`, `memory`, `amap`, `zhipu`, `bazi`, `engram`
**移除：** `git`, `sequentialthinking`, `everything`, `homeassistant`, `github`, `openwebsearch`, `brightdata`, `context7`, `playwright`, `excel`, `xiaomi-home`

每台保留的服务器同样用 `mcp-compressor --compression-level max` 包装。详见真实配置 `~/.hermes/profiles/mom/config.yaml`。

### 三层 Token 节省效果

```
原始（19个未压缩）      42K tokens → ¥0.11/句
↓ 加 mcp-compressor
P0（19个已压缩）        10K tokens → ¥0.033/句  省76%
↓ 切 mom profile + compressor
P1（8个已压缩）          ~4K tokens → ¥0.01/句   再省60% → 共省90%
```

切换 mom profile 后，聊相关话题的成本砍到 1/10。按 3000 句/月算，月省 ~¥240。

## 效果验证与测量

### 方法一：查 Hermes 系统提示词大小

重启 gateway 后看日志中系统提示词的 token 估算值：

```bash
journalctl -u hermes-gateway --since "5 min ago" --no-pager | grep -i "system.*token\|tools.*schema\|MCP.*tools"
```

### 方法二：统计 MCP 服务器工具数

```bash
# 统计 config 中每个 MCP 服务器的工具数（估算）
python3 -c "
import yaml
with open('~/.hermes/config.yaml') as f:
    cfg = yaml.safe_load(f)
servers = cfg.get('mcp_servers', {})
# 按类型估算工具数
estimates = {
    'filesystem':10,'fetch':3,'time':4,'git':15,'memory':5,
    'sequentialthinking':2,'everything':15,'homeassistant':8,'github':25,
    'openwebsearch':4,'brightdata':4,'context7':3,'playwright':12,'amap':8,
    'zhipu':5,'excel':6,'bazi':5,'xiaomi-home':15,'engram':5
}
total = sum(estimates.get(n,5) for n in servers)
# 压缩前 ~220 chars/tool = ~42K tokens, 压缩后 ~65 chars/tool = ~10K tokens
# 1 K tokens ≈ 3700 chars (中英文混合)
print(f'服务器数: {len(servers)}')
print(f'估算工具数: ~{total}')
print(f'压缩前: ~{total * 220 // 1000}K tokens')
print(f'压缩后: ~{total * 65 // 1000}K tokens')
"
```

### 方法三：查 mcp-compressor 缓存的压缩结果

mcp-compressor 会缓存压缩后的 tools/list 响应，可在其缓存中查看：

```bash
# 找缓存文件（版本号可能不同）
find ~/.cache -path '*mcp*compressor*cache*' -o -path '*mcp*compress*cache*' 2>/dev/null | head -5
```

### 方法四：直接计算 token 节省金额

```bash
# 以 DeepSeek V4 Flash 定价为例
python3 -c "
原tokens = 42000
新tokens = 10000
节省 = (原tokens - 新tokens) / 原tokens * 100
价 = 2.5 / 1000000  # ¥2.5/1M tokens
print(f'每句节省: {节省:.0f}%')
print(f'每句费用: 以前 ¥{原tokens*价:.3f} → 现在 ¥{新tokens*价:.3f}')
print(f'月省(3000句): ¥{(原tokens-新tokens)*价*3000:.0f}')
"
```

## 已知问题

- **max 压缩级别**可能过度压缩工具描述导致 LLM 理解偏差（极少发生）
- 压缩主要用于 `tools/list` 响应，不影响实际 tool call 的 JSON schema 有效性
- 新增 MCP 服务器时需手动添加 mcp-compressor 包装
