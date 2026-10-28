# 在 PVE LXC 里用 Docker 部署 Web 服务

适用于：往 PVE 上新增一个常驻 Web 服务（文档处理、媒体、工具站），不想动现有容器。

## 一、先算资源，别凭感觉说「装不下」

```sh
export SSHPASS=$(grep '^PVE_ROOT_PASSWORD=' ~/.hermes/.env | cut -d= -f2-)
sshpass -e ssh root@192.0.2.10 'free -h; nproc; pvesm status; pct list; qm list'
sshpass -e ssh root@192.0.2.10 'grep -h "ip=" /etc/pve/lxc/*.conf'   # 看现有容器是否 DHCP
```

- 现有容器**全部 DHCP** 时，新容器也用 DHCP，不必手工规划静态 IP（建完从 `pct exec N -- ip -4 addr show eth0` 读回来）。
- 注意 `pct create` 的告警 `Sum of all thin volume sizes exceeds ... thin pool`：这是 thin 超配提示，不是失败，但别再往同一个 pool 里塞大磁盘。

## 二、建容器（一条命令，一次到位）

```sh
CTPASS=$(openssl rand -base64 12 | tr -d '/+=' | head -c 14)
sshpass -e ssh root@192.0.2.10 "
pct create 320 local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst \\
  --hostname <名字> --cores 2 --memory 4096 --swap 2048 \\
  --rootfs local-lvm:20 \\
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \\
  --features nesting=1,keyctl=1 \\
  --unprivileged 1 --onboot 1 --password '$CTPASS' --start 1"
```

- `features nesting=1,keyctl=1` 是**跑 Docker 的硬前提**，漏了容器里 dockerd 起不来。
- `--onboot 1` 一次写好，别等 the user 重启 PVE 后发现服务没了。
- 生成的 root 密码写进 `/root/<服务>-ct-password.txt`（600），不要只打印在聊天里。
- 先确认模板已在：`pveam list local`（Debian 12 / Ubuntu 24.04 模板通常已缓存）。

## 三、装 Docker（CT 内，走官方源）

```sh
pct exec 320 -- bash -c '
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker'
```

安装时的 perl locale 告警无害，忽略。

## 四、跑容器（通用骨架）

```sh
docker run -d --name <服务> --restart unless-stopped \\
  -p <宿主端口>:<容器端口> \\
  --memory 3g \\
  -e PUID=1000 -e PGID=1000 -e UMASK=022 \\
  -v /opt/<服务>/configs:/configs \\
  -v /opt/<服务>/logs:/logs \\
  <镜像>
```

- **目录先 `mkdir -p` 全建好**再 run，Docker 会自动建成 root 所有，UID 映射就错了。
- `--memory` 留出 1G 给容器系统本身（CT 4G → 容器 3G）。
- 数据目录统一放 `/opt/<服务>/`，容器重建不丢。

## 五、验证（不看日志尾部就宣布成功 = 会翻车）

```sh
docker inspect --format '{{.State.Health.Status}}/{{.RestartCount}}' <服务>   # RestartCount 涨 = 在崩
curl -s -o /dev/null -w '%{http_code}\n' http://<IP>:<端口>/
docker stats --no-stream --format '{{.Name}} CPU:{{.CPUPerc}} MEM:{{.MemUsage}}'
```

**`RestartCount > 0` 必须查日志**：`docker logs <服务> 2>&1 | grep -iE 'error|exception|caused by|StackOverflow|OutOfMemory' | tail -20`，并看 `docker inspect --format 'ExitCode={{.State.ExitCode}} OOMKilled={{.State.OOMKilled}}'` 区分「OOM」和「代码 bug」。

---

## Stirling-PDF 专章

镜像 `docker.stirlingpdf.com/stirlingtools/stirling-pdf:latest`（约 3.6G，实测空闲仅占 ~700MB 内存 / 0.3% CPU，不是内存大户，日常 2 核 4G 足够）。

### 起服务

```sh
docker run -d --name stirling-pdf --restart unless-stopped \\
  -p 8080:8080 --memory 3g \\
  -e DOCKER_ENABLE_SECURITY=true -e SECURITY_ENABLELOGIN=true \\
  -e LANGS=zh_CN -e SYSTEM_DEFAULTLOCALE=zh-CN \\
  -e INSTALL_BOOK_AND_ADVANCED_HTML_OPS=false \\
  -e PUID=1000 -e PGID=1000 -e UMASK=022 \\
  -v /opt/stirling/configs:/configs -v /opt/stirling/logs:/logs \\
  -v /opt/stirling/customFiles:/customFiles -v /opt/stirling/pipeline:/pipeline \\
  -v /opt/stirling/tessdata:/usr/share/tesseract-ocr/5/tessdata \\
  docker.stirlingpdf.com/stirlingtools/stirling-pdf:latest
```

### 改密码 —— 只用 API，别碰 settings.yml

**这是踩过的最大坑**：想用 `settings.yml` 的 `initialLogin`（username/password/enabled）让系统首启建账号，v3.2.2 在 `initialSecuritySetup` bean 里抛 **`StackOverflowError`**，容器无限重启（`RestartCount` 一路涨，`OOMKilled=false`）。而且 settings.yml 会被模板回写，手改的 initialLogin 值也会被清掉。

**正确做法：走 REST API，数据库文件一律不动。**

```sh
# 1) 登录（端点必须是 /api/v1/auth/login，不是 /api/v1/user/login）
TOK=$(curl -s -X POST http://<IP>:8080/api/v1/auth/login \\
  -H 'Content-Type: application/json' \\
  -d '{"username":"admin","password":"stirling"}' \\
  | python3 -c "import sys,json; print(json.load(sys.stdin)['session']['access_token'])")

# 2) 改密码（参数在 query string，不是 body）
curl -s -X POST "http://<IP>:8080/api/v1/user/change-password?currentPassword=stirling&newPassword=<新密码>" \\
  -H "Authorization: Bearer $TOK"

# 3) 验证新密码能登录、旧密码已失效（两个都要测）
```

- 首次安装后默认凭据是 **admin / stirling**，`showDefaultCredentials:true`、`firstTimeSetup:true` 可在 `/api/v1/proprietary/ui-data/login` 查到。
- 改密码接口返回 `{"description":"Password changed successfully...","message":"credsUpdated"}`，随后旧 token 失效，需重新登录。
- 想知道有哪些接口：`curl http://<IP>:8080/v1/api-docs`，用 Python 过滤含 user/login/auth/password 的 path。

### 改配置的安全姿势

`/opt/stirling/configs/settings.yml` 是 YAML，**不要用跨行正则去改**（`(?:.|\n)*?` 一类会吞掉相邻键，把 `oauth2:` 段落搅坏）。要改就先 `tar czf` 整个 configs 备份，再用精确的单行替换；改完 `docker restart` 前心里要有回滚命令。

---

## 交付话术

给 the user's 验收信息必须含：访问地址（域名 + 内网 IP 两条）、账号密码、**实测数据**（HTTP 码、响应时间、内存/CPU 占用、启动耗时）、配置明细（核/内存/磁盘/开机自启/数据目录），以及一句「PVE 剩余资源」。他要的是「已装好且实测通过」，不是「可以装」。
