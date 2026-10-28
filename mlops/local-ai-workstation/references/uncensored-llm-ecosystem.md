# Hugging Face 「无审查开源 LLM」生态调研（2026-09 实测）

## 怎么快速量出真实数量（可复用方法）

HF 的 `/api/models` 单次最多返回 `limit=1000` 条，所以得到的是**下界**（返回数 == limit 就标 `≥`）。
HF 需要走代理（本机 `local-hk-proxy` → `socks5h://127.0.0.1:7899`，见 pve-administration）。

脚本：`~/.hermes/scripts/uncensored_llm_survey.py`
输出 JSON：`~/.hermes/research/uncensored-llm-survey.json`
核心调用：
```
GET https://huggingface.co/api/models?search=<关键词>&sort=downloads&direction=-1&limit=1000
GET https://huggingface.co/api/models?author=<作者>&limit=1000
```
用法：换关键词/作者名即可量其他生态（如 "GGUF"、"vision"）。

## 关键词命中（2026-09-21）

| 关键词 | 命中 |
|---|---|
| abliterated | ≥1000 |
| uncensored | ≥1000 |
| heretic | ≥1000 |
| dolphin | ≥1000 |
| nsfw | ≥1000 |
| refusal | 579 |
| nofilter | 167 |
| unaligned | 78 |
| decensored | 72 |

`abliterated` + `uncensored` 两词去重后 **≈1500+ 个**。

## 底座分布（决定"去哪找中文可用的"）

| 底座 | 数量 | 占比 |
|---|---|---|
| **Qwen** | 952 | **62%** |
| Gemma | 273 | 18% |
| Llama | 178 | 12% |
| GLM / Mistral / DeepSeek / Phi / Yi | 34 / 34 / 32 / 17 / 8 | 其余 |

**结论：中文场景直接看 Qwen 系去审查版，生态最全、质量最高。**

## 产出方（谁在持续做）

| 作者 | 数量 | 定位 |
|---|---|---|
| mradermacher / QuantFactory | ≥1000 各 | GGUF 量化搬运（几乎每个新模型都有）|
| DavidAU | 395 | 海量无过滤微调（NEO/Fable 系，名字很长是特色）|
| TheDrummer | 220 | 无过滤角色扮演 |
| Goekdeniz-Guelmez | 193 | Josiefied 系列 |
| **huihui-ai** | 186 | **国产大户**：Qwen/DeepSeek/Gemma 全系 abliterated |
| mlabonne | 181 | abliteration 方法论作者 |
| aifeifei798 | 168 | 国产去审查微调 |

## 下载榜 TOP 8（= 社区真正在用的）

1. huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF — 262 万
2. JonathanColetti/Qwen3.8-27B-Uncensored-GGUF — 229 万
3. HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF — 219 万
4. HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive — 184 万
5. 0bserverx/Qwen3.8-27B-Heretic-Abliterated-Uncensored-GGUF — 178 万
6. DavidAU/Qwen3.5-9B-The-Defiant-Fable-...-GGUF — 152 万
7. DavidAU/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-...-GGUF — 130 万
8. HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive — 88 万（赞 3731，全场最高）

## 四大流派

1. **Abliteration**（数学上定位并消融"拒绝方向"）—— mlabonne / FailSpy / huihui-ai；工具 **Heretic** 已自动化，以至于 "Heretic" 变成了模型名里的质量标签
2. **去对齐微调**（Dolphin / Josiefied / DavidAU NEO 系）
3. **NSFW / 角色扮演特化**（TheDrummer、DavidAU）
4. **成体系的社区品牌**（HauhauCS 的 Uncensored-Aggressive / Balanced 系列，2026 新贵，赞数最高）

## 本地已存档的副本（CT <ID> 容器）

目录：`/root/models/Qwen3.8-27B-Uncensored/`（下载脚本 `scripts/download_qwen27b.sh`，校验脚本 `scripts/verify_gguf_download.py`）

| 文件 | 字节数 | 用途 |
|---|---|---|
| Qwen3.8-27B-Uncensored-Q4_K_M.gguf | 16,810,714,528 | 质量优先，16G 显存需少量 offload |
| ...HauhauCS-Aggressive-IQ3_M.gguf | 12,789,303,424 | 16G 显存可全放，速度快 |
| mmproj-...-F16.gguf | 927,606,912 | 多模态视觉投影（配 Q4_K_M 仓库）|

**下载速度实测**：HF 走本地香港代理（`socks5h://127.0.0.1:7899`）可达 **33 MB/s**；`hf-mirror.com` 从本机不通，别浪费时间。
**传大文件到内网 PC**：在容器起 `python3 -m http.server 8899`，PC 浏览器访问 `http://<容器IP>:8899/` 直接下（千兆约 110 MB/s，比让 PC 自己翻墙快得多）。容器 IP 用 `hostname -I` 查。
**校验铁律**：16G 级下载必须比对 HF API 的 `size` + LFS `sha256`，不要只看 curl 退出码。

## 消费级显卡选型（16G 显存为例）

| 目标 | 选什么 | Q4 显存 |
|---|---|---|
| 速度优先、中文够用 | Qwen3.5-9B / Gemma4-12B 去审查版 | 6–8G ✅ 全放显存 |
| 质量优先 | **Qwen3.8-27B GGUF Q4_K_M**（下载榜甜点位）| 14–17G ⚠️ 16G 刚好/需少量 offload |
| 大模型低成本 | Qwen3.6-35B-A3B（MoE 只激活 3B）| ~18G ⚠️ 需 offload，速度降 |

## 必须知道的三件事

- **去审查 ≠ 可以生成违法内容**：模型能力放开不等于法律责任消失。
- **能力会退化**：abliteration 后推理/指令遵循/长上下文通常下降几个点 → **别用在工作任务上**。
- **命名陷阱**：很多模型名里带 "Claude-4.6-Opus"、"GPT"、"Heretic" 等**只是标题借壳**，与真模型无关；判断质量看下载量/赞数/底座，不看名字。
