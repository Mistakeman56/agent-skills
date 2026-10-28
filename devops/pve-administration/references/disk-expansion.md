# 磁盘扩容：给 PVE 上的 CT/VM 扩根分区

## 关键认知（先看，能省一小时）

- PVE 默认是 **LVM-Thin**：`vgs` 的 `VFree` 只是**池外**剩余。真正空间在薄池 `data` 里，看
  `lvs pve/data -o lv_size,data_percent`。`vgs` 显示只剩 12G 不代表没空间——薄池 348G 只用了 40%。
- 物理盘 476.9G → VG 475.94G = `pve/root` 96G + `pve/swap` 8G + 薄池 data + 12G free。
- **薄卷扩展（`lvextend` 一个 thin volume）是元数据操作，秒级、不搬数据**，只要有池容量。
  扩完 LVM 会警告「所有薄卷虚拟尺寸之和 > 池容量」——这是 thin over-provision，正常，看实际用量即可。
- 扩 LV **不会**自动扩文件系统，必须再 `resize2fs`（ext4）。少这步 = `df` 还是旧大小。

## 主机/凭据

- PVE host: `192.0.2.10`（root，密码在 `~/.hermes/.env` 的 `PVE_ROOT_PASSWORD`，用
  `sshpass -f` 或环境变量，**别打印、别写进 memory**）
- Hermes 自己 = **CT <ID>**（unprivileged LXC），根 LV = `pve/vm-202-disk-0`，major:minor `252:9`

## 步骤

```bash
# 1) 看真实余量
sshpass -f <pwfile> ssh root@192.0.2.10 'vgs; lvs -o lv_name,lv_size,data_percent,pool_lv pve/data pve/vm-202-disk-0'

# 2) 扩薄卷（秒级）
sshpass -f <pwfile> ssh root@192.0.2.10 'lvextend -L 160G pve/vm-202-disk-0'

# 3) 扩文件系统 —— 必须从宿主机进容器挂载 ns（见陷阱 1-3）
sshpass -f <pwfile> ssh root@192.0.2.10 '
CTPID=""; for p in $(pgrep -x lxc-start); do
  case "$(tr "\0" " " < /proc/$p/cmdline)" in *" 202"*) CTPID=$p;; esac
done
nsenter -t $CTPID -m -- sh -c "mknod /dev/dm9 b 252 9"
nsenter -t $CTPID -m -- resize2fs /dev/dm9
nsenter -t $CTPID -m -- rm -f /dev/dm9   # 用完删掉
'

# 4) 验证（在容器内）
df -hT /
```

## ⚠️ Pitfalls

1. **`pct pid <vmid>` 在 PVE 9 不存在**（会打印整份 pct usage）。取 PID 用
   `pgrep -x lxc-start` + 读 `/proc/<pid>/cmdline` 匹配 `-n <vmid>`；或 `lxc-info -n <id> -p -H`。
2. **容器内 `mknod` 报 `Operation not permitted`**：unprivileged CT 建不了块设备节点，也读不到
   `/dev/mapper/...`。所以 `resize2fs` 只能在宿主机执行，用 `nsenter -t <pid> -m` 进容器挂载 ns
   （宿主 root 权限 + 不受容器 device cgroup 限制），在那里的 `/dev` 造节点。
3. **别在宿主机直接 `resize2fs /dev/pve/vm-202-disk-0`**：宿主 `/proc/mounts` 看不到该挂载（在容器
   mount ns 里），resize2fs 会当成离线 fs 去改一个**正在挂载**的文件系统 → 有损坏风险。必须 nsenter
   让它输出 `on-line resizing required`（这才是在线扩）。
4. **`pgrep -af 'lxc-start -n 202'` 会匹配到你自己的 ssh 命令行**（模式出现在 shell 命令里）。
   用 `pgrep -x lxc-start` 只匹配真实进程名。
5. **薄池没开自动扩容**：宿主报
   `WARNING: You have not turned on protection against thin pools running out of space.`——池写满时
   所有 CT 会一起冻结。开法见下文「薄池自动扩容与监控」；宿主级变更，**动手前先问用户**。

## 薄池自动扩容与监控（池写满冻结所有 CT 的防线）

```bash
# 1) 备份 + 只改“automatic default value”那两行
#    （example 行也是 `# ... = 70/20`，正则命中两处会互相覆盖 → 从后往前只改最后一处）
cp -a /etc/lvm/lvm.conf /etc/lvm/lvm.conf.bak.$(date +%Y%m%d-%H%M%S)
python3 - <<'PY'
import re
p = '/etc/lvm/lvm.conf'; lines = open(p).read().splitlines(True)
def patch_last(pat, repl):
    for i in range(len(lines) - 1, -1, -1):
        if re.match(pat, lines[i]):
            lines[i] = repl; return True
    return False
assert patch_last(r'\s*# thin_pool_autoextend_threshold = 100\s*$', '\tthin_pool_autoextend_threshold = 80\n')
assert patch_last(r'\s*# thin_pool_autoextend_percent = 20\s*$',   '\tthin_pool_autoextend_percent = 3\n')
open(p, 'w').writelines(lines)
PY

# 2) 回读生效值（用 LVM 自己的工具，肉眼看文件不算）
lvmconfig activation/thin_pool_autoextend_threshold
lvmconfig activation/thin_pool_autoextend_percent

# 3) 起监控 + 给老薄池开监控（缺这步 autoextend 永远不会跑）
systemctl enable --now lvm2-monitor
lvs -o lv_name,seg_monitor,segtype pve/data    # 必须显示 monitored
lvchange --monitor y pve/data                  # 历史创建的薄池默认没开

# 4) 验收：同尺寸干跑，WARNING 消失 = 配置生效
lvextend -L 160G pve/vm-202-disk-0
```

- **`thin_pool_autoextend_percent` 是薄池的百分比**，必须算进 `vgs` 的 `VFree`：10%≈35G > 剩余 12G
  → 触发时 lvextend 直接因空间不足失败，等于没开。配成能塞进剩余量的值（本机 3%≈10.5G ≤12G）。
- 监控状态字段是 **`seg_monitor`**（`-o monitor` 报 `Unrecognised field`）；`dmeventd` 不在线时
  自动扩容不会执行，所以第 3 步不能省。
- VG 只剩十几 G 时，自动扩容最多救一次：真正保险是加告警（cron 检查 `data_percent` >75% 推微信）。

## 实测参考（2026-10，本机）

`vm-202-disk-0` 80G(用 97.54%) → 160G：薄卷扩展 0.5s、`resize2fs` 在线扩 0.58s，容器内 `df` 立即
显示 158G/48%，全程不停服、不动数据。另：找宿主机可扫局域网 **8006 端口**（Proxmox UI）——本机是
`192.0.2.10`，只有 22+8006 同时开的那台就是。
