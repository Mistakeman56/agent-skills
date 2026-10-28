---
name: minecraft-modpack-server
description: "Host modded Minecraft servers (CurseForge, Modrinth)."
tags: [minecraft, gaming, server, neoforge, forge, modpack]
platforms: [linux, macos]
---

# Minecraft Modpack Server Setup

## When to use
- User wants to set up a modded Minecraft server from a server pack zip
- User needs help with NeoForge/Forge server configuration
- User asks about Minecraft server performance tuning or backups

## Gather User Preferences First
Before starting setup, ask the user for:
- **Server name / MOTD** — what should it say in the server list?
- **Seed** — specific seed or random?
- **Difficulty** — peaceful / easy / normal / hard?
- **Gamemode** — survival / creative / adventure?
- **Online mode** — true (Mojang auth, legit accounts) or false (LAN/cracked friendly)?
- **Player count** — how many players expected? (affects RAM & view distance tuning)
- **RAM allocation** — or let agent decide based on mod count & available RAM?
- **View distance / simulation distance** — or let agent pick based on player count & hardware?
- **PvP** — on or off?
- **Whitelist** — open server or whitelist only?
- **Backups** — want automated backups? How often?

Use sensible defaults if the user doesn't care, but always ask before generating the config.

## Steps

### 1. Download & Inspect the Pack
```bash
mkdir -p ~/minecraft-server
cd ~/minecraft-server
wget -O serverpack.zip "<URL>"
unzip -o serverpack.zip -d server
ls server/
```
Look for: `startserver.sh`, installer jar (neoforge/forge), `user_jvm_args.txt`, `mods/` folder.
Check the script to determine: mod loader type, version, and required Java version.

### 2. Install Java
- Minecraft 1.21+ → Java 21: `sudo apt install openjdk-21-jre-headless`
- Minecraft 1.18-1.20 → Java 17: `sudo apt install openjdk-17-jre-headless`
- Minecraft 1.16 and below → Java 8: `sudo apt install openjdk-8-jre-headless`
- Verify: `java -version`

### 3. Install the Mod Loader
Most server packs include an install script. Use the INSTALL_ONLY env var to install without launching:
```bash
cd ~/minecraft-server/server
ATM10_INSTALL_ONLY=true bash startserver.sh
# Or for generic Forge packs:
# java -jar forge-*-installer.jar --installServer
```
This downloads libraries, patches the server jar, etc.

### 4. Accept EULA
```bash
echo "eula=true" > ~/minecraft-server/server/eula.txt
```

### 5. Configure server.properties
Key settings for modded/LAN:
```properties
motd=\u00a7b\u00a7lServer Name \u00a7r\u00a78| \u00a7aModpack Name
server-port=25565
online-mode=true          # false for LAN without Mojang auth
enforce-secure-profile=true  # match online-mode
difficulty=hard            # most modpacks balance around hard
allow-flight=true          # REQUIRED for modded (flying mounts/items)
spawn-protection=0         # let everyone build at spawn
max-tick-time=180000       # modded needs longer tick timeout
enable-command-block=true
```

Performance settings (scale to hardware):
```properties
# 2 players, beefy machine:
view-distance=16
simulation-distance=10

# 4-6 players, moderate machine:
view-distance=10
simulation-distance=6

# 8+ players or weaker hardware:
view-distance=8
simulation-distance=4
```

### 6. Tune JVM Args (user_jvm_args.txt)
Scale RAM to player count and mod count. Rule of thumb for modded:
- 100-200 mods: 6-12GB
- 200-350+ mods: 12-24GB
- Leave at least 8GB free for the OS/other tasks

