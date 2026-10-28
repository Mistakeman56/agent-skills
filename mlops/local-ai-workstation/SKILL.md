---
name: local-ai-workstation
description: >-
  Select consumer GPUs for local LLM inference, deploy Ollama/vLLM/llama.cpp
  with AMD/NVIDIA/Intel hardware, and orchestrate multi-agent AI workflows
  (CrewAI, LangGraph, AutoGen) on consumer hardware. Covers GPU comparison,
  model sizing, framework selection, and real-world AI workflow patterns.
license: Proprietary. LICENSE.txt has complete terms
platforms: [linux, windows, macos]
---

# Local AI Workstation — GPU Selection, Deployment & Multi-Agent Workflows

## When to Use

This skill covers three related domains:

### A. GPU Selection for AI Inference
When the user asks about:
- Which GPU to buy for local LLM inference
- NVIDIA vs AMD vs Intel for AI
- RTX 3050 / 4060 Ti / 4080 Super / 4090 comparison
- VRAM requirements for specific models
- "能不能用A卡跑AI" / "Intel Arc怎么样"

### B. Deploying Local Models
When the user asks about:
- Setting up Ollama / vLLM / llama.cpp on Windows/Linux
- Running models on consumer GPUs
- Quantization (Q4, Q8, etc.) and model sizing
- Connecting local models to Hermes or other agents

### C. Multi-Agent Workflows (the "工作流" interest)
When the user asks about:
- AI workflow orchestration / multi-agent systems
- CrewAI / LangGraph / AutoGen
- Multiple small models collaborating
- "用几个小模型完成复杂任务"
- Real-world use cases for AI agents

## GPU Selection for Local AI (2026)

### Decision Flow

```
想跑本地AI模型
  ├─ 预算充足（¥6000+）→ RTX 4080 Super 16GB ✅
  ├─ 性价比优先（¥2000-3500）→ RTX 4060 Ti 16GB ✅ 强烈推荐
  ├─ 极致省（¥500-1000）→ RTX 3050 6GB/8GB ⚠️ 只能跑小模型
  ├─ 考虑A卡 → RX 7900 XTX 24GB 🟡 性价比高但需折腾软件
  └─ 考虑I卡 → Intel Arc ❌ 不推荐，生态差
```

### GPU Comparison (2026)

| GPU | VRAM | 价格区间 | 模型能力 | 速度(21B Q4) | 推荐度 |
|:--|:--:|:--:|:--|:--:|:--:|
| **RTX 4060 Ti 16GB** | 16GB GDDR6 | ~¥2000二手 | Gemma 21B Q4, Llama 13B, Qwen 14B | ~18 tok/s | ⭐⭐⭐⭐⭐ |
| **RTX 4080 Super** | 16GB GDDR6X | ~¥7000 | 同上模型 | ~45 tok/s | ⭐⭐⭐⭐ |
| **RX 7900 XTX** | 24GB GDDR6 | ~¥5000 | **70B Q3/KM** 也能跑！ | ~35 tok/s | ⭐⭐⭐ |
| **RTX 3050 6GB** | 6GB GDDR6 | ~¥500 | 仅能跑 3-8B Q4 小模型 | 取决于模型 | ⭐⭐ |
| **Intel Arc B70** | 12GB | ~¥2000 | Ollama不支持，生态极差 | ~5 tok/s | ⭐ |

**Key insight:** VRAM determines WHAT you can run, compute speed determines HOW FAST. 4060 Ti 16GB and 4080 Super have the same VRAM (16GB) — they can run the same models. The 4080S is 2.5x faster but costs 3.5x more. For inference tasks (not training), 4060 Ti 16GB offers the best cost/performance.

### AMD ROCm (2026 Status)

ROCm 7.2 has matured significantly:
- ✅ PyTorch stable, vLLM compatible, llama.cpp compatible, Ollama compatible
- ✅ RX 7900 XTX (24GB) offers best VRAM/value ratio
- ✅ Open-source stack (can trace/debug driver-level issues)
- ⚠️ Debugging/profiling tooling still behind CUDA
- ⚠️ Framework support varies — check compatibility before buying
- ⚠️ Community support smaller than NVIDIA

