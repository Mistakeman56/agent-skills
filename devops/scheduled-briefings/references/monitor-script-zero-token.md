# `monitor_script` 盯梢模式：盯着 0 token，有变化才唤醒 agent

> 配套阅读：`references/no-agent-watchdog.md`（`no_agent` 看门狗模式）。
> 本文是它的**变体**，用户明确要的就是这一种。

## 什么时候用哪个

`no_agent` 的代价是**没有判断力**——脚本只会照本宣科，碰上没预料到的情况不会处理，只能把原始 stdout 原样丢给用户。

| 模式 | 空闲时 | 有变化时 | 有判断力 |
|---|---|---|---|
| `no_agent=True` + `script` | 0 token | 0 token（stdout 原样发出） | ❌ |
| **`monitor_script` + agent** | **0 token**（脚本输出字节不变 → 调度器完全跳过 LLM，记静默 tick） | 跑 agent（注入 `MONITOR CHANGE DETECTED` + unified diff） | ✅ |

**用户偏好（2026-09-11，原话）**：
> "那也不用 no——agent，只要盯梢的时候不消耗 token 就行，挂着吧"

⇒ 用户要的是「**常驻挂着、闲着不烧 token，但发现变化后要 agent 来判断/加工/核对**」。
**别默认推 `no_agent`**，那会丢掉判断力；也不要因为"要自动化"就上每分钟一次的全 agent cron。

## 三个模式的一句话记忆

- **纯定时播报** → `script` + agent（每次都要模型加工）
- **固定阈值告警**（余额/磁盘/心跳），输出即最终文案 → `no_agent=True`
- **盯变化 + 需要判断**（新邮件是不是发票、是不是公司抬头、要不要发）→ **`monitor_script`**

## 监视脚本三条纪律

1. **输出必须稳定**：不含时间戳、不含"当前时间"、排序确定（按 `created_at` 等稳定键排），
   否则每次 tick 都算"变化"，等于把 LLM 当轮询用。
2. **查询失败要回放上次成功快照**（缓存到文件，如 `~/.hermes/state/<job>_last.txt`），
   否则网络抖一下就被判成"变化"唤醒 agent。没有缓存时输出一个**固定的**错误串（别带 traceback/时间）。
3. **排除易变字段**：状态类字段（已读/未读、lock、last_seen、processing 标志）一碰就翻转。
   只输出真正代表**内容**的字段。

提示词里写死：
> 上下文没有 `MONITOR CHANGE DETECTED` → 只回 `[SILENT]`，不调任何工具。
> 首次 tick 必定跑一次 agent 建基线，这次也回 `[SILENT]`。

## 骨架

```python
#!/usr/bin/env python3
"""cron monitor_script — 输出必须字节稳定；失败回放上次快照。"""
import json, os, subprocess

CACHE = os.path.expanduser('~/.hermes/state/<job>_last.txt')
ENV = {k: v for k, v in os.environ.items()
       if k.lower() not in ('http_proxy', 'https_proxy', 'all_proxy', 'clash_proxy')}

def snapshot() -> str:
    r = subprocess.run(['<cli>', '...'], capture_output=True, text=True, env=ENV, timeout=120)
    raw = r.stdout + r.stderr
    obj, _ = json.JSONDecoder().raw_decode(raw[raw.find('{'):])   # CLI 常在 JSON 后附一行 tip
    rows = sorted((it['created_at'], it['id'], it.get('title', '')) for it in obj['data']['data'])
    return f"COUNT={len(rows)}\n" + "\n".join('|'.join(map(str, x)) for x in rows)

try:
    out = snapshot()
    open(CACHE, 'w', encoding='utf-8').write(out)
    print(out)
except Exception:
    try:
        print(open(CACHE, encoding='utf-8').read())   # 回放上次成功快照 → 不触发变化
    except OSError:
        print('SNAPSHOT_UNAVAILABLE')                  # 固定串，绝不带 traceback
```

## 创建 cron

```bash
hermes cron create "盯梢任务" --schedule "every 30m" \
  --monitor-script "monitor.py" --deliver origin
```

（`cronjob` 工具同参：`monitor_script="monitor.py"`，相对路径解析到 `~/.hermes/scripts/`。
`monitor_script` 与 `no_agent=True` **互斥**，与 `monitor_url` 也互斥。）

## ⚠️ LXC/容器里所有任务静默全挂：缺 user D-Bus，网关把 worker 包进 systemd-run（2026-10-04 踩过）

**症状**：`Last run` 全是
`error: Restart-safe cron worker dispatch failed: cron external worker exited before ownership acknowledgement (exit 1)`；
但 **`hermes cron run <id>` 手动跑却成功** —— 于是极容易误判成"任务本身没问题、只是调度器抽风"。

**为什么手跑成功骗人**：
- CLI 手动跑 → `_is_supervised_gateway_process()` 为 False → `mode=in_process`，**根本不派 worker**；
- 网关跑 → 在 systemd 下（有 `INVOCATION_ID`）→ 必定派外部 worker。**手跑成功 ≠ 调度能跑。**

