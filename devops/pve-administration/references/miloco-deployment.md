# Xiaomi Miloco 2.0 部署记录 (CT <ID>)

## 环境

| 项目 | 值 |
|------|-----|
| VMID | 310 |
| IP | 192.0.2.10 |
| OS | Debian 12 |
| 资源 | ⚠️ 2核/1GB/20GB（**1GB 会 OOM，至少需要 2048MB**） |
| Miloco 版本 | 2026.9.11（2026-10 升级；运行时装在 uv 前缀 `/root/.local/share/uv/tools/miloco/`，`pip3 list` 里的 2026.6.18 是已废弃的旧 pip 包，不代表实际运行版本） |
| Web 面板 | http://192.0.2.10:1810 |
| 安装路径 | /opt/xiaomi-miloco (源码) |
| 配置目录 | /root/.openclaw/miloco/ |
| 日志 | /root/.openclaw/miloco/log/miloco-backend.log |

## 安装步骤（推荐）

1. 创建 LXC 容器（Debian 12, 2核/4GB/20GB, bridged vmbr0）
2. 换 apt 清华源 + 配 DNS（203.0.113.1）
3. `apt install git python3 python3-pip`
4. `git clone https://github.com/xiaomi/miloco /opt/xiaomi-miloco`
5. 手动安装 uv：`pip install --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple uv`
6. 手动下载 release 包（install.sh 的自动下载极慢）：
   ```bash
   cd /tmp && uv download miloco==2026.6.18 --python-version 3.11
   # 或从 GitHub releases 手动下载 .whl 文件
   ```
7. 用 `--no-deps` 安装三个 .whl 包：
   ```bash
   pip install --break-system-packages --no-deps \
     miloco-2026.6.18-py3-none-any.whl \
     miloco_cli-2026.6.18-py3-none-any.whl \
     miloco_miot-2026.6.18-py3-none-manylinux_2_28_x86_64.whl
   ```
8. 逐个补依赖（清华源）：
   ```bash
   pip install --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple \
     uvicorn fastapi scipy tokenizers onnxruntime opencv-python-headless \
     aiofiles aiohttp av fastmcp paho-mqtt pillow psutil zeroconf aiocache
   ```
9. 配置：
   ```bash
   miloco-cli config set server.python_bin /usr/bin/python3
   miloco-cli config set model.omni.api_key <MIMO_API_KEY>
   miloco-cli config set model.omni.base_url https://api.xiaomimimo.com/v1
   miloco-cli config set model.omni.model xiaomi/mimo-v2.5
   ```
10. 解压模型文件（必须！否则感知引擎报"模型文件缺失"）：
    ```bash
    tar -xzf /tmp/miloco-models-2026.6.18.tar.gz -C /root/.openclaw/miloco/models/
    # 验证：ls /root/.openclaw/miloco/models/
    # 应有: bge-small-zh-v1.5-int8.onnx, bge-small-zh-v1.5-tokenizer.json,
    #        det_4C.onnx, human_body_reid_v2.onnx, silero_vad.onnx
    ```
11. 启动：`miloco-cli service start`

## ⚠️ 已知坑（按踩坑顺序）

### 1. install.sh 极慢 — 必须绕过
脚本从 `releases.astral.sh` 下载 uv，在中国基本不通（>5分钟无响应）。**直接手动执行各步骤，不要跑 install.sh。**

### 2. uv 从 pip 清华源安装
```bash
pip3 install --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple uv
```
装好后如果脚本仍检测不到 uv，复制到 `/usr/local/bin/`。

### 3. OpenClash 代理返回 407
iStoreOS 的 Clash 代理对 pip HTTPS 请求返回 `407 Proxy Authentication Required`。**不要配代理给 pip，直接用国内镜像（清华源）。**

### 4. `--no-deps` 后逐批补依赖
装三个 .whl 后缺大量依赖。按报错分批装：
```bash
# 第一批：核心
pip install --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple \
  uvicorn fastapi scipy tokenizers onnxruntime opencv-python-headless

# 第二批：miot 依赖
pip install --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple \
  aiofiles aiohttp av fastmcp paho-mqtt pillow psutil zeroconf aiocache

# pydantic 可能版本冲突，强制升级
pip install --break-system-packages -i https://pypi.tuna.tsinghua.edu.cn/simple "pydantic>=2.13.4"
```

### 5. ⭐ server.host 默认 127.0.0.1 — 必须改 config.json
这是最容易踩的坑。`miloco-cli config set` 不支持 `server.host` 和 `server.port`，**必须直接编辑 JSON 文件**：

```bash
# 编辑配置
cat > /root/.openclaw/miloco/config.json << 'EOF'
{
  "server": {
    "python_bin": "/usr/bin/python3",
    "host": "0.0.0.0",
    "port": 1810,
    "token": "你的token"
  },
  "model": {
    "omni": {
      "api_key": "你的MIMO_API_KEY",
      "base_url": "https://api.xiaomimimo.com/v1",
      "model": "xiaomi/mimo-v2.5"
    }
  }
}
EOF

# 然后重启服务
miloco-cli service restart
```

配置文件路径：`/root/.openclaw/miloco/config.json`（JSON 格式，不是 YAML）。

