# Minecraft Server Post-Start Verification

When user says "帮我开我的MC服务器" and the server runs in a PVE LXC container:

## Finder Pattern

The Minecraft server might not be where you expect. Use the **Java process cwd** to find it:

```bash
# 1. Find Java PID
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- ps aux | grep java | grep -v grep"

# 2. Get working directory of the Java process
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- readlink /proc/<PID>/cwd"
# This gives the exact server directory, regardless of where you thought it was

# 3. List the server directory
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- ls -la \$(readlink /proc/<PID>/cwd)"
```

## Port Verification

Minecraft uses port 25565 by default. Check via server.properties and actual listening:

```bash
# Check configured port
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- grep 'server-port' <server_dir>/server.properties"

# Check actual listening (java process)
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- ss -tlnp | grep 25565"

# External connectivity test (from LXC 202)
nc -zv 192.0.2.X 25565
```

## Log Analysis (Done! marker)

Minecraft prints "Done (Xs)!" when the server is fully ready:

```bash
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- grep 'Done' <server_dir>/logs/latest.log"
# Expected: "[date] [Server thread/INFO] [minecraft/DedicatedServer]: Done (3.820s)! For help, type \"help\""
```

## Mod Count

```bash
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- ls <server_dir>/mods/*.jar 2>/dev/null | wc -l"
```

## Version Info

Check the core mod version (e.g., gtocore for GregTech Odyssey):
```bash
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- ls <server_dir>/mods/ | grep -i gtocore"
# → gtocore-0.5.4.jar
```

## Tailscale Connectivity for Friends

If the friend connects via Tailscale, verify from the Minecraft container:
```bash
# Ping the friend's Tailscale IP
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- ping -c 3 -W 3 100.x.x.x"

# Check Tailscale connection type (direct or relay)
sshpass -p 'PVE_PASS' ssh root@PVE_HOST "pct exec <VMID> -- tailscale ping --c 3 100.x.x.x"
# "pong from ... via x.x.x.x:port in 20ms" → direct connection, excellent
# "via DERP" → relayed, not ideal for gaming
```

**Important:** For MC gaming, aim for direct Tailscale connection. Latency under 50ms is excellent; under 100ms is fine. DERP relay will be 200ms+ and wonky.

**Ping spike pattern with Tailscale:** When you first ping a new Tailscale peer, the first 2-3 ICMP pings will be very high (800ms-4s) as Tailscale negotiates the direct connection/port mapping. Once the direct path is established, latency drops to normal (20-50ms). Always wait for the `tailscale ping` command (which gives the true latency from tailscaled's perspective) rather than judging from the first few ICMP pings.

### Remote Windows SSH (via Tailscale)

When you need to SSH into a friend's Windows machine through Tailscale to help them (e.g., find misplaced Minecraft files):

1. **Prerequisite:** The remote Windows user must have OpenSSH Server installed and your public key configured (see the `windows-remote-assist` devops skill for the full flow)
2. **From any Tailscale-connected Linux machine:** `ssh USERNAME@100.x.x.x`
3. **For finding Minecraft installations,** common Windows paths to check:
   - `C:\Users\<username>\AppData\Roaming\.minecraft` (official launcher)
   - `C:\Users\<username>\AppData\Local\Programs\` (Prism/CurseForge/DMCA launchers)
   - `C:\ProgramData\Microsoft\Windows\Start Menu\Programs\` (shortcuts)
   - Search via PowerShell: `Get-ChildItem -Path C:\Users -Recurse -Filter "minecraft*" -Directory -ErrorAction SilentlyContinue | Select FullName`

## User-facing Summary

When reporting to the user, give a **compact summary table**:

```
| 项目 | 状态 |
|------|------|
| 容器 | <VMID>号（Ubuntu 24.04） |
| IP | 192.0.2.X |
| 端口 | 25565 ✅ **已开放** |
| 核心 | Forge 1.20.1 (47.4.13) |
| 启动耗时 | X.XXs |
| 内存占用 | X.XGB / YGB (Z%) |
| 模组 | N个（含gtocore-0.5.4等） |
| online-mode | true（正版验证） |

连接地址：100.x.x.x:25565（Tailscale内网）
```
