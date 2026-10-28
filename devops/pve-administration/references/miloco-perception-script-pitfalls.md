# Miloco 感知监控脚本常见坑

## 脚本挂起：缺少 --jsonl

`miloco-cli perceive logs --limit N` **不加 `--jsonl` 会建立长轮询/SSE连接**。行为取决于后端状态：

- **有新事件正在产生** → SSE 长轮询，**挂起等待新事件**
- **只有历史事件（无新事件）** → 返回历史数据后退出（可能误导性地"成功"）

这意味着：**不加 `--jsonl` 的脚本行为不一致** — 感知引擎正常运行时挂起，引擎停摆时反而"正常"返回过期数据。

```bash
# ❌ 挂起（当有新事件时）或返回过期数据（当引擎停摆时）
miloco-cli perceive logs --limit 10

# ✅ 始终立即返回，JSONL格式（每行一个JSON对象）
miloco-cli perceive logs --jsonl --limit 10
```

**症状：** Python subprocess 30秒超时，脚本退出码1，报告 `TimeoutExpired`。

**⚠️ 关键陷阱：** 如果感知引擎已停摆多天（日志陈旧），不加 `--jsonl` 的命令会"成功"返回陈旧数据，掩盖了引擎异常。**始终使用 `--jsonl` 确保脚本行为可预测。**

## 2>/dev/null 吞掉真实错误

脚本中 `miloco-cli service status 2>/dev/null` 会隐藏后端连接失败的错误信息，导致无法判断是超时还是后端未就绪。

```bash
# ❌ 错误被吞掉，无法诊断
miloco-cli service status 2>/dev/null
# 真实错误: {"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}

# ✅ 保留 stderr，脚本中检查返回码和输出
miloco-cli service status 2>&1
```

## 调试用法：--since 时间范围过滤

`miloco-cli perceive logs` 支持 `--since` 参数获取指定时间范围内的日志（**仅供调试，不读写 cursor 文件**）：

```bash
# 最近1小时的日志
miloco-cli perceive logs --since 1h --limit 10

# 最近24小时
miloco-cli perceive logs --since 24h --limit 5

# 时间单位：h(小时), m(分钟), s(秒), d(天), 组合如 2h30m
miloco-cli perceive logs --since 2h30m --limit 20
```

**⚠️ 与 `--jsonl` 的区别：** `--since` 是调试用的，会忽略 cursor 文件（不自动记录读取位置）。脚本中如果需要增量拉取，应使用 `--jsonl`（不带 `--since`）。

**⚠️ 2026-07-04 发现：`2>/dev/null` + 短超时 = 静默失败**

`miloco-cli service status` 在后端 STARTING 阶段会阻塞等待 API 就绪。如果同时使用 `2>/dev/null`（隐藏 stderr）和短超时（30秒），脚本会以 `TimeoutExpired` 退出但**没有任何错误信息**——无法区分"后端启动太慢"和"命令本身挂起"。

**已确认的时序：**
- 后端 STARTING 阶段：`miloco-cli service status 2>/dev/null` 阻塞 >30秒 → 超时
- 后端 RUNNING 阶段：`miloco-cli service status` 立即返回 JSON（uptime_seconds > 0）
- `pct exec 310 -- echo OK` 在 STARTING 阶段正常返回（不依赖后端 API）

**结论：** 去掉 `2>/dev/null` + 增大超时到 45-60秒，才能在 STARTING 阶段正确诊断。

## 后端刚重启时 CLI 连接失败

Miloco 后端重启后（OOM kill、手动重启、容器重启），需要几秒到十几秒才能开始接受连接。期间 CLI 会返回：

```json
{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}
```

**诊断步骤：**
```bash
# 1. 检查服务状态（uptime 很短 = 刚重启）
pct exec 310 -- miloco-cli service status
# {"running": true, "uptime_seconds": 9, ...}

# 2. 检查 supervisord 日志（找重启原因）
pct exec 310 -- tail -20 /root/.openclaw/miloco/log/supervisord.log
# 看 "terminated by SIGKILL" = OOM

# 3. 检查端口是否在监听
pct exec 310 -- ss -tlnp | grep 1810

# 4. 等几秒后重试
sleep 5 && miloco-cli perceive logs --jsonl --limit 5
```

**脚本中应加的重试逻辑：**
```python
import time

def get_perception_logs(max_retries=3, delay=5):
    for attempt in range(max_retries):
        result = run_cmd('export PATH=/usr/local/bin:$PATH; miloco-cli perceive logs --jsonl --limit 10 2>&1')
        try:
            data = json.loads(result)
            if 'error' not in data:
                return data
        except json.JSONDecodeError:
            pass
        if attempt < max_retries - 1:
            print(f"后端未就绪，{delay}秒后重试 ({attempt+1}/{max_retries})...")
            time.sleep(delay)
    return None
```

## 感知日志时间戳滞后检测