### 6. miloco-cli 启动后验证
```bash
# 检查是否绑定 0.0.0.0
ss -tlnp | grep 1810
# 应显示: 0.0.0.0:1810（不是 127.0.0.1:1810）

# 检查日志
tail -5 /root/.openclaw/miloco/log/miloco-backend.log
# 看到 "Application startup complete" + "Uvicorn running on http://0.0.0.0:1810" 就对了
```

## 升级到新版（官方 install.sh 两阶段，2026-10 实测 2026.6.18 → 2026.9.11）

升级 ≠ 首次安装：CT <ID> 网络能通 GitHub/astral.sh 时，**官方脚本可直接跑**，账号（`account.is_bound`）与模型配置会在 AGENT_JSON 里回显保留，上面那套「绕过 install.sh 手动装 .whl」只用于装不上的场景。

```bash
# 0) 先查有无新版（装前必做）
# GitHub releases: github.com/XiaoMi/xiaomi-miloco → 最新 tag 对比本机版本

# 1) 备份（数据目录整份 + 版本留底）
BK=/root/.openclaw/miloco/backup-$(date +%Y%m%d-%H%M%S); mkdir -p "$BK"
cp -a /root/.openclaw/miloco/config.json /root/.openclaw/miloco/miloco.db \
      /root/.openclaw/miloco/observability.db* "$BK"/
pip3 list 2>/dev/null | grep -i miloco > /root/.openclaw/miloco/version-backup.txt

# 2) 停服务（用 supervisorctl，别用 pkill）
/usr/local/bin/supervisorctl -c /root/.openclaw/miloco/supervisord.conf stop all

# 3) 两阶段安装（脚本传到 CT <ID> 后执行）
bash /tmp/miloco-install.sh --agent-prepare   # 环境检查+装包+服务初始化，回显 AGENT_JSON
echo $? # 看 "account.is_bound": true / "model.configured": true 是否保留
bash /tmp/miloco-install.sh --agent-finish    # 非交互下跳过账号/模型重绑定（已绑即正确）

# 4) 手动启动（两个阶段都不会把服务拉起来）
/usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf
# 等 15~20s → ss -lnt 里有 1810 → curl http://<CT <ID>>:1810/ 返回 200
```

**升级四个固定陷阱：**

1. **装完 `pip3 list` 仍显示旧版本** —— 新版装进 uv 前缀（`…/uv/tools/miloco/` 的 venv），系统 pip 的旧三件套并存但不再被调用。**以 supervisord.conf 的 `command` 为准**（它已被改写成新 python 路径），验证版本用那个 python：
   `pct exec 310 -- /root/.local/share/uv/tools/miloco/bin/python -c "import importlib.metadata as m; print(m.version('miloco'))"`
2. **启动 supervisord 别和 `pkill` 同一条命令** —— 先 pkill 再起的竞态会把刚 spawn 的 miloco-backend 用 SIGTERM 打死，supervisord.log 里表现为 uptime 秒级 `stopped: miloco-backend (terminated by SIGTERM)`、端口又空了。干净启动：只跑 supervisord 一条，等 15~20s 再验。
3. **`--agent-finish` 的 OpenClaw 插件步报 `openclaw command not found` 属预期**（容器里没装 openclaw/node/npm 运行时），不影响后端与网页；是否给 Hermes 接入是独立决策（`--agent-platform hermes` 会装 16 个 skill，常驻描述约 900 token/轮），不是升级的一部分。
4. **「删 OpenClaw」只删源码目录** `/opt/xiaomi-miloco/plugins/openclaw/`（+ `scripts/openclaw_config_tool.py`，先 `tar czf` 存档再删）。`/root/.openclaw/` 是 miloco 的 MILOCO_HOME（supervisord.conf、config.json、数据库全在里面），名字带 openclaw 但与 OpenClaw 运行时无关，动它 = 删数据。

## 配置项

通过 `miloco-cli config set` 可用的 path：
- `server.python_bin` — Python 路径（必填）
- `server.token` — Web 面板认证 token
- `server.url` — 服务 URL
- `server.tls_certfile` / `server.tls_keyfile` — 已废弃，忽略
- `model.omni.api_key` — MiMo API Key
- `model.omni.base_url` — MiMo API 地址
- `model.omni.model` — 模型名
- `agent.auth_bearer` — Agent 认证
- `agent.webhook_url` — Webhook 回调

**不可通过 CLI 设置，需直接编辑 config.json：**
- `server.host` — 默认 127.0.0.1，改 0.0.0.0 才能外部访问
- `server.port` — 默认 1810

**⚠️ 改完 config.json 后必须 `miloco-cli service restart` 生效。**

## Miloco 架构

Miloco 2.0 设计为 **OpenClaw 的插件**（Agent plugin），但可以**独立运行**：

```
OpenClaw / Hermes（AI 大脑）
       ↕ HTTP API / CLI / Webhook
   Miloco（身体：感知+控制）
       ↕ MIoT 协议
   米家设备（灯、空调、摄像头...）
```

- 安装包内含 `miloco-openclaw-plugin-2026.6.18.tgz`（OpenClaw 插件，独立模式不需要）
- 独立模式下 Web 面板 + CLI + HTTP API 全可用
- 已知 OpenClaw skill 安装指南：`https://raw.githubusercontent.com/XiaoMi/xiaomi-miloco/main/scripts/install-guide.md`
- Miloco 可通过 MCP 或 HTTP API 与 Hermes 集成（待开发）

