# 内网应用服务清单（2026-10 更新）

PVE 宿主 `192.0.2.10`，公网入口统一走 CT <ID> Caddy（`192.0.2.10`）。
泛解析 `*.example.com` 已覆盖，**加新子域名不需要改 DNS**。

| 服务 | CT | 内网地址 | 公网域名 | 技术栈 |
|---|---|---|---|---|
| Stirling-PDF | 320 | 192.0.2.10:8080 | pdf.example.com:18443 | Docker，镜像 3.58G，mem_limit 3g |
| Vaultwarden | 321 | 192.0.2.10:8080 | pass.example.com:18443 | Docker，1核/1G/6G，实测 16MB 内存 |

两者都 `--restart unless-stopped`，数据挂载在 `/opt/<name>/`，容器重建不丢数据。
Caddyfile 末尾追加，`admin off` → **只能 `systemctl restart caddy`**，重启会短暂中断全部站点（先 `cp -a` 备份）。

## Caddy 站点块模板

```caddy
https://<sub>.example.com:18443, https://<sub>.example.com {
	tls /etc/caddy/certs/fullchain.pem /etc/caddy/certs/privkey.pem
	encode gzip
	import hdrs
	request_body {
		max_size 525MB
	}
	reverse_proxy http://<内网IP>:<端口> {
		header_up Host {http.request.host}
		header_up X-Real-IP {remote_host}
		header_up X-Forwarded-Proto {scheme}
		flush_interval -1   # WebSocket 必需（Vaultwarden 实时同步）
	}
}
```

## 导航页（nav-monitor）

新增服务要改**两个文件**，缺一个卡片就显示不出来：

1. `~/.hermes/nav-monitor/collector.py` → `SERVICES` 字典加 `"key": "http://ip:port/"`
   - **注意对齐空格**：现有行是 `"pdf":          "http://..."`，用单空格 replace 会静默失败，必须 `grep -n` 看实际缩进
2. `/var/www/nav/index.html` → 加 `<a class="card svc" data-svc="key">` 卡片块

然后 `systemctl restart nav-monitor`，验证 `/var/www/nav/api/status.json` 的 **`services`** 字段（顶层是 `{ts, devices, cycle_ok, services}`，不是直接在根上）。

## 定时任务现状

| timer | 时间 | 作用 |
|---|---|---|
| invoice-archive.timer | 每 :15/:45 | 发票上传 Stirling（与 cron 错峰） |
| vaultwarden-backup.timer | 每天 03:22 | 打包数据库+密钥，留 30 份 |
| vaultwarden-update.timer | 每周日 04:40 | 拉新镜像重建容器（该项目有安全公告，必须跟） |

备份目录 `~/.hermes/backups/vaultwarden/`；脚本 `~/.hermes/scripts/vaultwarden_backup.py`。

## 踩过的坑

- **`pct exec` 会 `cd /`**，脚本里的相对路径全部失效 → 一律写绝对路径或先 `cd`。
- **空目录挂载会遮盖镜像内容**（Stirling 的 tessdata 就是这样把中文包和 `configs/` 遮没的）→ 自定义挂载前先 `docker cp` 把镜像原内容提出来。
- **替换挂载目录后必须 `docker restart`**，否则容器仍绑旧 inode，改了看不出来。
- 容器内 `sqlite3` 命令不一定存在（Vaultwarden 精简镜像就没有）→ 备份直接拷 `db.sqlite3` + `-wal` + `-shm` 三个文件，WAL 模式少拷会丢最近数据。
- `python3 shutil.make_archive(..., "gzip", ...)` 会报 `unknown archive format`，正确格式名是 **`gztar`**。
