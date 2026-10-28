# 在 iStoreOS 路由器上装 AI 编程 agent（Claude Code / Kimi Code）

用户环境：iStoreOS 24.10.8，x86_64（Intel J4125），8G RAM，SSH 端口 **2222**（ed25519 免密）。
根分区 overlay 仅 **1.9G**，但有 **231G SATA 挂在 /mnt/sata1-4**（Docker 也在这块盘上）。

**核心原则：大程序全部装到 /mnt/sata1-4，overlay 只放几 KB 的包装脚本。**
安装前先 `df -h` 确认 overlay 余量；装完 overlay 只应增加 node 本体（约 53MB）。

**路由器上还没有的常用命令**：`timeout`、`python3`、`diff`（BusyBox 精简版）。SSH 进来跑长命令时不要在远端用 `timeout`。

## 一、Claude Code（原生，走 opkg 的 node）

Claude Code 的 npm 包在 **Node 20 上能跑**，所以直接装 opkg 的 node 即可，不需要 Docker。

```bash
# 1) 装 node + npm（opkg，国内用清华镜像源，iStoreOS 默认已配）
opkg update && opkg install node node-npm   # node 20.20.2-r1, npm 10.8.2

# 2) 目录 + npm 全局装到 SATA（关键：别装进 overlay）
mkdir -p /mnt/sata1-4/claude-code/{npm-global,work,cache}
npm config set registry https://registry.npmmirror.com
npm config set prefix /mnt/sata1-4/claude-code/npm-global
npm config set cache  /mnt/sata1-4/claude-code/cache

# 3) 安装（约 230MB，9 秒）
cd /mnt/sata1-4/claude-code && npm install -g @anthropic-ai/claude-code

# 4) 验证
/mnt/sata1-4/claude-code/npm-global/bin/claude --version   # → 2.1.197
```

包装脚本 `/usr/bin/claude`（把 PATH、env 文件、工作目录一次性搞定）：

```sh
#!/bin/sh
export PATH=/mnt/sata1-4/claude-code/npm-global/bin:/usr/bin:/usr/sbin:/bin:/sbin
[ -f /mnt/sata1-4/claude-code/.env ] && . /mnt/sata1-4/claude-code/.env
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=2048}"   # 限堆，别把 8G 路由器拖垮
cd "${CLAUDE_WORKDIR:-/mnt/sata1-4/claude-code/work}" 2>/dev/null || true
exec /mnt/sata1-4/claude-code/npm-global/bin/claude "$@"
```

认证由用户自己填 `/mnt/sata1-4/claude-code/.env`（chmod 600）：官方 `ANTHROPIC_API_KEY`，或中转 `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`。
**不要把密钥写进聊天或落盘到 agent 侧**——放模板注释让用户自己改。

## 二、Kimi Code（Docker 方案）

Kimi Code（月之暗面，MIT，`@moonshot-ai/kimi-code`）**要求 Node ≥ 22.19**，而 OpenWrt opkg 最高只有 **node 20.20.2** ✗。
opkg 里也没有 1.x 旧版（npm 上 `@moonshot-ai/kimi-code@1` 直接 404）。

**解法：路由器已装 Docker（27.3.1），用 node:24-alpine 容器跑，程序装在 SATA 上。**
（官方也提供单二进制安装脚本 `curl -fsSL https://code.kimi.com/kimi-code/install.sh | bash`，但那是 glibc 二进制，OpenWrt 是 musl，**不要用**。）

```bash
docker pull node:24-alpine          # 171MB，Docker Hub 在路由器上可直连
mkdir -p /mnt/sata1-4/kimi-code/{prefix,work}

# 装进宿主机的 SATA 目录（--prefix 指向挂载点），后续每次运行不用重装
docker run --rm -v /mnt/sata1-4/kimi-code:/kc node:24-alpine sh -c \
  'npm config set registry https://registry.npmmirror.com >/dev/null 2>&1; \
   npm i -g --prefix /kc/prefix @moonshot-ai/kimi-code'

# 验证
docker run --rm -v /mnt/sata1-4/kimi-code:/kc node:24-alpine /kc/prefix/bin/kimi --version   # → 2.0.2
```

包装脚本 `/usr/bin/kimi`（`--env-file` 传用户自己填的 key，TTY 自动判断）：

```sh
#!/bin/sh
ENVF=/mnt/sata1-4/kimi-code/.env
WORK=${KIMI_WORKDIR:-/mnt/sata1-4/kimi-code/work}
if [ -t 0 ]; then TTYFLAG="-it"; else TTYFLAG="-i"; fi
exec docker run --rm $TTYFLAG --name kimi-code-$$ --env-file "$ENVF" \
  -v /mnt/sata1-4/kimi-code:/kc -v "$WORK":/work -w /work \
  -e HOME=/kc -e TERM="${TERM:-xterm-256color}" \
  -e NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=2048}" \
  node:24-alpine /kc/prefix/bin/kimi "$@"
```

认证：跑起来后在 CLI 里 `/login`（OAuth，无需 Key），或把 `MOONSHOT_API_KEY` 写进 `.env`。
注意 npm 装的时候会 warn `install-scripts ... postinstall` 被跳过——**不影响使用**，`--version`/`--help` 都正常。

## 三、卸载 / 回滚

```bash
# Claude Code
opkg remove node node-npm          # 卸依赖（overlay 回收 ~53MB）
rm -rf /mnt/sata1-4/claude-code /usr/bin/claude

# Kimi Code
rm -rf /mnt/sata1-4/kimi-code /usr/bin/kimi
docker rmi node:24-alpine          # 不用了再删镜像；容器是 --rm，没有残留
```

## 四、坑位总结

| 坑 | 说明 |
|---|---|
| Node 版本墙 | Kimi Code 要 ≥22.19，opkg 只有 20 → 只能 Docker；Claude Code 容忍 20 |
| musl vs glibc | 官方"单二进制"安装脚本是 glibc 的，OpenWrt（musl）跑不了，**别用 install.sh** |
| overlay 只有 1.9G | npm prefix / 数据目录一律指向 /mnt/sata1-4，否则很快写满根分区 |
| npm 慢 | 设 `registry=https://registry.npmmirror.com`，从 9s 变 1s 级 |
| 内存 | 8G 够用，但包装脚本限 `--max-old-space-size=2048` 防单进程吃爆 |
| Docker TUI | `docker run -it` 交互正常；非交互（`-p`）要用 `-i`，否则输出异常 |
| 别动路由配置 | 这类安装只碰 opkg / SATA / Docker，**不碰 OpenClash、防火墙**（用户红线）|