## 已知设备 DID（user，按楼层）

### 一楼（客厅层）

| 设备名 | DID | 房间 | 类型 |
|--------|-----|------|------|
| 客厅开关 | 2020879703 | 客厅 | switch |
| 灯光总闸 | 2021067696 | 客厅 | switch |
| 小米智能开关三开2 | 2000452006 | 客厅 | switch |
| 一楼电视 | ir.1975079422243524608 | 客厅 | television |
| 一楼空调 | ir.1979475288836689920 | 客厅 | air-conditioner |
| 一楼窗帘 | 2077425766 | 客厅 | curtain |
| 一楼中枢 | 1177403990 | 客厅 | gateway |
| Xiaomi 智能音箱 Pro 🔊 | 981192128 | 客厅 | speaker |
| 客厅温湿度计 | blt.3.1mpr2g66h0g00 | 客厅 | sensor |
| 厨房灯 | 888466709 | 厨房 | switch |
| 电饭锅 | 949995539 | 厨房 | outlet |
| 米家净水器Pro | 993604970 | 厨房 | water-purifier |
| 小米人体传感器2S | blt.3.1mq6moh5o4k01 | 厨房 | motion-sensor |
| 一楼卫生间灯 | 2000304181 | 一楼卫生间 | switch |

### 二楼（主卧层）

| 设备名 | DID | 房间 | 类型 |
|--------|-----|------|------|
| 小米智能开关三开 | 946243288 | 二楼主卧 | switch |
| 小米智能开关双开2 | 2042811252 | 二楼主卧 | switch |
| 空调 1.5匹 | 898889695 | 二楼主卧 | air-conditioner |
| 橙色智能音箱 🔊 | 979931026 | 二楼主卧 | speaker |
| Xiaomi 中枢网关 | 1180424028 | 二楼主卧 | gateway |
| 主卧温湿度计 | blt.3.1mp1qe79p0c01 | 二楼主卧 | sensor |
| 二楼窗帘 | 2079455069 | 二楼主卧 | curtain |
| 客房灯 | 2021723733 | 二楼客房 | switch |
| 二楼卫生间 | 2000438087 | 二楼卫生间 | switch |

### 三楼（书房层）

| 设备名 | DID | 房间 | 类型 |
|--------|-----|------|------|
| 蓝色智能音箱 🔊 | 979939218 | 三楼书房 | speaker |
| 空调 1.5匹 | 898663441 | 三楼书房 | air-conditioner |
| Yeelight 吸顶灯 | 827125644 | 三楼书房 | light |
| Yeelight 磁吸灯 | 1136134697 | 三楼书房 | light |
| Yeelight 磁吸灯2 | 1136134703 | 三楼书房 | light |
| 书房筒灯开关 | 888910528 | 三楼书房 | switch |
| 筒灯组 | group.2018687421600759808 | 三楼书房 | light |
| 射灯组 | group.1979220889048604672 | 三楼书房 | light |
| 三楼窗帘 | 2077414306 | 三楼书房 | curtain |
| 台式机电源 | 2004219772 | 三楼书房 | outlet |
| 智能插座 | 949974607 | 三楼书房 | outlet |
| 三楼监控 | 1180976594 | 三楼书房 | camera |
| 三楼中枢 | 1181564907 | 三楼书房 | gateway |
| 三楼温湿度计 | blt.3.1mrtsdh884k01 | 三楼书房 | sensor |
| 三楼灯(卫生间) | 2042769877 | 三楼卫生间 | switch |
| 三楼楼梯灯 | 2042692296 | 三楼走廊 | switch |
| 小屋开关 | 2042776131 | 小屋 | switch |

### 室外

| 设备名 | DID | 房间 | 类型 |
|--------|-----|------|------|
| 小米室外摄像机 4 Pro | 1179415436 | 前院 | camera |
| 北院摄像头 | 1176694677 | 北院 | camera |
| 前院灯 | 2079099780 | 前院 | outlet |

完整列表：`miloco-cli device list`

## ⚠️ 音箱麦克风不能用于语音输入

Miloco 的感知引擎**只认摄像头的麦克风**，不认小爱音箱的麦克风。3个感知设备全是摄像头（前院/北院/三楼书房）。小爱音箱目前只能**输出（TTS）**，不能**输入（ASR）**。

想跟 Miloco 说话 → 必须站在摄像头前面、大声说，让它听见。对着小爱音箱说"小爱同学"是小米自己的助手在听，Miloco 听不到。

## ⚠️ PITFALL: `miloco-cli perceive logs` 在脚本/自动化中会无限挂起

`miloco-cli perceive logs --limit N`（不带 `--jsonl`）会建立一个**长轮询/SSE 连接**，持续监听新事件。在 cron job、Python subprocess、或任何需要脚本退出的场景中，**命令永远不会返回**，导致超时。

**正确用法：**
```bash
# ✅ 脚本/自动化中必须加 --jsonl（返回 JSONL 后立即退出）
miloco-cli perceive logs --jsonl --limit 10

# ❌ 会挂起（长轮询模式，等待新事件）
miloco-cli perceive logs --limit 10
```

`--jsonl` 模式：每行输出一条 `{"<timestamp>":{...}}` JSONL，返回已有日志后立即退出。`--limit` 仅在 `--jsonl` 模式下生效。

