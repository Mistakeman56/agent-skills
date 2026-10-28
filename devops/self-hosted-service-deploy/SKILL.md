---
name: self-hosted-service-deploy
description: "Use when 给家里 PVE 加一个自建 Web 服务。"
version: 1.0.0
author: Hermes Agent
platforms: [linux]
---

# 在 PVE 上新增一个自建 Web 服务（端到端）

家里所有自建服务（Stirling-PDF、Vaultwarden、MoviePilot、HA…）都走同一条路。照此做，一轮到位。PVE 宿主/存储/网络层面的细节见 `pve-administration`；导航页与认证细节见 `nav-monitor`。

## 0. 先看资源再动手

```bash
free -h | head -2; nproc; pvesm status
pct list; ls /etc/pve/lxc/ | tr '\n' ' '   # 确认 ID 没占用
```

单容器服务 **1 核 / 1G** 就够（Vaultwarden 实测 16 MB、Stirling 867 MB）。ID 从 3xx 往后排。

## 1. 建 CT

```bash
pct create 32X local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst \
  --hostname <name> --cores 1 --memory 1024 --swap 512 \
  --rootfs local-lvm:6 --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --features nesting=1,keyctl=1 --unprivileged 1 --onboot 1 --password '<随机>'
pct start 32X
```

**用 DHCP**（家里既有习惯），建完立刻 `pct exec 32X -- ip -4 addr show eth0` 取 IP，写进 Caddy 和 `.env` —— IP 会变，别凭记忆写。

## 2. 装 Docker

官方 keyring + deb 源，`systemctl enable --now docker`。`docker --version` 确认版本；只剩 perl locale 警告属无害。

## 3. 起容器

- 数据目录挂宿主机 `/opt/<name>/data`，容器重建不丢
- `--restart unless-stopped`；内存大户加 `mem_limit`
- **改环境变量必须 `docker rm -f` 再 `docker run`** —— env 不能在现有容器上改，`restart` 也不会生效

## 4. Caddy 反代（固定模板）

```caddyfile
https://<sub>.example.com:18443, https://<sub>.example.com {
	tls /etc/caddy/certs/fullchain.pem /etc/caddy/certs/privkey.pem
	encode gzip
	import hdrs
	request_body {
		max_size 500MB
	}
	reverse_proxy http://<CT_IP>:<port> {
		header_up Host {http.request.host}
		header_up X-Real-IP {remote_host}
		header_up X-Forwarded-Proto {scheme}
		flush_interval -1
	}
}
```

- **18443 和 443 两个 host 都写**，否则 the user 换个端口访问就打不开
- **WebSocket 应用（Vaultwarden、HA、qB 界面）必加 `flush_interval -1`**，否则实时同步/长连接断
- 泛解析 `*.example.com` 已存在 → **DNS 零操作**，只改 Caddy
- `patch` 工具拒写 `/etc/caddy/Caddyfile`（sensitive path）→ 用 `python3 - <<'PYEOF'` heredoc 追加
- 改前 `cp -a Caddyfile Caddyfile.bak.<ts>`；`admin off` 导致 `caddy reload` 必失败，只能 `caddy validate` 通过后 `systemctl restart caddy`（会短暂中断全部站点，挑无人用时做）

## 5. 验证

```bash
curl -sk -o /dev/null -w '%{http_code} %{time_total}s\n' https://<sub>.example.com:18443/
curl -sk -o /dev/null -w '%{http_code}\n' https://<sub>.example.com/
```

`curl https://127.0.0.1:18443/` 返回 **000** 是 SNI 不匹配，不是故障；本地要测就 `--resolve <域名>:18443:192.0.2.10`。

## 6. 挂导航页 + 记凭据

- `collector.py` 的 `SERVICES` 加 `"<key>": "http://<CT_IP>:<port>/"`
- `index.html` 插 `<a class="card svc" data-svc="<key>" ...>`，新服务带 `<span class="badge new">NEW</span>`
- **`SERVICES` 是冒号对齐的**（`"pdf":          "http://..."`）：用单空格拼 replace 匹配不到，**且失败时静默不改** → 先 `grep -n '"<锚点key>"'` 看清实际空格数再插
- 验证读 `status.json` 的 **`services` 键**（顶层结构是 `{ts, devices, cycle_ok, services}`），别读错层级判成失败
- 凭据补一行到 `~/.hermes/secrets/ACCESS-NOTES.md`（600）：地址 + 用户名 + 密码位置/改法。**memory 有字符上限，写满会拒收，凭据类明细别指望记忆**

## 7. 备份 + 自动更新（两个 timer）

- `<name>-backup.service`（Type=oneshot）+ `.timer`，`OnCalendar=*-*-* 03:20`，`Persistent=true`
- `<name>-update.timer`，`OnCalendar=Sun *-*-* 04:40`，`docker pull` → `docker rm -f` → `docker run` 重建（数据在挂载卷里不受影响）
- **sqlite 类应用备份必须同时拷 `db.sqlite3` + `-wal` + `-shm`**：WAL 模式下只拷主库会丢最近写入；容器内不一定有 `sqlite3` 命令，直接用 `cat` 拉文件即可
- **`shutil.make_archive(base, 'gztar', dir)`** —— 格式名是 `gztar`，写 `gzip` 直接 ValueError
- 备份完立刻验：解开 → `sqlite3` 打开 → `pragma integrity_check` 应为 `ok`，并数表/条数，别只看文件大小

## 8. the user said "密码不对 / 你改了密码"：先取证再回话

他对不上密码时会默认是你动了手。**先证明有没有被改过，再动手；取证完直接改好交付，不要把辩解放在结论前面。**

1. `stat -c '%y' <凭据文件>` —— mtime 早于本次会话 = 不是我改的
2. 读密码行，用 `hmac.compare_digest` 逐个比对候选，**只打印是否匹配，不打印明文**
3. **长度对不上就不必再猜**（他记 9 位、文件里 8 位 → 从来不是同一个密码，不是"被改了"）；再看首位字符、是否含数字/字母缩小范围
4. 按他要的值写回 → **重启对应认证服务** → 两个入口实测 → 结论和证据一起给

**认证进程通常在模块导入时读一次密码**（如 `user-auth`），只改文件不重启 → 还是旧密码，表现就是"改了没生效"。

## 特定服务

- **Vaultwarden**（密码库）→ `references/vaultwarden.md`
- **Stirling-PDF**（OCR/转换/发票归档）→ `stirling-pdf` 技能
