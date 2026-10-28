# Cloud LLM Provider Pricing & Safe Switching (for the Hermes agent)

Price table current as of **2026-09** (China-region RMB list prices). Always re-verify on the vendor pricing
page before quoting numbers to the user — this market re-prices monthly.

## 1. Unit prices (元 / 百万 tokens)

| Model | 输入·缓存命中 | 输入·未命中 | 输出 | 上下文 | 峰谷 |
|:--|:--:|:--:|:--:|:--:|:--:|
| `deepseek-flash` (V4.1 Flash) | **0.02 闲 / 0.04 峰** | 1 闲 / 2 峰 | **4 闲 / 8 峰** | 1M+ | ✅ 闲时半价 |
| `deepseek-v4-pro` (0813) | 0.15 / 0.30 | 4.5 / 9.0 | 13.5 / 27.0 | 1M+ | ✅ |
| `mimo-v2.6-pro` | 0.025 | 3 | **6** | **1M** | ❌ 全天一价 |
| `mimo-v2.6-flash` | 0.02 | 1 | **2** | 1M | ❌ |
| `kimi-k3` | 2 | 20 | **100** | 1M | ❌ |
| `GLM-5.3` | 2 | 8 | 28 | 1M | ❌ |

DeepSeek peak window = **工作日 9:00–12:00 与 14:00–18:00（北京时间）**，其余含周末全天算闲时，闲时价格为高峰的一半。
Batch/deferrable work should be scheduled into the off-peak window — free 50% saving.

## 2. Cost model for AGENT workloads (the part people get wrong)

An agent session is **cache-hit dominated**, not output dominated: the system prompt + tool schemas +
history are re-sent every turn and hit the prompt cache (~85–90% hit rate), so **缓存命中单价 is the number
that decides the bill**, followed by uncached input, and only then output.

Estimate per session (assume ~5M cumulative billed tokens, 86% cache hit, 100K output):

| Model | ≈ 一个会话 |
|:--|:--:|
| `mimo-v2.6-flash` | **¥0.99** |
| `deepseek-flash` 闲时 | **¥1.19** |
| `deepseek-flash` 高峰 | ¥2.37 |
| `mimo-v2.6-pro` | ¥2.81 |
| `kimi-k3` | **¥32.6** |

**Two conclusions that keep recurring:**
- A "flagship-class" model is **NOT automatically cheaper** than the cheap model you already run.
  MiMo-V2.6-Pro beats Kimi K3 by ~12× on price at the same capability tier, **but costs ~2.4× the
  `deepseek-flash` off-peak price** (input ¥3 vs ¥1, output ¥6 vs ¥4). Switching to it buys *performance*,
  not savings — say so explicitly instead of letting "价格特别便宜" stand uncorrected.
- If the goal is *saving money*, the move is the vendor's **Flash/lite tier** (MiMo-V2.6-Flash ≈ ¥0.99,
  i.e. cheaper than `deepseek-flash` off-peak), not the Pro tier.
- Never compare two vendors' aggregate intelligence scores unless they are on the **same index version**.
  A vendor-quoted score on a newer revision (e.g. "46 on AA v4.3.2") is not comparable to an older-revision
  score (e.g. "50 on AA v4.1"); say the comparison is unavailable rather than implying a ranking.

## 3. Safe switching procedure (zero downtime, one-step rollback)

Never point `model.*` at an untested key — a bad key takes the whole gateway down and the user cannot chat.

1. **Back up first**: copy `config.yaml` + `.env` into `backups/pre-<provider>-<timestamp>/`.
2. **Probe the endpoint without credentials** to separate "site down" from "key wrong":
   a bare POST should return `401 Invalid API Key` quickly, not a timeout.
3. **Probe the key + exact model id with curl before writing any config** and require the response to
   contain the model's reply; abort on anything else without touching config:
   ```bash
   curl -s --max-time 30 -X POST "$BASE/chat/completions" \
     -H "api-key: $KEY" -H 'Content-Type: application/json' \
     -d '{"model":"mimo-v2.6-pro","messages":[{"role":"user","content":"只回复两个字：通了"}],"max_completion_tokens":50}'
   ```
4. **Write config, keeping `model.provider: custom`** (see pitfalls) — set `model.base_url`, `model.api_key`,
   `model.default`; also mirror the key into `.env` for later reference.
5. **Hand the restart to the user** — tell them to send `/restart`. Never run `systemctl restart hermes-gateway`
   from inside the agent: the command lives in the gateway's own cgroup and a SIGKILL mid-restart leaves the
   service dead instead of restarting.

Keep a rollback script next to the switch script (`scripts/rollback_model_<old>.sh`) that restores the newest
`backups/pre-*` pair and prints the resulting `model:` block. Then observe 2–3 turns for tool-calling and
format correctness; new models ship small defects in their first weeks.

## 4. Pitfalls

- **`model.provider` must stay `custom`** for this user (all endpoints are third-party/China direct). Never
  "fix" it to `openai` / `anthropic` / the vendor's built-in provider name, even when the endpoint is
  OpenAI-compatible — it breaks the whole model connection.
- **Avoid MiMo Token Plan (订阅制) for agent use.** The credit system penalises long context
  (>100K → 1 token = 4 credits) while a Hermes system prompt is 40K+ on every single call, so the
  headline monthly price buys a fraction of its face value. Pay-as-you-go also has **查得到的余额**;
  the Token Plan proxy has **no balance endpoint at all** (all billing paths 404), so no monitoring is
  possible. Prefer pay-as-you-go (`sk-` keys, `api.xiaomimimo.com/v1`).
- **Model ids are case-sensitive and lowercase** (`mimo-v2.6-pro`, `mimo-v2.6-flash`). Chinese vendor docs
  often still list the previous generation's ids — check the vendor's model page for the id you are about
  to write into config.
- **Confirm the context window before switching.** Marketing context (1M) and the value the API actually
  serves to a third-party framework can differ; if a small context is served, the agent's long prompt
  breaks in ways that look like model stupidity.
- **Don't quote single-number prices** from third-party blogs: they mix pre-/post-discount tiers and
  retired model names. Quote the split (cache-hit / miss / output, peak / off-peak) and check the vendor's
  own pricing page.