**调试用法：** `--since 1h` 手动指定时间范围（不读写 cursor 文件），但同样需要 `--jsonl` 才能立即退出。

## ⚠️ PITFALL: miloco.main 高 CPU 导致容器无响应（不同于 crash loop）

当 `miloco.main` 进程（感知引擎，ONNX 推理）CPU 占用飙升时，CT <ID> 整个容器会变得极慢甚至无响应，表现为 `pct exec 310 -- echo OK` 都超时。这**不是** crash loop（进程在运行但卡住了）。

**诊断步骤（从 PVE 宿主机）：**
```bash
# 1. 检查 PVE 负载（高 = 容器抢 CPU）
sshpass -p 'PASS' ssh root@PVE_HOST "uptime"
# load average > 10 → 有问题

# 2. 检查容器进程 CPU 占用
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec 310 -- ps aux | grep miloco"
# miloco.main 占 CPU > 50% → 感知引擎过载

# 3. 确认容器是否还活着（最简单的 pct exec 测试）
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec 310 -- echo CT310_OK"
# 超时 → 容器卡死

# 4. 检查端口是否还在监听
sshpass -p 'PASS' ssh root@PVE_HOST "ss -tlnp | grep 1810"
# 有输出 → 后端进程还在但卡住了
```

**与 crash loop 的区别：**

| 特征 | crash loop | 高 CPU 卡死 |
|------|-----------|------------|
| 进程状态 | 反复崩溃重启 | 一直在运行 |
| supervisord uptime | 很短（秒级） | 很长（小时级） |
| pct exec | 有时能进有时不能 | 完全超时 |
| CPU 占用 | 低（刚启动就崩） | 高（50%+） |
| 端口 1810 | 间歇性不响应 | 可能响应但慢 |

**可能原因：**
- 摄像头画面复杂（多人/复杂场景）→ ONNX 推理耗时暴涨
- 感知引擎内存不足 → 频繁 GC → CPU 飙升
- 多个摄像头同时触发推断

**修复：**
```bash
# 方案1：重启容器（最快恢复）
sshpass -p 'PASS' ssh root@PVE_HOST "pct reboot 310"

# 方案2：增加 CPU 分配
sshpass -p 'PASS' ssh root@PVE_HOST "pct set 310 --cores 4"
# 然后重启容器

# 方案3：增加内存（ONNX 推理需要 ≥2GB）
sshpass -p 'PASS' ssh root@PVE_HOST "pct set 310 --memory 2048"
```

**预防：** 确保 CT <ID> 至少分配 2核/2GB。1GB 内存 + 2核 对感知引擎来说太紧张。

## ⚠️ PITFALL: Miloco 后端 crash loop 诊断（supervisord autorestart）

当 `miloco-backend` 进程因 OOM 或其他原因反复崩溃时，supervisord 的 `autorestart=true` 会立即重启，形成**快速崩溃循环**。表现为：CLI 命令超时、端口 1810 间歇性不响应、进程列表中出现 `<defunct>` 僵尸进程。

### OOM 诊断关键：查 supervisord.log，不是 journalctl

Miloco 由 supervisord 管理（非 systemd），OOM kill 不会出现在 `journalctl` 中。**唯一可靠的 OOM 证据在 supervisord.log 里：**

```bash
# ✅ 正确 — 查 supervisord 日志
pct exec 310 -- grep 'SIGKILL' /root/.openclaw/miloco/log/supervisord.log | tail -20
# 输出示例：2026-07-03 03:37:10,334 WARN exited: miloco-backend (terminated by SIGKILL; not expected)

# ❌ 错误 — journalctl 找不到 supervisord 管理的服务
pct exec 310 -- journalctl -u miloco-backend | grep oom
```

**确认 OOM 循环：** 如果 30 分钟内出现 10+ 次 SIGKILL → 几乎确定是 OOM。

**诊断步骤：**
```bash
# 1. 检查 supervisord 状态（看 uptime 是否很短）
sshpass -p 'PASS' ssh root@PVE_HOST 'pct exec 310 -- /usr/local/bin/supervisorctl -c /root/.openclaw/miloco/supervisord.conf status'

# 2. 检查端口是否在监听
sshpass -p 'PASS' ssh root@PVE_HOST 'pct exec 310 -- ss -tlnp | grep 1810'

# 3. 查看后端日志末尾（找 OOM/crash 证据）
sshpass -p 'PASS' ssh root@PVE_HOST 'pct exec 310 -- tail -20 /root/.openclaw/miloco/log/miloco-backend.log'

# 4. 检查容器内存（ONNX 推理需要大量 RAM）
sshpass -p 'PASS' ssh root@PVE_HOST 'pct exec 310 -- free -h'
```

**常见原因：** 容器内存不足（ONNX 模型加载 + 推理需要 ≥2GB，1GB 会 OOM）。
**修复：** 增加容器内存分配（`pct set 310 --memory 2048`），然后重启容器。

**⚠️ 注意：** `miloco-cli service restart` 可能无法在 crash loop 中正常工作。直接操作 supervisord：
```bash
# 重启后端
sshpass -p 'PASS' ssh root@PVE_HOST 'pct exec 310 -- /usr/local/bin/supervisorctl -c /root/.openclaw/miloco/supervisord.conf restart miloco-backend'

# 查看实时日志
sshpass -p 'PASS' ssh root@PVE_HOST 'pct exec 310 -- /usr/local/bin/supervisorctl -c /root/.openclaw/miloco/supervisord.conf tail miloco-backend'
```

