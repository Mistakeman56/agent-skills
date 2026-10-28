# 在 LXC 里跑 Docker 服务（部署 + 验收 + 上线 + 改配置的安全做法）

适用：把一个现成的 Docker 服务（PDF 工具、下载器、面板…）常驻在 PVE 的独立 LXC 里，比装在 N5095 小盒子上快、也好备份。

> 发布到公网域名 / 防火墙 DNAT 的权威细节在 `home-public-services`；导航页与探活的权威细节在 `nav-monitor`。本文只记「容器侧」以及这两处技能里容易漏掉的几条增量规则。

## 1. 建容器

```bash
pveam list local                       # 先确认有 debian-12-standard 模板
pveam update && pveam download local debian-12-standard_12.x_amd64.tar.zst
pct create 320 local:vztmpl/debian-12-standard_*.tar.zst \
  --hostname svcname --cores 2 --memory 4096 --swap 2048 \
  --rootfs local-lvm:20 --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --features nesting=1,keyctl=1 --unprivileged 1 --onboot 1 --start 1
```

- **`features: nesting=1,keyctl=1` 是 Docker-in-LXC 的硬性前提**；缺 `keyctl` 时容器内 systemd 服务行为诡异，`docker ps` 也会莫名失败。
- 用 DHCP（和家里其余 CT 一致）→ IP 从 `pct exec 320 -- ip -4 addr show eth0` 取，**别猜**。取到后如果要长期反代，记得在路由器钉静态租约。
- 建完会看到 thin pool 超配警告（`Sum of all thin volumes exceeds available`），只要不是要立刻写满就没事。

## 2. 装 Docker + 起服务

```bash
pct exec 320 -- bash -c 'apt-get update && apt-get install -y ca-certificates curl \
  && curl -fsSL https://get.docker.com | sh && systemctl enable --now docker'
```

拉镜像/起容器建议写成一次性 heredoc 丢进去跑，避免多次 `pct exec` 往返。`--restart unless-stopped` + `--memory` 必须显式给。
**`--memory` 不要等于 CT 总内存**：Java/Node 类服务按上限吃堆，留 1G 给系统（4G 的 CT 给 3G）。

## 3. 验收：必须看 RestartCount，不能只看 `docker ps`

`docker ps` 里 `Up 5 seconds (health: starting)` 看起来完全正常，**实际可能已经崩了 6 次**。

```bash
pct exec 320 -- docker inspect --format 'Health={{.State.Health.Status}} Restarts={{.RestartCount}} OOM={{.State.OOMKilled}} Exit={{.State.ExitCode}}' svcname
```

- `Restarts > 0` → 启动即崩的循环，**立刻** `docker logs --tail 50` 找 `error|exception|Caused by|fatal`。
- `OOM=false` + `ExitCode=0` → 不是内存问题，是应用自身异常（Java `StackOverflowError` 这类）。
- 健康通过的标准：`healthy` 且 `Restarts=0`，再用 `curl -o /dev/null -w '%{http_code}' http://IP:PORT/` 拿到 200。

## 4. 改应用配置文件：先备份，别用跨行正则

```bash
pct exec 320 -- bash -c 'tar czf /opt/svc-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /opt/svc configs'
```

**多行非贪婪正则改嵌套 YAML 会吃掉相邻键**：`(  section:(?:.|\n)*?enabled:)\s*false` 这类表达式会把中间不属于该 section 的行一并吞掉，而 YAML 不一定立刻报错——等到服务起不来才发现。规则：

- 优先用**应用自带的环境变量**覆盖配置，而不是改 YAML。
- 必须改时，逐行精确替换（按完整原字符串），改完回归校验：`pct exec 320 -- grep -A6 'section:' configs/settings.yml`，**逐行人工比对，不只看改的那一行**。
- 容器内通常没有 PyYAML，`python3 -c 'import yaml'` 会 ModuleNotFoundError；不要把它当校验手段，用肉眼 + 应用自己的启动日志。

## 5. 改应用密码：走官方 API，不要动数据库

通用套路（大多数自托管应用都有 SpringDoc/OpenAPI 文档）：

