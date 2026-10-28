# 2026-07-11 Cron: test -f vs which in Partial Hang

## Summary
Container was in partial hang state. `which miloco-cli` failed but `test -f /usr/local/bin/miloco-cli` confirmed the binary existed. This is a diagnostic gap — the skill previously recommended `which` for binary existence checks, but `which` is unreliable in partial hang.

## Commands and Results

| Command | Result | Time |
|---------|--------|------|
| `pct exec 310 -- echo hello` | ✅ `hello` | instant |
| `pct exec 310 -- pwd` | ✅ `/root` | instant |
| `pct exec 310 -- test -f /usr/local/bin/miloco-cli` | ✅ `EXISTS` | instant |
| `pct exec 310 -- which miloco-cli` | ❌ exit 1, `NOT_FOUND` | instant |
| `pct exec 310 -- /usr/local/bin/miloco-cli --help` | ❌ timeout 20s | 20s |
| `pct exec 310 -- /usr/local/bin/miloco-cli perception log --limit 5` | ❌ timeout 45s | 45s |
| `pct exec 310 -- ls /usr/local/bin/` | ❌ timeout 20s | 20s |
| `pct exec 310 -- ps aux \| head -15` | ❌ timeout 20s | 20s |

## Key Finding
`which` is a shell built-in that requires spawning a subprocess to resolve PATH. In partial hang, the container's exec subsystem can handle simple builtins (`test`, `echo`) but not subprocess-spawning commands. `test -f` is a true shell builtin that doesn't need subprocess spawning.

## Lesson
Always use `test -f <fullpath>` instead of `which <name>` for binary existence checks in partial hang scenarios. The skill's "3-level probe" should include this as an alternative.

## Diagnosis
- PVE host: reachable (ping OK, SSH OK)
- CT <ID>: running (pct status OK)
- Binary: exists (`test -f` confirms)
- miloco-cli: hangs (all subprocess commands timeout)
- Pattern: classic partial hang (builtin ok, subprocess fail)
