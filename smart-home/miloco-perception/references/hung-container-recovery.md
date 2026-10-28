# Hung Container Recovery — CT <ID>

## Symptom
- `pct exec 310 -- echo OK` hangs (timeout after 15s)
- PVE host is reachable via SSH
- `pct status 310` shows "running"
- Load average on PVE may be elevated (9+)

## Diagnosis
```bash
sshpass -p "..." ssh root@192.0.2.10 "uptime && pct status 310"
```
If `pct exec` hangs but status is "running", container is hung.

## Fix: stop + start (NOT reboot)
`pct reboot` can also hang for a hung container. Use:
```bash
sshpass -p "..." ssh root@192.0.2.10 "pct stop 310"   # succeeds
sshpass -p "..." ssh root@192.0.2.10 "pct start 310"  # succeeds
```

## ⚠️ PITFALL: Lock File Blocks `pct stop`

When `pct stop` fails with:
```
trying to acquire lock...
can't lock file '/run/lock/lxc/pve-config-310.lock' - got timeout
```

Remove the stale lock file first:
```bash
sshpass -p "..." ssh root@192.0.2.10 "rm -f /run/lock/lxc/pve-config-310.lock && pct stop 310"
```

## Post-restart patience
1. Wait 10s after `pct start` before first `pct exec`
2. **Check supervisord** — it may NOT auto-start after container stop+start:
   ```bash
   sshpass -p "..." ssh root@192.0.2.10 \
     "pct exec 310 -- bash -c 'ps aux | grep supervisord | grep -v grep'"
   ```
   If no supervisord process: start it manually (⚠️ use FULL PATH — `nohup supervisord` fails with "No such file" even after PATH export):
   ```bash
   sshpass -p "..." ssh root@192.0.2.10 \
     "pct exec 310 -- bash -c 'nohup /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf &>/tmp/supervisord.log &'"
   sleep 5
   ```
   Then verify supervisord is running and miloco-backend is STARTING/RUNNING:
   ```bash
   sshpass -p "..." ssh root@192.0.2.10 \
     "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; supervisorctl -c /root/.openclaw/miloco/supervisord.conf status'"
   ```
3. miloco-backend needs ~30s after supervisord starts to become available
4. First `miloco-cli perceive logs` call will return:
   `{"error": "cannot connect to Miloco backend at http://127.0.0.1:1810"}`
5. Retry after 15s sleep

## PATH fallback
After cold container start, `miloco-cli` may not be on PATH.
Use full path: `/usr/local/bin/miloco-cli`

## Complete recovery sequence
```bash
HOST=root@192.0.2.10
PASS="<PASSWORD>"

# 1. Diagnose
sshpass -p "$PASS" ssh -o ConnectTimeout=5 $HOST "uptime && pct status 310"
sshpass -p "$PASS" ssh -o ConnectTimeout=5 $HOST "pct exec 310 -- echo OK"  # expect hang

# 2. Recover
sshpass -p "$PASS" ssh -o ConnectTimeout=5 $HOST "pct stop 310"
sshpass -p "$PASS" ssh -o ConnectTimeout=5 $HOST "pct start 310"

# 3. Wait for container to boot
sleep 10
sshpass -p "$PASS" ssh -o ConnectTimeout=5 $HOST "pct exec 310 -- echo OK"

# 4. Check supervisord — may NOT auto-start after container restart
sshpass -p "$PASS" ssh -o ConnectTimeout=5 $HOST \
  "pct exec 310 -- bash -c 'ps aux | grep supervisord | grep -v grep'"
# If no output, start supervisord manually (use FULL PATH):
sshpass -p "$PASS" ssh -o ConnectTimeout=5 $HOST \
  "pct exec 310 -- bash -c 'nohup /usr/local/bin/supervisord -c /root/.openclaw/miloco/supervisord.conf &>/tmp/supervisord.log &'"
sleep 5

# 5. Verify supervisord + backend status
sshpass -p "$PASS" ssh -o ConnectTimeout=5 $HOST \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; supervisorctl -c /root/.openclaw/miloco/supervisord.conf status'"

# 6. Wait for backend to bind port 1810 (~30s after supervisord start)
sleep 15
sshpass -p "$PASS" ssh -o ConnectTimeout=5 $HOST \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; export MILOCO_TOKEN=95ac63403f1f45a38f66f72bd085b27b81c2352c3f1546f991c03c07f3f7a082; miloco-cli perceive logs --since 1h --limit 5 --jsonl 2>&1'"

# 7. Post-recovery verification — "No logs found" is EXPECTED, not a failure
# CLI quirk: `perceive devices` accepts NO `--jsonl` flag (unlike `perceive logs`) —
# passing it errors with "No such option '--jsonl'". Call it plain.
# The engine was down during the outage window, so `perceive logs --since 24h` can return
# "No logs found" even after a fully healthy restart. Do NOT treat empty logs as continued failure.
# Confirm health via the devices endpoint instead:
sshpass -p "$PASS" ssh -o ConnectTimeout=5 $HOST \
  "pct exec 310 -- bash -c 'export PATH=/usr/local/bin:$PATH; export MILOCO_TOKEN=95ac63403f1f45a38f66f72bd085b27b81c2352c3f1546f991c03c07f3f7a082; miloco-cli perceive devices'"
# Expect: {"code": 0, "message": "ok", ...} with cameras "online": true.
# Healthy = miloco-backend RUNNING + cameras online + (possibly empty) logs.
# Also check `uptime` inside CT <ID>: load should be dropping back toward normal.
```