```
-Xms12G
-Xmx24G
-XX:+UseG1GC
-XX:+ParallelRefProcEnabled
-XX:MaxGCPauseMillis=200
-XX:+UnlockExperimentalVMOptions
-XX:+DisableExplicitGC
-XX:+AlwaysPreTouch
-XX:G1NewSizePercent=30
-XX:G1MaxNewSizePercent=40
-XX:G1HeapRegionSize=8M
-XX:G1ReservePercent=20
-XX:G1HeapWastePercent=5
-XX:G1MixedGCCountTarget=4
-XX:InitiatingHeapOccupancyPercent=15
-XX:G1MixedGCLiveThresholdPercent=90
-XX:G1RSetUpdatingPauseTimePercent=5
-XX:SurvivorRatio=32
-XX:+PerfDisableSharedMem
-XX:MaxTenuringThreshold=1
```

### 7. Open Firewall
```bash
sudo ufw allow 25565/tcp comment "Minecraft Server"
```
Check with: `sudo ufw status | grep 25565`

### 8. Create Launch Script
```bash
cat > ~/start-minecraft.sh << 'EOF'
#!/bin/bash
cd ~/minecraft-server/server
java @user_jvm_args.txt @libraries/net/neoforged/neoforge/<VERSION>/unix_args.txt nogui
EOF
chmod +x ~/start-minecraft.sh
```
Note: For Forge (not NeoForge), the args file path differs. Check `startserver.sh` for the exact path.

### 9. Set Up Automated Backups
Create backup script:
```bash
cat > ~/minecraft-server/backup.sh << 'SCRIPT'
#!/bin/bash
SERVER_DIR="$HOME/minecraft-server/server"
BACKUP_DIR="$HOME/minecraft-server/backups"
WORLD_DIR="$SERVER_DIR/world"
MAX_BACKUPS=24
mkdir -p "$BACKUP_DIR"
[ ! -d "$WORLD_DIR" ] && echo "[BACKUP] No world folder" && exit 0
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="$BACKUP_DIR/world_${TIMESTAMP}.tar.gz"
echo "[BACKUP] Starting at $(date)"
tar -czf "$BACKUP_FILE" -C "$SERVER_DIR" world
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[BACKUP] Saved: $BACKUP_FILE ($SIZE)"
BACKUP_COUNT=$(ls -1t "$BACKUP_DIR"/world_*.tar.gz 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt "$MAX_BACKUPS" ]; then
    REMOVE=$((BACKUP_COUNT - MAX_BACKUPS))
    ls -1t "$BACKUP_DIR"/world_*.tar.gz | tail -n "$REMOVE" | xargs rm -f
    echo "[BACKUP] Pruned $REMOVE old backup(s)"
fi
echo "[BACKUP] Done at $(date)"
SCRIPT
chmod +x ~/minecraft-server/backup.sh
```

Add hourly cron:
```bash
(crontab -l 2>/dev/null | grep -v "minecraft/backup.sh"; echo "0 * * * * $HOME/minecraft-server/backup.sh >> $HOME/minecraft-server/backups/backup.log 2>&1") | crontab -
```

## Diagnosing an Existing Minecraft Server

When the user says "帮我开我的MC服务器" and it's an **existing server** in a stopped PVE container (not a new setup):

### 1. Find the Container

```bash
# On PVE host
sshpass -p 'PASS' ssh root@PVE_HOST "pct list"
# Look for stopped containers matching the user's description
```

### 2. Start and Verify

```bash
# Start it
sshpass -p 'PASS' ssh root@PVE_HOST "pct start <VMID>"

# Wait 3-5 seconds, then check status
sshpass -p 'PASS' ssh root@PVE_HOST "pct status <VMID>"

# Get container IP
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- ip addr show eth0 | grep 'inet ' | head -1"
```

### 3a. Locate the Server (When Not Running)

If no Java process is running, scan the filesystem for MC server artifacts:

```bash
# Search common locations for server.properties (definitive MC marker)
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- find /root /home /opt /srv /data -maxdepth 5 -type f \( -name 'server.properties' -o -name 'eula.txt' -o -name 'ops.json' -o -name 'run.sh' -o -name 'run.bat' \) 2>/dev/null"

# Quick scan of top-level directories
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- ls -la /root/ /home/ /opt/ /srv/ /data/ 2>/dev/null"
```

Common locations: `/root/Desktop/mc_server/`, `/opt/minecraft/`, `/home/*/server/`, `/data/minecraft/`.