## CLI 设备控制

Miloco 绑定小米账号后自动发现所有米家设备。关键命令：

```bash
# 列出所有设备
miloco-cli device list

# 查看设备规格（属性/动作）
miloco-cli device spec <DID>

# 控制设备
miloco-cli device control <DID> <spec_name> <value>
# 例：开灯
miloco-cli device control 2020879703 on true
# 例：空调调温
miloco-cli device control 898663441 target-temperature 26

# 音箱 TTS 播报
miloco-cli device action <DID> <spec_name> <params>

# 查询设备属性
miloco-cli device props <DID>
```

设备 spec_name 示例（从 `device spec` 输出复制）：
- `on` / `on@吊灯` — 开关（多组件带 @ 后缀消歧）
- `brightness` — 亮度
- `target-temperature` — 空调目标温度
- `motor-control` — 窗帘（0=停, 1=开, 2=关）
- `play-text` — 音箱 TTS

## ⚠️ Webhook URL 必须指向 CT <ID> 实际 IP

Miloco 在 CT <ID>（192.0.2.10），Hermes webhook 在 CT <ID>（192.0.2.10）。
**不要用 PVE 宿主机 IP（192.0.2.10）**——LXC 容器间通过 vmbr0 桥接直接通信，不经过宿主机。

```bash
# 正确：指向 CT <ID> 的实际 IP
miloco-cli config set agent.webhook_url http://192.0.2.10:18789/miloco/webhook

# 错误：指向 PVE 宿主机（LXC 容器连不上宿主机端口）
# http://192.0.2.10:18789/miloco/webhook  ← 不通！
```

验证连通性：
```bash
pct exec 310 -- curl -s -o /dev/null -w "%{http_code}" \
  --connect-timeout 5 http://192.0.2.10:18789/miloco/webhook \
  -X POST -H "Content-Type: application/json" -d '{"action":"test"}'
# 返回 200 = 连通
```

## Webhook 实时推送（Miloco → Hermes）

Miloco 感知引擎检测到事件后，会通过 HTTP POST 实时推送到 agent webhook。

### Webhook 格式

```json
POST <agent.webhook_url>
{
  "action": "agent",
  "payload": {
    "message": "感知事件描述文本",
    "sessionKey": "session_id",
    "lane": "perception",
    "traceId": "trace_id",
    "idempotencyKey": "idempotency_key",
    "timeoutMs": 30000
  }
}
```

Agent 需返回：
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "runId": "agent_run_id",
    "status": "ok"
  }
}
```

### 配置 webhook URL

```bash
# 改为 Hermes 所在主机的地址（CT <ID> 的实际 IP，不是 PVE 宿主机 IP）
miloco-cli config set agent.webhook_url http://192.0.2.10:18789/miloco/webhook
miloco-cli service restart
```

默认值 `http://127.0.0.1:18789/miloco/webhook` 是 OpenClaw 端口。改为 Hermes 主机 IP + 自定义端口即可对接。

### ⚠️ Webhook 协议要点（Miloco 期望的请求/响应格式）

Miloco 会 POST 两种 action：

**1. `agent` — 感知事件推送**
```json
POST /miloco/webhook
{
  "action": "agent",
  "payload": {
    "message": "[感知引擎]事件提醒：\n时间：...\n来源：...\n检测到：...\n事件优先级：...\n建议：...",
    "sessionKey": "agent:main:miloco-suggest",
    "lane": "miloco-suggest",
    "traceId": "uuid",
    "idempotencyKey": "uuid",
    "timeoutMs": 180000
  }
}
```

**2. `get_trace` — 轮询 turn 执行结果**
```json
POST /miloco/webhook
{
  "action": "get_trace",
  "payload": { "runId": "hermes_xxx" }
}
```

**必须返回的格式（两种 action 通用）：**
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "runId": "hermes_xxx",
    "status": "ok"
  }
}
```

**⚠️ PITFALL: 不正确回复 get_trace 会导致 Miloco 疯狂轮询（每3秒一次）！**
如果 webhook 接收器只保存事件但不返回 `{"code":0,...}` 格式，Miloco 会无限重试 `get_trace`，日志被刷爆。

### Hermes 端接收器

Flask 接收器脚本：`~/.hermes/scripts/miloco-webhook-receiver.py`
事件队列目录：`~/.hermes/miloco-events/`

启动：
```bash
cd ~/.hermes/scripts && python3 miloco-webhook-receiver.py &
# 或用 terminal(background=true) 启动
```

验证：
```bash
curl -s http://127.0.0.1:18789/health
# {"status":"ok","service":"miloco-webhook-receiver"}

# 查看最近事件
curl -s http://127.0.0.1:18789/events | python3 -m json.tool
```

### Miloco CLI 常用命令

```bash
# 服务管理
miloco-cli service status
miloco-cli service restart
miloco-cli service logs -f

# 设备操作
miloco-cli device list          # 列出所有设备
miloco-cli device spec <DID>    # 查看设备属性/动作规格
miloco-cli device control <DID> <spec_name> <value>  # 控制设备
miloco-cli device action <DID> <spec_name> <params>  # 执行动作（TTS等）
miloco-cli device props <DID>   # 查询设备当前属性值