如果感知日志最新时间戳与当前时间差超过几个小时，说明后端曾长时间中断：

```python
from datetime import datetime, timezone

latest_ts = logs[-1].get("t", "")
if latest_ts:
    latest_dt = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    gap_hours = (now - latest_dt).total_seconds() / 3600
    if gap_hours > 2:
        print(f"⚠️ 感知数据滞后 {gap_hours:.0f} 小时，后端可能曾中断")
```

## 脚本超时设置建议

| 场景 | 建议超时 | 原因 |
|------|---------|------|
| 正常运行 + --jsonl | 15秒 | CLI 快速返回 |
| 后端 STARTING 阶段 | **60秒** | ONNX 模型加载 + API 绑定，实测 >45秒 |
| 后端刚重启（已 RUNNING） | 30-45秒 | API 已绑定但可能仍在初始化 |
| 首次启动 | 60秒 | ONNX 模型加载慢 |

**⚠️ 关键教训（2026-07-04 确认）：** 后端 STARTING → RUNNING 的过渡时间可达45-60秒。30秒超时在 STARTING 阶段必然失败。**推荐 cron 脚本超时设为60秒**，配合重试逻辑（3次，间隔5秒）。

## ⚠️ CPU 饥饿导致 pct exec 完全无响应（2026-07 发现）

当 `miloco.main` 在启动阶段加载 ONNX 模型（`bge-small-zh-v1.5-int8.onnx`、`det_4C.onnx` 等）时，可能占用 **95%+ CPU**，导致 **CT <ID> 容器内所有进程被阻塞**——不仅是 `miloco-cli`，连 `echo ok`、`cat /proc/uptime`、`ss -tlnp` 等基础命令都超时。

**与"后端未就绪"的区别：**

| 场景 | 后端状态 | pct exec 基础命令 | pct exec 系统查询 | CLI 表现 | CPU |
|------|---------|------------------|-------------------|---------|-----|
| 后端未启动 | 未运行 | ✅ 能用 | ✅ 能用 | 返回 `cannot connect` | 正常 |
| 后端正常运行 | RUNNING, CPU 低 | ✅ 能用 | ✅ 能用 | 正常返回 | 正常 |
| **CPU 饥饿** | **RUNNING, CPU 95%+** | **❌ 也超时** | **❌ 也超时** | **挂起** | **>90%** |
| **部分降级** | **RUNNING/崩溃, CPU 70-90%** | **✅ 能用** | **❌ 超时** | **挂起/报错** | **中等** |

**诊断方法（通过 PVE 宿主机，不走 pct exec）：**

```bash
# 1. 直接在 PVE 宿主机查容器进程 CPU 占用
sshpass -p 'PASS' ssh root@PVE_HOST "ps aux --sort=-%cpu | head -10"
# 找 miloco.main 进程，看 %CPU 是否 >90%

# 2. 查 PVE 整体负载
sshpass -p 'PASS' ssh root@PVE_HOST "uptime"
# load average > 核心数 = 过载

# 3. 查是否有残留的阻塞进程（之前超时的 pct exec 产生的）
sshpass -p 'PASS' ssh root@PVE_HOST "ps aux | grep 'pct exec.*310' | grep -v grep"
# 有多个 = 进程堆积，会加剧 CPU 竞争
```

**恢复步骤：**

```bash
# 1. 先清理堆积的阻塞进程
sshpass -p 'PASS' ssh root@PVE_HOST "kill -9 <PID_OF_STUCK_PROCESSES>"

# 2. 杀掉高 CPU 的 miloco.main（让 supervisord 重启）
sshpass -p 'PASS' ssh root@PVE_HOST "kill -9 <MILOCO_MAIN_PID>"
# supervisord 会自动重启（autorestart=true）

# 3. 等待新进程完成初始化（通常 30-60 秒）
sleep 30

# 4. 确认端口 1810 已绑定
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec 310 -- ss -tlnp | grep 1810"
```

**脚本防御建议：**
- 超时设为 45-60 秒（覆盖 ML 模型加载时间）
- 超时后不要立即重试——先检查 `ps aux` 确认是否 CPU 饥饿
- 如果 CPU >90%，等 60 秒再重试，而不是立即重试加重负担
- 考虑在脚本开头先检查后端是否就绪（`miloco-cli perceive devices`），未就绪时直接跳过本轮采集

## 进程存活但后端不响应（第三种故障模式）

除了"后端未启动"和"CPU饥饿"之外，还存在第三种场景：**`miloco.main` 进程在运行，但端口 1810 没有监听**。

**特征：**
- `ps aux | grep miloco` → 看到 miloco.main 进程（PID 存在）
- `ss -tlnp | grep 1810` → **无输出**（端口未绑定）
- `miloco-cli perceive logs` → `cannot connect to Miloco backend`
- `pct exec` 基础命令（`echo ok`、`cat /proc/uptime`）→ **正常响应**（与 CPU 饥饿不同）

