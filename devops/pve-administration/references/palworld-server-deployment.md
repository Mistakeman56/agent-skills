# Palworld Dedicated Server — PVE Deployment Reference

## Server Requirements (Pocketpair Official)

| Resource | Minimum | Recommended (2 players) | Recommended (16+ players) |
|----------|---------|------------------------|--------------------------|
| CPU | 4 cores | 4 cores | 8+ cores |
| RAM | 16GB | 16-20GB | 32GB+ |
| Disk | 25GB | 50GB | 100GB+ |
| Network | 10Mbps | 20Mbps | 50Mbps+ |

**Critical:** Palworld server is MUCH heavier than Minecraft. A Forge MC server with 200 mods uses ~6-7GB RAM; Palworld dedicated server alone needs 12-16GB minimum.

## User's Current Setup (2026-07)

| Container | RAM | CPU | Current Use |
|-----------|-----|-----|-------------|
| CT100 (ubuntu24) | 10GB | 6 cores | MC Forge 1.20.1 (GTO 0.5.6-alpha), uses ~6.6GB |
| CT <ID> (hermes-agent) | 8GB | 6 cores | Hermes Gateway + 11 MCP servers |
| PVE Host | 16GB total | — | Shared across all CTs |

**Plan:** User will add 16GB RAM stick → 32GB total → increase CT100 to 20GB → run MC and Palworld alternately (not simultaneously).

## Installation on Ubuntu 24.04 (CT100)

### Prerequisites
```bash
# Install SteamCMD dependencies
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install -y lib32gcc-s1 steamcmd

# Or install via package manager
sudo apt install -y steamcmd
```

### Install Palworld Server
```bash
# Create dedicated user
sudo useradd -m -s /bin/bash palworld
sudo su - palworld

# Install via SteamCMD
steamcmd +force_install_dir ~/palworld-server +login anonymous +app_update 2394010 validate +quit

# Or use the official install script (if available)
curl -sSL https://github.com/pearlpalworld/pearlpalworld-install/raw/main/install.sh | bash
```

### Configuration
```bash
# Main config file
~/palworld-server/PalWorldSettings.ini

# Key settings for 2-player server:
[WorldSettings]
ServerName=assistant的帕鲁服
ServerPassword=          # Leave empty for no password
ServerAdminPassword=admin123
MaxPlayers=4             # Small server, 4 is fine
Region=                  # Leave empty for Asia
```

### Systemd Service
```bash
cat > /etc/systemd/system/palworld.service << 'EOF'
[Unit]
Description=Palworld Dedicated Server
After=network.target

[Service]
Type=simple
User=palworld
WorkingDirectory=/home/palworld/palworld-server
ExecStart=/home/palworld/palworld-server/PalServer.sh
Restart=always
RestartSec=10
Environment="LD_LIBRARY_PATH=/home/palworld/palworld-server/linux64"

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now palworld
```

## Memory Budget Planning (After 32GB Upgrade)

### Scenario A: MC Only
- CT100: 20GB allocated, MC JVM heap 7GB, ~13GB free
- CT <ID>: 8GB allocated
- Host: 4GB free for OS + buffers

### Scenario B: Palworld Only
- CT100: 20GB allocated, Palworld ~12-14GB, ~6-8GB free
- CT <ID>: 8GB allocated
- Host: 4GB free

### Scenario C: Both Running (NOT RECOMMENDED)
- MC: 6.6GB + Palworld: 12GB = 18.6GB
- CT100 only has 20GB → only 1.4GB free → OOM risk
- **User agreed: only run one at a time**

## Tailscale for Palworld

Palworld uses port 8211 (UDP) by default. For Tailscale play:

```bash
# Check if port is listening
ss -ulnp | grep 8211

# Friend connects via:
# Palworld → Connect → IP: 100.64.0.1:8211
```

**Note:** Tailscale direct connection is ideal (<50ms). DERP relay (200ms+) will cause noticeable lag in Palworld since it's more latency-sensitive than MC for base building/combat.

## Port Forwarding (If Not Using Tailscale)

```bash
# UDP 8211 for Palworld
# On iStoreOS router:
iptables -t nat -A PREROUTING -i pppoe-wan -p udp --dport 8211 -j DNAT --to-destination 192.0.2.10:8211
iptables -A FORWARD -i pppoe-wan -o br-lan -p udp --dport 8211 -j ACCEPT
```

## Palworld vs MC Resource Comparison

| Metric | MC Forge 1.20.1 (GTO) | Palworld Dedicated |
|--------|----------------------|-------------------|
| RAM (typical) | 6-7GB | 12-16GB |
| CPU (typical) | 1-2 cores | 2-4 cores |
| Disk (server files) | ~2GB | ~15GB |
| Disk (world save) | ~500MB | ~1-5GB |
| Network (per player) | ~100KB/s | ~200-500KB/s |
| Startup time | 30-60s | 60-120s |
| Port (default) | 25565 TCP | 8211 UDP |

## Pitfalls

1. **Palworld eats RAM for breakfast** — 16GB minimum, not optional. MC's 10GB container will OOM with Palworld.
2. **Save corruption** — Always shut down gracefully (`kill -SIGTERM` or in-game exit). Force kills corrupt saves.
3. **Updates break mods** — Palworld updates frequently; dedicated server must be updated to match client version.
4. **No cross-play** — Steam and Xbox/Game Pass versions are separate. Friend must have Steam version.
5. **UDP port** — Unlike MC (TCP), Palworld uses UDP. Tailscale handles this automatically, but manual firewall rules need `-p udp`.
