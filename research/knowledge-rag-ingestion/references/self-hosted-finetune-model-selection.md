# Self-Hosted Fine-Tuning: Model Selection Guide (RTX 4080S + 4060Ti)

> Generated 2026-05-18 from user's plan to fine-tune a small model with their Hermes Agent conversation history.

## Hardware Constraint

| GPU | VRAM | Role |
|:----|:----:|:-----|
| RTX 4080 Super | 16GB | Training (LoRA) |
| RTX 4060 Ti | 16GB | Inference (Ollama) |

## Model Candidates (7-14B Range, Mid-2026)

| Model | Params | Train 4080S | Infer 4060Ti | Chinese | Score |
|:------|:------:|:----------:|:------------:|:-------:|:-----:|
| **🥇 Qwen2.5-7B-Instruct** | 7B | ✅ 11GB | ✅ 50 tok/s | ⭐⭐⭐⭐⭐ | 9.8/10 |
| LLaMA-3.1-8B | 8B | ✅ 12GB | ✅ 45 tok/s | ⭐⭐⭐ | 8.5/10 |
| Phi-4 | 14B | ⚠️ 15GB | ⚠️ 10 tok/s | ⭐⭐ | 7/10 |
| MiniCPM-3-4B | 4B | ✅ 7GB | ✅ 80 tok/s | ⭐⭐⭐⭐ | 7.5/10 |
| DeepSeek-Coder-V2-Lite | 16B | ❌ overflow | ❌ overflow | ⭐⭐⭐⭐ | 6/10 |

## Why Qwen2.5-7B-Instruct Wins

1. **Chinese capability** — Alibaba's model, pre-trained on 18T tokens with heavy Chinese content. LLaMA's Chinese is weak even after fine-tuning.
2. **LoRA headroom** — 4080S 16GB: model ~14GB (bf16) + LoRA ~2GB = fits with ~0GB spare but viable with gradient checkpointing. Qwen2.5-7B uses ~11GB with LoRA + gradient checkpointing (vs Phi-4 14B at ~15GB which is too tight).
3. **Inference speed** — 4060Ti 16GB: Qwen2.5-7B Q4_K_M ~5-6GB VRAM, ~50 tok/s. Phi-4 Q4 would be ~8-9GB and much slower.
4. **Tool ecosystem** — Unsloth/LlamaFactory/llama.cpp all have first-class Qwen support.
5. **Conversation format** — Qwen2.5 uses ChatML format (`<|im_start|>user\n...\n<|im_end|>\n<|im_start|>assistant\n...`) which is standard and easy to convert from ShareGPT jsonl.

## Training Stack

```bash
# Training (4080S)
pip install unsloth  # Fast LoRA, 2x speed
# Or
pip install llama-factory  # Web UI, easier for beginners

# Inference (4060Ti via PVE/LXC)
curl -fsSL https://ollama.com/install.sh | sh
ollama create my-model -f Modelfile  # Load LoRA-merged model
```

## Dataset Format

Convert Hermes conversation history to ShareGPT format:
```json
{
  "conversations": [
    {"from": "system", "value": "You are Hermes, a helpful AI assistant..."},
    {"from": "human", "value": "帮我查一下今天A股行情"},
    {"from": "gpt", "value": "好的，先查一下当前北京时间..."}
  ]
}
```

Key dataset design choices:
- Include system prompt + tool call outputs as chain-of-thought
- User corrections/reprimands → high-quality hard negatives
- Session metadata (time, context, tool results) → compress into system prompt, not conversation turns

## Estimated Costs

| Item | Cost |
|:----|:----:|
| Training (LoRA, 1000 examples, 3 epochs, 4080S) | ~¥10 electricity |
| Inference (4060Ti, Ollama) | ¥0 (local) |
| Fallback API (DeepSeek for complex queries) | ¥2-5/month |
| **vs DeepSeek-only** | **Saves ¥50-60/month** |

## Recommendation

**Qwen2.5-7B-Instruct** is the clear winner for 16GB dual-GPU budget. Only reconsider if:
- RTX 4090 (24GB) available → can train 14B models (Phi-4, Qwen2.5-14B)
- User upgrades to RTX 5090 (32GB) → opens 32B models
- New 7B model with better Chinese (DeepSeek-V3-R1-7B, etc.) releases
