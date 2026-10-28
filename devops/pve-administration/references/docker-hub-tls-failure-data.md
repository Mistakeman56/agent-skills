# Docker Hub via Clash — TLS Failure Diagnosis Data

Collected 2026-05-19 from PVE LXC 202 (Debian 12, x86_64).

## Problem

`docker pull` always fails with `EOF` despite correct proxy configuration.

## Quick Diagnosis

```bash
# 3-second test to distinguish config issue vs node issue
curl -o /dev/null -s -w "%{http_code}" -x http://Clash:hrFM183F@192.0.2.10:7890 "https://www.google.com" && echo " (普通HTTPS通)"
curl -o /dev/null -s -w "%{http_code}" -x http://Clash:hrFM183F@192.0.2.10:7890 "https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/alpine:pull" && echo " (Docker Hub auth)"
curl -o /dev/null -s -w "%{http_code}" -x http://Clash:hrFM183F@192.0.2.10:7890 "https://registry-1.docker.io/v2/" && echo " (Docker Hub registry)"
```

- Google: 200 ✅
- Docker Hub auth: 000 ❌ (SSL_ERROR_SYSCALL after CONNECT tunnel established)
- Docker Hub registry: 000 ❌ (same)

## Diagnostic Details

### Step 1: Verify proxy env is passed to dockerd correctly

In LXC (no systemd), dockerd must be launched with env vars in the exec command:

```bash
cat > /root/start-docker.sh << 'SCRIPT'
#!/bin/bash
export HTTP_PROXY=http://Clash:hrFM183F@192.0.2.10:7890
export HTTPS_PROXY=http://Clash:hrFM183F@192.0.2.10:7890
export NO_PROXY=localhost,127.0.0.1,192.0.2.10/16
exec /usr/local/bin/dockerd --iptables=false
SCRIPT
chmod +x /root/start-docker.sh
bash /root/start-docker.sh &
```

**⚠️ Hermes password masking:** `grep`/`cat` will show `***` in place of `hrFM183F` in the terminal output. The actual file content is correct — verify with:
```bash
grep -o 'hrFM183F' /root/start-docker.sh && echo "密码正确"
```

**Verify proxy is loaded by dockerd:**
```bash
docker info 2>&1 | grep -i proxy
# Should show: HTTP Proxy: http://xxxxx:***@192.0.2.10:7890
```

### Step 2: Test the proxy from shell (bypassing dockerd)

```bash
# If this fails too, it's NOT a dockerd config issue
curl -v --connect-timeout 10 -x http://Clash:hrFM183F@192.0.2.10:7890 "https://auth.docker.io/token?service=registry.docker.io&scope=repository:jiange1236/allinone:pull" 2>&1 | head -30
```

Result from today:
- CONNECT tunnel: ✅ `HTTP/1.1 200 Connection established`
- TLS handshake: ❌ `OpenSSL SSL_connect: SSL_ERROR_SYSCALL in connection to auth.docker.io:443`

This means the Clash proxy node (SSRDOG) established a TCP tunnel but the TLS handshake to Docker Hub's CDN failed.

### Step 3: Test registry-mirrors (alternative endpoint)

```bash
# Quick availability test
for mirror in \
    "docker.1ms.run" \
    "docker.xuanyuan.me" \
    "docker.m.daocloud.io" \
    "docker.unsee.tech" \
    "hub.uuuadc.top" \
    "docker.hlyun.org" \
    "dockerpull.cn"; do
    
    code=$(curl -s --connect-timeout 8 -o /dev/null -w "%{http_code}" "https://$mirror/v2/" 2>&1)
    echo "$mirror: $code"
done
```

Results from today (2026-05-19, from China, via Clash proxy):

