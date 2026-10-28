# 盯模型仓：新基座 / 社区微调 / 量化 / 无审查变体

用 `monitor_script` 盯 Hugging Face、Civitai 这类**模型仓**的新条目。
监控纪律见 `references/monitor-script-zero-token.md`，本文只讲模型仓特有的部分。

参考实现：`~/.hermes/scripts/qwen_uncensored_watch.py`。

## 1. 数据源与查询式

Hugging Face 公开 API（无需 key，按更新时间倒序）：

```
https://huggingface.co/api/models?search=<kw>&sort=createdAt&direction=-1&limit=200
https://huggingface.co/api/models?author=<login>&sort=createdAt&direction=-1&limit=50
```

Civitai（LoRA/checkpoint 的主场，不保证稳定）：

```
https://civitai.com/api/v1/models?query=<kw>&limit=25&sort=Newest
```

各国网络可达性不同：从中国访问这两个站需本地代理，见 `cn-blocked-api-access`
（`export https_proxy=socks5h://127.0.0.1:7899 http_proxy=...`）。脚本里用 `subprocess` + `curl`，
不要用 `urllib`——它不理会代理绕开环境变量。

## 2. 蹲的重点是**第三方作者**，不是官方 org

官方 org 只会发基座；用户真正等的变体（量化、合并、去限制微调、工作流整合包）**全部来自第三方仓库**。
所以扫描要两路一起跑：

1. **关键词搜索**：目标模型名（含变体拼写，如 `2.1` / `2_1`），以及变体词表
   （`uncensored` / `nsfw` / `abliterat` / `unfiltered` / `gguf` / `lora` / `turbo` / `fp8` / `nvfp4` / `comfy`）；
2. **已知出片作者名单**（`author=` 查一遍），把历史上做过同类变体的作者固定进列表——
   新变体往往由同一批人先发。

基座发布当天不会有变体，社区通常几天到数周才跟上：**监控的价值在于抢先知道**，不是预测日期。

## 3. 快照稳定性（模型仓上最容易踩雷的一条）

`createdAt`、模型 id 是不可变字段 ✓；而 **`downloads` / `likes` / `lastModified` / 趋势分是每次都会变的**，
一旦写进快照，**每一 tick 都判为变化 → 每个 tick 都唤醒 agent**，盯梢直接退化成轮询。

⇒ 快照每行只写 `modelId|createdAt`，外加一个 `TOTAL=<行数>`；绝不写下载量、点赞、修改时间。

## 4. 多源失败处理

HF 必查，Civitai 尽力。`snapshot()` 内任何一段抛异常都走「回放上次缓存」，
否则 Civitai 抽风一次就会被当成「有变化」。第二个源可选，**别让它变成噪声源**。

## 5. 唤醒后要报什么

上下文里出现 `MONITOR CHANGE DETECTED` 时，用中文回一条简报（小程序友好，≤10 行）：

- 模型完整 ID + 链接；
- 发布时间、**底座是哪一代**（是不是目标版本，别把上一代看漏）；
- **形式**：LoRA / 完整权重 / GGUF 量化（带量化等级与显存需求）/ ComfyUI 整合包；
- **License**——基座换代时许可会变（如 Apache → Research/仅非商用），必须主动提醒用户能不能商用；
- 一句「值不值得试」的判断（对用户那台机器能不能跑）。

提示词里写死：**与目标无关的变化只回一行「（无关变化，忽略）」**，不要为无关条目写简报。
拿不准的字段写「未确认」，不要编。