# 感知操作
miloco-cli perceive logs --jsonl --limit 10  # 查看感知日志（⚠️ --jsonl 必须加，否则脚本挂起）
miloco-cli perceive devices           # 查看感知设备列表
miloco-cli perceive query --device <DID> --question "画面中有人吗？"

# 账号管理
miloco-cli account status       # 查看绑定状态
miloco-cli account bind         # 绑定小米账号
```

## 摄像头云台（PTZ）控制

前院摄像头（小米室外摄像机 4 Pro 三摄变焦版）支持云台，有预设位置。

```bash
# 切换预设位置
miloco-cli device control 1179415436 cruise-position '位置一'
miloco-cli device control 1179415436 cruise-position '位置二'
```

**⚠️ 无连续巡逻模式的 MIoT 接口。** 要让摄像头持续来回扫描，需在米家 App 里开启巡航模式（选2个预设位置之间自动来回转）。MIoT spec 只暴露 `cruise-position` 属性（切换位置）和校准 action，没有"开始巡逻"的开关。

## 感知引擎

Miloco 感知引擎用 MiMo v2.5 分析摄像头画面，约每 25 秒一次推断。

### 已接入摄像头（user）

| 摄像头 | 位置 | 设备型号 |
|--------|------|---------|
| 前院 | 前院 | 小米智能室外摄像机 4 Pro 三摄变焦版 |
| 北院 | 北院 | 北院摄像头 |
| 三楼书房 | 三楼书房 | 三楼监控 |

### 感知日志查询

```bash
# 查看最近感知日志（⚠️ --jsonl 必须加，否则脚本/自动化中会无限挂起）
miloco-cli perceive logs --jsonl --limit 10

# 查看感知设备列表
miloco-cli perceive devices

# 主动查询（指定问题）
miloco-cli perceive query --device <DID> --question "画面中有人吗？"
```

感知日志格式：每条包含时间戳 + 各摄像头画面描述（自然语言），引擎会自动识别人物身份。

### 规则引擎（自动化核心）

Miloco 内置规则引擎，基于感知事件自动触发设备控制。**规则必须挂在任务（task）下**，创建顺序：先建 task → 再建 rule。

#### 创建流程

```bash
# 1. 先创建任务（占位）
miloco-cli task create \
  --task-id 'study_light_auto' \
  --description '三楼书房检测到有人时自动开灯'

# 2. 再创建规则（绑定到任务）
miloco-cli rule create \
  --name '书房有人自动开灯' \
  --task-id 'study_light_auto' \
  --condition '三楼书房检测到有人' \
  --mode event \
  --source 1180976594 \
  --action '{"did":"888910528","iid":"prop.2.1","value":true,"idempotent":true}'
```

#### 参数说明

| 参数 | 说明 |
|------|------|
| `--task-id` | 任务 ID（snake_case，必须先 task create） |
| `--condition` | 触发条件（自然语言） |
| `--mode event` | 单点触发模式 |
| `--mode state` | 进入/退出配对模式（需 --on-enter-action / --on-exit-action） |
| `--source` | 感知源设备 DID（可选，不填=所有摄像头） |
| `--action` | 设备直控 JSON（`{"did","iid","value","idempotent"}`） |
| `--action-desc` | Agent 回调描述（让 Agent 自主决策） |

#### action JSON 格式

```json
// 设备控制（幂等，重复触发不变）
{"did":"888910528","iid":"prop.2.1","value":true,"idempotent":true}

// 音箱播报（带冷却，10分钟内不重复）
{"did":"979939218","iid":"action.5.3","params":["欢迎回来"],"idempotent":false,"cooldown_minutes":10}
```

`iid` 格式：`prop.<siid>.<piid>` 或 `action.<siid>.<aiid>`，从 `miloco-cli device spec <DID>` 输出中复制。

#### 管理规则

```bash
miloco-cli rule list              # 列出所有规则
miloco-cli rule disable <rule_id> # 禁用规则
miloco-cli rule enable <rule_id>  # 启用规则
miloco-cli rule delete <rule_id>  # 删除规则
miloco-cli rule logs              # 查看规则执行日志
miloco-cli task list              # 列出所有任务（含规则摘要）
```

#### 已部署规则（user）

| 规则名 | 条件 | 动作 | 设备 DID |
|--------|------|------|----------|
| 书房有人自动开灯 | 三楼书房检测到人 | 开筒灯 | 888910528 |
| 客厅有人自动开灯 | 客厅检测到人 | 开客厅灯 | 2020879703 |
| 走廊有人自动开灯 | 三楼走廊检测到人 | 开楼梯灯 | 2042692296 |
| 厨房有人自动开灯 | 厨房检测到人 | 开厨房灯 | 888466709 |
| 卫生间有人自动开灯 | 三楼卫生间检测到人 | 开卫生间灯 | 2042769877 |

## ⚠️ 已知 bug：Miloco 感知引擎读取开关状态而非灯实际状态（2026-06-26 发现）

Miloco 日志会报告"书房灯已亮起"，但实际上灯没亮——它读的是**无线开关（switch 类型）的状态**，不是**灯（light 类型）的实际状态**。

**复现：**
```bash
# 查看开关状态 → on@开关 = true（开关处于"开"位置）
miloco-cli device props 888910528  # 书房筒灯开关

