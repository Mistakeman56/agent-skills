# 2026-07-10 — nsenter from PVE host fails to kill LXC container processes

## Symptom
After CLI process pileup (multiple stuck `miloco-cli` processes in D/R state, container load 12+), both `pct exec` and `lxc-attach` hung completely. Attempted to kill processes from PVE host using `nsenter` to enter the container's PID namespace.

## Attempted approach
```bash
# Get container init PID
lxc-info -n 310 -p -H  # returned 657927

# Try to kill stuck processes via nsenter
nsenter -t 657927 -p -- kill -9 775817 776001 776442 775560
# Result: "kill: (775817): No such process" for ALL PIDs
```

## Why it fails
The PVE host's `ps aux` shows container processes with their **internal PIDs** (the PIDs as seen inside the container). However, `nsenter -t <init_pid> -p` enters the container's PID namespace, and the PIDs don't match — the processes visible from the host's ps are not addressable via the container's namespace through nsenter.

This is distinct from the existing `killall -9` unreliability inside `pct exec` (which is a signal delivery issue). `nsenter` fails at a more fundamental level — the PID mapping itself doesn't work for LXC containers in this PVE setup.

## Outcome
Container stop/start was required as the only viable recovery path. The nsenter attempt wasted ~30 seconds but caused no harm.

## Lesson
When both `pct exec` and `lxc-attach` hang completely (Scenario A), do NOT attempt `nsenter` as a workaround for PID-targeted kills. Go directly to container stop/start:
```bash
sshpass -p "<PASSWORD>" ssh root@192.0.2.10 "rm -f /run/lock/lxc/pve-config-310.lock && pct stop 310 && sleep 3 && pct start 310"
```
