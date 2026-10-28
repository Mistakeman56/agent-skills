#!/bin/bash
# LoL blackbox (netlog) parser - run in Git Bash ON the PC:
#   ssh user@192.0.2.10 'bash -s' < scripts/netlog-blackbox.sh
# Override game dir:  GD=/path bash netlog-blackbox.sh
# Labels are ASCII on purpose (Windows remote scripting rule); Chinese only in
# the default path value.
GD="${GD:-/d/WeGameApps/英雄联盟/Game/Logs/GameLogs}"
if [ ! -d "$GD" ]; then echo "GameLogs dir not found: $GD (set GD=...)"; exit 1; fi

echo "=== sessions ==="
for d in "$GD"/20*; do
  n=$(ls "$d"/*netlog.txt 2>/dev/null | head -1)
  [ -n "$n" ] || continue
  first=$(grep -vE 'Packet Loss|flag to indicate|\[time\]|^$' "$n" | head -1 | cut -c1-19)
  last=$(grep -vE 'Packet Loss|flag to indicate|\[time\]|^$' "$n" | tail -1 | cut -c1-19)
  echo "$(basename "$d"): [$first -> $last]"
done

echo ""
echo "=== per-session: reconnects / loss / ping ==="
# PITFALL: line prefixes use HYPHENS (2026-10-10T12-13-19:). Match ^[0-9] then
# strip with [0-9-]*T[0-9-]*:  -- a T[0-9:]+: regex silently matches 0 rows.
# Data-row cols: 1=time 7=loss 9=ping 24=reconnect. Header rows contain the
# words "Packet Loss"/"reconnect = flag": never grep keywords, parse columns.
for d in "$GD"/20*; do
  n=$(ls "$d"/*netlog.txt 2>/dev/null | head -1)
  [ -n "$n" ] || continue
  S=$(basename "$d")
  grep '^[0-9]' "$n" | sed 's/^[0-9-]*T[0-9-]*: //' | awk -F',' -v S="$S" '
    NF>=23 {
      t=$1; gsub(/^ +| +$/,"",t)
      ping=$9+0; loss=$7+0; rc=$24+0; gsub(/ /,"",rc)
      total++
      if (rc>0) { rcs++; if (rcs<=8) printf "%s reconnect @%s ping=%d loss=%d\n", S, t, ping, loss }
      if (loss>0) { lc++; if (loss>maxl) {maxl=loss; maxlt=t} }
      if (ping>maxp) {maxp=ping; maxpt=t}
      sum+=ping
    }
    END {
      if (total>0) printf "%s | samples=%d reconnects=%d loss_rows=%d max_loss=%d@%s max_ping=%d@%s avg_ping=%d\n\n", S, total, rcs+0, lc+0, maxl, maxlt, maxp, maxpt, sum/total
      else printf "%s | no data rows (check prefix regex)\n\n", S
    }
  '
done