**可能原因：**
- 后端启动过程中某步骤卡住（如 ONNX 模型加载失败但进程未退出）
- 配置文件错误导致 Uvicorn 无法绑定端口
- 后端进程处于僵尸/半死状态

**诊断步骤：**
```bash
# 1. 确认进程存在但端口未绑定
pct exec 310 -- ps aux | grep miloco | grep -v grep
pct exec 310 -- ss -tlnp | grep 1810
# 进程存在 + 端口未绑定 = 第三种故障

# 2. 检查 supervisord 日志找根因
pct exec 310 -- tail -30 /root/.openclaw/miloco/log/supervisord.log
# 看是否有 error/warning 但进程未被 kill

# 3. 检查 miloco 后端日志（如果有）
pct exec 310 -- ls -la /root/.openclaw/miloco/log/
pct exec 310 -- tail -30 /root/.openclaw/miloco/log/*.log

# 4. 杀掉进程让 supervisord 重启
sshpass -p 'PASS' ssh root@PVE_HOST "kill -9 <MILICO_MAIN_PID>"
# supervisord autorestart=true 会自动拉起新进程

# 5. 等待 30-60 秒后验证端口
sleep 30
pct exec 310 -- ss -tlnp | grep 1810
```

## ⚠️ supervisorctl 在 pct exec 中可能挂起或拒绝连接

当 supervisord 管理的服务处于异常状态（如反复 SIGKILL 重启循环）时，`supervisorctl` 命令本身可能**无限挂起**：

```bash
# ❌ 这些命令可能挂起不返回
pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf status
pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf restart all
```

**原因：** supervisord 通过 UNIX socket 与 supervisorctl 通信，当子服务状态异常时，socket 通信可能阻塞。

### supervisord 进程在但 HTTP API（端口 9001）未绑定

另一种场景：supervisord 进程存在（`ps aux | grep supervisord` 有输出），但 `supervisorctl` 报 `http://localhost:9001 refused connection`。这意味着 supervisord 的 HTTP/XML-RPC 接口没有启动或已崩溃，但 supervisord 主进程仍存活。

**症状：**
- `ps aux | grep supervisord` → 进程存在
- `supervisorctl status` → `http://localhost:9001 refused connection`
- 子服务（如 miloco.main）可能在运行但状态不受 supervisord 管控

**恢复（杀掉 supervisord + 子服务，全部重启）：**
```bash
# 1. 杀掉 supervisord 和所有子服务
sshpass -p 'PASS' ssh root@PVE_HOST "kill -9 $(pgrep -f supervisord) $(pgrep -f miloco.main) 2>/dev/null"
sleep 2

# 2. 重启 supervisord（它会自动拉起子服务）
sshpass -p 'PASS' ssh root@PVE_HOST \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; supervisord -c /root/.openclaw/miloco/supervisord.conf'"
sleep 15  # 等待 ONNX 模型加载

# 3. 验证全部恢复
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec 310 -- ss -tlnp | grep 1810"  # 端口绑定
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec 310 -- curl -s --max-time 3 http://127.0.0.1:1810/ | head -1"  # Web UI
```

**替代方案：直接操作进程（不经过 supervisorctl）**
```bash
# 绕过 supervisorctl，直接 kill 进程
sshpass -p 'PASS' ssh root@PVE_HOST "ps aux | grep miloco | grep -v grep"
sshpass -p 'PASS' ssh root@PVE_HOST "kill -9 <PID>"
# supervisord 会自动重启（autorestart=true）

# 如果 supervisord 本身也卡了，重启 supervisord
sshpass -p 'PASS' ssh root@PVE_HOST "kill -9 <SUPERVISORD_PID>"
# supervisord 通常由 init 管理，会自动重启
```

**诊断命令（不经过 pct exec，直接在 PVE 宿主机）：**
```bash
# 在 PVE 宿主机上查看容器内进程（不走 pct exec，避免阻塞）
sshpass -p 'PASS' ssh root@PVE_HOST "ps aux --sort=-%cpu | head -10"
sshpass -p 'PASS' ssh root@PVE_HOST "cat /proc/$(sshpass -p 'PASS' ssh root@PVE_HOST 'pgrep -f miloco.main')/status 2>/dev/null | grep -E 'State|VmRSS'"
```

## 绕过 miloco-cli：直接调用 API（调试/备用方案）

