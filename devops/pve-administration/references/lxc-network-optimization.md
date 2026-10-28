# LXC 容器网络优化清单

在新创建的 LXC 容器中，网络下载通常很慢（特别是 pypi.org / Docker Hub 等境外源）。
按此清单一次性配置好，以后就不用再折腾。

## 0. 先检查 Clash 代理是否可用

```bash
export ALL_PROXY=http://Clash:hrFM183F@192.0.2.10:7890
curl -s -o /dev/null -w "%{http_code}" --max-time 8 -x "$ALL_PROXY" https://www.google.com
# → 200 说明代理通
```

## 1. pip 换阿里云镜像（最常用）

```bash
mkdir -p /root/.config/pip
cat > /root/.config/pip/pip.conf << 'EOF'
[global]
index-url = https://mirrors.aliyun.com/pypi/simple/
trusted-host = mirrors.aliyun.com
EOF
```

**速度对比：** pypi.org ~10s → 阿里云 ~0.3s

## 2. npm 换淘宝镜像（如果有 Node.js）

```bash
npm config set registry https://registry.npmmirror.com
```

**速度对比：** npm 官方 ~850ms → 淘宝 ~190ms

## 3. Docker 配置镜像加速（如果有 Docker）

```bash
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ],
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
```

**注意：** LXC 容器中 dockerd 需要 iptables，如启动报错先装 iptables：

```bash
apt-get install -y iptables
```

然后启动 dockerd：

```bash
dockerd --config-file /etc/docker/daemon.json &
```

## 4. 终端环境变量自动走代理

```bash
cat >> /root/.bashrc << 'EOF'

# ===== Clash代理配置 =====
export CLASH_PROXY="http://Clash:hrFM183F@192.0.2.10:7890"
export ALL_PROXY="$CLASH_PROXY"
export HTTP_PROXY="$CLASH_PROXY"
export HTTPS_PROXY="$CLASH_PROXY"
# Git走代理
git config --global http.proxy "$CLASH_PROXY" 2>/dev/null
# 内网不走代理
export NO_PROXY="localhost,127.0.0.1,192.0.2.10/16,192.0.2.10/8,.local"
EOF
```

**重要说明：** 新开的 terminal 会自动加载代理，但 `execute_code` 中的 `terminal()` 调用不会自动继承 shell 环境变量。每次需要在 terminal 命令中手动 export：

```bash
export ALL_PROXY=http://Clash:hrFM183F@192.0.2.10:7890
```

## 5. 直连 vs 代理 vs 镜像的速度参考

| 源 | 直连 | Clash代理 | 国内镜像 |
|---|---|---|---|
| pypi.org | 10s ❌ | 10s ❌ (DIRECT规则) | **0.3s** ✅ 阿里云 |
| npm 官方 | 851ms | — | **193ms** ✅ 淘宝 |
| Docker Hub | 超时 ❌ | EOF ❌ (节点问题) | **0.2s** ✅ docker.1ms.run |
| GitHub | 535ms ✅ | — | 无需镜像 |
| Go模块代理 | 861ms | — | **103ms** ✅ 中科大 |

## 核心原则

**用户明确要求：** 遇到网络问题第一反应是检查 Clash 代理，不要绕路换源。

```
网络超时/下载慢
  └─ 检查 ALL_PROXY 设了吗？
       ├─ 没设 → export ALL_PROXY=...（95% 情况解决）
       └─ 设了但还慢 → 测代理通不通
            ├─ 代理不通 → 修代理（Clash挂了/密码变了）
            └─ 代理通但特定源慢 → 再考虑换国内镜像
```

但 **pypi.org 是例外**：即使走代理也慢（美国CDN限速），直接换阿里镜像更快。
