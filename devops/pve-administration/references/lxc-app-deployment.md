# 往 LXC 容器里部署一个应用（Step 1–4 流程 + 坑）

SKILL.md 里原来的四步流程搬到这里。前置：容器已建、`sshpass` 到 PVE 宿主机可用。

## Step 1: Install Dependencies

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- apt-get install -y -qq php8.2-cli php8.2-curl"
# Check: pct exec <VMID> -- php -v
# ⚠️ php-curl alone does NOT pull in php-cli. Always install php8.2-cli explicitly.
```

## Step 2: Push Files to the Container

**⚠️ PITFALL: `pct push` requires the target directory to exist first.** Create it explicitly:

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- mkdir -p /var/www"
```

**⚠️ PITFALL: `pct push` needs the file to be ON the PVE host, not on your agent server.** Use base64 piping to transfer:

```bash
# On hermes agent server:
cat /local/path/script.php | base64 -w0 | \
  sshpass -p 'PASS' ssh root@PVE_HOST \
  "base64 -d > /tmp/script.php && pct push <VMID> /tmp/script.php /var/www/script.php"
```

## Step 3: Create a systemd Service

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- bash -c 'cat > /etc/systemd/system/myapp.service << EOF
[Unit]
Description=My HTTP Service
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/php -S 0.0.0.0:8989 -t /var/www /var/www/router.php
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable myapp
systemctl start myapp'"
```

## Step 4: Manage the Service

```bash
# Always use pct exec -- systemctl (not direct systemctl on PVE host)
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- systemctl status myapp --no-pager | head -10"
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- systemctl restart myapp"
```

**⚠️ PITFALL: `pct exec` with complex commands.** Always use `--` separator and quote the bash -c argument. Commands with pipes, redirects, or variables MUST be wrapped in `bash -c '...'`. Bare `pct exec <VMID> systemctl status foo` silently fails or returns garbled output.

## 关联坑（部署时一并检查）

- **gunicorn/uvicorn 默认绑 127.0.0.1** → 部署时一次性把 host/port/依赖全配好（用户明确要求「一次配完再问」），部署后 `pct exec <VMID> -- ss -tlnp | grep gunicorn` 复查。
- **PHP 内置服务器单线程**：>10 并发就瓶预，生产上用 nginx / PHP-FPM。
- **容器内代理环境变量**继承 iStoreOS 的 Clash：用 `--noproxy '*'` 测直连、`-x $HTTPS_PROXY` 测代理，分清楚再下结论。