# 查看灯状态 → on = false（灯实际是关的）
miloco-cli device props 827125644  # Yeelight 吸顶灯
```

**影响：** Miloco 的"有人→开灯"规则会误判灯已亮，因为开关是 on 的。实际上开关只是处于"开"位置，灯本身可能是关的（比如手动关了灯但开关没拨回来）。

**修复方向：** Miloco 感知规则应检查 `light` 类型设备的 `on` 属性，而非 `switch` 类型的 `on@开关` 属性。

## MiMo API

- 注册/获取 Key: https://platform.xiaomimimo.com
- API Base URL: https://api.xiaomimimo.com/v1
- 模型: xiaomi/mimo-v2.5（感知）, xiaomi/mimo-v2.5-pro（Agent 推理）
- Voice clone 模型: mimo-v2.5-tts-voiceclone（推广期免费）

## 音箱 TTS 播报（按楼层路由）

小米智能音箱支持通过 Miloco CLI 进行 TTS 播报（`play-text` 动作）。

### ⚠️ PITFALL: 不同音箱型号的 action IID 不同！

**不能假设所有音箱的 play-text 都是同一个 IID！** 必须先 `device spec` 查看。

| 音箱 | DID | 房间 | play-text IID | 备注 |
|------|-----|------|---------------|------|
| Xiaomi 智能音箱 Pro | 981192128 | 客厅 | `action.7.3` | siid=7 |
| 橙色智能音箱 | 979931026 | 二楼主卧 | `action.7.3` | siid=7 |
| 蓝色智能音箱 | 979939218 | 三楼书房 | `action.5.3` | siid=5 |

**查询方法：**
```bash
miloco-cli device spec <DID> | grep -A3 "actions"
# 找 play-text 对应的 action.X.X
```

### TTS 命令格式

```bash
# ⚠️ 直接传文本值，不带 text-content:string= 前缀！
# 通用格式（IID 从 spec 查询）
miloco-cli device action <DID> <action.X.X> 要说的话

# 客厅音箱（action.7.3）
miloco-cli device action 981192128 action.7.3 你好

# 三楼音箱（action.5.3）
miloco-cli device action 979939218 action.5.3 你好
```

**⚠️ 关键发现（2026-06-26 反复验证）：`text-content:string=` 前缀必须去掉！**

miot-cli 的参数格式 `text-content:string=value` 是 spec 描述，不是实际命令参数。直接传文本值即可：
- ✅ `miloco-cli device action 979939218 action.5.3 你好` → 音箱说"你好"
- ❌ `miloco-cli device action 979939218 action.5.3 text-content:string=你好` → 音箱说"text-content:string=你好"

### ⚠️ PITFALL: SSH + pct exec 的引号嵌套导致 TTS 念出参数名

当通过 SSH → pct exec → miloco-cli 执行 TTS 时，引号嵌套错误会导致参数名被当作语音内容念出来。

**正确写法（只念文本内容）：**
```bash
# ✅ 整个 pct exec 命令用单引号包裹，直接传文本值
sshpass -p 'PASS' ssh root@PVE_HOST 'pct exec 310 -- miloco-cli device action 979939218 action.5.3 你好'
```

**错误写法（会念出前缀）：**
```bash
# ❌ 外层双引号 + text-content:string= 前缀
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec 310 -- miloco-cli device action 979939218 action.5.3 'text-content:string=你好'"
```

**Python subprocess 中的写法（已验证可用）：**
```python
# ✅ 正确 - 整个 pct exec 命令用单引号包裹，直接传文本
cmd = (
    f"sshpass -p '{SSH_PASS}' ssh -o StrictHostKeyChecking=no root@{PVE_HOST} "
    f"'pct exec {CTID} -- {MILoco_CLI} device action {did} {action} "
    f"{text}'"
)

# ❌ 错误 - text-content:string= 前缀会导致音箱念出参数名
cmd = (
    f"sshpass -p '{SSH_PASS}' ssh -o StrictHostKeyChecking=no root@{PVE_HOST} "
    f"'pct exec {CTID} -- {MILoco_CLI} device action {did} {action} "
    f"text-content:string={text}'"
)
```

### ⚠️ 按楼层路由音箱（用户在几楼就用几楼的音箱）

摄像头检测到事件后，**必须用对应楼层的音箱播报**，否则用户听不到。

| 事件来源 | 应该用的音箱 |
|----------|-------------|
| 三楼书房/三楼监控 | 蓝色智能音箱 (979939218) |
| 二楼主卧/二楼监控 | 橙色智能音箱 (979931026) |
| 客厅/一楼监控 | Xiaomi 智能音箱 Pro (981192128) |
| 前院/北院（室外） | 客厅音箱（最近的室内） |

**用户已明确说过："你在1楼的小爱音箱说话，我在3楼，我听不见。"**

### ⚠️ PITFALL: 音箱 TTS 必须在白天使用（8:00-22:00）
**晚上10点后绝对不能测试音箱 TTS**——家里人会睡觉。assistant已明确要求。
凌晨测试 TTS 会导致家人被吵醒，用户会非常不满。

### Webhook 接收器完整实现

Flask 接收器 `~/.hermes/scripts/miloco-webhook-receiver.py` 需要正确处理 Miloco 的两种 action：

```python
# 关键：agent action 保存事件 + 返回 runId
# get_trace action 查询 runId 状态 + 返回同样格式
# 两种都必须返回 {"code": 0, "message": "ok", "data": {"runId": "...", "status": "ok"}}
```

启动方式：
```bash
# 后台启动（Hermes terminal background=true）
nohup python3 ~/.hermes/scripts/miloco-webhook-receiver.py > ~/.hermes/miloco-events/webhook.log 2>&1 &
# 验证
curl -s http://127.0.0.1:18789/health
ss -tlnp | grep 18789
```

### Webhook 接收器 v5（按楼层音箱播报 + 微信双通知）

v5 是最新版本，核心升级：**摄像头检测到事件 → 对应楼层的音箱直接说话 + 微信通知**。

**架构：**
```
Miloco 感知引擎（摄像头每25秒推断）
    ↓ POST webhook