**⚠️ Chinese/Unicode paths**: PVE may show URL-encoded names (e.g., `GTO#U65b0#U670d...`). Use wildcard globs: `ls /root/Desktop/mc_server/GTO*/server/` instead of the full path.

### 3b. Identify the Server Software (Running or Not)

```bash
# If Java is running, find server dir from PID:
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- ps aux | grep java | grep -v grep"
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- readlink /proc/<PID>/cwd"

# If not running, use the path found in step 3a.
# Identify mod loader from run.sh or startup scripts:
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- cat <server_dir>/run.sh"
# Forge: references libraries/net/minecraftforge/forge/<version>/
# NeoForge: references libraries/net/neoforged/neoforge/<version>/

# Count mods
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- ls <server_dir>/mods/ | wc -l"

# Identify core modpack from mod list (e.g., gtocore for GregTech Odyssey)
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- ls <server_dir>/mods/ | grep -iE 'gtocore|atm|create|mechanical'"
```

### 4. Audit Container Resources

Before starting, verify the container has enough resources for the modpack:

```bash
# Container allocation (from PVE host)
sshpass -p 'PASS' ssh root@PVE_HOST "pct config <VMID> | grep -E 'cores|memory|swap|rootfs'"

# Actual usage inside container
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- bash -c 'java -version 2>&1; echo ---; free -h; echo ---; nproc; echo ---; df -h /'"

# JVM args (check if heap matches container RAM — Xmx should be ~75-80% of container memory)
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- cat <server_dir>/user_jvm_args.txt"
```

**⚠️ PITFALL: JVM heap too large crashes the PVE host, not just the container.** If `-Xmx8G` is set in a 10GB container, Java heap + metaspace + native memory ≈ 10GB+. The container consumes all its RAM, causing the PVE host to enter severe memory pressure (pvestatd timeout, pveproxy crash, firewall stalls, SSH failures). The user will report "PVE挂了" — check PVE host journal, not just MC logs. See `references/container-causes-host-crash.md` in the pve-administration skill for the full debugging workflow. **Rule: Xmx ≤ 75% of container RAM, and total container allocations ≤ 80% of host physical RAM.**

- **Rule of thumb**: Xmx ≤ 80% of container RAM. A container with 10GB RAM should set `-Xmx8G`. If Xmx is larger than container RAM, Java will OOM-kill.

### 5. Verify Network Connectivity

```bash
# Check port is open
nc -zv <CONTAINER_IP> 25565

# Check server.properties for key settings
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- grep -E 'server-port|online-mode|motd|max-players|difficulty|enable-status' <server_dir>/server.properties"
```

### 6. Check Server is Fully Started

Look in `logs/latest.log` for: `Done (Xs)! For help, type "help"`

```bash
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- grep 'Done' <server_dir>/logs/latest.log"
```

### 7. Tailscale Connectivity (if user's friends connect remotely)

```bash
# Check Tailscale is running in the container
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- tailscale status"

# Check if the friend's node is reachable (direct connection)
# ⚠️ ALWAYS use "tailscale ping", NOT regular "ping"!
# Regular ICMP ping may route differently (290ms+) even when WireGuard tunnel is direct (20ms).
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- tailscale ping -c 3 <friend_tailscale_ip>"

# Expected output for direct connection:
#   pong from mydevice (100.x.x.x) via <public_ip>:<port> in 20ms  ← good!
# If DERP relay: "via DERP (hkg) in 290ms" → check firewall/Tailscale config

# The friend connects using: <container_tailscale_ip>:25565
# Key metric: look for "direct" (not DERP) and sub-50ms for gaming

# ⚠️ In LXC containers with proxy env vars, unset before running tailscale commands:
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY tailscale ping -c 3 <friend_tailscale_ip>"
```

### Telling the User the Connection Info

After verification, present clearly:

```
✅ 服务器已启动
- 内网地址: <internal_ip>:25565
- Tailscale: <tailscale_ip>:25565（朋友用这个连）
- 版本: Forge/NeoForge X.XX (MC 1.xx)
- 延迟: 朋友~<X>ms（直连/DERP）
- online-mode: true/false
```

