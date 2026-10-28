# NAS 配置隐患体检（UGOS Pro / 绿联 DXP4800）

目标：一次性把硬盘、存储、容器、UPS、对外端口过一遍，**先查后报**，产出分优先级的清单；不要边查边打断用户。

## 1. 一批命令拿全

```sh
sshpass -p '<pw>' ssh user@192.0.2.10     # 该用户已入 docker 组；scp 不可用，脚本走 base64 管道
uname -r; uptime; free -h; df -h; lsblk
sudo du -h --max-depth=2 /volume2
docker ps -a --format '  {{.Names}} | {{.Image}} | {{.Status}}'
journalctl -p err --since "24 hours ago" --no-pager
```

**UGOS 卷布局**：`/volume1` 系统、`/volume2` 数据（`downloads0` 媒体、`@home` 用户家目录、`@thumbnail` 缩略图缓存**可清**）、`/volume3` 小分区。
- `du` 对**硬链接媒体会重复计数**（`已整理` 与 `未整理` 指向同一 inode）→ 汇报时说明是逻辑大小不是实占，别拿它当剩余空间。
- `@home` 常藏安装包/备份等大文件，值得单列。

## 2. SMART 巡检

- `smartctl` 在 `/usr/sbin/smartctl`，**需要 root**。
- SSH 里用 base64 管道传脚本时，`echo pw | sudo -S …` 会**抢走脚本自己的 stdin** → 在脚本内用 here-string 缓存凭据：
  ```sh
  sudo -S -v <<< '<pw>' 2>/dev/null
  /usr/sbin/smartctl -H /dev/sda
  /usr/sbin/smartctl -A /dev/sda
  ```
- 逐盘看 `Reallocated_Sector_Ct` / `Current_Pending_Sector` / `Offline_Uncorrectable`（应为 0）与 `Temperature_Celsius`。`Reported_Uncorrect > 0` 且 `Hardware_ECC_Recovered` 极高 = 该盘要盯但未必坏，**判据是 pending/uncorrectable 是否为 0，不能只看 `PASSED` 一项**。

**UGOS 自带的 smartd 配置是坏的**：`DEVICESCAN -d removable …` **只扫可移动设备**，机械盘/NVMe 根本不进监控（所以日志恒空）。修法 —— 备份 `/etc/smartd.conf` 后追加显式设备行：
```
/dev/sda -a -o on -S on -n standby -m once -M exec /usr/share/smartmontools/smartd-runner
/dev/sdb -a -o on -S on -n standby -m once -M exec /usr/share/smartmontools/smartd-runner
/dev/sda -s (S/../.././02) -m once -M exec /usr/share/smartmontools/smartd-runner   # 每月 2 号短自检
```
`systemctl restart smartmontools`，然后**触发一次 `smartd -q one-check` 或查 syslog**，确认出现 `is SMART capable. Adding to "monitor" list` 才算配上了，否则等于没配。
- 通知链是 `smartd-runner` → `/etc/smartmontools/run.d/10mail` → `/usr/bin/mail`；**没配 MTA 就只有日志，不会主动通知**，要主动告警得另想办法。

## 3. 硬盘休眠（用户常问「有没有启用」）

查三处：
- `/etc/power.conf` —— 若只有 `power_boot` / `wake_on` / `enable_scheduled_power`，就是**没配磁盘休眠**；
- `/etc/systemd/sleep.conf` + `systemctl is-active sleep.target` —— inactive = 系统不休眠；
- systemd timers 里有没有 spindown 类定时器。

NAS 保持 7×24 常醒是对的（避免唤醒延迟和掉服务）。`/sys/block/sdX/device/power/control` 的 `on` 是 runtime PM，**不等于停转**，别把它当成休眠证据。

## 4. UPS（NUT）

- 配置 `/etc/nut/ups.conf`，`offdelay` = **断电多久关机**。出厂给的 12 秒太激进，市电闪断就关机 → 建议 60~120 秒。
- 改前 `cp -a` 备份，改后 `systemctl restart nut-server nut-monitor`，用 `upsc <ups名> ups.status` 确认 `OL` 才算生效。
- `upsd.users` 里的默认密码属低危（仅本地访问），但别写进聊天。

## 5. 容器清单里的信号

- `Exit 137` = SIGKILL（常见 OOM）；`Exit 143` = SIGTERM（被停）；`Exit 0` + 很久以前 = 手动停的。
- 同一服务出现一 running 一 Exited 两个容器 = 残留；先确认配置目录在 volume 里，再 `docker rm`（**不带 -v**，绝不动 volume）。
- 停了很久的容器只列出来问用户，不自作主张删。

## 6. 对外端口核对

对照路由器 `uci show firewall | grep redirect`，逐条确认 **`dest_port` 在目标机上有监听**（`ss -lnt | grep <端口>`）。PostgreSQL / Redis / SMB / NFS / SSH 这类不该出现在 WAN 转发里；只暴露业务端口（BT 做种、桌面入口）。
