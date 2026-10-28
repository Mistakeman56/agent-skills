---
name: hermes-model-failover
description: Use when a Hermes model call refuses or fails.
---

# Hermes 模型调用失败与降级

当某一轮对话没答出来 —— 拒答、限流、5xx、模型好像没生效 —— 按下面顺序做，不要凭猜反复重试。

## 第 1 步：先判类型，别重发

**拒答对未改动的 prompt 是确定性的** —— 同一个问题重发一百次结果一样。换思路：
改写 prompt / 缩小上下文，或者换个模型（第 3 步）。

不要自己推理分类规则，直接读 Hermes 源码：
- `agent/error_classifier.py` → `FailoverReason` 枚举，每条都有注释说明该 fallback、该压缩还是该中止
- `agent/turn_truncation.py` → `handle_content_policy_refusal`，拒答的完整分支

判断用哪个：报错文案是 `⚠️ The model declined to respond (safety refusal)` → 走拒答分支；
带 HTTP 状态码（429/500/401/404）→ 走错误分类分支。两者的降级条件不同，见
`references/failure-reasons.md`。

## 第 2 步：确认 fallback 链是不是空的

```bash
hermes fallback list
```

输出 `No fallback providers configured.` 就是空的 —— **这就是错误被直接甩给用户的原因**。

关键事实：Hermes **本来就会**在拒答时尝试降级（源码里 `_has_pending_fallback()` 为真就切模型，
为假才把错误发出去）。所以看到裸拒答报错，先查配置，不要去怀疑功能坏了。

## 第 3 步：配降级链

**用 `hermes config set`，不要直接改文件** —— 直接编辑 config.yaml 会被拒（安全策略）。它接受
JSON 字符串形式的 list：

```bash
hermes config set fallback_providers \
  '[{"provider":"custom","base_url":"https://api.deepseek.com","key_env":"DEEPSEEK_API_KEY","model":"deepseek-flash"}]'
```

- 每条**至少要 `provider` + `model`**，缺任一条会被忽略
- 自定义 OpenAI 兼容端点额外要 `base_url` + `key_env`（**`key_env` 是环境变量名，不是密钥本身**）
- 内置 provider（`deepseek` / `openrouter` / `anthropic` …）用自己的默认 env，可不写 base_url
- 想要多层兑底就 array 里放多条，按顺序试
- **改前先备份**：`cp config.yaml config.yaml.bak.$(date +%Y%m%d-%H%M%S)`

`hermes fallback add` 是**交互式选择器**，无 TTY 的 SSH/自动化里用不了 —— 直接 `config set`。

## 第 4 步：验证（三样都要）

```bash
hermes fallback list                       # 链条条目数、provider、model 对不对
hermes config get fallback_providers       # 读回原始结构
python3 -c "import yaml; d=yaml.safe_load(open('~/.hermes/config.yaml')); print(len(d), d['model']['default'])"
                                           # YAML 仍合法 + 主模型没被改掉
```

最后再实测一次原失败请求。改完**下一轮就生效，不需要重启**。

## 第 5 步：让切换快起来（配完链再调这个）

链能切了，但每个模型都重试 3 次，就是 3 个模型 × 3 次 = **9 次请求、十几秒**才认输。
真正「有问题马上切」要同时关小重试：

```bash
hermes config set agent.api_max_retries 1
```

- **必须带 `agent.` 前缀**。设顶层 `api_max_retries` 不报错但**根本不被读**（源码
  `agent/agent_init.py` 读的是 `_agent_section`）。
- 官方在 `hermes_cli/config_defaults.py` 里就写着 `Set 1 for fast failover to fallback
  providers` —— 1 是官方推荐的快速降级值，调高是拿切换延迟换容忍度。
- `hermes config set` 对**它不认识的 key 会警告 `not a recognized config key` 却照样写入**。
  警告 = 这个 key 不生效，别被「✓ Set …」骗过去；读回 + 解析 YAML 确认：

```bash
hermes config get agent.api_max_retries
python3 -c "import yaml; d=yaml.safe_load(open('~/.hermes/config.yaml')); print(d['agent'].get('api_max_retries'))"
```

## 第 6 步：`APIConnectionError` 有两种 —— 先看它的上一行

同一个报错文案底下藏着两类完全不同的故障。**判据是紧挨着它的前一行日志**：

```
agent.chat_completion_helpers: Stream stale for 240s (threshold 240s) — no chunks received.
                               model=<模型> context=~244,103 tokens. Killing connection.
agent.conversation_loop: API call failed (attempt 1/1) error_type=APIConnectionError
```

- **前面有 `Stream stale … no chunks received`** → **流式首包超时**：Hermes 的看门狗主动掐的连接，
  跟网络无关。这种时候直连测 API 会秒通（首包 0.1–0.7s），别去查 DNS、别去换 key。
- **没有 Stream stale、且几秒内连着几条 `attempt 1/1` 全挂** → 才是真的连不上（出口代理 / DNS 挂了）。

```bash
grep -a "APIConnectionError" ~/.hermes/logs/errors.log | tail -20   # 看每条的前后文
grep -ac "Stream stale" ~/.hermes/logs/errors.log                   # 超时型占多少
```

### 流式首包超时怎么治

病根通常是**上下文太大**：预填充几十万 token 期间一个 chunk 都收不到，超过阈值就被杀，最后落到
`Rebuilt-message restart limit (1) exceeded` → 用户看到的就是「no reply」。模型没坏、API 没坏。

1. **先缩上下文（唯一根治）**。看会话体积：
   ```bash
   python3 -c "
   import sqlite3;c=sqlite3.connect('~/.hermes/state.db');cur=c.cursor()
   cur.execute('SELECT session_id,COUNT(*),SUM(LENGTH(COALESCE(content,\"\"))) FROM messages GROUP BY session_id ORDER BY 3 DESC LIMIT 5')
   [print(r) for r in cur.fetchall()]"
   ```
   上万条消息 / 千万字符级 = 十几二十万 token，就是它。让用户发 `/compress` 或开新会话。
