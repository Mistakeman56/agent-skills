# VMware VMDK → Proxmox VE 虚拟机迁移指南

将 VMware 虚拟机磁盘（VMDK）迁移到 Proxmox VE 的完整工作流。适用于从旧版 VMware Workstation/Player 导出的 Windows 虚拟机需要跑在 PVE 上的场景。

## 完整流程

### 1. 获取 VMDK 文件

通常从网盘/课程资料下载为 zip：
```bash
# 下载
wget -O vm.zip "分享链接"
# 解压
python3 -c "
import zipfile
with zipfile.ZipFile('vm.zip', 'r') as z:
    z.extractall('vm/')
"
# VMDK 就在解压目录里
ls -lh vm/*.vmdk
```

### 2. 查看 VMX 确认原始配置（必做）

```bash
cat vm/*.vmx
```

**关键看：**
- `scsi0.present = "TRUE"` vs `ide0.present` — 磁盘控制器类型
- `scsi0.virtualDev = "buslogic"` 或 `"lsilogic"` — 具体 SCSI 型号（**未指定时 VMware 根据 guestOS 自动选**）
- `guestOS = "win2000AdvServ"` — 客户机类型
- `memsize = "128"` — 内存大小

### 3. 传到 PVE 宿主机

```bash
# SCP 传输
sshpass -p '密码' scp vm/磁盘名.vmdk root@pve_ip:/root/

# 或 rsync（如果支持）
rsync -avP vm/磁盘名.vmdk root@pve_ip:/root/
```

### 4. 在 PVE 上转换 VMDK → qcow2

```bash
# 安装 qemu-utils（如需要）
apt install qemu-utils -y

# 转换
qemu-img convert -f vmdk -O qcow2 /root/磁盘名.vmdk /root/vm.qcow2

# 验证
qemu-img info /root/vm.qcow2
```

### 5. 创建 VM 并导入磁盘

```bash
# 选择空闲 VM ID
for id in $(seq 100 400); do
  qm status $id 2>/dev/null || { echo $id; break; }
done

# 创建 VM（以 Win2K Advanced Server 为例）
QM_ID=300
qm create $QM_ID \
  --name win2k-vm \
  --memory 1024 \
  --cores 2 \
  --cpu qemu64 \
  --machine pc-i440fx-9.0 \
  --bios seabios \
  --net0 e1000,bridge=vmbr0 \
  --vga cirrus \
  --ostype l26 \
  --agent 0 \
  --boot order=scsi0 \
  --onboot 0

# 导入磁盘
qm importdisk $QM_ID /root/vm.qcow2 local-lvm

# 挂载磁盘（选择合适的 SCSI 控制器）
qm set $QM_ID --scsihw lsi --scsi0 local-lvm:vm-${QM_ID}-disk-0
```

### 6. 处理 0x7B INACCESSIBLE_BOOT_DEVICE

从 VMware 迁移 Win2K/WinXP 到 PVE 几乎必出 `STOP 0x0000007B`。原因：

| VMware 默认控制器 | PVE 可选控制器 | 兼容性 |
|---|---|---|
| **BusLogic**（Win2K 默认） | ❌ PVE 不支持 | — |
| LSI Logic | ✅ `lsi` / `lsi53c810` | Win2K 原生驱动，**BSOD 0x7B**（驱动签名不匹配） |
| — | `megasas` | 可能检测不到磁盘 |
| — | `pvscsi` | 需要 VMware Tools |

**根因：** VMware 的 BusLogic/LSI Logic 驱动实现与 QEMU 的 LSI 实现有差异，Win2K 加载错误的驱动后无法访问启动分区。

### 深层原因分析（为什么改注册表也没用）

用 hivex 挂载 Win2K 磁盘分析后发现：
- VMware VM 只有 `vmscsi.sys` 作为 SCSI 驱动文件，`symc810.sys` / `symc8xx.sys` 在注册表中有服务条目但**磁盘上没有对应的 .sys 文件**
- `boot.ini` 已经是 `multi(0)disk(0)rdisk(0)partition(1)`（IDE 路径），但内核的 boot volume mount I/O 路径在安装时绑定到 SCSI 控制器，与 boot.ini 无关
- 即使禁用所有 SCSI 驱动、启用 IDE 驱动、加 `/safeboot:minimal`，BSOD 依旧
- **结论：** 内核级的磁盘 I/O 路径在安装时就固化了，无法通过离线修改注册表改变

