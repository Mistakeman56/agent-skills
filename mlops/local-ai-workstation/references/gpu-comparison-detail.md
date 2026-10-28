# GPU Comparison for Local AI Inference (2026)

Compiled 2026-05-16 from BrightData search + GitHub + vendor docs.

## Consumer GPU Benchmarks (LLM Inference)

| GPU | VRAM | Memory BW | CUDA Cores | Price (CNY) | Inference Speed (21B Q4) | Power |
|:--|:--:|:--:|:--:|:--:|:--:|:--:|
| RTX 5090 | 32GB GDDR7 | 1.8 TB/s | 21760 | ~¥17000 | ~90 tok/s | 575W |
| RTX 4090 | 24GB GDDR6X | 1.0 TB/s | 16384 | ~¥12000 | ~65 tok/s | 450W |
| **RTX 4080 Super** | **16GB GDDR6X** | **736 GB/s** | **10240** | **~¥7000** | **~45 tok/s** | **320W** |
| **RTX 4060 Ti 16GB** | **16GB GDDR6** | **288 GB/s** | **4352** | **~¥2000 (二手)** | **~18 tok/s** | **165W** |
| RTX 3050 6GB | 6GB GDDR6 | 144 GB/s | 2304 | ~¥500 | ~8 tok/s | 70W |
| RX 7900 XTX | 24GB GDDR6 | 960 GB/s | 6144 (stream) | ~¥5000 | ~35 tok/s | 355W |

## Model Sizing Table

VRAM requirements for common models at different quantization levels:

| Model | FP16 | Q8 | Q4_K_M | Q3_K_M | Q2_K |
|:--|:--:|:--:|:--:|:--:|:--:|
| Gemma 3B | 6GB | 3.5GB | **2.1GB** | 1.7GB | 1.3GB |
| Qwen 3B | 6GB | 3.5GB | **2.1GB** | 1.7GB | 1.3GB |
| Gemma 8B | 16GB | 9GB | **5.2GB** | 4GB | 3GB |
| Qwen 7B | 14GB | 8GB | **4.5GB** | 3.5GB | 2.8GB |
| Llama 13B | 26GB | 14GB | **8.1GB** | 6.5GB | 5GB |
| Qwen 14B | 28GB | 15GB | **8.5GB** | 7GB | 5.5GB |
| **Gemma 21B** | **42GB** | **22GB** | **12.5GB** | **10GB** | **8GB** |
| Llama 70B | 140GB | 72GB | 40GB | 32GB | 24GB |

**Key:** Bold = recommended quant for the card size.

## Multi-Model Fit Matrix

How many models can fit on a given GPU simultaneously:

| GPU | Scenario | Model Combo | Total VRAM |
|:--|:--|:--|:--:|
| 4060 Ti 16GB | 3 models | Gemma 3B(2.1G) + Qwen 7B(4.5G) + Llama 13B(8.1G) | 14.7GB ✅ |
| 4060 Ti 16GB | 2 models | Qwen 7B(4.5G) + Gemma 21B(12.5G) | 17GB ❌ (too big) |
| 4080 Super 16GB | 3 models | Same as 4060 Ti — same VRAM | 14.7GB ✅ |
| 3050 6GB | 2 small | Gemma 3B(2.1G) + Qwen 3B(2.1G) | 4.2GB ✅ |
| 3050 8GB | mixed 2 | Gemma 3B(2.1G) + Qwen 7B(4.5G) | 6.6GB ✅ (tight) |

## Source URLs (from session 2026-05-16)

- AMD ROCm 2026 review: https://www.kunalganglani.com/blog/amd-rocm-vs-cuda-local-ai-open-source-guide
- Intel Arc discussion: https://www.reddit.com/r/LocalLLaMA/comments/1sbi5sg/has_anyone_here_tried_inference_on_intel_arc_gpus/
- Intel IPEX-LLM: https://github.com/intel/ipex-llm
- Best GPU for LLMs 2026: https://corelab.tech/llmgpu/
- vLLM alternatives comparison: https://blog.premai.io/10-best-vllm-alternatives-for-llm-inference-in-production-2026/