| Mirror | HTTP Status | docker pull result |
|--------|:-----------:|:------------------:|
| docker.1ms.run | 401 | `unknown blob` (layer download failed) |
| docker.xuanyuan.me | 401 | not tested after 401 |
| hub.uuuadc.top | **200** | `EOF` after manifest HEAD |
| dockerpull.cn | **200** | `invalid character '<'` (HTML response) |
| docker.m.daocloud.io | 401 | not tested |
| docker.unsee.tech | 000 (timeout) | N/A |
| docker.hlyun.org | 000 (timeout) | N/A |

**Key observation:** `hub.uuuadc.top` returns HTTP 200 (seems available) but fails at the manifest layer with `EOF`. `dockerpull.cn` returns 200 but with HTML not JSON. None of the mirrors reliably worked for actually pulling images.

### Step 4: Verify Clash node is the problem

Test other Cloudflare-hosted sites through same proxy:
```bash
curl -s --connect-timeout 10 -x http://Clash:hrFM183F@192.0.2.10:7890 -o /dev/null -w "%{http_code}\n" "https://www.google.com"      # 200
curl -s --connect-timeout 10 -x http://Clash:hrFM183F@192.0.2.10:7890 -o /dev/null -w "%{http_code}\n" "https://github.com"       # 200
curl -s --connect-timeout 10 -x http://Clash:hrFM183F@192.0.2.10:7890 -o /dev/null -w "%{http_code}\n" "https://huggingface.co"    # 200 (after adding Clash rule)
curl -s --connect-timeout 10 -x http://Clash:hrFM183F@192.0.2.10:7890 -o /dev/null -w "%{http_code}\n" "https://auth.docker.io"   # 000
```

Google/GitHub/HuggingFace all work. Docker Hub specifically does not — it's not a general proxy failure, it's specific to Docker Hub's CDN infrastructure.

## Root Cause

**The SSRDOG proxy node to Docker Hub CDN (Fastly/Cloudfront) TLS connection is timing out.** This is a node-level issue, not a configuration issue.

## Workarounds (attempted & failed)

| Approach | Result |
|----------|--------|
| dockerd with HTTP_PROXY env | ❌ EOF — Docker Hub CDN unreachable via node |
| registry-mirrors (dockerpull.cn etc.) | ❌ All failed — HTML response or unknown blob |
| Manual curl via proxy to auth.docker.io | ❌ SSL_ERROR_SYSCALL |
| Manual curl via proxy to registry-1.docker.io | ❌ 000 timeout |

## Workarounds (would work)

| Approach | How |
|----------|-----|
| **Run Docker on another machine** (e.g. Windows PC with Docker Desktop) | The Windows PC's network path to Docker Hub is different (not through Clash proxy over SSRDOG) |
| **PVE host SSH docker** | If PVE host itself can reach Docker Hub (different NAT/routing), SSH to PVE host and run docker commands from there |
| **Skip Docker entirely, use static binaries** | Many tools publish Linux amd64 binaries as GitHub releases (e.g. `iptv-proxy`) — download via `curl -x proxy` which handles TLS differently than dockerd |

## About Docker on LXC

**Static binary install (no apt):**
```bash
# Download from Aliyun mirror (fast from China)
curl -s "https://mirrors.aliyun.com/docker-ce/linux/static/stable/x86_64/docker-27.0.3.tgz" -o /tmp/docker.tgz
cd /tmp && tar xzf docker.tgz
cp docker/docker* docker/containerd* docker/runc docker/docker-init docker/docker-proxy /usr/local/bin/
```

**Start without systemd:**
```bash
mkdir -p /etc/docker /var/lib/docker /var/lib/containerd /run/docker
dockerd --iptables=false &
# --iptables=false is critical for unprivileged LXC containers
# Without it, dockerd errors: "failed to find iptables"
```

**Aliyun mirror URL:** `https://mirrors.aliyun.com/docker-ce/linux/static/stable/x86_64/docker-27.0.3.tgz` — 73MB, downloaded in ~2 seconds from China. Much faster than Docker's official CDN.
