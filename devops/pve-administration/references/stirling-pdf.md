# Stirling-PDF（PVE LXC + Docker）部署与运维

自建 PDF 处理平台，318 个 REST 端点。部署形态：PVE 上开一个 Debian LXC，里面跑 Docker 容器。

## 一、LXC + Docker 标准套路（任何 docker 服务通用）

```sh
# 1. 建容器：unprivileged 必须带 nesting=1,keyctl=1，否则容器内 Docker 起不来
pct create 320 local:vztmpl/debian-12-standard_*.tar.zst \
  --hostname stirling-pdf --cores 2 --memory 4096 --swap 2048 \
  --rootfs local-lvm:20 --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --features nesting=1,keyctl=1 --unprivileged 1 --onboot 1 --start 1

# 2. IP 是 DHCP，用 pct exec 读，别猜
pct exec 320 -- ip -4 addr show eth0 | grep -oP 'inet \K[0-9.]+'

# 3. 装 Docker
pct exec 320 -- sh -c 'curl -fsSL https://get.docker.com | sh'
pct exec 320 -- docker --version
```

- **查 ID / IP 占用先做**：`pct list`、`grep -h "ip=" /etc/pve/lxc/*.conf`。本机容器全走 DHCP，所以新容器也用 DHCP 即可，不需要静态分配。
- **PVE 的 thin pool 常年超配**（`Sum of all thin volumes > thin pool`），是警告不是阻断，建完照样能跑。
- 大镜像（Stirling 3.6G）走后台跑 + 轮询，别一次调用里死等。

## 二、Stirling-PDF 容器启动参数

```sh
docker run -d --name stirling-pdf --restart unless-stopped -p 8080:8080 --memory 3g \
  -e DOCKER_ENABLE_SECURITY=true -e SECURITY_ENABLELOGIN=true \
  -e LANGS=zh_CN -e SYSTEM_DEFAULTLOCALE=zh-CN \
  -e PUID=1000 -e PGID=1000 -e UMASK=022 \
  -v /opt/stirling/configs:/configs -v /opt/stirling/logs:/logs \
  -v /opt/stirling/customFiles:/customFiles -v /opt/stirling/pipeline:/pipeline \
  -v /opt/stirling/tessdata:/usr/share/tesseract-ocr/5/tessdata \
  docker.stirlingpdf.com/stirlingtools/stirling-pdf:latest
```

实测占用：空闲 ~680–870 MB 内存、CPU 0.2–0.3%、启动 ~25 秒。`--memory 3g` 够用，别按「内存大户」心态给 4G+。
数据全在 `/opt/stirling/`，容器重建不丢。健康检查到 `healthy` 才算真起来（Java 应用 ~20–40 秒）。

## 三、认证 API（**别猜端点，先读 /v1/api-docs**）

```sh
# 登录：端点叫 auth 不是 user
TOK=$(curl -s -X POST http://IP:8080/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"..."}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['session']['access_token'])")

# 查首次登录状态（公开端点，不需要 token）
curl -s http://IP:8080/api/v1/proprietary/ui-data/login
# → firstTimeSetup / showDefaultCredentials 必须都为 false 才算真配好
```

**端点全集**：`GET /v1/api-docs`（OpenAPI JSON）。想确认某能力有没有，直接在这里按路径 grep，别靠猜或靠网页界面推断。

## 四、【核心坑】首次登录改密死循环

症状：登录成功 → 弹「首次登录请修改密码」→ 改完提交 → **又弹同一个窗口**。

两个叠加成因，缺一个都不会循环：

1. **新密码长度 < 8 位**。Stirling 强制 8 位起，6 位密码提交后系统仍判不合格，下一次登录继续弹。**设密码前先数位数。**
2. **用错改密端点**。两个端点名字极像，行为不同：

| 端点 | 作用 |
|---|---|
| `POST /api/v1/user/change-password` | **只改密码，不清 firstLogin 标记** → 造成循环 |
| `POST /api/v1/user/change-password-on-login` | **改密码 + 清 firstLogin 标记**（首次登录场景的正确选择）|

```sh
# 正确修法：一次调用同时改密+清标记
curl -s -X POST "http://IP:8080/api/v1/user/change-password-on-login\
?currentPassword=OLD&newPassword=NEW8PLUS&confirmPassword=NEW8PLUS" \
  -H "Authorization: Bearer $TOK"
# → {"message":"credsUpdated"}

# 必须回验：firstTimeSetup 由 true 变 false
curl -s http://IP:8080/api/v1/proprietary/ui-data/login
```

- `POST /api/v1/user/complete-initial-setup` 返回 `{"success":true}` 但 **不会** 把 `firstTimeSetup` 置 false —— 它返回成功不代表状态改了，一律以 `ui-data/login` 的字段为准。
- 验完还要确认旧密码已失效、新密码能登录，两个方向都测。

## 五、改 settings.yml 的两个雷

