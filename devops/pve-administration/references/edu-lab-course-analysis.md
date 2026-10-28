# Educational Lab VM Deployment — Course PDF Analysis

## Pattern: Deploy Lab VMs from Course PDF

When a user asks you to deploy VMs for a university course, they usually have a PDF syllabus/lab manual. **Analyze the PDF first** — it tells you exactly what OS, network topology, and tools are needed.

### Step 1: Extract PDF Text

Use the `ocr-and-documents` skill. For simple text PDFs, fastest is:

```bash
pip install pypdf2 -q
python3 -c "
import PyPDF2
with open('/path/to/course.pdf', 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    print(f'Total pages: {len(reader.pages)}')
    for i, page in enumerate(reader.pages):
        print(f'\\n--- PAGE {i+1} ---')
        print(page.extract_text())
"
```

### Step 2: Identify Lab Topology

Look for:
1. **Network type** — Host-only (VMNet1), NAT (VMNet8), Bridged
2. **Subnet** — e.g. `192.0.2.10/24` (typical for VMware VMNet1)
3. **VM roles** — Hacker/Target/Server/Gateway
4. **IP assignments** — static IPs in the lab manual

### Step 3: Determine OS Requirements

Read the software/tools section of the PDF. Key questions:
- **What tool is used?** (e.g., Cain & Abel, Wireshark, Metasploit)
- **What OS does it require?** Check tool name: "Cain for Windows2k" = Win2000; "for Windows xp" = XP
- **Is a specific edition needed?** Professional is usually sufficient for client tools; Server edition only needed if the lab says "Server" or "AD/domain"
- **Can the OS be downgraded?** Many Win2K Advanced Server labs work fine on Win2K Professional

### Step 4: Map to PVE Equivalents

| VMware Concept | PVE Equivalent |
|---------------|-----------------|
| VMNet1 (host-only) | `vmbr1` bridge with no physical interface |
| VMNet8 (NAT) | `vmbr1` + masquerade NAT |
| Folder/share | PVE storage (`local-lvm`) |
| VMware Tools | Guest agent (if supported by old OS) |

### Step 5: Check Virtual Hardware Compatibility

Legacy Windows (Win2K/XP/2003):
- ⚠️ Force `--machine pc-i440fx-9.0` (NOT q35)
- ⚠️ `--cpu qemu64` (NOT host — KVM unavailable in LXC)
- ⚠️ `--kvm 0` if TCG emulation (very slow, warn user)
- ⚠️ Use IDE or LSI SCSI controller (NOT VirtIO)
- ⚠️ Use e1000 NIC (NOT VirtIO)

## Case Study: Network Security ARP Attack Lab (Week 11, Ch 4)

### PDF Source
- Course: 网络安全 (Network Security)
- Chapter: 4.1 ARP攻击
- Week: 第11周

### Discovered Topology
```
[VMNet1 / Gateway] 192.0.2.10  (host machine / Windows 10 VMNet1)
       |
  [Hacker VM]      192.0.2.10  (Win2K Pro + Cain & Abel)
       |
  [Target VM]      192.0.2.10  (Win2K Server/Pro, victim)
```

### Discovered OS Requirements
- **Hacker machine**: Windows 2000 (Pro is fine) with Cain & Abel
- **Target machine**: Windows 2000 (Pro or Server — both work for ARP cache demonstration)
- **Edition verdict**: **Win2000 Professional SP4 is sufficient** — no need for Advanced Server
- **Tool**: Cain & Abel (Win2K-compatible)

### PVE Deployment Plan (for this specific lab)
1. Create 2 VMs on PVE (both Win2K Pro SP4)
2. Add a second bridge `vmbr1` (host-only, no physical NIC) — or use existing `vmbr0` in isolated mode
3. Set IPs manually in guest OS:
   - Hacker: 192.0.2.10/24
   - Target: 192.0.2.10/24
   - (No gateway needed — host-only, no DHCP)
4. Target VM: no extra setup needed
5. Hacker VM: upload Cain & Abel via FTP → install → run ARP poisoning

### Network Notes
- VMware VMNet1 = host-only /24 subnet. In PVE, replicate with bridge-only (no physical port) + manual IP assignment.
- The lab uses a single flat L2 segment — all three devices (Gateway, Hacker, Target) are on the same subnet. ARP poisoning works by manipulating L2→L3 mappings.
- No DHCP or routing needed — just static IPs.