2. **抬阈值**：默认 180s；可按 provider 配 `stale_timeout_seconds`（源码
   `agent/chat_completion_helpers.py` 先读 per-provider 配置，再退环境变量）。给大上下文留预填充时间。
3. **别指望 `api_max_retries: 1` 兜底**：第 5 步那个「快速降级」值意味着超时**只试一次就放弃**，
   大上下文场景会直接把错误甩给用户。缩上下文 / 抬阈值才是解。
4. **换模型是绕不是修。** 预填充快的模型能在阈值内吐首包，于是「切过去就好了」——但同一个大上下文
   继续长下去，新模型一样会撞线。

### 「SSH 里的 CLI 不说话，但微信还活着」= 两条路的代理环境不一样

gateway 进程和 SSH 里的 CLI 进程**不共享环境变量**，这是最容易看错的一点：

```bash
tr '\0' '\n' < /proc/<gateway-pid>/environ | grep -i proxy   # gateway 有没有代理
env | grep -i proxy                                           # 你当前 shell 有没有
grep -rn "HTTP_PROXY" /etc/environment ~/.bashrc              # 全局代理是哪来的
```

容器里常见 `/etc/environment` + `~/.bashrc` 全局设 `HTTP_PROXY=http://…@<路由器>:7890`。
**代理一停（OpenClash `enable=0` / 进程没了），SSH 里的 CLI 每个请求 0.02 秒被拒**，而 gateway
因为环境里压根没有代理变量反而直连正常 —— 症状就是「微信能说话，SSH 里一直不说话」。
先确认代理活没活，再决定修哪边：

```bash
netstat -lntp | grep 7890                    # 端口有没有在听
curl -s -o /dev/null -w "%{http_code}\n" -x http://127.0.0.1:7890 https://www.google.com
```

修法二选一：把代理重新起起来（见 `pve-administration` 的 OpenClash 升级/排障），或把容器里那个
全局 `HTTP_PROXY` 去掉（gateway 本来就不需要它）。

## 第 7 步：整机换主模型（欠费 / 换厂商）—— 四处必须一起改

只改 `model.default` 不够：另外几处**独立引用旧 provider**，漏一处 402 就会一直刷，看起来像「换了还没换干净」。

1. `model.default` + `model.provider`（主模型）
2. `fallback_providers` —— 删掉欠费/失效条目，改前先 `cp config.yaml ~/.hermes/backups/` 备份
3. `auxiliary.*` 全部子项（vision、压缩、审批…每项都有自己的 `provider`/`model`/`key_env`）
4. `hermes cron list` 里带 `creation-snapshot` 的任务 —— 快照是创建时固化的模型，用 `hermes cron resnap <id>` 刷新，否则定时会话仍在走旧 provider
5. **按模型名做 key 的设置**（如压缩阈值表）—— 换了模型名旧 key 永远匹配不上，**静默回退默认值**，表现是「上下文到老都不压缩」

```bash
python3 -c "import yaml;d=yaml.safe_load(open('~/.hermes/config.yaml'));print(d['model']['default'], len(d['fallback_providers']))"
awk '/^<今天日期> <当前小时>:/' ~/.hermes/logs/errors.log | grep -c '402'   # 必须 = 0
hermes cron list | grep -i '<旧provider>'                                   # 应无输出
```
**不用重启网关**：`agent/auxiliary_client.py` 每次调用现读 config（无缓存），改完下一轮生效。

## 坑

1. **别把拒答当成「模型不好用」去换模型。** 拒答是**分类器**判的，不是能力问题；换一个同样会答的
   模型不是修，只是绕。先确认降级链在不在。
2. **降级会重置 prompt cache。** cache 按模式/模型分键，切过去的那一轮会变慢，属正常。
3. **辅助任务有独立降级链**（`auxiliary.<task>` 配 `provider`/`model`），主链不覆盖它们。
   视觉、压缩、审批等挂了先看各自那段配置，不是主模型的问题。
4. **只读文档会得出「拒答不支持降级」的错误结论。** 文档的触发列表只写了 rate-limit/5xx/连接错误，
   拒答的降级在源码里 —— 据此放弃配置就白错过了。
5. **验证要同时确认主模型没被改。** 改 fallback 时手滑碰到 `model.default` 会把整个会话换到另一个
   模型，用户只会感觉「你变笨了」。
6. **先分清「模型故障」和「网络故障」，再决定查哪边。** 看到 `APIConnectionError` 就去换模型、
   换 key 是白费 —— 判断依据是**同时有几个互不相干的域名在报 `name resolution`**：
   小米 + DeepSeek + 腾讯三个一起失败 = 出口 DNS 挂了，该去查网络层（见 `local-dns`）；
   只有一个域名失败才是那个 provider 的事。判据优先于直觉，先 `grep` 日志再动手。
   这类瞬时错误**不要动 Hermes 配置**：`Transient APIConnectionError`、「every provider in the fallback
   chain kept failing over」就是抖动，重发即好。用户把这段报错贴过来时，先用一句话说清「这是瞬时连接抖动、
   没改过任何配置」，然后继续他手上的活 —— 见错就重配会把本来正常的链路改坏（用户原话：「你别给自己修坏了」）。
7. **自动降级救不了「出口全断」。** 降级链里每个 provider 都走同一个 DNS/出口，全挂时切过去
   只是把同一个错误换三个模型重试三遍。网络层必须有自己的独立降级（本地 DNS + 上游并发），
   否则 fallback 只是把故障时间拉长。