**Verdict:** Viable for inference in 2026, especially if you want 24GB VRAM without paying RTX 4090 prices. Expect to spend some time on setup and debugging. (Source: kunalganglani.com ROCm guide, 2026)

### Intel Arc (2026 Status)

- ❌ Ollama does NOT natively support Intel Arc acceleration
- ❌ IPEX-LLM (the old workaround) is archived/stopped
- ❌ vLLM has minimal Intel GPU support
- ⚠️ Only viable via llama.cpp SYCL backend — requires custom builds
- ⚠️ Known GPU timeout issues with LLM inference on Arc B50/B70

**Verdict:** Not recommended for any AI workload. Buy NVIDIA or AMD instead. (Sources: Reddit r/LocalLLaMA, Intel community forum, premai.io)

### Model Sizing Quick Reference

| Model | Size | Q4 Quantized | GPU Needed |
|:--|:--:|:--:|:--|
| Gemma 3B | ~3B | ~2GB | RTX 3050 4GB+ |
| Qwen 7B / Gemma 8B | ~7-8B | ~4-5GB | RTX 3060 12GB+ |
| Llama 13B / Qwen 14B | ~13-14B | ~8GB | RTX 4060 Ti 16GB+ |
| **Gemma 21B** / Qwen 21B | ~21B | **~12GB** | RTX 4060 Ti 16GB ✅ |
| Llama 70B / Qwen 72B | ~70B | ~40GB | 2x 3090 / RX 7900 XTX (Q3) |

## Multi-Agent Workflow Frameworks (2026)

### Framework Comparison

| Framework | Core Concept | Best For | Entry Barrier | Stars |
|:--|:--|:--|:--:|:--:|
| **CrewAI** 🥇 | Role-based (角色/目标/任务) | Fast prototyping, simple multi-agent | Low | 27k+ |
| **LangGraph** 🥇 | Directed graph (有向图+状态管理) | Complex branching workflows, production | Medium | 27k+ |
| **OpenAI Agents SDK** | Handoff pattern (代理间转移控制) | OpenAI ecosystem teams | Low | New |
| **AutoGen/AG2** | Conversational (辩论+迭代改进) | Research, code review, analysis | Medium | 30k+ |
| **Google ADK** | Hierarchical agent tree | Google Cloud teams, multimodal | Medium | New |
| **Claude Agent SDK** | Tool-use-first, MCP native | Claude+MCP ecosystem | Low | New |

### When to Use Each

**CrewAI** — Start here:
```python
# Define agents with roles
researcher = Agent(role="Researcher", goal="Find info", ...)
writer = Agent(role="Writer", goal="Write report", ...)
# Create crew
crew = Crew(agents=[researcher, writer], tasks=[research_task, write_task])
crew.kickoff()
```

**LangGraph** — Upgrade to this when you need:
- Conditional routing ("if result > X, go to node A, else node B")
- Human-in-the-loop approvals (pause, wait, resume)
- Time-travel debugging (replay any state)
- Sub-graph composition (a full graph as a node)
- Production-grade state persistence

### Practical Architecture Pattern (Multiple Small Models on One GPU)

```
Consumer GPU (16GB VRAM)
         │
    Ollama Server (localhost:11434)
         │
    Orchestrator (CrewAI / LangGraph)
         ├─ Model A: Gemma 3B (2GB)  → Data formatting
         ├─ Model B: Qwen 7B (4GB)   → Text extraction
         └─ Model C: Llama 13B (8GB) → Code generation
                                    = 14GB total ← fits in 16GB!
```

Even a **RTX 3050 6GB/8GB** can do this:
- 1x 7B Q4 (~4GB) + 1x 3B Q4 (~2GB) = 6GB — tight but works
- Each model specializes in one task type

### Running Multiple Models via Ollama

```bash
# Start Ollama with environment variable for GPU
ollama serve

# In separate terminals, run different models
ollama run gemma3:7b    # One model
ollama run qwen3:7b     # Another model (queues on same GPU)

# Or use the API directly
curl http://localhost:11434/api/generate -d '{
  "model": "gemma3:7b",
  "prompt": "Format this data..."
}'
```

