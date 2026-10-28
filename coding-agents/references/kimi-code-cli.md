# Kimi Code CLI（Kimi 出的终端 AI 编程 Agent，类似 Claude Code）

用户在 cmd/终端里用 `kimi` 命令。2026-08 实测：查"能不能设置不用 approve"。

## 免审批启动参数（用户问的核心）

| 参数 | 行为 | 适用 |
|---|---|---|
| `kimi --yolo`（别名 `-y` / `--yes` / `--auto-approve`） | 自动批准普通工具调用，跳过审批请求（文件写入+Shell命令） | 受信任目录下的批处理 |
| `kimi --auto` | auto 权限模式：工具审批自动处理，Agent 完全不会提问 | 想完全放手 |
| `kimi --plan` | Plan 模式：先读代码产出计划，不动手改文件 | 探索/规划 |

**规则**：
- `--yolo` 和 `--auto` **互斥**，不能一起用
- `--prompt` 不能与 `--yolo`/`--auto`/`--plan` 同用（非交互模式固定 auto 权限）
- 恢复会话时可覆盖原权限：`kimi --continue --auto`
- `--yolo` 跳过普通工具确认，但 **Plan 模式的退出审批不会被跳过**；Plan 模式下 Bash 按普通放行规则处理
- **警告：只用在受信任项目目录**，会跳过文件写入和 Shell 确认

## 常用命令速查

```bash
kimi                    # 交互式新会话
kimi --continue         # 继续当前目录最近会话
kimi --session [id]     # 恢复指定会话/选择器
kimi -m <model>         # 指定模型别名
kimi -p "prompt"        # 非交互单次执行（流式输出到 stdout，不请求审批）
kimi -p "..." --output-format stream-json   # 结构化 JSON 输出
kimi --skills-dir <dir> # 自定义 Skills 目录（可重复）
kimi --agent <name>     # 指定主 Agent
kimi web                # 前台跑本地 REST/WebSocket 服务 + Web UI（默认 58627 端口）
kimi doctor             # 校验 config.toml / tui.toml
kimi upgrade            # 检查更新
```

## 子命令

`login`（device-code 登录）、`acp`（ACP IDE 模式）、`web`（本地服务+Web UI）、`doctor`、`export`、`migrate`、`upgrade`、`provider`（管理供应商）。

## 配置持久化

启动参数（`default_model`、权限模式）可在 `config.toml` 持久化（默认路径 `~/.kimi-code` 或 `KIMI_CODE_HOME`）。`kimi doctor` 校验配置。用户问"能不能永久免审批"时：查 config.toml 的权限模式字段，或直接用 `kimi --yolo` 每次启动。

## 注意

- `kimi server` 命令树已废弃（改用 `kimi web`），唯一例外是 `kimi server kill`（停旧版服务）
- `kimi web --dangerous-bypass-auth` 会彻底关闭鉴权——仅限可信网络
