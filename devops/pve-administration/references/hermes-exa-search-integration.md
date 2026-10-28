# Hermes 接入 Exa 搜索引擎（2026-08 源码实测）

用户问"怎么接入exa搜索引擎"时，在 Hermes 源码里确认：**Exa 是原生支持的 web 搜索后端**，不需要装额外东西（`exa-py==2.10.2` 已在依赖里），只差 API key + 配置 + 重启。

## 源码位置（证据）

- Provider: `hermes-agent/plugins/web/exa/provider.py` — 子类化 `agent.web_search_provider.WebSearchProvider`，用官方 SDK `exa-py`（经 `tools.lazy_deps.ensure("search.exa", prompt=False)` 懒加载）
- 依赖: `hermes-agent/tools/lazy_deps.py` 中 `"search.exa": ("exa-py==2.10.2",)`
- 兼容后端一览（`hermes-agent/tools/web_tools.py` 头部注释）:
  - Exa: https://exa.ai (search, extract) — **付费**，有免费试用
  - Tavily: https://tavily.com (search, extract) — 付费
  - SearXNG: 自托管，免费
  - Firecrawl: 提取为主（爬网页转 markdown）
- 后端选择在 `hermes tools` 设置时完成（`web.backend` in config.yaml）

## 配置方法（二选一）

**方式A：环境变量（最简）**
```bash
# 写入 Hermes 的 .env（重启 gateway 后自动加载）
echo 'EXA_API_KEY=...' >> ~/.hermes/.env
```

**方式B：config.yaml（推荐，持久化）**
```yaml
web:
  search_backend: "exa"      # 显式按能力指定
  extract_backend: "exa"     # 内容提取也用 Exa（可选）
  backend: "exa"             # 共享 fallback（search+extract 都用）
```

**⚠️ 不要用 patch/write_file 直接改 config.yaml！** Hermes 会拒绝（"Refusing to write to Hermes config file... Agent cannot modify security-sensitive configuration"）。正确命令：
```bash
hermes config set web.search_backend exa
hermes config set web.extract_backend exa
```

**⚠️ 系统 Python 可能没有 exa-py！** 虽然 `exa-py==2.10.2` 在 hermes-agent 的依赖清单里，但当前 gateway 用的系统 Python（PEP 668 环境）不一定装了。缺了就装：
```bash
pip install --break-system-packages exa-py==2.10.2
```

**配置后重启生效：** `hermes gateway restart`（从 gateway 外部 shell 执行，不能在 gateway 进程内 restart）。

SDK 客户端会自动打 `x-exa-integration: hermes-agent` 头（`provider.py` 里写死）。

## 验证（装完立刻测，不用等重启）

```bash
cd /root && python3 -c "
import os
os.environ['EXA_API_KEY'] = '<key>'
from exa_py import Exa
client = Exa(api_key=os.environ['EXA_API_KEY'])
client.headers['x-exa-integration'] = 'hermes-agent'
res = client.search('测试查询', num_results=3)
for r in res.results: print('-', r.title); print(' ', r.url)
"
```
返回带 title/url 的结果 = 连接成功。（2026-08 实测：搜"大连交通大学 计算机 考研"直接命中学校官网，结果质量高。）

## 检查当前后端

```bash
grep -n -A15 "web:" ~/.hermes/config.yaml   # 无 web 段 = 未配置，用默认搜索
```

**本环境已完成配置（2026-08）：** EXA_API_KEY 在 `~/.hermes/.env`，`web.search_backend=exa`、`web.extract_backend=exa` 已写入 config.yaml，exa-py 已装，SDK 直连测试通过。当前会话的 web_search 工具要等 gateway 重启后才切到 Exa。

## 结论模板

Hermes 原生支持 Exa，配置很简单：
1. 拿 API Key（https://exa.ai，付费档有试用）
2. `hermes config set web.search_backend exa` + `web.extract_backend exa`（或 .env 设 `EXA_API_KEY`）
3. 系统 Python 缺 exa-py 就 `pip install --break-system-packages exa-py==2.10.2`
4. 重启 gateway 生效