```bash
# 1) 列端点，找真正的 login / change-password 路径
curl -s http://IP:PORT/v1/api-docs | python3 -c "import sys,json; d=json.load(sys.stdin); [print(p) for p in d['paths'] if any(k in p.lower() for k in ['auth','password','user'])]"
# 2) 登录拿 token
TOK=$(curl -s -X POST http://IP:PORT/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<default>"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['session']['access_token'])")
# 3) 改密码（参数在 query 上）
curl -s -X POST "http://IP:PORT/api/v1/user/change-password?currentPassword=<default>&newPassword=<new>" -H "Authorization: Bearer $TOK"
# 4) 必验：新密码能登、旧密码失效
```

**坑**：猜端点会得到误导性的 `{"error":"Authentication required"}`（例如 `/api/v1/user/login` 根本不存在），会让人以为是密码错或安全模块没开——**先去 api-docs 拿真路径**，再判断认证状态。`/api/v1/proprietary/ui-data/login` 能直接告诉你 `firstTimeSetup` / `showDefaultCredentials` / `enableLogin` 的真实状态，比翻配置快。

## 6. 上线：反代 + 导航页（容器侧的增量要点）

**HTTP 服务走 18443 时不需要动 DNS 也不需要动防火墙** —— `*.example.com` 是泛解析，18443→CT <ID> 的 DNAT 早就存在，Caddy 按 Host 分流。只有新开公网端口才需要 uci redirect。

- **`patch` 工具拒写 `/etc/caddy/Caddyfile`**（`Refusing to write to sensitive system path`）→ 先 `cp -a` 备份，再用 python `open(p,'a').write(block)` 追加，然后 `caddy validate` → `systemctl restart caddy`（`admin off` 下 reload 必失败）。
- **上传/转换/渲染类服务必须放大反代限制**，否则表现为「小文件正常、大文件 413 或 504」：
  ```
  request_body { max_size 500MB }
  reverse_proxy http://IP:PORT {
      transport http { read_timeout 300s  write_timeout 300s }
  }
  ```
- **内网自测 `curl -k https://127.0.0.1:18443` 返回 000 是正常的**（证书只签 `*.example.com`，IP 直连过不了 SNI，curl exit 35）。正确验法：`curl -sk --resolve 域名:18443:192.0.2.10 https://域名:18443/`。**别因为 000 回滚配置。**
- **上线验收要用域名跑一次真实业务请求**（登录 API / 上传 / 取页面），首页 200 只是静态壳。
- 导航页同步（卡片 `sv-KEY`/`sm-KEY` + `collector.py` 的 `SERVICES` + `systemctl restart nav-monitor` + 读 `api/status.json` 确认 `up:true`）是**必做步骤**，只改 Caddy 不补卡片，the user will 直接问「导航页怎么没有」。

## 7. Stirling-PDF 专属记录

- 镜像 `docker.stirlingpdf.com/stirlingtools/stirling-pdf:latest`（约 3.6G），容器内 8080。
- 挂载：`configs`（含 H2 数据库 `stirling-pdf-DB-*.mv.db`）、`logs`、`customFiles`、`pipeline`、`tessdata`。
- 常用 env：`DOCKER_ENABLE_SECURITY=true`、`SECURITY_ENABLELOGIN=true`、`LANGS=zh_CN`、`SYSTEM_DEFAULTLOCALE=zh-CN`、`PUID/PGID=1000`、`UMASK=022`、`INSTALL_BOOK_AND_ADVANCED_HTML_OPS=false`（省内存）。
- 默认账号 `admin` / `stirling`（`showDefaultCredentials: true`），登录后强制改密。
- **不要用 `SECURITY_INITIALLOGIN_*` 环境变量或 `settings.yml` 的 `initialLogin` 块去「预置密码」**：当前版本会在 `initialSecuritySetup` bean 初始化时抛 `java.lang.StackOverflowError`，容器无限重启（Restarts 持续 +1，日志里只有这一条异常）。正确路径是「用默认密码登录 API → change-password」。
- 真密码在 H2 库里、无法从日志读到；改密码后旧密码应立刻 `Invalid username or password`，两个方向都要验。
- 实测空闲占用：~860MB / 3G 上限、CPU <0.3%；批量转换时才涨。n5095 小盒子（4G/单千兆）已无需部署，这台 CT 覆盖其用途。
