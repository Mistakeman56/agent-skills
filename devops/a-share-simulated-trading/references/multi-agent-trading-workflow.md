# Multi-Agent AI Workflow & GPU Comparison Notes

## Date: 2026-05-16
## Source: Conversation with assistant about AI agent workflows

## Multi-Agent Frameworks (2026 State)

### Top Frameworks for Orchestrating Multiple LLM Agents

| Framework | Paradigm | Entry Barrier | Best For |
|-----------|----------|:------------:|----------|
| **CrewAI** | Role-based (agents have role/goal/backstory) | Low (20 lines Python) | Quick prototypes, simple pipelines |
| **LangGraph** | Graph-based (nodes + edges + state) | Medium | Complex branching workflows, production |
| **AutoGen/AG2** | Conversational agents (multiple agents debating) | Medium | Code review, research analysis |
| **OpenAI Agents SDK** | Handoff pattern (triage + specialists) | Low | Teams already in OpenAI ecosystem |
| **Google ADK** | Hierarchical agent tree | Medium | Google Cloud / multimodal |

### Recommendation Path
1. Start with **CrewAI** for rapid prototyping
2. Move to **LangGraph** when you need state checkpointing, conditional routing, production reliability

### What People Build with Multi-Agent Workflows

**Customer Support:** Triage agent → Order lookup → Refund agent → Human escalation
**Data Analysis:** SQL agent → Chart builder → Report writer
**Content Creation:** Research agent → Script writer → Visual designer
**Trading/Finance:** News monitor → Technical analyst → Risk controller → Report writer
**Code Development:** Code writer → Code reviewer → Test writer
**Personal Productivity:** Morning briefing (weather+calendar+GitHub+news) → Daily task list

## GPU Comparison for Local AI Inference

### Consumer GPU AI Capability Matrix (2026)

| GPU | VRAM | Bandwidth | Inference Speed | Price | Verdict |
|-----|:----:|:---------:|:---------------:|:----:|:--------|
| **RTX 4060 Ti 16GB** 🥇PVE | 16GB | 288 GB/s | ~18 tok/s (Gemma 21B) | ~¥2000二手 | **Best value for AI** |
| **RTX 4080 Super** | 16GB | 736 GB/s | ~45 tok/s (Gemma 21B) | ~¥7000 | Fast but expensive |
| **RX 7900 XTX** (AMD) | 24GB | 960 GB/s | Good (ROCm 7.2) | ~¥5000 | More VRAM, needs tinkering |
| **RTX 3050** | 6-8GB | ~200 GB/s | Can run 7B Q4 | ~¥800 | Can run small models |
| **Intel Arc B70** | 12GB | ~400 GB/s | Poor | ~¥1500 | **Not recommended** |

### AMD ROCm vs NVIDIA CUDA (2026)

**AMD ROCm is finally viable for inference:**
- ROCm 7.2 supports consumer RDNA 3 GPUs (7900 XTX, 7900 XT)
- PyTorch, vLLM, llama.cpp, Ollama all compatible
- RX 7900 XTX (24GB) costs much less than RTX 4090 (24GB)
- **Pain points:** Debugging tools behind NVIDIA, smaller community, some CUDA-only libraries

**Intel Arc: NOT recommended for AI:**
- Ollama doesn't natively support Intel Arc
- IPEX-LLM library being archived
- GPU timeout errors with LLM inference
- Workarounds needed (llama.cpp SYCL backend)

### Multi-Model Workflow Design

The idea: deploy multiple small(er) models on a single GPU and orchestrate them:

```
RTX 4060 Ti 16GB (or user's 4080S)
  ├─ 7B model (Q4: ~4GB) → Data formatting tasks
  ├─ 3B model (Q4: ~2GB) → Text extraction
  ├─ 7B model (Q4: ~4GB) → Code generation
  └─ ~6GB remaining for context + OS
```

Even **RTX 3050 (6GB)** can run:
- 1x 7B Q4 model (~4GB) + 1x 3B model (~2GB)
- Two small models collaborating via CrewAI

## Scheduling Codex Deployment on PVE Server

When the user has ChatGPT Plus and their $20 gift card arrives:

1. `npm install -g @openai/codex` on the server
2. Auth: Either use `codex login --device-auth` (with browser on phone) or migrate `auth.json` from MacBook
3. If phone verification blocks login → see `codex` skill pitfalls for workarounds
4. Once authenticated, Hermes can delegate coding tasks via `codex exec` commands

## GPT Plus Integration with Hermes

Three ways to use a ChatGPT Plus subscription with Hermes:

| Method | How | Cost |
|--------|-----|------|
| Codex CLI subagent | `delegate_task` → spawns `codex exec` | Included in Plus |
| OpenAI API provider | Use $5 API key from account | Separate billing |
| ChatGPT web proxy | Unofficial reverse proxy | Unreliable |

The Codex CLI approach is the most natural fit: Hermes handles reasoning/planning, Codex handles coding execution.
