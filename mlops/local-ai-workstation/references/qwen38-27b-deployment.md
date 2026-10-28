# Qwen3.8-27B 本地部署实测情报（2026-08 采集，来自 Exa/官方 model card）

## 模型身份
- Qwen3.8-27B：稠密 27B 原生视觉-语言模型，Apache-2.0，2026-08-14 开源。
- 架构：混合注意力（hybrid attention）——64 层中只有 16 层是完整注意力（KV cache 随长度增长），
  其余 48 层用 Gated DeltaNet 线性注意力（固定大小循环状态）。KV cache ≈ 传统同尺寸稠密模型的 1/4。
- 原生上下文 262,144 token（可扩 1M 是 Qwen Cloud 托管特性，本地按 262K 规划）。
- 视觉：mmproj 约 0.9GB 单独文件，纯文本用户可跳过。

## KV cache 实测（社区测，Q4_K_M 下）
| 上下文 | KV cache |
|---|---|
| 8K | ~0.5 GB |
| 32K | ~2.0 GB |
| 128K | ~8 GB |
| 256K | ~16.4 GB |

## 量化文件大小（unsloth 官方推荐）
| Quant | 大小 | 适合 |
|---|---|---|
| UD-IQ2_XXS | 9.0 GB | 12GB 卡（质量损失明显） |
| UD-Q3_K_XL | 13.4 GB | 16GB 卡想要上下文余量 |
| IQ4_XS | 15.7 GB | 16GB 卡最大能整体装下的 |
| **Q4_K_M** | **17.1 GB** | **24GB 卡甜点位**（LM Studio 默认） |
| UD-Q4_K_XL | 17.9 GB | 24GB 有性能追求 |
| Q5_K_M | 19.8 GB | 24GB+ |
| ggml-org Q4_K_M | ~19.0 GB | 标准 K-quants + MTP 头 |

## 硬件档位结论（关键！）
- **16GB GPU（4080S/4060Ti）＝最尴尬档**：Q4_K_M 17.1GB 放不下 → 只能 Q3_K_XL 13.4GB 或
  IQ4_XS 15.7GB，上下文被压到 8-32K；或 Q4 + CPU offload（<10 tok/s 不可用）。
  **16GB 跑 27B 不值得**，不是模型差，是显存卡在模型文件本身。
- **24GB GPU（4090/3090）＝甜点位**：Q4_K_M 17.1GB + 32K-64K 上下文轻松。
- **48GB 统一内存 Mac（M4 Pro）＝便携理想**：MLX 4bit 实测 14.3 tok/s 生成、128.8 tok/s 预填充、
  峰值 17.2GB / 48GB，64K-128K 上下文随便开。模型+上下文全驻内存，不挤。

## 代码能力（厂商自报，未独立复现，标注"with caveats"）
| 基准 | 分数 | 对比 |
|---|---|---|
| SWE-bench Pro | 61.7 | Claude Opus 4.6 Max = 53.4（**超过**） |
| Terminal-Bench 2.1 | 73.0 | — |
| DeepSWE 1.1 | 42.2 | — |
| OSWorld-Verified | 84.3 | 电脑操作智能体 |

## 正确的用途定位
- **主打"本地编程智能体"**（opencode / Claude Code / Qwen Code + Ollama/LM Studio 本地端点），
  不是聊天助手。编程任务每次只给一个 issue + 相关文件，上下文需求 10-15K，正好避开上下文短板。
- Ollama 官方建议编程 agent 至少 64K 上下文；Ollama 在 24-48GB 上默认只给 32K，要显式 `num_ctx`。
- 实测反馈：质量好但**默认过度思考**（xhigh 思考模式拖慢），LM Studio 默认上下文 8192 也要手动调高。

## 接 Hermes 的判断
- Hermes 系统提示词（工具 schema+技能+记忆）≈ 8K-12K tokens，单轮请求常 15K-30K。
  16GB 跑 27B 只有 8-32K 上下文 → **撑爆，不能当主力**。
- 48GB Mac 上可作**视觉/隐私专用 provider**（原生看图，替代 image-analysis 中转）或
  delegate 子代理跑机械任务；主力仍留 DeepSeek 云 API。
- **Qwen 官方 API 是更省心的替代**：$0.33/M 输入 $2.40/M 输出（与 DeepSeek Flash 同价位级），
  1M 上下文 + 全功能，不占本地显存。