### Transferring Files from One PVE Container to Another (Lazy Method)

When you need to copy a binary/tool from a container that has it to a container that doesn't (e.g., Tailscale), and `pct push` is restricted:

```bash
# Step 1: Stream the file through PVE host via pct exec -> dd
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <SOURCE_VMID> -- dd if=/path/to/binary bs=1M" | dd of=/tmp/binary bs=1M

# Step 2: Copy to the target container from PVE host's /tmp
sshpass -p 'PASS' ssh root@PVE_HOST "pct push <TARGET_VMID> /tmp/binary /path/to/destination"

# If pct push is restricted, stream through PVE host again
sshpass -p 'PASS' ssh root@PVE_HOST "cat /tmp/binary" | sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <TARGET_VMID> -- dd of=/path/to/destination bs=1M"
```

⚠️ Tailscale requires `/dev/net/tun` in the LXC container. If missing:
- PVE can add it via `pct set <VMID> --dev <config>` 
- Or add `lxc.cgroup2.devices.allow: c 10:200 rwm` and `lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file` to the container config

## Graceful Shutdown (When User Isn't Playing)

When the user says "最近不玩了，帮我关掉" or similar — don't just kill the process. Do a clean shutdown with world backup.

### Step 1: Send `stop` Command via Screen

```bash
# Find the screen session name
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- screen -ls"
# Typically shows: 803.mc (Detached)

# Send the stop command (graceful — saves world, kicks players)
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- screen -S mc -X stuff 'stop\n'"
# ⚠️ The \n is literal — screen -S <name> -X stuff sends keystrokes, including newline
```

Wait 15-30 seconds for a 2GB world. Check if Java exited:
```bash
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- ps aux | grep java | grep -v grep"
# Empty output = server stopped. screen -ls should show "No Sockets found"
```

### Step 2: Disable Auto-Restart Service

If the server runs via systemd (check with `systemctl list-units --type=service | grep mc`):
```bash
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- systemctl stop mc.service"
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- systemctl disable mc.service"
# This prevents auto-restart on boot or crash
```

**⚠️ Record the service name!** You'll need it to re-enable later when the user wants to play again.

### Step 3: Backup the World

```bash
# Create timestamped backup
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- bash -c '
  BACKUP_DIR=/root/Desktop/mc_server/backups/world_$(date +%Y%m%d_%H%M%S)
  mkdir -p $BACKUP_DIR
  cp -a /root/Desktop/mc_server/GTO*/server/world $BACKUP_DIR/
  du -sh $BACKUP_DIR
'"
```

**⚠️ Chinese paths**: Use `GTO*` wildcard glob, not the full Unicode path.

### Step 4: Optionally Stop the Container

If user won't play for a while:
```bash
sshpass -p 'PASS' ssh root@PVE_HOST "pct stop <VMID>"
```

This frees the container's memory for other services.

### Re-enabling Later

When user wants to play again:
```bash
# Re-enable the service
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- systemctl enable mc.service"
sshpass -p 'PASS' ssh root@PVE_HOST "pct exec <VMID> -- systemctl start mc.service"
# Or if container was stopped:
sshpass -p 'PASS' ssh root@PVE_HOST "pct start <VMID>"
```

## Diagnosing Memory Leaks (AllTheLeaks Mod)

Many modpacks include the **AllTheLeaks** mod which reports memory stats every 10 minutes. When the user reports "MC服务器内存泄漏" or the server keeps crashing, check the latest log for AllTheLeaks output.

### Reading AllTheLeaks Output

```
[Server thread/INFO] [AllTheLeaks/]: Listing memory leaks so far...
[Server thread/INFO] [AllTheLeaks/]: B: 1107MB / C: 2760MB / Diff: +1653MB
[Server thread/INFO] [AllTheLeaks/]: Memory Leaks detected: (/atl force_refresh to update)
[Server thread/INFO] [AllTheLeaks/]: | Player:
[Server thread/INFO] [AllTheLeaks/]: |- ServerPlayer (minecraft): 1
```