当 `miloco-cli` 挂起、`pct exec` 链路超时、或需要快速验证后端是否正常时，**直接用 curl 调 Miloco REST API** 是最可靠的方式。

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/perception/logs` | GET | 感知日志（需要 `?limit=N` 参数） |
| `/api/perception/devices` | GET | 感知设备列表 |
| `/api/perception/perceive` | POST | 主动感知查询 |
| `/api/perception/clear` | POST | 清除感知缓存 |

**⚠️ 端口 1810 只绑定在容器内 127.0.0.1**，不能从 PVE 宿主机直接访问。必须通过 `pct exec` 在容器内执行 curl。

### 获取 Bearer Token

Token 在配置文件中：
```bash
pct exec 310 -- python3 -c "import json; print(json.load(open('/root/.openclaw/miloco/config.json'))['server']['token'])"
```

### 直接 curl 调用示例

```bash
# 在 CT <ID> 容器内执行（通过 pct exec）
TOKEN=$(pct exec 310 -- python3 -c "import json; print(json.load(open('/root/.openclaw/miloco/config.json'))['server']['token'])")

pct exec 310 -- curl -s --connect-timeout 5 --max-time 10 \
  -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:1810/api/perception/logs?limit=10"
```

**返回格式：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "logs": [
      {
        "id": "uuid",
        "t": "2026-06-24T17:31:43+00:00",
        "d": {
          "三楼书房": "user赤裸上身坐在书房的电脑桌前。",
          "前院": "前院露台区域无人、无宠物活动。"
        }
      }
    ],
    "count": 10,
    "total_inferences": 0
  }
}
```

**与 miloco-cli 的区别：**
- `code: 0` = 成功；非零 = 失败（CLI 会 `sys.exit(3)`）
- `d` 字段是 `{区域: 描述}` 字典，不是字符串
- 没有 cursor 自动管理（需要手动传 `?after=<ISO时间>` 增量拉取）

### 何时使用直接 API

| 场景 | 推荐方式 |
|------|---------|
| 正常 cron 采集 | `miloco-cli perceive logs --jsonl --limit N` |
| CLI 挂起/超时 | 直接 curl API |
| 验证后端是否正常 | `curl http://127.0.0.1:1810/`（返回 HTML = 正常） |
| 调试 API 返回结构 | curl + jq |
| miloco-cli 未安装/PATH 问题 | 直接 curl API |

### ⚠️ API 鉴权错误

如果返回 `{"code":1003,"message":"Invalid or missing service token"}`，说明：
- Token 未传或格式错误（必须是 `Bearer <token>`）
- Token 与 config.json 中的不匹配

## ⚠️ `pct exec` 挂起时的备用方案：`lxc-attach`（2026-07-04 发现）

当容器处于内存压力（cgroup memory 达到上限）或 PVE 任务层阻塞时，`pct exec` 会挂起，但 `lxc-attach` 仍可正常工作。这是因为 `pct exec` 经过 PVE 的任务管理层（需要获取锁），而 `lxc-attach` 直接进入容器的命名空间。

**诊断容器内存是否到上限：**
```bash
# 从 PVE 宿主机检查（不走 pct exec）
sshpass -p 'PASS' ssh root@PVE_HOST "cat /sys/fs/cgroup/lxc/310/memory.current; cat /sys/fs/cgroup/lxc/310/memory.max"
# 如果 current == max → 容器内存满，pct exec 很可能挂起
```

**备用方案：用 `lxc-attach` 替代 `pct exec`：**
```bash
# ❌ pct exec 挂起
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec 310 -- echo OK"  # 超时

# ✅ lxc-attach 正常
sshpass -p 'PASS' ssh root@PVE_HOST "lxc-attach -n 310 -- echo OK"  # 立即返回
```

**Python 脚本中的写法：**
```python
def run_cmd(cmd, timeout=60):
    """通过 PVE SSH 在 CT <ID> 里执行命令 (使用 lxc-attach 比 pct exec 更可靠)"""
    full_cmd = f"sshpass -p \"{SSH_PASS}\" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 root@{PVE_HOST} \"lxc-attach -n {CTID} -- bash -c '{cmd}'\""
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip()
```

**⚠️ 注意：`lxc-attach` 也需要容器已启动。** 如果容器本身 stopped，`lxc-attach` 也会失败。先用 `pct status <VMID>` 确认容器 running。

**恢复内存压力的容器：**
```bash
# 停止 + 启动（比 reboot 更可控）
sshpass -p 'PASS' ssh root@PVE_HOST "pct stop 310 && sleep 3 && pct start 310"
```

## ⚠️ `miloco-cli service status` 内部 supervisorctl PATH 问题（2026-07-04 发现）

`miloco-cli service status` 内部调用 `supervisorctl`，但 `supervisorctl` 位于 `/usr/local/bin/`，在 `pct exec` 的默认 PATH 中可能不存在。

**症状：** `miloco-cli service status` 报 `FileNotFoundError: [Errno 2] No such file or directory: 'supervisorctl'`，或者挂起不返回。

**修复：** 在命令前设置 PATH：
```bash
# ❌ supervisorctl 找不到
pct exec 310 -- miloco-cli service status

# ✅ 手动设置 PATH
pct exec 310 -- env PATH=/usr/local/bin miloco-cli service status

# ✅ 或者用 bash -c
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli service status'
```

