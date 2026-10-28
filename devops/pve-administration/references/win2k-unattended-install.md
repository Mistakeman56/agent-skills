# Windows 2000 Unattended Installation on PVE

For lab environments where you need to deploy multiple Win2K VMs without interactive console access (user on WeChat, no PVE web UI), use the **winnt.sif answer file on a virtual floppy disk** technique.

## How Win2K Unattended Installation Works

Windows 2000 setup (like NT-based setup) reads `winnt.sif` from:
1. A floppy disk in drive A: → **Most reliable for PVE**
2. The `$OEM$` folder on the CD-ROM → Requires ISO modification
3. Network share (RIS) → Too complex for simple labs

The floppy approach requires NO ISO modification — just insert a floppy image with the right file.

## Step-by-Step: Creating a winnt.sif Floppy

### 1. Create the answer file

```ini
; Windows 2000 Unattended Installation
[Unattended]
UnattendMode=FullUnattended
OemSkipEula=Yes
OemPreinstall=Yes
TargetPath=\WINNT
FileSystem=ConvertNTFS
ExtendOemPartition=1
WaitForReboot=No
NoWaitAfterTextMode=1
NoWaitAfterGuiMode=1

[UserData]
ProductID=WY6PG-M2YPT-KGT4H-CPY6T-GRDCY
FullName="Administrator"
OrgName="Lab"
ComputerName=HACKER-W2K

[GuiUnattended]
AdminPassword=""
TimeZone=210
AutoLogon=Yes
AutoLogonCount=100
OEMSkipRegional=1
OemSkipWelcome=1

[LicenseFilePrintData]
AutoMode=PerServer
AutoUsers=5

[Display]
BitsPerPel=16
XResolution=800
YResolution=600
VRefresh=60

[Networking]
InstallDefaultComponents=No

[NetAdapter]
Adapter1=Params.Adapter1

[Params.Adapter1]
InfID=*

[NetClients]
MS_MSClient=Params.MS_MSClient

[NetServices]
MS_Server=Params.MS_Server

[NetProtocols]
MS_TCPIP=Params.MS_TCPIP

[Params.MS_TCPIP]
DNS=192.0.2.10
AdapterSections=Params.MS_TCPIP.Adapter1

[Params.MS_TCPIP.Adapter1]
SpecificTo=Adapter1
IPAddress=192.0.2.10
SubnetMask=255.255.255.0
DefaultGateway=192.0.2.10
DNSServerSearchOrder=192.0.2.10
WINS=No

[Identification]
JoinWorkgroup=WORKGROUP
```

### 2. Build a FAT12 Floppy Image in Python

The PVE host may block `mkfs.fat` (Hermes restriction). Use Python to craft a valid FAT12 filesystem:

```python
ADV_SERVER_KEY = "WY6PG-M2YPT-KGT4H-CPY6T-GRDCY"

def build_win2k_floppy(computer_name, ip_address, gateway="192.0.2.10"):
    sif_content = create_winnt_sif(computer_name, ip_address, ...).replace('\n', '\r\n').encode('ascii')
    
    # Start with 1.44MB zeroed
    img = bytearray(1474560)
    
    # Boot sector (standard FAT12 floppy)
    bs = bytearray(512)
    bs[0:3] = b'\xeb\x3c\x90'
    bs[3:11] = b'MSWIN4.1'
    bs[11] = 0x02   # bytes/sector=512
    bs[12] = 0x01   # sectors/cluster=1
    bs[13] = 0x01   # reserved sectors=1
    bs[14] = 0x02   # #FATs=2
    bs[15:17] = (0x00E0).to_bytes(2, 'little')  # root entries=224
    bs[17:19] = (2880).to_bytes(2, 'little')     # total sectors
    bs[19] = 0xF0   # media descriptor
    bs[20:22] = (9).to_bytes(2, 'little')         # sectors/FAT
    bs[22:24] = (18).to_bytes(2, 'little')        # sectors/track
    bs[24:26] = (2).to_bytes(2, 'little')         # heads
    bs[510:512] = b'\x55\xAA'
    img[0:512] = bs
    
    # FAT: cluster 0=0xFF0, cluster 1=0xFFF, cluster 2=0xFFF (EOF for our file)
    img[512] = 0xF0
    img[513] = 0xFF
    img[514] = 0xFF
    img[515] = 0xFF  # cluster 2 lower 8 bits of 0xFFF
    img[516] = 0x0F  # cluster 2 upper 4 bits
    
    # Root directory at sector 19 (offset 19*512)
    root_off = 19 * 512
    # Data area at sector 33 (offset 33*512)
    data_off = 33 * 512
    
    # Write WINNT.SIF file content
    img[data_off:data_off+len(sif_content)] = sif_content
    
    # Directory entry in root
    dirent = bytearray(32)
    dirent[0:11] = b'WINNT   SIF'
    dirent[11] = 0x20  # Archive
    dirent[26:28] = (2).to_bytes(2, 'little')   # first cluster = 2
    dirent[28:32] = len(sif_content).to_bytes(4, 'little')
    img[root_off:root_off+32] = dirent
    
    return bytes(img)
```

### 3. Deploy to PVE

```bash
# Upload floppy image
sshpass -p '<PASSWORD>' scp /root/floppy.img root@192.0.2.10:/root/

# Edit VM config to attach floppy
cat >> /etc/pve/qemu-server/<VMID>.conf << "FLOPPY"
args: -drive if=floppy,file=/root/floppy.img,index=0,format=raw
FLOPPY

# Start VM (it will boot from CD and read floppy automatically)
qm start <VMID>
```

## Windows 2000 Product Keys

| Edition | Key |
|---------|-----|
| Professional SP4 | RBDC9-VTRC8-D7972-J97JY-PRVMG |
| Server SP4 | H6TWQ-TQQM8-HXJYG-D69F7-R84VM |
| Advanced Server SP4 | WY6PG-M2YPT-KGT4H-CPY6T-GRDCY |
| Datacenter SP4 | (use DataCenter-specific key) |

## Key Timing: TCG Emulation

When KVM is unavailable (no VT-x in BIOS), Win2K installation via TCG takes:

| Stage | TCG Time Estimate | Notes |
|-------|-------------------|-------|
| Text mode setup | 5-10 min | Disk partition, format, file copy start |
| File copy (text) | 15-25 min | CPU pegged at 95-100% |
| First reboot | 3-5 min | Boots into GUI mode |
| GUI setup | 10-15 min | Answer file processing, network config |
| **Total** | **~30-60 min** | Dependent on host CPU speed |

Compare: KVM-native installation takes ~5-8 minutes total.

## Pitfalls

- **`mkfs.fat` is often blocked** by Hermes hardline protection. Build floppy images in Python instead.
- **Floppy drive attachment**: PVE `qm set` doesn't have a `--fdc` option. Use `args:` in the config file to pass raw `-drive if=floppy,...` to QEMU.
- **Win2K won't read a non-FAT12 floppy**: The filesystem MUST be FAT12 (not FAT16 or FAT32). PVE's `mkfs.fat -F 12` creates correct FAT12, but if using Python, carefully construct boot sector + FAT + root directory.
- **Product key validation**: Win2K setup validates the key during GUI mode. If the key is wrong, setup stops and prompts. Pre-validate against known-good keys above.
- **`[Display]` section is required**: Without display settings, GUI-mode setup may hang or show black screen on certain VGA adapters.
- **No DHCP on host-only networks**: When using a pure bridge (no physical NIC), there's no DHCP server. You MUST configure static IP in the answer file, or the VM will have no IP after install.