Note: Ollama queues requests on a single GPU. For truly parallel inference, you need either:
- Multiple GPUs (one model per GPU)
- A serving framework like vLLM with tensor parallelism
- CPU offloading for one model while GPU runs another

## Real-World Multi-Agent Use Cases (Inspiration)

### 1. Customer Support Triage (Most Mature)
- Agent classifies intent → searches knowledge base → resolves 70% autonomously
- Remaining 30% → routes to human with full context
- Measured ROI: 70% reduction in human ticket handling

### 2. Data Analyst Agent
- Connects to SQL/CRM/ERP → pulls data → identifies root causes → builds charts → writes report
- Reduces weeks of manual work to minutes

### 3. Sales / RFP Agent
- Autonomously researches prospects → scores leads → drafts 300+ page proposals
- 3x efficiency gain (NTT Data)

### 4. Compliance Monitoring
- Continuous audit checks across all transactions → flags anomalies in real-time
- Moves from sample-based auditing to 100% coverage

### 5. Document Processing
- Ingests PDFs/scans → extracts key data → classifies → follows up on missing info
- Reduces months of manual review to hours

### 6. Code Review Agent
- Integrated into CI/CD → checks every PR for security, bugs, style → suggests fixes
- 4x faster than human experts on short-term tasks (RE-Bench)

### 7. Workflow Orchestration
- "Conductor" agent triggers chains across tools
- Example: Salesforce deal closes → Notion onboarding → Slack channel → Asana tasks
- 82% of enterprises implementing this (HBR 2025)

### 8. Personal Efficiency (OpenClaw-style)
- Morning briefing (calendar+weather+GitHub+HN)
- Email triage (classify, draft replies, unsubscribe)
- Second brain (save notes via chat, retrieve later)
- Financial monitoring (earnings, position sizing, stop-loss alerts)

## Connecting Local Models to Hermes

### Via `custom_providers` in config.yaml

```yaml
custom_providers:
  local-ollama:
    base_url: "http://192.0.2.X:11434/v1"  # Your PC's Ollama IP:port
    api_key: "ollama"  # Ollama accepts any string as API key
    models:
      - "gemma4:26b"           # Model name from `ollama list`
```

Then use the provider by its `custom:<name>` identifier:

- **One-off:** `hermes chat --provider custom:local-ollama --model gemma4:26b -q "..."`  
- **Permanent switch:** `hermes model` → pick `custom:local-ollama` from provider list  
- **Per-session load:** `hermes --profile my-local-profile` (if you created a profile with this custom provider)

### Verification

Confirm the API is reachable from the Hermes host:
```bash
# Test OpenAI-compatible endpoint
curl -X POST http://192.0.2.X:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemma4:26b","messages":[{"role":"user","content":"ping"}],"stream":false}'
```

### ⚠️ Critical: Ollama must listen on 0.0.0.0, not 127.0.0.1

By default Ollama binds to `127.0.0.1:11434` — only localhost can reach it. To allow Hermes (running on a different machine/LXC) to connect:

```cmd
:: On Windows (Admin CMD):
setx OLLAMA_HOST 0.0.0.0

:: Then restart Ollama: right-click tray icon → Quit, then restart from Start Menu
```

Or from PowerShell:
```powershell
[System.Environment]::SetEnvironmentVariable('OLLAMA_HOST','0.0.0.0','User')
```
Then restart Ollama manually.

Verify after restart:
```cmd
netstat -ano | findstr 11434
```
Expected: `0.0.0.0:11434` (not `127.0.0.1:11434`)

### Token Savings: When to Use Local vs Cloud

| Task Type | Recommend | Reason |
|:--|:--|:--|
| Simple formatting, extraction | ✅ Local (Gemma 21B+) | Free, fast enough |
| Bulk text processing | ✅ Local | 100k+ tokens, zero cost |
| Simple Q&A, known docs | ✅ Local | Low complexity |
| Complex reasoning, planning | ☁️ Cloud (DeepSeek V4, Claude) | Needs reasoning depth |
| Code generation, debugging | ☁️ Cloud | Needs exact logic |
| Market analysis, strategy | ☁️ Cloud | Needs deep reasoning |
| Long-context work (32K+) | ⚠️ Check local model's context | Gemma 26B has 256K context |

