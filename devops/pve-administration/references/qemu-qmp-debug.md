# QEMU QMP Debug — Check VM Boot Progress Without Console

When deploying VMs without web UI/VNC access (e.g., user on WeChat), use QEMU's QMP (QEMU Machine Protocol) to peek into the VM display.

## Check VM Display State via Screendump

```bash
# Connect to QMP socket (local to PVE host)
echo '{"execute":"qmp_capabilities"}
{"execute":"screendump","arguments":{"filename":"/tmp/vm-screen.ppm"}}' \
  | socat - UNIX-CONNECT:/var/run/qemu-server/<VMID>.qmp

# Copy screendump off PVE for analysis
sshpass -p 'PASS' scp root@PVE_IP:/tmp/vm-screen.ppm /tmp/

# Analyze pixel colors to classify screen content
python3 -c "
with open('/tmp/vm-screen.ppm','rb') as f:
    f.readline(); f.readline(); f.readline()
    data = f.read()

from collections import Counter
# Sample every 10th pixel
sample = []
w,h = 720,400
for y in range(0,h,10):
    for x in range(0,w,10):
        idx = (y*w+x)*3
        if idx+2 < len(data):
            sample.append((data[idx],data[idx+1],data[idx+2]))

for (r,g,b),cnt in Counter(sample).most_common(5):
    if r>200 and g>200 and b>200: desc='White'
    elif r<50 and g<50 and b<50: desc='Black'
    elif r<100 and g<100 and b>150: desc='Blue'
    elif r>150 and g>80 and b<80: desc='Orange/Red'
    elif r>200 and g<100 and b<100: desc='Bright Red'
    else: desc=f'Other({r},{g},{b})'
    print(f'RGB({r:3d},{g:3d},{b:3d}) x{cnt:4d} - {desc}')
"
```

## Screen Interpretation Guide

| Dominant Color | Likely State |
|---------------|--------------|
| Blue (0,0,168) | Win2K boot splash / setup blue screen |
| Black | Powered off / BIOS POST / text-mode setup |
| White + blue bands | Win2K GUI mode setup (welcome wizard) |
| Green/teal bars | Win2K desktop (classic theme) |
| Gray + text | Text-mode Win2K setup or menu |
| Orange/red bar | Win2K Setup loading bar during file copy |

## Check if Screen Changes Over Time

```bash
# Take two screendumps 30s apart
echo '{"execute":"qmp_capabilities"}
{"execute":"screendump","arguments":{"filename":"/tmp/a.ppm"}}' \
  | socat - UNIX-CONNECT:/var/run/qemu-server/<VMID>.qmp

sleep 30

echo '{"execute":"qmp_capabilities"}
{"execute":"screendump","arguments":{"filename":"/tmp/b.ppm"}}' \
  | socat - UNIX-CONNECT:/var/run/qemu-server/<VMID>.qmp

# Compare MD5
md5sum /tmp/a.ppm /tmp/b.ppm
# Same hash = VM stuck; different hash = progress being made
```

## Check Disk I/O Activity

```bash
echo '{"execute":"qmp_capabilities"}
{"execute":"query-blockstats"}' | socat - UNIX-CONNECT:/var/run/qemu-server/<VMID>.qmp 2>/dev/null
```

Look for `rd_operations_total` and `wr_operations_total` — if they're incrementing, the VM is working. If stuck at 0, the VM is idle/waiting.

## Check CPU Usage of KVM Processes

```bash
ps aux | grep "kvm.*<VMID>" | awk '{print $1, $3, $11}'
```

High CPU (90-100%) on TCG = VM is actively emulating (good sign, means the guest is doing work).
