# XPenology (黑群晖) on PVE — Installation Notes

## RR Project

- GitHub: https://github.com/RROrg/rr
- Official site: https://rrorg.cn
- Latest: v26.4.0 (2025)
- PVE script: https://github.com/RROrg/rr/raw/refs/heads/main/scripts/pve.sh

## PVE Script Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| --onboot | 1 | Auto-start VM on PVE boot |
| --efi | 1 | UEFI boot (required for DSM 7.x) |
| --bltype | sata | Bootloader disk type: sata/usb/nvme |
| --storage | (auto) | Storage target (e.g., local-lvm) |
| --img | (empty) | Local image path (skip download) |

## DSM Version Compatibility

| CPU | DSM 7.1 | DSM 7.2 | DSM 7.3 |
|-----|---------|---------|---------|
| Intel 4th gen+ | ✅ | ✅ | ✅ |
| Intel 3rd gen | ✅ | ✅ (v26.4.0 fix) | ❌ |
| AMD Ryzen | ✅ | ✅ | ✅ |
| AMD 3rd gen | ✅ | ✅ (v26.4.0 fix) | ❌ |

## VM Config (created by script)

- VMID: auto-incremented (303 in our case)
- Name: RR-DSM
- CPU: host, 2 cores
- RAM: 4096 MB
- BIOS: OVMF (UEFI)
- Machine: q35
- Boot disk: ~984MB (RR bootloader, sata0)
- Data disk: 32GB (sata1, for DSM storage pool)
- Network: virtio, vmbr0
- Serial: socket (for console access)

## Nested Virtualization Check

The PVE host at 192.0.2.10 is itself a VM (CPU shows "Genuine Intel(R) 0000", no vmx flag). This means:

1. `egrep -c '(vmx|svm)' /proc/cpuinfo` returns 0
2. KVM module loads but `kvm_intel` does not
3. `qm start` fails with "KVM virtualisation configured, but not available"
4. LXC containers work fine (share host kernel)
5. QEMU VMs cannot start

**Resolution:** Enable nested virtualization on the parent hypervisor (the machine running this PVE VM).

## Physical NAS Comparison (for user reference)

| Model | Price (used) | CPU | RAM | DSM Max | Docker | Verdict |
|-------|-------------|-----|-----|---------|--------|---------|
| DS716 | ¥600 | Atom C2538 | 2GB | 7.1 | ❌ | Overpriced |
| DS916+ | ¥700-800 | Pentium N3710 | 8GB | 7.1 | Limited | Stuck on old DSM |
| DS223j | ¥1300 new | Realtek RTD1619B | 1GB | 7.2 | ❌ ARM | 70% experience |
| DS918+ | ¥1000-1200 | J3455 | 4-32GB | 7.2 | ✅ | Best value |
| DS920+ | ¥1000-1200 | J4125 | 4-32GB | 7.2 | ✅ | Best value |
| DS224+ | ¥2000 new | J4125 | 2-32GB | 7.2 | ✅ | New with warranty |