Estimated savings from offloading mechanical tasks: **15-25%** of cloud token consumption.

### Task Allocation Strategy

| Task Type | Model | Reason |
|:--|:--|:--|
| Complex reasoning, planning | DeepSeek V4 Flash (cloud) | Best quality |
| Data formatting, extraction | Gemma 21B+ (local) | Free, fast enough |
| Bulk text processing | Gemma 21B+ (local) | 100k+ tokens, free |
| Simple Q&A from known docs | Gemma 21B+ (local) | Low complexity |
| Code generation, debugging | DeepSeek V4 Flash | Needs reasoning |
| Market analysis, strategy | DeepSeek V4 Flash | Needs deep reasoning |

### Estimated Token Savings

Based on the user's usage patterns (2026-05-16 analysis):
- ~20% of tasks are "mechanical" enough to offload (formatting, extraction, simple batch processing)
- Offloading those cuts DeepSeek token consumption by **15-25%**
- Monthly savings: roughly ¥5-15/month (from ~¥30-50 to ~¥22-42)

### ⚠️ Gemma 4 26B A4B (Q4_K_M) Specific Quirks

**Context Window:** 256K tokens officially. Enough for most agentic tasks.

**Ollama API Behavior:**
- `/v1/chat/completions` returns **reasoning in `reasoning` field**, **final answer in `content` field**
- The model does internal chain-of-thought before producing the response
- `finish_reason: stop` means the full response completed; `length` means it was truncated
- The reasoning field can be verbose (step-by-step planning) — this is normal, the model spends output tokens on thinking

**Performance on RTX 4080 Super (16GB, Q4_K_M):**
- Inference speed: ~40 tok/s
- VRAM usage: ~17GB (fits in 16GB? Actually slightly over — likely uses ~1-2GB RAM swap)
- First-token latency: ~2-3s (includes model load + reasoning planning)

**Connecting to Hermes:**
```yaml
# config.yaml
custom_providers:
  local-ollama:
    base_url: "http://WINDOWS_IP:11434/v1"
    api_key: "ollama"
    models: ["gemma4:26b"]
```
Then use as `hermes chat --provider custom:local-ollama --model gemma4:26b`.

But a BETTER pattern for token savings: **use local model as a `delegate_task` subagent**, not as the primary Hermes model. See section below.

### Parallel Delegation: Local Model as Hermes SubAgent

**Best pattern for token savings:** Keep Hermes on DeepSeek (or your paid cloud provider) as the orchestrator, and use `delegate_task` to offload mechanical tasks to the local model.

**Why this beats switching Hermes to the local model:**
- Hermes's system prompt (~10K+ tokens of MCP tool schemas, memory, skills) would be wasted on a local model that can't use most of those tools
- The local model in a subagent gets a lean context (just the task) — higher quality output per token
- The orchestrator reviews and approves before anything reaches the user
- User only pays for the orchestration turns, not the mechanical subtask turns

**Workflow:**
```
You (DeepSeek, cloud) ← orchestrator
  ├─ delegate_task(goal="Format this JSON", context={...})
  │   └─ Gemma 4 26B (local, 4080S) ← subagent, lean context
  │       └─ Returns formatted result
  ├─ You review and approve
  └─ Deliver to user
```

**SubAgent config for the local model:**
```yaml
# config.yaml — delegation section
delegation:
  model: gemma4:26b
  provider: custom:local-ollama
  # All subagents spawned via delegate_task will use this model
```

Or, per-call:
```python
delegate_task(
    goal="Format this text as JSON",
    context="<task details>",
    toolsets=['file', 'terminal']  # only give it what it needs
)
# The subagent picks up the default delegation model from config
```