- **B (Baseline)**: Memory at server start — this is the "clean" heap size after loading
- **C (Current)**: Current heap usage
- **Diff**: Growth above baseline — this is the leak
- **Player count**: Leaks often correlate with player connections/disconnections

### Interpreting Leak Rate

Track multiple AllTheLeaks entries over time to calculate leak rate:

```bash
# Extract all AllTheLeaks memory lines from compressed logs
zcat logs/2026-*.log.gz | grep "AllTheLeaks.*B:.*C:.*Diff"
```

Example timeline:
```
23:07 → C: 2726MB / Diff: +1619MB
23:17 → C: 2739MB / Diff: +1632MB  (+13MB in 10min)
23:37 → C: 2757MB / Diff: +1650MB  (+18MB in 10min)
01:37 → C: 2838MB / Diff: +1731MB  (+81MB in 120min)
```

**Leak rate thresholds:**
- < 5MB/10min: Normal fluctuation, not a real leak
- 5-20MB/10min: Moderate leak — monitor, may need mod update
- \> 20MB/10min: Serious leak — server will eventually OOM

### Common Leak Sources

- **Player logout not cleaning up**: Most common in modded. Each disconnect leaks entity data, chunk references, or capability data. AllTheLeaks shows "Server Player Logout" events alongside growth.
- **Chunk loading without unloading**: Mods that auto-load chunks (chunk loaders,anchors) without proper cleanup
- **Tile entity leaks**: Machines that create temporary tile entities without removing them
- **Entity duplication**: Mob farms or spawners that create entities faster than they're cleaned up

### What To Do

1. **Short-term**: Restart the server periodically (every 12-24h) to reset leak accumulation
2. **Medium-term**: Check mod versions — leaking mods often fix leaks in updates. Focus on the biggest mods (GregTech, Create, AE2, Ars Nouveau)
3. **Long-term**: Use `/atl force_refresh` in-game to reset the baseline, then monitor which player actions trigger the biggest jumps

## Diagnosing Startup Failures (Stuck in Mod Loading)

When the server log ends during mod loading (no "Done!" marker), the server never fully started. Common causes:

### Log Shows Only Warnings, Then Ends

```
[modloading-worker-0/WARN] [GregTechCEu/]: Material ... does not have required property ...
```
If the log stops here (typically 20-60 seconds of startup), possible causes:

1. **Out of memory during loading**: Mod loading is memory-intensive. Check:
   ```bash
   pct exec <VMID> -- free -h
   # If available < 500MB when server should be loading → OOM
   pct exec <VMID> -- dmesg | grep -i "oom\|killed\|java"
   ```

2. **Insufficient container RAM for JVM heap**: If `-Xmx8G` but container only has 10GB, heap + metaspace + native memory ≈ 10GB+ → container OOM. **Fix**: Either increase container RAM or reduce `-Xmx`.

3. **Corrupted mod jar**: A corrupted download in `mods/` can cause silent hang during class loading. Check if any jar files are 0 bytes:
   ```bash
   find <server_dir>/mods/ -name "*.jar" -size 0
   ```

4. **Mod version conflict**: Two mods expecting different versions of a library. Check `debug.log` (not just `latest.log`) for `ClassNotFoundException` or `NoSuchMethodError`.

### Memory Sizing Rule of Thumb

| Mod Count | Recommended -Xmx | Container RAM |
|-----------|------------------|---------------|
| 50-100 | 4-6GB | 8GB |
| 100-200 | 6-10GB | 12-14GB |
| 200-350+ | 10-16GB | 16-24GB |

**Critical**: Leave at least 2-3GB for OS + native memory beyond `-Xmx`. Java needs heap + metaspace (~256MB) + thread stacks + native allocations. In a container, this "OS overhead" is the container's non-heap usage — if Xmx is too close to container RAM, the container OOMs and drags down the PVE host. See the "Container crashes the PVE host" pitfall above.

### G1HeapRegionSize Tuning

