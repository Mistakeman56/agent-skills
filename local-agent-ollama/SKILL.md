---
name: local-agent-ollama
description: Use when connecting local Ollama to Claude Code agents.
---

# 本地 Ollama → Claude Code 接入（PC 192.0.2.10）

## 架构结论（2026-09-26 实测）
**Ollama 原生支持 Anthropic 协议** —— `POST /v1/messages` 直接 HTTP 200 + 标准 Anthropic 响应体，**不需要 LiteLLM / 任何桥接代理**。同时有 OpenAI 兼容的 `/v1/chat/completions`。

Claude Code 认 `ANTHROPIC_BASE_URL` + `/v1/messages` → 直连 Ollama 即可。

## Claude Code 配置（`~/.claude/settings.json`）
```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:11434",
    "ANTHROPIC_AUTH_TOKEN": "ollama",
    "ANTHROPIC_MODEL": "qwen38-27b-uncensored",
    "ANTHROPIC_SMALL_FAST_MODEL": "qwen38-27b-uncensored",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "qwen38-27b-uncensored",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "qwen38-27b-uncensored",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "qwen38-27b-uncensored",
    "CLAUDE_CODE_SUBAGENT_MODEL": "qwen38-27b-uncensored"
  },
  "theme": "dark-ansi"
}
```
**必须设全 4 个别名模型**（OPUS/SONNET/HAIKU + SUBAGENT），否则 Claude Code 内部请求 `claude-*` 别名会 404。

回滚文件 `D:\cc_config_backup\settings.json.bak.20260926-134722`（原内容只有 theme 一项）。

## num_ctx 硬下限（关键数字）
- **Claude Code 的 system prompt + 工具定义 = 27,327 tokens**（实测，`--print` 模式）
- 16384 → 直接 `400 exceed_context_size_error`
- **必须 ≥ 32768**（实测 32768 跑通，回 `CLAUDE_OK`, exit 0）
- 纯聊天 `ollama run` 默认 4096 够用；**Agent 场景别用 4096**（`n_tokens=4095, truncated=1` 会截断）

## 16GB 显存塞 32768 的配方（RTX 4080 SUPER）
三个杠杆缺一不可：
1. `OLLAMA_KV_CACHE_TYPE=q4_0`（User 级持久；q8_0 会把模型挤出 GPU → `52%/48% CPU/GPU` + 3.7 tok/s）
2. `OLLAMA_FLASH_ATTENTION=1`
3. Modelfile `PARAMETER num_ctx 32768`

结果 `12 GB · 100% GPU · CONTEXT 32768`，显存 15034/16376。

显存账（IQ3 27B 11GB 模型）：4096→全 GPU；16384→q8_0 会 offload、q4_0 可以；32768→必须 q4_0+FA。

## 模型
`qwen38-27b-uncensored` = `ollama create` 导入自 `D:\ollama_import\Huihui-Qwen3.8-27B-abliterated-UD-IQ3_S.gguf`（11,952,901,024 B，hf-mirror 下载）
- 生成速度 **24~31 tok/s**（长对话稳定值；冷启动短回复只有 3.8~5.4 tok/s，别被误导）
- prompt eval ~300 tok/s
- Ollama 官方库没有此模型 → 必须手动下 GGUF + `ollama create`

## Ollama 服务起法（Windows + SSH）
- **`ollama app.exe` 是托盘 GUI，在 SSH session 里起不来**（Start-Process 后立刻退出）
- 可用计划任务 `schtasks /TN OllamaServe /TR "powershell -File D:\start_ollama.ps1"` 跑 `ollama.exe serve`
- `start_ollama.ps1` 里**显式 `$env:OLLAMA_KV_CACHE_TYPE='q4_0'`** 再启动（计划任务不保证读到 User registry env）
- 自启原本靠 `启动文件夹\Ollama.lnk`（重启后恢复，会带上新 User env）
- **坑**：schtasks 起 `ollama serve` 时 stdout 被丢弃 → **`%LOCALAPPDATA%\Ollama\server.log` 不再写入**，排障改用 `ollama ps` / `Get-NetTCPConnection -LocalPort 11434` / `nvidia-smi`

## Claude Code 调用姿势（SSH 实测）
- `claude` 是 `.ps1` shim，**`Start-Process -FilePath 'claude'` 会立刻死**；用 `claude.cmd`（真身 `node_modules\@anthropic-ai\claude-code\bin\claude.exe`）
- 必须 `< NUL` 重定向 stdin，否则卡 3 秒 warning
- **单次调用约 4~6 分钟**（27327 token 每轮全量重灌）→ SSH 同步等必超时
- 可靠做法：`schtasks` 后台跑 + 结果落盘（`D:\cc_test_out.txt`），轮询读文件

## 性能现状（待优化）
实测首跑 6 分 07 秒（13:57:04 → 14:03:11）。27327 token 固定开销是主因。可选优化：
- `OLLAMA_KEEP_ALIVE` 保持模型常驻（已设 30m）
- 精简 Claude Code 的 tool schema / 关掉部分功能
- 换 9B 模型（显存腾出 → 更大 KV cache → prompt cache 命中更多）