**What Gemma 4 26B can do as a subagent:**
| Task | Quality | Notes |
|:-----|:--------|:------|
| JSON/CSV formatting | ✅ Good | Handles structured output well |
| Translation (EN↔CN) | ✅ Good | Natural bilingual capability |
| Short text summarization | ✅ Good | 26B MoE quality is solid |
| Regex / string extraction | ✅ Good | Follows pattern rules accurately |
| Code formatting / lint prescreen | ✅ Good | Can check syntax, indent, imports |
| Simple shell command generation | ✅ Good | `find`, `grep`, `sort` patterns |
| Grammar/spelling review | ✅ Good | Reliable for short docs (<1K words) |
| Data cleaning (dedup, normalize) | ✅ Good | Pattern-based work is its strength |
| Complex multi-file code | 🟡 OK | Reasoning may truncate; needs clear specs |
| Tool-use chains | ❌ Weak | No MCP tools in subagent context |
| Deep technical analysis | ❌ Weak | Reasoning depth insufficient |

**Cost savings estimation (real):**
- Each `delegate_task` to local model costs ¥0 (zero API cost)
- Mechanical tasks are ~20% of total turns → saves 15-25% of cloud token spend
- Additional benefit: reduces latency for simple tasks (no network round trip to cloud API)
- Overhead: ~2-3s first-token latency for Gemma 4 on 4080S

## Reference Files

| File | Content |
|:--|:--|
| `references/multi-agent-frameworks-2026.md` | Detailed framework comparison (LangGraph, CrewAI, AutoGen, OpenAI SDK, Google ADK) |
| `references/gpu-comparison-detail.md` | Detailed GPU benchmarks, model sizing tables, AMD/Intel specifics |
| `references/codex-cli-guide.md` | OpenAI Codex CLI installation, auth, limits, comparison with Claude Code/Cursor, integration patterns |
| `references/cloud-provider-pricing-and-switching.md` | Current CN cloud price table (DeepSeek / MiMo / Kimi / GLM), the cache-hit cost model for agent sessions, and the zero-downtime provider-switching procedure |

## Pitfalls

- **Ollama on Windows queues requests on single GPU** — can't parallelize. vLLM or multiple GPUs needed for true parallel inference.
- **gTTS latency** (included for completeness) — ~1-2s per generation. Fine for casual use, not for real-time.
- **AMD ROCm still has rough edges** — debugging/profiling tools are behind CUDA. Community support is smaller. Expect to spend time on setup.
- **Intel Arc is not viable** for AI workloads in 2026. Don't recommend it.
- **Multiple small models ≠ multi-agent orchestration** — you still need an orchestration framework (CrewAI/LangGraph) to coordinate them. Just running two Ollama instances doesn't make them "talk to each other."
- **VRAM is the hard constraint** — model size in Q4 is the primary bottleneck. Compute speed is secondary for inference.
- **4070K without VT-x** — the user's PVE host (12700K) has VT-x disabled in BIOS. VMs run via TCG soft emulation only. No GPU passthrough possible until VT-x is enabled.
- **Don't over-recommend AMD** — despite ROCm improvements, the user's existing 4080 Super AND 4060 Ti 16GB candidate are NVIDIA. AMD is only worth considering if they need 24GB VRAM at a discount.
- **Switching the cloud provider behind Hermes: probe the endpoint, THEN the key + exact model id with curl, and only then write config** — an untested key written straight into `model.*` takes the whole gateway down and the user can no longer chat. Back up `config.yaml` + `.env` first so rollback is one file copy. Full recipe: `references/cloud-provider-pricing-and-switching.md`.
- **`model.provider` stays `custom` for this user** — every endpoint is a third-party/China direct API. Never "fix" it to `openai` / `anthropic` / a vendor's built-in provider name even when the endpoint is OpenAI-compatible; that breaks the connection outright.
- **For agent workloads, compare cache-hit price first, output price second** — the system prompt is re-sent every turn at 85–90% cache hit rate, so a "cheaper" flagship can still cost multiples of the model already in use. A vendor-quoted intelligence score is only comparable to another vendor's score on the **same index version**.
- **Monthly "Token Plan" subscriptions (credit systems) are the wrong shape for agent use** — long-context credit multipliers hit every single call, and the subscription proxies typically expose no balance endpoint, so usage cannot be monitored. Prefer pay-as-you-go keys.
- **Never run `systemctl restart hermes-gateway` from inside the agent** — the command shares the gateway's cgroup, so a SIGKILL mid-restart leaves the service dead instead of restarted. After a model/config change, hand the `/restart` to the user.