**更好的方案：跳过 `miloco-cli service status`，用 `miloco-cli perceive logs --jsonl --limit 1` 做健康检查。** 这样一个命令同时验证了：(1) 后端进程在运行，(2) API 端口在监听，(3) 感知功能正常。

## ✅ 已修复脚本：~/.hermes/scripts/miloco-perceive.py（2026-07-04 修复）

该 cron 脚本在 2026-07-04 cron 运行时因 TimeoutExpired 崩溃。根因：CT <ID> 容器内存达到 2GB 上限，`pct exec` 全部挂起。

### 修复内容
1. ✅ **`pct exec` → `lxc-attach`** — 内存压力下仍可正常工作
2. ✅ **超时改为 60 秒** — 覆盖后端 STARTING 阶段
3. ✅ **`ensure_backend()` 用 `miloco-cli perceive logs` 做健康检查** — 绕过 supervisorctl PATH 问题
4. ✅ **添加 try/except 错误处理** — 超时和 JSON 解析异常不再崩溃
5. ✅ **添加重试逻辑** — 后端不可用时尝试 `miloco-cli service start`

### 修复要点（供参考）
- `lxc-attach` 比 `pct exec` 在内存压力下更可靠
- `ensure_backend()` 不应使用 `miloco-cli service status`（supervisorctl PATH 问题），改用 `miloco-cli perceive logs --limit 1`
- 容器内存到上限时需 `pct stop` + `pct start` 恢复（比 reboot 更可控）

## ⚠️ 容器重启后 supervisord 不自动启动（2026-07-03 发现）

CT <ID> 重启后（`pct reboot 310`），supervisord **不会自动启动**。原因是 supervisord 不是 systemd 服务——它是通过 `nohup supervisord -c ...` 手动启动的。

**症状：** `pct reboot` 后，`ps aux | grep miloco` 无输出，但 `pct status 310` 显示 `running`。

**恢复（优先用 miloco-cli，备选手动 supervisord）：**
```bash
# ✅ 首选：miloco-cli service start（自动处理 supervisord + 等待就绪）
sshpass -p 'PASS' ssh root@PVE_HOST \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli service start'"
# 返回 {"code":0,"message":"started","pid":351} = 成功
# 等待 5-10 秒后验证
sleep 5
sshpass -p 'PASS' ssh root@PVE_HOST \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli service status'"
# {"running": true, "uptime_seconds": 26, ...} = 后端就绪

# 备选：手动启动 supervisord（当 miloco-cli 不可用时）
sshpass -p 'PASS' ssh root@PVE_HOST \
  "pct exec 310 -- nohup /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf > /dev/null 2>&1 &"
# 等待 15-20 秒让 ONNX 模型加载
sleep 15
sshpass -p 'PASS' ssh root@PVE_HOST \
  "pct exec 310 -- ss -tlnp | grep 1810"
```

**永久修复（可选）：** 创建 systemd 服务让 supervisord 自动启动：
```bash
pct exec 310 -- bash -c 'cat > /etc/systemd/system/miloco-supervisord.service << EOF
[Unit]
Description=Miloco Supervisord
After=network.target

[Service]
Type=forking
ExecStart=/usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf
ExecStop=/usr/local/bin/supervisorctl -c /root/.openclaw/miloco/supervisord.conf shutdown
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable miloco-supervisord'
```

## ⚠️ 端口监听但 API 挂起（第四种故障模式，2026-07-03 发现）

`miloco.main` 进程运行，端口 1810 在监听，`curl http://127.0.0.1:1810/` 能返回 Web UI 的 HTML，但 **API 端点无响应，`miloco-cli` 命令挂起或返回 `cannot connect`**。

**与前三种故障的区别：**

| 场景 | 进程 | 端口 1810 | Web UI | pct exec 基础命令 | miloco-cli | CPU |
|------|------|-----------|--------|-------------------|------------|-----|
| 后端未启动 | ❌ 无 | ❌ 无 | ❌ 无 | ✅ 正常 | `cannot connect` | 正常 |
| CPU 饥饿 | ✅ 有 | ⚠️ 可能绑定 | ⚠️ 可能超时 | **❌ 全超时** | **❌ 全超时** | **>90%** |
| 进程活但端口未绑定 | ✅ 有 | ❌ 无 | ❌ 无 | ✅ 正常 | `cannot connect` | 正常 |
| **端口监听但 API 挂起** | **✅ 有** | **✅ 有** | **✅ 返回 HTML** | **✅ 正常** | **❌ 挂起/报错** | **正常** |
| **容器内部 hang（无锁）** | **❓ 不确定** | **❓ 不确定** | **❓ 不确定** | **❌ 全超时** | **❌ 全超时** | **正常** |

**诊断步骤：**