When changing `-Xmx`, also adjust `G1HeapRegionSize` — it must be proportioned to heap size:

| Heap Size | G1HeapRegionSize |
|-----------|-----------------|
| 2-4GB | 2m |
| 4-8GB | 4m |
| 8-16GB | 8m |
| 16GB+ | 16m |

**Why**: G1GC divides the heap into regions. If the region size is too large for the heap, G1 has too few regions to manage efficiently, leading to longer GC pauses and wasted memory. The aikars flags default to 8m which only works well for 8GB+ heaps.

## Understanding MC Startup Time

The log line `Done (Xs)! For help, type "help"` is **misleading for modded servers**. It only measures from `DedicatedServer` initialization to "Done" — it does NOT include mod loading time (which can be 30-60+ seconds for large modpacks).

**To calculate actual startup time**, measure from service start to the `Done` marker:
```bash
# Service start time (from systemd)
systemctl status mc.service | grep "Active:"

# Done time (from log)
grep 'Done' logs/latest.log
# Example: [01Jul2026 07:51:21.718] ... Done (3.492s)!
# Actual total = 07:51:21 - service_start_time ≈ 35 seconds (not 3.5s!)
```

The `Dedicated server took 34.822 seconds to load` line (printed by ModernFix) gives the actual mod loading time. Total startup ≈ mod loading + `Done (Xs)`.

**Why this matters**: If you report "3.5 seconds startup" to the user, they'll correctly call you out — the real time for a 100+ mod GTO pack is typically 27-40 seconds.

## mc.service + Screen Pattern

Many PVE MC servers use this architecture:
```
systemd (mc.service) → /usr/local/bin/mc-monitor.sh → screen -dmS mc ./run.sh
```

**Key behaviors:**
- `systemctl start mc.service` starts the monitor script which launches screen + Java
- `systemctl status mc.service` shows the service as "active" but the actual Java process is in the screen session
- To interact with the server console: `screen -S mc -X stuff 'stop\n'`
- `systemctl stop mc.service` does NOT stop the MC server — it only stops the monitor wrapper. The screen/Java process keeps running.
- To actually stop the server: send `stop` via screen, then disable the service

**Verification after start:**
```bash
# Check screen session exists
screen -ls  # should show "mc" session

# Check Java process
ps aux | grep java | grep -v grep

# Check server is ready
grep 'Done' logs/latest.log
```

## Diagnosing Client Version Mismatch

When a player gets `Internal Exception: java.lang.IndexOutOfBoundsException` on connect, the most common cause is **client and server running different modpack versions**.

### Quick Check
```bash
# Check server modpack version from mod jar filename
pct exec <VMID> -- ls <server_dir>/mods/ | grep -iE 'gtocore|atm|create'
# Example output: gtocore-forge-1.20.1-0.5.6-alpha.jar → server is v0.5.6-alpha

# Compare with client version (shown in Minecraft title bar)
# Client: "GregTech Odyssey | 0.5.4-2f9f4a" → client is v0.5.4
# Server: v0.5.6-alpha → MISMATCH!
```

### The Error Pattern
```
Internal Exception: java.lang.IndexOutOfBoundsException: index: 8, length: 52 (expected: range(0, 15))
```
This specific error (index out of range with mismatched expected/actual lengths) is characteristic of modpack version mismatches — the client tries to parse packet data using a different schema than the server sends.

### Fix
The client must match the server version exactly. Direct the user to download the matching client pack from the modpack's CurseForge/Modrinth page.

