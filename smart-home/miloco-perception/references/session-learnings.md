# Session-Specific Learnings — 2026-07-13

## Key Pitfalls Discovered

### 1. `pct exec` PATH Not Preserved

Even with `export PATH=/usr/local/bin:$PATH` inside the bash -c command, `miloco-cli` may not be found. `pct exec` does not always source the environment reliably.

**Always use the full path** instead of relying on PATH:

```bash
# ❌ Unreliable — PATH not always preserved:
pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; miloco-cli perceive logs'

# ✅ Reliable — use absolute path:
pct exec 310 -- /usr/local/bin/miloco-cli perceive logs
```

### 2. `--since` Flag Format

The `--since` flag accepts **relative time offsets**, NOT absolute dates:

```bash
# ❌ Wrong — absolute date format rejected:
miloco-cli perceive logs --since 2026-07-13
# Error: "Invalid 'since' format... Expected e.g. '30m', '1h', '2h30m', '7d'"

# ✅ Correct — relative time:
miloco-cli perceive logs --since 2h     # last 2 hours
miloco-cli perceive logs --since 30m    # last 30 minutes
miloco-cli perceive logs --since 7d     # last 7 days
```

### 3. Backend Health Check (bypasses systemd)

The `miloco-backend` service may not be registered as a systemd unit, but the backend itself runs fine. Don't rely on `systemctl status miloco-backend` — it will show "not found" even when healthy.

**Check backend health directly**:

```bash
pct exec 310 -- curl -s http://127.0.0.1:1810/health
# Returns: {"status":"ok"}
```

### 4. Available `perceive` Subcommands

Only these exist (no `status` or `events`):
- `clear` — clear perception cache/buffers
- `devices` — list perception-capable devices (cameras)
- `logs` — query perception event history
- `query` — active multimodal perception query

### 5. SSH Command Format for Device Control

Full SSH command pattern for controlling devices on CT <ID>:

```bash
sshpass -p "<PASSWORD>" ssh -o StrictHostKeyChecking=no root@192.0.2.10 \
  "pct exec 310 -- /usr/local/bin/miloco-cli device control <DID> <property> <value>"
```

### 6. Known Device DIDs

| Device | DID |
|--------|-----|
| 客厅开关 | 2020879703 |
| 三楼楼梯灯 | 2042692296 |
| 书房筒灯开关 | 888910528 |
| 三楼灯 | 2042769877 |
| 一楼卫生间灯 | 20004181 |
| 厨房灯 | 888466709 |
| 小屋开关 | 2042776131 |

### 7. Never Start Backend with `nohup`

Starting `miloco-backend` with `nohup miloco-backend &` bypasses supervisord and causes **pct exec to hang indefinitely** — even `pct exec 310 -- uptime` times out.

**Always use supervisord**:
```bash
# ✅ Correct
pct exec 310 -- supervisorctl -c /root/.openclaw/miloco/supervisord.conf start miloco-backend

# ❌ WRONG — causes container hang
pct exec 310 -- bash -c 'nohup miloco-backend &>/tmp/miloco-backend.log &'
```

If pct exec hangs after a nohup start: `pct exec 310 -- killall miloco-backend`, wait 5s, then restart via supervisord.

See `references/pitfall-nohup-backend-start.md` for full recovery procedure.
