# PVE LXC 容器停摆排查：磁盘被 core dump 撑满 + LXC 里必然失败的 systemd 单元

适用场景：某个 LXC 容器"莫名其妙起不来了"、`pct start` 报错、开机自启失败。

## 0. 速查
```bash
ssh root@<PVE_HOST>            # 家庭环境：192.0.2.10
pct list                        # 看状态；stopped 的看 last-start
lvs -o name,data_percent,lv_size | grep vm-<id>   # 看磁盘真实占用
journalctl -u pve-container@<id> --no-pager | tail -30   # 看 start 失败原因
```

## 1. 经典故障：`pct start` 失败 + `No space left on device`
**症状**
```
unable to open file '/fastboot.tmp.<pid>' - No space left on device
TASK ERROR: startup for container '<id>' failed
```
`/fastboot.tmp.*` 是 PVE 的 pre-start hook 在**容器 rootfs 里**写的临时文件。
→ 说明**容器自己的磁盘 100% 满**（不是 thin pool 满；pool 满会报 thin 相关错误）。

**定位**
```bash
mkdir -p /mnt/ct<id>
mount -o ro /dev/pve/vm-<id>-disk-0 /mnt/ct<id>     # 先只读挂
df -h /mnt/ct<id>
du -sh /mnt/ct<id>/* 2>/dev/null | sort -h | tail -20
du -sh /mnt/ct<id>/.[!.]* 2>/dev/null | sort -h | tail -20   # 别忘隐藏目录
```

**本案元凶（2026-09 CT100）**：容器的 lightdm/Xorg 崩溃循环，每次段错误按 `core_pattern=core`
（相对路径 → 落在崩溃进程的 CWD = 容器 `/`）产生一个 core dump。
`find / -maxdepth 1 -name 'core.[0-9]*' | wc -l` → **59,642 个 × 1.8MB ≈ 68 GB**，把 98G 磁盘撑满。

**清理（必须先 remount rw！只读挂载下 find -delete 报 "Read-only file system"）**
```bash
mount -o remount,rw /mnt/ct<id>      # 或 umount + mount（不带 ro）
# 确认元凶进程：file core.<pid>  → "from '/usr/lib/xorg/Xorg ...'"
find /mnt/ct<id> -maxdepth 1 -name 'core.[0-9]*' -type f -delete
```
⚠ 一定加 `-maxdepth 1`：`core.[0-9]*` 会误匹配 `/usr/share/man/man5/core.5.gz`。

**顺带清日志**（崩溃循环同时把 syslog 写到 GB 级）
```bash
for f in var/log/syslog var/log/kern.log var/log/auth.log var/log/lightdm/*.log; do
  [ -f "/mnt/ct<id>/$f" ] && : > "/mnt/ct<id>/$f"; done
rm -rf /mnt/ct<id>/var/log/journal/*
```

**根治（否则重启后继续刷 core）**：在容器停机状态下直接改 rootfs 里的 systemd 配置
```bash
R=/mnt/ct<id>
ln -sf /lib/systemd/system/multi-user.target $R/etc/systemd/system/default.target
rm -f $R/etc/systemd/system/display-manager.service
ln -sf /dev/null $R/etc/systemd/system/lightdm.service      # mask
umount $R && pct start <id>
```
`mask` 掉 lightdm 后 xrdp 仍可用（xrdp 自己拉 X 会话，不依赖 display-manager）。

## 1b. 删完文件磁盘**没变小**？跑 fstrim（必做）
LVM-thin 上删文件只释放**文件系统**里的块，**不会自动还给 thin pool**。
症状：容器内 `df` 已经 27G/98G，但 `lvs` 里 `vm-<id>-disk-0` 仍是 `Data% 99.95`，pool 占用也没降。
```bash
lvs -o name,data_percent pve/data pve/vm-<id>-disk-0   # 回收前后对比
pct fstrim <id>                                        # 关键一步
# 输出示例：/var/lib/lxc/100/rootfs/: 71.5 GiB (76723564544 bytes) trimmed
```
本案效果：pool `data` 44.52% → 24.23%，`vm-100-disk-0` 99.95% → 29.15%。
→ 定期 `pct fstrim <id>`（或给 thin 存储开 discard）比事后救火强。