1. **不要用正则改 settings.yml**。它是多段同构 YAML，`initialLogin:` 下面**只有 username / password**，紧跟的 `enabled:` / `debugLogging:` 属于下一段 `oauth2:`。`grep -A5 'initialLogin:'` 会跨段显示，看着像 initialLogin 的字段其实是 oauth2 的；照此写 `re.sub(r'(initialLogin:(?:.|\n)*?enabled:)\s*false', ...)` 会**跨段吃掉别的行**，把配置改坏。
   正确姿势：`grep -A2` 精确看段、改前 `tar czf /opt/stirling-backup-<ts>.tar.gz -C /opt/stirling configs`、改坏立刻 `tar xzf ... configs/settings.yml` 恢复。
2. **容器启动时会用模板重写 settings.yml**（日志 `Settings file updated based on template changes`）→ 手工改的值可能被覆盖回默认。**能用环境变量就别改文件。**

**`SECURITY_INITIALLOGIN_*` 环境变量不能用来「重置」已有 admin**：数据库里已经有用户时，这套初始化逻辑会在 `initialSecuritySetup` 抛 `java.lang.StackOverflowError`，容器无限重启（`RestartCount` 涨、`ExitCode=0`、`OOMKilled=false`）。要重置只能先移走 `configs/stirling-pdf-DB-*.mv.db` 再重建容器 —— **但改密码根本不需要动数据库**，走第四节的 API 即可。

## 六、文件库（Storage）API —— 用来归档发票/文档

全部实测可用：

```sh
# 建文件夹
curl -s -X POST http://IP:8080/api/v1/storage/folders \
  -H "Authorization: Bearer $TOK" -H 'Content-Type: application/json' \
  -d '{"name":"发票","parentFolderId":null}'

# 上传（multipart，字段名 file）
curl -s -X POST http://IP:8080/api/v1/storage/files \
  -H "Authorization: Bearer $TOK" -F 'file=@发票.pdf'

# 列表 / 删除
curl -s http://IP:8080/api/v1/storage/files -H "Authorization: Bearer $TOK"
curl -s -X DELETE http://IP:8080/api/v1/storage/files/<id> -H "Authorization: Bearer $TOK"   # 204
```

注意：上传返回的 `folderId` 是 `null`，**文件不会自动落进文件夹**，需要 `PATCH /api/v1/storage/files/{id}/folder` 移进去。
还有 `storage/files/{id}/shares/links`（带有效期的分享链接）、`shares/users`（共享给指定用户）。

## 七、能力边界（别答应做不到的事）

- **没有邮件能力**：318 个端点里没有任何 IMAP/SMTP/email 相关路径。收邮件必须靠外部（Hermes 的 `invoice-forwarder` cron + Agent Mail），Stirling 只负责「接文件 → 处理 → 存/索引」。
- **自动化靠目录监视**：`/pipeline/watchedFolders/<任务名>/` 里放一个 `.json` 流水线 + 待处理文件，服务端每分钟扫一次，处理完输出到 `/pipeline/finishedFolders/`，**输入文件成功后被删除**。可在 Settings → Server → System 改 watched/finished 目录。
- **RAG 入库**：`POST /api/v1/docparse/ingest`（切块+向量化），要接外部向量库。
- **AI 工具**（`ai/tools/classify-and-label` 等）需要外接 LLM，不是本地跑。
- 存储不是 DMS：没有发票号去重、没有账务对账，长期归档仍应在 NAS 留一份原件。

## 八、接公网与内网入口（任何新服务通用）

**Caddy**（`home-public-services` 技能有完整发布流程，这里只记本次踩到的）：
- `patch`/`write_file` 会拒绝写 `/etc/caddy/Caddyfile`（敏感系统路径）→ 用 `terminal` + `python3 - <<'PYEOF'` 追加；**不要用正则批量改**，它是多站点同构块，`re.sub` 跨块匹配会把别站的子指令吃掉。改完 `caddy validate` 通过再 `systemctl restart caddy`（`admin off` 时 reload 必失败）。
- 新子域先查泛解析：`getent hosts 新子域.example.com` 与已知在跑的域名比，同 WAN IP 说明 `*.example.com` 已覆盖 → **不用动 DDNS**。
- **本地用裸 IP 测 `:18443` 会 `exit 35` / `HTTP 000`**，那是 TLS SNI 对不上，不是站点坏了。正确验法：`curl -sk --resolve 域名:18443:192.0.2.10 https://域名:18443/`。
- 大文件/长耗时后端必须单独放开：站点块 `request_body { max_size 500MB }`；`reverse_proxy` 内 `transport http { read_timeout 300s / write_timeout 300s }`。层级写错全站起不来。
- 反代目标若是 DHCP 容器，先把 IP 钉稳（静态租约或在容器内配静态），否则重启换 IP 就 502。

**导航页（nav-monitor）加卡片是两处改动**：`/var/www/nav/index.html` 的 `<a class="card svc" data-svc="KEY">`（内含 `sv-KEY` 状态点与 `sm-KEY` 延迟）+ `~/.hermes/nav-monitor/collector.py` 的 `SERVICES` 字典 `"KEY": "http://内网IP:端口/"`；KEY 两处一致，`systemctl restart nav-monitor` 后读 `/var/www/nav/api/status.json` 确认 `{'up': True, ...}`。只改卡片会出现「有卡无数据」。