**根因链**（`tools/process_registry.py`）：`restart_safe_gateway_child_argv()` 探测
`_systemd_run_user_scope_available()` —— 该探测**只看 `systemd-run` 二进制在不在**。
容器里二进制在、但**没有 user systemd 会话** → 探测返回 True ✗ →
worker 被包成 `systemd-run --user --scope --unit=cron-* python -m cron.scheduler …` →
运行时 `Failed to connect to bus: No medium found` → **秒退 exit 1**。
（worker 的 stdout/stderr 都被丢进 DEVNULL，所以日志里只剩网关那句误导性文案。）

**修**（源码 docstring 自己给的解药）：
```bash
loginctl enable-linger root          # 或对应网关用户
systemctl start user@0.service       # 起 user manager
ls /run/user/0/bus                   # 出现即成功
# 决定性验证（必须带这两个 env，systemd-run --user 靠它们找 bus）：
env XDG_RUNTIME_DIR=/run/user/0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/0/bus \
    systemd-run --user --scope --unit=fixtest /bin/true && echo FIXED
```
`enable-linger` 会写 `/var/lib/systemd/linger/<user>` → **重启后依然有效**。
**不需要重启网关**（`systemd_user_bus_env()` 每次派发时现取 bus 地址）。

**只有真实调度 tick 才算验证**：把 schedule 临时改成 `*/2 * * * *`，等一轮，然后确认
`Last run: … ok` **且** `executions.db` 里那行的 `pid` 是**新的 worker pid**（不是网关 pid）。
若 `pid` 等于网关 pid + `handoff_pending=0`，说明 worker 又被包进 systemd-run 了。

## ⚠️ 脚手架铁律：monitor 脚本必须有可执行位（2026-10-04 踩过）

**外部 worker 是拿 shebang 直接 exec 脚本的，不套 `python3 <path>`。**
脚本若是 `644` → worker 起不来 → 任务每 tick 都报：

```
Restart-safe cron worker dispatch failed:
  cron external worker exited before ownership acknowledgement (exit 1)
```

**诊断要点（这个错误极具误导性）**：
- 手动 `python3 xxx.py` **一切正常**（退出 0、输出正确）→ 会把人带偏去查脚本逻辑。
- `executions.db` 里**没有任何失败记录** → 因为崩溃发生在派发阶段、写库之前；
  `cron list` 只显示 `failure_streak` 一路涨。
- **一行定性**：`~/.hermes/scripts/xxx.py >/dev/null 2>&1; echo $?` → `126` + `Permission denied` 就是它。

**预防：建完 monitor 脚本立刻 `chmod +x`，并批量体检全部存量：**

```bash
chmod +x ~/.hermes/scripts/*.py
# 列出所有被当成 monitor 的脚本 + 权限，非 755 即隐患
python3 -c "
import json,os
d=json.load(open('~/.hermes/cron/jobs.json'))
js=d if isinstance(d,list) else d.get('jobs',d)
for j in (js if isinstance(js,list) else js.values()):
    if isinstance(j,dict) and j.get('monitor_script'):
        p='~/.hermes/scripts/'+j['monitor_script']
        print(oct(os.stat(p).st_mode)[-3:], j['monitor_script'])
"
```

（Hermes 更新后可能改变调用方式 → 老脚本集体失效，报错却只说「worker 退出」，务必先查权限再查逻辑。）

## ⚠️ 微信 iLink 限流会吞掉投递（2026-10-04 踩过）

`deliver: origin` 到 weixin 时，若**投递瞬间用户正在跟你聊天**（或两个 job 撞在一起），iLink 直接拒：

```
delivery_failed: iLink sendmessage rate limited; cooldown active for 30.0s
```

- agent **已经跑完并生成了内容**（`Execution: completed`），只是最后一步没送出去 →
  状态是 `delivery_failed` 而不是 `error`，别当成任务逻辑坏。
- **不会自动重试**，这一条通知就永久丢了 → 重要盯梢要错开时间：
  不同 job 用不同分钟位（如 `5,35` vs `:15/:45`），别都用 `every 30m` 撞同一个时刻。
- 验证/手测时先等 **35-45 秒**让冷却过期再 `hermes cron run`，否则测一次失败一次、误判成代码问题。
- 判据：`jobs.json` 里 `last_delivery_error: null` + `last_status: ok` 才算真送达。

## ⚠️ 调度陷阱（真的踩过，2026-09-11）

- **`schedule='30m'` 会被解析成一次性任务**（返回里 `repeat: "once"`），跑完就没了！
  循环必须写 **`schedule='every 30m'`**（或 cron 表达式 `*/30 * * * *`）。
- **事后 `update` 只改 schedule 不会重置 `repeat`** —— 建错了只能 `remove` 掉重建。
- **建完立刻 `cronjob(action='list')` 复核** `repeat: forever` + `next_run` 有值再收工，
  别只看创建时返回的 `schedule` 字符串（它可能已经是 cron 表达式，但 `repeat` 还停在 `once`）。

## 成本核算（回答用户"挂着烧不烧 token"）

- 脚本 tick 本身：**0 LLM token**（只是跑 Python + 命令行）。
- 输出不变的那些 tick：**0 LLM token**（调度器直接跳过，连模型都不启动）。
- 只有**变化那一次**真的跑 agent：一次很小的对话量（几十 token 输入起）。
- 对比：每分钟一次的全 agent cron = 每次 ~42K token 输入（含工具描述），¥ 级别/天。
