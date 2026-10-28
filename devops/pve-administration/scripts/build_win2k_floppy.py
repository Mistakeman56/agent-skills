#!/usr/bin/env python3
"""
build_win2k_floppy.py — Create a FAT12 floppy image with winnt.sif
for unattended Windows 2000 installation on PVE.

Usage:
    python3 build_win2k_floppy.py <name> <ip> [output_file]

Example:
    python3 build_win2k_floppy.py HACKER-W2K 192.0.2.10
    python3 build_win2k_floppy.py SERVER-W2K 192.0.2.10 server.img
"""

import sys
import os

# Build 5.00.2195.6717 = SP4
PRODUCT_KEYS = {
    "professional": "RBDC9-VTRC8-D7972-J97JY-PRVMG",
    "server": "H6TWQ-TQQM8-HXJYG-D69F7-R84VM",
    "advanced": "WY6PG-M2YPT-KGT4H-CPY6T-GRDCY",
    "datacenter": "",  # needs specific key lookup
}

def make_winnt_sif(computer_name, ip_address, gateway="192.0.2.10",
                   subnet="255.255.255.0", product_key=None):
    """Generate winnt.sif content for unattended Win2K installation."""
    
    if product_key is None:
        product_key = PRODUCT_KEYS["advanced"]
    
    lines = [
        "; Windows 2000 Unattended Installation",
        "[Unattended]",
        "UnattendMode=FullUnattended",
        "OemSkipEula=Yes",
        "OemPreinstall=Yes",
        "TargetPath=\\WINNT",
        "FileSystem=ConvertNTFS",
        "ExtendOemPartition=1",
        "WaitForReboot=No",
        "NoWaitAfterTextMode=1",
        "NoWaitAfterGuiMode=1",
        "",
        "[UserData]",
        f"ProductID={product_key}",
        'FullName="Administrator"',
        'OrgName="Lab"',
        f"ComputerName={computer_name}",
        "",
        "[GuiUnattended]",
        'AdminPassword=""',
        "TimeZone=210",
        "AutoLogon=Yes",
        "AutoLogonCount=100",
        "OEMSkipRegional=1",
        "OemSkipWelcome=1",
        "",
        "[LicenseFilePrintData]",
        "AutoMode=PerServer",
        "AutoUsers=5",
        "",
        "[Display]",
        "BitsPerPel=16",
        "XResolution=800",
        "YResolution=600",
        "VRefresh=60",
        "",
        "[Networking]",
        "InstallDefaultComponents=No",
        "",
        "[NetAdapter]",
        "Adapter1=Params.Adapter1",
        "",
        "[Params.Adapter1]",
        "InfID=*",
        "",
        "[NetClients]",
        "MS_MSClient=Params.MS_MSClient",
        "",
        "[NetServices]",
        "MS_Server=Params.MS_Server",
        "",
        "[NetProtocols]",
        "MS_TCPIP=Params.MS_TCPIP",
        "",
        "[Params.MS_TCPIP]",
        f"DNS={ip_address}",
        "UseDomainNameDevolution=No",
        "EnableLMHosts=Yes",
        "AdapterSections=Params.MS_TCPIP.Adapter1",
        "",
        "[Params.MS_TCPIP.Adapter1]",
        "SpecificTo=Adapter1",
        f"IPAddress={ip_address}",
        f"SubnetMask={subnet}",
        f"DefaultGateway={gateway}",
        f"DNSServerSearchOrder={ip_address}",
        "WINS=No",
        "",
        "[Identification]",
        "JoinWorkgroup=WORKGROUP",
        "",
    ]
    return "\r\n".join(lines)