Webhook 接收器 v5（CT <ID>:18789）
    ├→ 解析事件（优先级/来源/检测内容/建议）
    ├→ 过滤低价值事件（仅"书房衣物堆积"）
    ├→ 选择对应楼层音箱 → sshpass→PVE→pct exec→miloco-cli → TTS播报
    └→ hermes send → 微信通知（备份，可能排队延迟）
```

**音箱路由逻辑（按事件来源）：**
- 三楼事件 → 蓝色智能音箱 (979939218, action.5.3)
- 二楼事件 → 橙色智能音箱 (979931026, action.7.3)
- 客厅/院子事件 → Xiaomi 智能音箱 Pro (981192128, action.7.3)

**事件过滤规则：**
- medium/high/urgent 优先级 → 自动播报+通知
- 涉及"人""人体""user""移动""进入""陌生人" → 也播报
- 忽略关键词：仅"书房沙发上堆满衣物"（真正重复无意义的）
- **不要过滤院子水渍/车辆等事件**——用户反馈前院/北院事件也应该通知
- 通知冷却：相同内容 5 分钟内不重复

**智能播报内容（只说有用信息，不念参数名）：**
- 检测到user → "检测到你回来了"
- 痛苦呻吟 → "检测到异常声音，请注意安全"
- 惊呼/哎呀 → "听到有人惊呼，需要帮助吗"
- 陌生人 → "检测到陌生人，请注意安全"
- 其他 → "检测到{内容}。{建议}"（内容截断20字，建议截断20字）

**⚠️ TTS 文本必须纯净：** 音箱播报的内容只包含有用信息，绝对不能出现 `text-content:string=`、`action.X.X`、`Test content` 等参数名或调试文本。用户已明确反馈："你说话之前有提示符没删掉，比如 Test content 这样的，我感觉你应该过滤一下，只说有用的信息。"

**SSH 到 CT <ID> 的方法（从 CT <ID>）：**
直接 SSH 到 CT <ID> 会失败（host key/auth 问题）。必须通过 PVE 宿主机：
```bash
# ✅ 正确：整个 pct exec 命令用单引号包裹，直接传文本值
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  'pct exec 310 -- /usr/local/bin/miloco-cli device action <DID> <ACTION> 要说的话'

# ❌ 错误：外层双引号 + text-content:string= 前缀
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- /usr/local/bin/miloco-cli device action <DID> <ACTION> text-content:string=..."
```

**启动：**
```bash
cd ~/.hermes/scripts && python3 miloco-webhook-receiver.py
# 或 terminal(background=true)
```

**测试 TTS：**
```bash
curl -X POST http://192.0.2.10:18789/test-tts \
  -H "Content-Type: application/json" \
  -d '{"text":"测试语音","speaker":"三楼书房"}'
```

**Cron job 微信通知（补充）：**
- 名称：`miloco-event-notifier`
- 频率：每 2 分钟
- 功能：读取 recent.json → 过滤重要事件 → send_message 到 weixin
- 已通知事件记录在 `~/.hermes/miloco-events/notified.txt`
- Cron job 独立于 gateway 运行，不受当前对话影响

**⚠️ PITFALL: `hermes send` 会排队等 gateway！**
`hermes send --to weixin` 会通过 gateway 发送，gateway 忙时会卡住。
用 cron job 代替 `hermes send` 更可靠。

### 手动启动 webhook 接收器

```bash
# 方式1：terminal background=true（推荐）
cd ~/.hermes/scripts && python3 miloco-webhook-receiver.py

# 方式2：systemd service（更稳定）
cat > /etc/systemd/system/miloco-webhook.service << 'EOF'
[Unit]
Description=Miloco Webhook Receiver
After=network.target

[Service]
Type=simple
WorkingDirectory=~/.hermes/scripts
ExecStart=/usr/bin/python3 miloco-webhook-receiver.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable --now miloco-webhook
```

### execute-text-directive（模拟语音指令）

除了 `play-text`（纯播报），还有 `execute-text-directive`（模拟语音指令）：

```bash
miloco-cli device action <DID> execute-text-directive \
  text-content="播放音乐" silent-execution=false
```

这相当于对小爱说了一句话，可以触发小爱的任何功能（播放音乐、控制设备等）。

**⚠️ 前提条件：** 音箱的 `execute-text-directive` 走的是小米自己的语音助手管线，**不经过 Miloco 感知引擎**。Miloco 听不到音箱说的话（只认摄像头麦克风），但可以通过这个 action 让音箱"假装"收到语音指令。这在需要通过音箱触发小米生态功能（如"打开净化器"、"播放QQ音乐"）时很有用。