```bash
# 1. 确认端口在监听
pct exec 310 -- ss -tlnp | grep 1810
# 输出: LISTEN ... python3 ... pid=256203 ... → 端口已绑定 ✅

# 2. 测试 Web UI（静态文件服务）
pct exec 310 -- curl -s --max-time 3 http://127.0.0.1:1810/ | head -5
# 返回 HTML → 静态文件服务正常 ✅

# 3. 测试 API 端点
pct exec 310 -- curl -s --max-time 5 http://127.0.0.1:1810/api/perception/logs?limit=3
# 挂起或返回错误 → API 层挂起 ❌

# 4. 测试 miloco-cli
pct exec 310 -- timeout 5 miloco-cli --help
# 挂起 → CLI 自身也被阻塞 ❌

# 5. 测试 pct exec 基础命令（排除 CPU 饥饿）
pct exec 310 -- echo ok && pct exec 310 -- cat /proc/uptime
# 正常返回 → 不是 CPU 饥饿 ✅

# 6. 检查 CPU（排除高负载）
sshpass -p 'PASS' ssh root@PVE_HOST "ps aux --sort=-%cpu | head -5"
# miloco.main CPU <20% → 不是 ML 推理阻塞
```

**可能原因：**
- Uvicorn worker 线程全部阻塞（如数据库锁、死锁、长请求占用所有 worker）
- FastAPI app 进入异常状态（如 ONNX 推理线程持有 GIL 阻塞 API server）
- 后端正在处理一个极长的推理请求，阻塞了所有其他请求

**恢复步骤：**

```bash
# 杀掉 miloco.main（让 supervisord 重启）
sshpass -p 'PASS' ssh root@PVE_HOST "kill -9 $(pgrep -f miloco.main)"
# 等待 supervisord 自动重启
sleep 30
# 验证 API 恢复
pct exec 310 -- curl -s --max-time 5 http://127.0.0.1:1810/ | head -3
```

**⚠️ 关键区别：** 这种情况下 `miloco-cli --help` 也会挂起（不是 miloco-cli 本身的问题，而是后端 API 不响应导致 CLI 的健康检查阻塞）。不要误判为 miloco-cli 安装损坏。

## ⚠️ pct exec 挂起：PVE 任务锁未释放（2026-07-03 发现）

当 `pct exec` 命令（包括简单的 `echo test`）都超时时，可能**不是容器问题**，而是 PVE 宿主机上的任务锁被卡住。

**根因：** PVE 的 `vzreboot`、`vzrelocate`、备份等任务会获取 `/run/lock/lxc/pve-config-<VMID>.lock`。如果任务卡死（网络问题、存储超时等），锁不会释放，导致所有对该容器的 `pct exec`/`pct stop`/`pct reboot` 命令挂起。

**诊断（通过 PVE SSH，不走 pct exec）：**

```bash
# 1. 检查容器状态（pct status 不需要锁）
sshpass -p 'PASS' ssh root@PVE_HOST "pct status 310"
# 输出 "status: running" → 容器本身没问题，是 pct exec 被锁阻塞

# 2. 检查锁文件
sshpass -p 'PASS' ssh root@PVE_HOST "ls -la /run/lock/lxc/pve-config-310.lock"

# 3. 找到持有锁的进程
sshpass -p 'PASS' ssh root@PVE_HOST "fuser /run/lock/lxc/pve-config-310.lock"
# 输出 PID → 这就是卡住的任务

# 4. 确认任务类型
sshpass -p 'PASS' ssh root@PVE_HOST "ps aux | grep <PID> | grep -v grep"
# 典型输出: task UPID:pve:...:vzreboot:310:root@pam: → 重启任务卡住了
```

**恢复：**

```bash
# 1. 杀掉卡死的任务进程
sshpass -p 'PASS' ssh root@PVE_HOST "kill -9 <PID>"

# 2. 清理锁文件（确保释放）
sshpass -p 'PASS' ssh root@PVE_HOST "rm -f /run/lock/lxc/pve-config-310.lock"

# 3. 验证 pct exec 恢复
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec 310 -- echo OK"
```

**与其他故障模式的区别：**

| 症状 | 后端未启动 | CPU 饥饿 | **任务锁卡住** |
|------|-----------|----------|---------------|
| `pct status` | running | running | **running** |
| `pct exec -- echo ok` | ✅ 正常 | ❌ 超时 | **❌ 超时** |
| `fuser lock文件` | 无输出 | 无输出 | **有 PID** |
| 容器内进程 | 无 miloco | CPU >90% | 正常 |

**⚠️ 注意：** 不要对卡住的任务执行 `pct stop` 或 `pct reboot`——这些操作也需要获取同一个锁，会继续挂起。必须先 `kill -9` 释放锁。

## ⚠️ 部分降级：简单命令可用但系统查询挂起（2026-07-04 发现）

CT <ID> 容器存在一种**介于正常和完全阻塞之间的中间状态**：

