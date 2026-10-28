---
name: uncensored-model-scouting
description: 找去审查/abliterated 模型并按显卡显存选型部署时用。
---

# 去审查模型选型与部署

当 the user needs to 「无审查 / uncensored / abliterated / Heretic」模型，且明确要求「我这个显卡能部署」时，
按下面顺序做。已在他 RTX 4080 SUPER 16G 上完成过生图模型与 LLM 两轮。

## 第 1 步：先判「审查到底在哪个部件」

**这一步决定买哪个文件，搞错了换多少模型都白搭。**

| 任务 | 审查所在 | 换什么 |
|---|---|---|
| 图像生成 | **文本编码器**（RL 对齐过的指令模型） | 换 abliterated 编码器；DiT 换不换不影响审查 |
| 文本 LLM | 整个模型 | 换整份 uncensored 权重 |

**验证方法（生图）**：别信仓库名，看模型 README 的原文。若写
「no fine-tuning, abliteration, or other weight modification」→ 这份权重**没被改过**，
「Uncensored」只是命名；它的价值在于本地部署本身没有云端安全包装，而不是模型变了。

## 第 2 步：HF API 搜现成 checkpoint

```python
import json, urllib.request, urllib.parse
def hf(q, limit=40, sort="downloads"):
    u = "https://huggingface.co/api/models?search=" + urllib.parse.quote(q) + f"&limit={limit}&sort={sort}&direction=-1"
    return json.loads(urllib.request.urlopen(u, timeout=25).read())
```

- 按 `sort=downloads` 拿热度，**热度高的更可能有人踩过坑**；同时记 `lastModified`（太旧的可能不支持当前框架）
- 关键词覆盖：`uncensored` / `abliterated` / `heretic` / 作者名（知名去审作者的作品线是成套的）
- 拿到候选后**逐个取 `pipeline_tag`**，排除不匹配的任务类型（生图模型常被标 `image-text-to-text`，不能当 LLM 用）

## 第 3 步：按显存实测选量化（不看宣传看字节数）

```python
u = f"https://huggingface.co/api/models/{repo}/tree/main?recursive=false"
# 每个 .gguf/.safetensors 的 size = f.get("lfs",{}).get("size") or f.get("size")
```

**留 2~4GB 给 KV cache / 激活 / 上下文**，不是「文件 ≤ 显存就能跑」：

| 文件大小 vs 显存(16G) | 判定 |
|---|---|
| ≤ 12 GB | 纯显存，舒服 |
| 12~14.5 GB | 可用，长上下文会紧 |
| 14.5~16.5 GB | 勉强，会部分 offload 到内存，变慢 |
| > 显存 | 换下一档量化，别硬上 |

同 repo 里**挑文件数最少、量化档位最合理的那份**；量化档位多不等于好。

## 第 4 步：部署与验证（这一步不能省）

- **LLM → Ollama**（the user's machine上已有）；**生图 → ComfyUI**（见 `comfyui-deployment`）
- **必须实测两件事**，不能只看它能跑：
  1. **去审真的生效** —— 拿一条会触发拒绝的提示词跑，看有没有拒绝文字/占位方块
  2. **能力没被打坏** —— 模型要接 Agent 就**实测 tool calling**，能出图就看画质/提示词遵循度

### Ollama 导入：库通常没有，得手動 GGUF + `ollama create`

`ollama search` / `ollama pull` 只覆盖官方库，abliterated 变体几乎都不在里面。流程：

1. 用 hf-mirror 拉 GGUF（国内直连快得多），**断点循环 + `--speed-time` 防长连 stall**；
   把**真实字节数**写进脚本，目标值写错会导致死循环空转
2. 写 `Modelfile`（`FROM <绝对路径>` + `PARAMETER ...`），注意 `FROM` 不能带引号
3. `ollama create <name> -f <Modelfile>`（复用 blob，几十秒）
4. `ollama list` 确认、`ollama run <name>` 手聊验证

### ⚠️ 显存不只装模型 —— num_ctx / KV cache 是第二笔账

`模型文件 ≤ 显存` 只是入场券。**每加一倍上下文，KV cache 就多占一份显存**，超了会把模型层挤到
CPU（`ollama ps` 的 `PROCESSOR` 列会从 `100% GPU` 变成 `52%/48%`，速度掉到个位数 tok/s）。

Agent 场景（Claude Code 类）的 system prompt + 工具定义动辄 25k+ token，**4096 默认值必然不够**。
16GB 卡上把上下文拉到 32768 的三个杠杆缺一不可：

1. `OLLAMA_KV_CACHE_TYPE=q4_0`（User 级持久环境变量）—— q8_0 会让模型被挤出 GPU
2. `OLLAMA_FLASH_ATTENTION=1`
3. Modelfile `PARAMETER num_ctx <目标>`

验证靠 `ollama ps` 一列就够：`CONTEXT` 是目标值 **且** `PROCESSOR` 是 `100% GPU` 才算成功。

**读显存以 `nvidia-smi` 为准**，`ollama ps` 报的 SIZE 是模型层，不含 KV cache。

### 探针要给足 token，否则“返空”被误判成故障

带推理链的模型会**先吃掉一整段 reasoning token 才吐正文**。`max_tokens: 16~300` 时这些 token
全部被思考占满，`content` 返回空字符串、`finish_reason=length` —— **看起来像模型坏了，其实是探针参数问题**。

- 测连通性给 `max_tokens >= 300`，并同时读 `usage.completion_tokens_details.reasoning_tokens`
- 空 `content` + 高 `reasoning_tokens` = 参数太小，不是模型拒绝、不是接口挂了
- 判断去审是否生效要看**正文**里的拒绝措辞，不能只看返回码或 `finish_reason`

## 坑

1. **仓库名写「Uncensored」不代表权重被改过。** 必须读 README 的 Uncensored/Modification 章节；
   拿「只量化未修改」的当去审版卖，会让用户以为白折腾。
2. **做 Agent 用的模型，优先找名字里带 `TOOLS` 的变体**，或实测 function calling。
   abliteration 擦拒绝向量时可能连带损伤工具调用格式 —— 「不拒绝但调不了工具」比拒绝更难查。
3. **同一模型在不同框架要不同 key 布局。** HF `transformers` 分片带 `model.language_model.` 前缀，
   ComfyUI 的 repack 版会去掉；拿原生分片喂 ComfyUI 会直接读不进去。
   **选仓库时先看它有没有专门为你的运行时准备的那份**（`-W4A8` / `-int8-convrot` / `GGUF` 等后缀）。
4. **显存紧张时先降量化，不要先降上下文。** 降量化只掉细节，降上下文会直接破坏长任务。
5. **别静默替换部件。** 若原计划的那份加载不了，改用替代品时**当次就tell the user**：换掉了什么、为什么、
   替代品丢了什么。让他事后才发现等于骗他。
6. **建议只给一个主推方案。** the user's 偏好是「已表达方向时给 1 个最优方案执行，别列多选项」；
   备选只在主推有硬伤时附带。
7. **别把冷启动的慢测当成稳态性能。** 首次调用含模型装载 + 全量 prompt eval，数字会低得离谱
   （个位数 tok/s）。要看长对话稳定值（日志里的 `tg =`），或等第二次再读数 —— 否则会得出
   「这个模型太慢」的错误结论并据此换模型。
8. **去审只解决模型，不解决接入层。** 把模型接进带系统提示 + 工具的 Agent 后，**上下文体积**
   往往才是真瓶颈（见上文 num_ctx）；模型本身没拒绝，任务也会因为上下文超限直接失败。