def build_floppy_image(computer_name, ip_address, gateway="192.0.2.10",
                       subnet="255.255.255.0", product_key=None):
    """
    Build a 1.44MB FAT12 floppy image containing winnt.sif.
    
    Returns bytes object with the complete floppy image.
    """
    sif_text = make_winnt_sif(computer_name, ip_address, gateway, subnet, product_key)
    sif_data = sif_text.encode("ascii")
    
    img = bytearray(1474560)  # 1.44MB = 2880 sectors × 512 bytes
    
    # ── Boot Sector (sector 0) ──
    bs = bytearray(512)
    # Jump instruction
    bs[0:3] = b'\xeb\x3c\x90'
    # OEM Name
    bs[3:11] = b'MSWIN4.1'
    # BIOS Parameter Block
    bs[11] = 0x02    # BytesPerSector (512)
    bs[12] = 0x01    # SectorsPerCluster
    bs[13] = 0x01    # ReservedSectors (boot sector)
    bs[14] = 0x02    # NumberOfFATs
    bs[15:17] = (0x00E0).to_bytes(2, 'little')  # RootEntries (224)
    bs[17:19] = (2880).to_bytes(2, 'little')     # TotalSectors (1.44MB)
    bs[19] = 0xF0    # MediaDescriptor
    bs[20:22] = (9).to_bytes(2, 'little')         # SectorsPerFAT
    bs[22:24] = (18).to_bytes(2, 'little')        # SectorsPerTrack
    bs[24:26] = (2).to_bytes(2, 'little')          # NumberOfHeads
    bs[26:28] = (0).to_bytes(2, 'little')          # HiddenSectors
    bs[36:40] = (2880).to_bytes(4, 'little')       # TotalSectors32
    # Extended BIOS Parameter Block
    bs[42:53] = b'WIN2K-BOOT' + b'\x20'  # Volume Label (11 bytes)
    bs[54] = 0xF0   # File system type tag
    # Boot signature
    bs[510] = 0x55
    bs[511] = 0xAA
    img[0:512] = bs
    
    # ── File Allocation Table (FAT) ──
    # FAT12 layout: each entry is 12 bits
    # Cluster 0 (media descriptor): 0xFF0
    # Cluster 1 (reserved): 0xFFF
    # Cluster 2 (our file, end-of-chain): 0xFFF
    
    # Bytes 512-514: covers clusters 0-1
    #   Cluster 0 (12 bits): bits 0-11  → 0xFF0
    #   Cluster 1 (12 bits): bits 12-23 → 0xFFF
    #   Byte 512: 0xF0 (lower 8 bits of cluster 0)
    #   Byte 513: 0xFF (upper 4 bits of cluster 0 + lower 4 bits of cluster 1)
    #   Byte 514: 0xFF (upper 8 bits of cluster 1)
    img[512] = 0xF0  # F0
    img[513] = 0xFF  # FF
    img[514] = 0xFF  # FF → together: F0 FF FF = clusters 0=FF0, 1=FFF
    
    # Cluster 2 at byte 515:
    #   0xFFF = 0xFF in lower byte, 0x0F in upper nibble
    #   Byte 515: 0xFF (lower 8 bits of 0xFFF)
    #   Byte 516: 0x0F (upper 4 bits of 0xFFF) + 0x0 (start of cluster 3)
    img[515] = 0xFF
    img[516] = 0x0F
    
    # Copy FAT1 to FAT2 (second FAT starts at sector 10 = offset 5120)
    fat_end = 512 + 9 * 512  # 9 sectors × 512 bytes
    img[5120:5120+9*512] = img[512:512+9*512]
    
    # ── Root Directory (starts at sector 19) ──
    # Layout: Reserved(1) + FAT1(9) + FAT2(9) = 19 sectors
    root_off = 19 * 512
    
    # Create directory entry for WINNT.SIF
    dirent = bytearray(32)
    dirent[0:11] = b'WINNT   SIF'  # 8.3 format (padded with spaces)
    dirent[11] = 0x20   # File attributes: Archive
    # Reserved (12-13): 0
    # Create time (14-16): 0
    # Create date (16-18): 0
    # Last access date (18-20): 0
    # EA index (20-22): 0
    # Last modified time (22-24): encode current time
    import time
    now = time.localtime()
    dos_time = (now.tm_hour << 11) | (now.tm_min << 5) | (now.tm_sec // 2)
    dos_date = ((now.tm_year - 1980) << 9) | (now.tm_mon << 5) | now.tm_mday
    dirent[22:24] = dos_time.to_bytes(2, 'little')
    dirent[24:26] = dos_date.to_bytes(2, 'little')
    dirent[26:28] = (2).to_bytes(2, 'little')   # First cluster = 2
    dirent[28:32] = len(sif_data).to_bytes(4, 'little')  # File size
    
    img[root_off:root_off+32] = dirent
    
    # ── Data Area (starts at sector 33) ──
    # 19 (reserved+FATs) + 14 (root dir) = 33 sectors
    data_off = 33 * 512
    
    # Write the file content
    img[data_off:data_off+len(sif_data)] = sif_data
    
    return bytes(img)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 build_win2k_floppy.py <ComputerName> <IP> [output_file]")
        print()
        print("Example:")
        print("  python3 build_win2k_floppy.py HACKER-W2K 192.0.2.10")
        print("  python3 build_win2k_floppy.py SERVER-W2K 192.0.2.10 server.img")
        print()
        print("Optional env vars:")
        print("  W2K_GATEWAY  (default: 192.0.2.10)")
        print("  W2K_SUBNET   (default: 255.255.255.0)")
        print("  W2K_PRODUCT_KEY (default: Advanced Server SP4 key)")
        sys.exit(1)
    
    name = sys.argv[1]
    ip = sys.argv[2]
    outfile = sys.argv[3] if len(sys.argv) > 3 else f"win2k-{name.lower()}-floppy.img"
    
    gateway = os.environ.get("W2K_GATEWAY", "192.0.2.10")
    subnet = os.environ.get("W2K_SUBNET", "255.255.255.0")
    product_key = os.environ.get("W2K_PRODUCT_KEY", None)
    
    img = build_floppy_image(name, ip, gateway, subnet, product_key)
    
    with open(outfile, "wb") as f:
        f.write(img)
    
    print(f"✅ Created floppy image: {outfile}")
    print(f"   ComputerName: {name}")
    print(f"   IP: {ip}")
    print(f"   Size: {len(img)} bytes ({len(img)/1024:.1f} KB)")