| pct exec 命令 | 结果 |
|---------------|------|
| `echo hello` | ✅ 正常返回 |
| `hostname -I` | ✅ 正常返回 |
| `ps aux` | ❌ 挂起超时 |
| `ss -tlnp` | ❌ 挂起超时 |
| `uptime` | ❌ 挂起超时 |
| `systemctl status` | ❌ 挂起超时 |
| `curl http://127.0.0.1:1810/` | 连接拒绝（端口未监听） |

**与完全 CPU 饥饿的区别：** CPU 饥饿时 `echo hello` 也挂起；部分降级时简单命令仍能返回，但涉及 `/proc`、`/sys`、网络查询的命令全部卡死。可能是 ONNX 模型加载占用大量 CPU 但未完全满载（70-90%），或者容器 I/O 阻塞导致 `/proc` 读取缓慢。

**⚠️ `ensure_backend()` 函数本身的陷阱：**

旧实现用 `ss -tln | grep :1810` 检查端口。在部分降级状态下，`ss` 命令本身会挂起，导致 `ensure_backend()` 也超时——**健康检查本身变成了问题的一部分**。

**推荐方案（已验证）：用 `miloco-cli service status` 替代 `ss` 或 `curl`。**

`miloco-cli service status` 返回结构化 JSON，解析 `"running": true` 即可判断后端状态。比 `ss` 更快且不会因 `/proc` 读取卡住。

```python
# ✅ 推荐：miloco-cli service status
check_cmd = f'sshpass -p "{SSH_PASS}" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 root@{PVE_HOST} \
  "pct exec {CTID} -- bash -c \'export PATH=/usr/local/bin:$PATH; miloco-cli service status 2>/dev/null\'"'
result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, timeout=30)
if '"running": true' in result.stdout:
    return False  # 后端正常
```

**诊断步骤（区分七种故障模式）：**

```bash
# 步骤 1：测试简单 pct exec（排除任务锁和完全阻塞）
pct exec 310 -- echo hello
# 不返回 → 任务锁卡住（查 fuser /run/lock/lxc/pve-config-310.lock）
# 返回 → 继续

# 步骤 2：用 miloco-cli service status 测试后端（最可靠）
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli service status'
# 返回 JSON + "running": true → 后端正常
# 返回 JSON + "running": false → 后端未启动
# 挂起 → 需要继续诊断

# 步骤 3：如果 miloco-cli 也挂起，用 curl 测试
pct exec 310 -- curl -s --max-time 3 http://127.0.0.1:1810/ | head -1
# 返回 HTML → 后端正常
# 连接拒绝 → 后端未启动
# 挂起 → 后端 API 层挂起

# 步骤 4：检查进程（此时 ps 可能也挂起）
# 不走 pct exec，直接在 PVE 宿主机查容器进程
ps aux | grep miloco | grep -v grep
# 无进程 → 后端未启动
# 有进程 + CPU 高 → CPU 饥饿
# 有进程 + CPU 正常 → 第四种故障（端口监听但 API 挂起）
```

**恢复优先级（部分降级时）：**
1. 先清理堆积的阻塞进程：`ps aux | grep 'pct exec.*310' | grep -v grep` → `kill -9` 全部
2. 检查是否有 miloco.main 进程：有则 kill 让 supervisord 重启
3. 如果 supervisord 也卡了：全部 kill + 重启 supervisord
4. 等 30-60 秒后用 curl 或 miloco-cli 验证

**⚠️ 避免在部分降级时多次重试 `ensure_backend()`：** 每次超时的 `pct exec` 会留下阻塞进程堆积，加剧问题。最多重试 1 次，第 2 次前必须先清理堆积进程。

## ⚠️ pct exec 短暂超时（Transient Timeout）— 重试即可恢复（2026-07-04 发现）

`pct exec` 命令偶尔会出现短暂超时（连续失败 3-5 次），但随后自动恢复正常。这与永久性故障（任务锁卡住、CPU 饥饿、内存压力）不同，**不需要干预，只需重试**。

**特征：**
- 连续超时 3-5 次后，`pct exec 310 -- echo OK` 突然恢复正常
- `pct status 310` 始终正常返回（不受影响，因为它不走 pct exec 的任务管理层）
- 容器内服务（miloco）本身正常运行

**诊断模式：**
```bash
# 1. pct status 不需要锁，始终可靠
pct status 310  # → status: running ✅

# 2. pct exec 暂时不可用 → 重试 2-3 次
pct exec 310 -- echo OK  # 超时
pct exec 310 -- echo OK  # 超时
pct exec 310 -- echo OK  # ✅ 恢复

# 3. 如果 5 次重试都失败 → 可能是真正的故障（检查任务锁/内存压力）
```

**何时不需要恐慌：**
- pct status 正常 + pct exec 超时 → 很可能是短暂超时，等 10 秒重试
- 只有复杂命令（miloco-cli）超时，简单命令（echo OK）正常 → 后端可能在启动中