## 2. LXC 里"注定失败"的 systemd 单元 —— 别当成故障
特权/非特权 LXC 里下列单元常见 `status=226/NAMESPACE`（"Failed to set up mount namespacing: Permission denied"）：
`logrotate`、`apparmor`、`NetworkManager`、`systemd-networkd`、`systemd-resolved`、
`systemd-logind`、`polkit`、`colord`、`nftables`。
→ 容器跑得好好的就不用管，`systemctl is-system-running` 会显示 `degraded`，这**不代表故障**。

**真要修 logrotate**（它挂了就没人轮转日志，容易重演磁盘满）：整体覆盖单元、去掉沙箱
```bash
cat > /etc/systemd/system/logrotate.service <<'EOF'
[Unit]
Description=Rotate log files
After=local-fs.target
[Service]
Type=oneshot
ExecStart=/usr/sbin/logrotate /etc/logrotate.conf
EOF
systemctl daemon-reload && systemctl start logrotate
```
（只加 `PrivateMounts=no` 的 drop-in 不够，`ProtectSystem=` 等仍会请求 mount namespace。）

## 3. LXC 里 DNS 失效（容器 ping 得通 IP 但解析不了域名）
PVE 每次启动容器会用宿主 resolv.conf 重写容器 `/etc/resolv.conf`。
本案容器内 `192.0.2.10` 不响应查询（宿主机查它是正常的），导致解析全挂。
持久修法（两处都做，互补）：
```bash
pct exec <id> -- bash -c 'printf "nameserver 203.0.113.1\nnameserver 203.0.113.1\n" > /etc/resolv.conf'
echo "nameserver: 203.0.113.1" >> /etc/pve/lxc/<id>.conf    # PVE 侧钉住，重启不再被覆盖
pct config <id>          # 无 "unknown config key" 警告即生效
```

## 4. 用 tailscale 当唯一稳定入口
容器 IP 是 DHCP（本案 CT100 拿 192.0.2.10，会变），
Tailscale 名字/IP（`tailscale status` 里的 100.x.x.x）才是稳定访问点 —— 报地址时优先给 Tailscale IP。
LXC + tailscale 重启后常见 `/dev/net/tun` 丢失，启动脚本里补：
```bash
mkdir -p /dev/net; [ -c /dev/net/tun ] || mknod /dev/net/tun c 10 200
chmod 666 /dev/net/tun; systemctl restart tailscaled
```

## 5. 长期封存一个容器（"等考完试/放假再开"）
```bash
# 1) 先优雅停掉里面的服务（例：MC 服务端），确认存档写完
pct exec <id> -- screen -S mc -p 0 -X stuff "stop\n"
pct exec <id> -- pgrep -c java        # 应为 0；日志里要有 "All dimensions are saved"
# 2) 禁开机自启 —— 否则宿主机重启时它自己就起来了，"封存"白做
pct set <id> --onboot 0
# 3) 优雅关机（ACPI）；超时才用 pct stop
pct shutdown <id> --timeout 90        # 再用 pct status <id> 确认 stopped
# 4) 打封存快照：thin 快照初始额外占用≈0（只共享块+记元数据）
pct snapshot <id> sealed-<日期>-<用途>   # 例 sealed-20260914-exam
pct listsnapshot <id>
# 5) 不启动容器，只读挂载核验关键数据还在
cd / && mount -o ro /dev/pve/vm-<id>-disk-0 /mnt/ct<id> \
  || mount -o ro,noload /dev/pve/vm-<id>-disk-0 /mnt/ct<id>
# ...du / find 核验...
cd / && umount /mnt/ct<id>            # 必须先离开目录，否则 "target is busy"
```
要点
- 封存前务必先 `pct fstrim <id>`，否则薄池里的空间一直占着不还。
- 快照名带用途+日期，日后可直接 `pct rollback <id> <snap>` 回到封存点。
- **快照期间 thin discard 受限**：快照存在时不建议长期高强度跑；要长期运行就 `pct delsnapshot` 删掉封存快照。
- `pct snapshot` 的告警含义：`thin_pool_autoextend_threshold not set` 是**真提示**（池满 = 所有容器一起挂，可在 `/etc/lvm/lvm.conf` 设阈值，但 VG 无空闲 PE 时也扩不动）；`Sum of all thin volume sizes exceeds pool` 是 thin 超额分配的**常态**警告，不用慌。
- 判断是否真封住：`pct status` = stopped、`pct config` 里 `onboot: 0`、`pct exec` 报 `container '<id>' not running!`。
