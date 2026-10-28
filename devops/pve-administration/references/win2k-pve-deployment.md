# Windows 2000 Advanced Server on PVE

Session-specific deployment notes from 2026-05-12.

## What We Had

User provided a VMware VM archive: `Windows 2000 Advanced Server(original).zip`
- Contents: VMDK, VMX, NVRAM (pre-installed VMware VM)
- VMware controller: **BusLogic SCSI** (default for Win2000AdvServ guest OS)
- PVE does NOT support BusLogic → `INACCESSIBLE_BOOT_DEVICE` BSOD on boot

## Fresh Install Approach (Recommended)

Instead of converting the VMware VM, do a clean install from ISO:

### 1. Get the ISO

Windows 2000 Advanced Server SP4 (English):
- Build: 5.00.2195.6717
- Size: ~375MB
- Product Key: `WY6PG-M2YPT-KGT4H-CPY6T-GRDCY`

Sources from China:
- archive.org → blocked by GFW
- winworldpc.com → CDN (dl-alt1.winworldpc.com) 可直接访问，但下载速度仅30-50KB/s
- **Ask user:** Baidu Netdisk link, cldisk.com link, or school LAN
- **Bright Data search:** 搜索索引页(如iboysoft.com)找到各种直链，再逐条测试可达性

### 2. Create VM

```bash
# PVE 9.1.1+
VMID=301  # Use an available ID
qm create $VMID \
  --name win2k-adv-server \
  --memory 1024 \
  --cores 2 \
  --cpu qemu64 \
  --machine pc-i440fx-9.0 \
  --bios seabios \
  --net0 e1000,bridge=vmbr0 \
  --vga cirrus \
  --ide2 local:iso/WIN2KAS_SP4.iso,media=cdrom \
  --boot order=ide2,ide0 \
  --kvm 0 \
  --onboot 0
```

### 3. Install

Start the VM from PVE web console (VNC):
1. Boot from CD
2. Follow text-mode installer (Win2K installer is mostly text + some GUI)
3. During install, create a single NTFS partition on the 4GB virtual disk
4. After install completes, log in as Administrator

### 4. Post-Install

- Set static IP (for lab network)
- Disable Windows Firewall (if applicable for security lab)
- Install any lab-specific tools

## What Went Wrong (VMware Migration) — 2026-06-29 详细复盘

### ⚠️ 核心结论：SCSI→IDE 转换无法通过修复实现

**不管怎么改注册表、禁用驱动、换控制器类型，SCSI→IDE 转换都行不通。** 内核的磁盘 I/O 路径在 SCSI 和 IDE 之间是根本不同的，BSOD 发生在驱动加载之前的最底层。

### Attempt 1: IDE (boot.ini 已经是 multi(0))
- boot.ini 原本就是 `multi(0)disk(0)rdisk(0)partition(1)\WINNT`
- Result: `INACCESSIBLE_BOOT_DEVICE` BSOD
- **关键发现：boot.ini 用 multi(0) 不代表 IDE 驱动能工作**

### Attempt 2-3: LSI / lsi53c810 SCSI
- Result: BSOD — QEMU 的 LSI 控制器与 VMware BusLogic 驱动不兼容

### Attempt 4: BusLogic
- PVE 不支持此控制器类型

### Attempt 5: 修改注册表禁用 SCSI、启用 IDE
- 用 hivex 修改 ControlSet001\Services：
  - vmscsi Start: 0→4 (disabled)
  - BusLogic Start: 0→4 (disabled)
  - symc810 Start: 0→4 (disabled)
  - atapi Start=0, IntelIde Start=0 (保留)
- **结果：仍然 BSOD 0x7B**

### Attempt 6: 安全模式
- boot.ini 加 `/safeboot:minimal`
- **结果：仍然 BSOD 0x7B** — BSOD 发生在 Safe Mode 介入之前

### Attempt 7: 换 machine type (pc-i440fx-6.2)
- **结果：仍然 BSOD 0x7B**

### 诊断发现（均正常但无帮助）
- MountedDevices 磁盘签名 `0x123e0a93` 与 MBR 一致 ✅
- HAL 是 halaacpi.dll（正确的 ACPI APIC HAL）✅
- atapi.sys、intelide.sys、pciidex.sys 均存在 ✅
- SetupType=0, SystemSetupInProgress=0（非安装模式）✅

### 根因分析
Win2000 在 VMware BusLogic SCSI 上安装时，内核的 boot volume mount 路径硬编码为 SCSI I/O 路径。即 boot.ini 写 multi(0)，NTLDR 也能找到 ntoskrnl.exe，但内核初始化时尝试通过 SCSI miniport 驱动链挂载启动卷——此时 SCSI 驱动已禁用，IDE 驱动虽然存在但内核的 I/O 路径已经绑定了 SCSI，无法切换。

**结论：必须从 ISO 全新安装。不要尝试修复 VMware 转换。**

## hivex Python API 备忘（如果需要编辑离线 Windows 注册表）

```python
import hivex, struct
h = hivex.Hivex("/path/to/SYSTEM", write=True)
root = h.root()

# 遍历值
for vk in h.node_values(node):
    key = h.value_key(vk)       # ⚠️ 是 value_key() 不是 node_value_key()
    typ = h.value_type(vk)       # 返回 tuple (type_id, storage_type)
    dword_val = h.value_dword(vk) # 仅 REG_DWORD (type 4)
    str_val = h.value_string(vk)  # 仅 REG_SZ (type 1)
    raw = h.value_value(vk)       # 返回 (type, bytes)

# 修改 DWORD 值
REG_DWORD = 4  # ⚠️ 不是 hivex.REG_DWORD（模块无此常量）
h.node_set_value(node, {"key": "Start", "t": REG_DWORD, "value": struct.pack("<I", 4)})

# 修改字符串值
h.node_set_value(node, {"key": "CmdLine", "t": 1, "value": b""})

# 保存并重新打开（commit 后句柄失效，必须重新打开读取验证）
h.commit("/path/to/SYSTEM")
h2 = hivex.Hivex("/path/to/SYSTEM")  # 重新打开读取
```

## KVM Availability

This PVE host has no hardware virtualization support (no VMX/SVM flags in CPU):
- `cat /proc/cpuinfo | grep vmx` → empty
- `systemd-detect-virt` → "none"
- Solution: `qm set <VMID> --kvm 0` + `--cpu qemu64`
- **Warning:** TCG emulation pegs CPU at 95-100% and boots very slowly