**何时需要干预：**
- 5 次重试全部超时 → 检查任务锁（`fuser /run/lock/lxc/pve-config-310.lock`）
- pct status 也异常 → 容器本身有问题
- 恢复后又反复超时 → 可能是内存压力（检查 cgroup memory）

**⚠️ 不要对短暂超时执行 `pct stop`/`pct reboot`** — 这些操作本身也需要 pct exec 通路，会加剧问题。

## ⚠️ 间歇性降级周期（服务反复可用/不可用，2026-07-04 发现）

`miloco-cli` 服务命令（`perceive logs`、`service status`）可能呈现**间歇性降级**：服务正常运行一段时间（返回"没有新的感知事件"），然后突然开始超时，持续几分钟后又自行恢复。

**典型时间线：**
```
23:00 — 超时（首次报告）
23:06 — 正常（"没有新的感知事件"）
23:14 — 正常
23:22 — 正常
23:31 — 又超时了（本次发现）
```

**特征：**
- `pct exec` 基础命令（`echo OK`、`ls`）始终正常
- `miloco-cli --help` 始终正常（静态帮助，不走后端）
- `miloco-cli perceive logs` 和 `miloco-cli service status` 间歇性超时
- 服务自行恢复，无需人工干预

**诊断要点：**
1. 如果服务刚在几轮前正常返回过数据，很可能是间歇性降级而非永久性故障
2. 间歇性降级 ≠ 容器 hang（容器 hang 时 `echo OK` 也超时）
3. 间歇性降级通常不需要立即重启——等几分钟重试即可
4. 如果降级周期越来越短（从几小时缩短到几分钟），可能在演变为永久性故障

**可能原因：**
- ONNX 模型推理周期性占用大量 CPU（每次推理时超时，推理完成后恢复）
- 内存压力周期性触发 cgroup 限制（GC 前超时，GC 后恢复）
- 后端 worker 线程周期性阻塞（长推理请求阻塞所有 worker）

**处理建议：**
- 在 cron 脚本中，如果本轮超时但前几轮正常，记录为"间歇性降级"而非"服务不可用"
- 不要在间歇性降级时立即重启——这会打断可能正在恢复的周期
- 如果连续 3+ 轮都超时（约 30 分钟），才考虑人工干预

## 完整诊断流程（六种故障模式速查）

当 `miloco-perceive.py` 超时时，按此顺序排查（覆盖七种故障模式）：

| 步骤 | 检查项 | 命令 | 判断 |
|------|--------|------|------|
| 1 | SSH 连通性 | `sshpass ... ssh root@PVE "echo OK"` | 失败 → 网络问题 |
| 2 | pct status（不需要锁） | `pct status 310` | 失败 → 容器已停止 |
| 3 | pct exec 可用性 | `pct exec 310 -- echo OK` | 失败 → 暂时超时/任务锁/CPU饥饿/内存压力 |
| 3a | 暂时超时（重试 3 次） | `pct exec 310 -- echo OK` x3 | 恢复 → 短暂超时，无需干预 |
| 3b | 容器内部 hang（无锁，重试仍失败） | `fuser /run/lock/lxc/pve-config-310.lock` → 无输出 | 无锁占用 → **直接 `pct reboot 310`**（最简单恢复路径） |
| 3c | 任务锁检查（重试仍失败） | `fuser /run/lock/lxc/pve-config-310.lock` | 有 PID → 任务锁卡住，先 kill |
| 3d | 内存压力检查 | `cat /sys/fs/cgroup/lxc/310/memory.current` | current == max → 用 lxc-attach |
| 4 | miloco.main 进程 | `ps aux \| grep miloco \| grep -v grep` | 无进程 → 后端未启动 |
| 5 | 端口 1810 | `ss -tlnp \| grep 1810` | 进程在但端口未绑定 → 第三种故障 |
| 6 | supervisord 日志 | `tail -30 supervisord.log` | 找 SIGKILL/error |
| 7 | CPU 占用 | `ps aux --sort=-%cpu \| head -5` | miloco.main >90% → CPU 饥饿 |

**恢复优先级：**
1. 先清理堆积的阻塞进程（`kill -9` stuck pct exec）
2. 杀掉异常的 miloco.main（让 supervisord 重启）
3. 等待 30-60 秒
4. 验证端口 1810 已绑定 + API 可响应（`curl http://127.0.0.1:1810/`）
5. 重试 miloco-cli 命令

**⚠️ 端口绑定 ≠ API 可用。** 验证恢复时不要只检查 `ss -tlnp | grep 1810`——端口绑定只能说明 TCP listener 在，不能说明 API 端点正常。应同时测试：
```bash
pct exec 310 -- ss -tlnp | grep 1810           # 端口绑定
pct exec 310 -- curl -s --max-time 3 http://127.0.0.1:1810/ | head -1  # Web UI
pct exec 310 -- curl -s --max-time 5 http://127.0.0.1:1810/api/perception/logs?limit=1  # API
```