## Pitfalls
- ALWAYS set `allow-flight=true` for modded — mods with jetpacks/flight will kick players otherwise
- `max-tick-time=180000` or higher — modded servers often have long ticks during worldgen
- First startup is SLOW (several minutes for big packs) — don't panic
- "Can't keep up!" warnings on first launch are normal, settles after initial chunk gen
- If online-mode=false, set enforce-secure-profile=false too or clients get rejected
- The pack's startserver.sh often has an auto-restart loop — make a clean launch script without it
- Delete the world/ folder to regenerate with a new seed
- Some packs have env vars to control behavior (e.g., ATM10 uses ATM10_JAVA, ATM10_RESTART, ATM10_INSTALL_ONLY)
- **Chinese paths in containers**: PVE passes Unicode characters through /proc/PID/cwd URL-encoded. Use wildcard globs (`GTO*`) to navigate. When running `grep` or `cat` in the server dir, use `bash -c 'cd path/GTO*/server && command'` pattern.
- **Checking modpack version for GT Odyssey**: Look for `gtocore-*.jar` in `mods/` — the version is in the filename (e.g., `gtocore-0.5.4.jar`). Check GitHub releases at `https://github.com/GregTech-Odyssey/GregTech-Odyssey/releases` for newer versions.
- **Windows friend needs SSH access? If they have Tailscale but no SSH**:
  - Tailscale alone doesn't give SSH into a Windows machine — they need OpenSSH Server installed
  - Install command (Admin PowerShell): `Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0; Start-Service sshd; Set-Service -Name sshd -StartupType 'Automatic'`
  - **Firewall**: An admin may need to add a rule: `New-NetFirewallRule -DisplayName 'OpenSSH Server' -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow`
  - **First install may need a reboot**: If output says `RestartNeeded : True`, the user MUST reboot before `sshd` service exists. On retry it will say `False`.
  - **Auth problem with Microsoft accounts**: Users with Microsoft-linked accounts *cannot* change their password via `net user`. They must either:
    - Install the SSH public key of the agent (the *agent's* pubkey goes into the user's `C:\ProgramData\ssh\administrators_authorized_keys`)
    - Or enable password auth in `sshd_config` and set a local password (only works for local accounts, not Microsoft accounts)
  - **Keygen for a friend on Windows**: They run `ssh-keygen -t ed25519` (no arguments, just Enter), then `type $env:USERPROFILE\.ssh\id_ed25519.pub` to get their public key.
  - **To give the agent access (admin user)**: The friend runs these commands in Admin PowerShell:
    ```powershell
    New-Item -Path "C:\ProgramData\ssh\administrators_authorized_keys" -ItemType File -Force
    Add-Content -Path "C:\ProgramData\ssh\administrators_authorized_keys" -Value "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIA9a8C9TA3lON9HrewFHRqBDIWhSKiXfaOaPCDh9JP7G hermes-agent-lxc202"
    icacls "C:\ProgramData\ssh\administrators_authorized_keys" /inheritance:r /grant "SYSTEM:(RX)" /grant "BUILTIN\Administrators:(RX)"
    Restart-Service sshd
    ```
    ⚠️ The `icacls` line is **critical** — without correct ACLs, key auth silently fails with the same `Permission denied` error.
  - **For non-admin users**: The authorized_keys goes in `~\\.ssh\authorized_keys` instead of `C:\ProgramData\ssh\administrators_authorized_keys`
- **Tailscale in LXC containers on PVE**:
  - LXC containers need `/dev/net/tun` for Tailscale to work. Check with `ls -la /dev/net/tun`
  - If missing, there are TWO ways to add it:
    - **Method 1 (if container is stopped):** `pct set <VMID> -dev0 /dev/net/tun,pass`
    - **Method 2 (if container is running or locked):** Edit the config file directly: `echo 'lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file' >> /etc/pve/lxc/<VMID>.conf` — then restart the container
  - ⚠️ **Common mistake:** `pct set 202 -dev0 /dev/net/tun,pass` fails with `invalid format - duplicate key in comma-separated list property: path` if the container is locked (e.g., `CT is locked (mounted)`). This happens because `pct set` can't modify a running/locked container. Use **Method 2** (edit config file directly) instead.
  - After adding TUN, kill old tailscaled processes and restart fresh

## Verification
- `pgrep -fa neoforge` or `pgrep -fa minecraft` to check if running
- Check logs: `tail -f ~/minecraft-server/server/logs/latest.log`
- Look for "Done (Xs)!" in the log = server is ready
- Test connection: player adds server IP in Multiplayer