### Python hivex 编辑 Windows 注册表的 API 注意事项

如果未来确实需要编辑 Windows 注册表离线（非 SCSI→IDE 场景），hivex Python API 有几个坑：
```python
import hivex, struct
h = hivex.Hivex("/path/to/SYSTEM", write=True)

# ❌ node_value_key() 不存在 → 用 value_key()
key = h.value_key(vk)

# ❌ hivex.REG_DWORD 不存在 → 用整数 4
REG_DWORD = 4

# ❌ 修改后立即读取可能返回旧值 → 必须 commit 后重新打开
h.node_set_value(node, {"key": "Start", "t": REG_DWORD, "value": struct.pack("<I", 4)})
h.commit("/path/to/SYSTEM")
h2 = hivex.Hivex("/path/to/SYSTEM")  # 重新打开验证
```

### ⚠️ 铁律：不要尝试修改注册表修复 SCSI→IDE 转换

**多次实验证明（2026-06-29）：** 即使用 hivex 禁用所有 SCSI 驱动（vmscsi、BusLogic、symc810）、启用 IDE 驱动（atapi、IntelIde），仍然 BSOD。安全模式也进不去。原因：内核的 boot volume mount I/O 路径在安装时绑定到 SCSI 控制器，与 boot.ini 的 multi(0) 设置无关。**必须从 ISO 全新安装。**

已尝试的所有失败方案：
1. IDE 控制器（boot.ini 已是 multi(0)）→ BSOD
2. LSI / lsi53c810 SCSI → BSOD（驱动不兼容）
3. hivex 修改注册表禁用 SCSI + 启用 IDE → BSOD
4. boot.ini 加 /safeboot:minimal → BSOD
5. 换 machine type pc-i440fx-6.2 → BSOD

### 7. 修复方案（需要 Win2K Advanced Server ISO）

1. **找到 Win2K Advanced Server ISO**（学校提供或网盘下载）
2. **上传到 PVE 存储：**
   ```bash
   sshpass -p '密码' scp win2k.iso root@pve_ip:/var/lib/vz/template/iso/
   ```
3. **挂载为光驱并设为第一启动项：**
   ```bash
   qm set $QM_ID --ide2 local:iso/win2k.iso,media=cdrom
   qm set $QM_ID --boot order=ide2,scsi0
   ```
4. **启动 VM → 按 R 进入恢复控制台 → 运行：**
   ```
   fixboot
   fixmbr
   bootcfg /rebuild
   ```
5. 重启 VM（恢复光驱启动顺序为 scsi0）

### 8. QEMU 截图（验证启动状态）

```bash
# 通过 QMP 接口截图
echo '{"execute":"qmp_capabilities"}
{"execute":"screendump","arguments":{"filename":"/tmp/screen.ppm"}}' \
  | socat - UNIX-CONNECT:/var/run/qemu-server/${QM_ID}.qmp

# 转 JPEG 并分析
ffmpeg -y -i /tmp/screen.ppm /tmp/screen.jpg 2>/dev/null
# 再用 vision_analyze 检查
```

### 9. 注意事项

- **VMX 配置文件** 是第一参考——控制器型号、内存、guestOS 类型都在里面
- **SCSI 控制器选择** 按优先级尝试：`lsi` → `lsi53c810` → `megasas` → `pvscsi`
- **KVM 不可用时**（`/proc/cpuinfo` 无 vmx/svm），VM 会降级为 TCG 全软件模拟，启动极慢（Win2K 约 5-10 分钟）
- **禁用 KVM**：`qm set $QM_ID --kvm 0 --cpu qemu64`
- **Win2K 内存建议**：最小 256MB，推荐 1024MB（PVE 默认）
- **网卡**：Win2K 原生支持 e1000，不需要额外驱动
- **显示**：Cirrus VGA 是 Win2K 兼容性最好的选择
