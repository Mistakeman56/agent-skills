# 2026-07-09: pgrep as fallback when ps aux hangs in partial hang

## Symptom
Pre-run script timeout. `pct exec` hung. `lxc-attach echo` worked, `lxc-attach ps aux` hung.

## Key discovery
`lxc-attach -n 310 -- pgrep -la python3` **worked** even though `ps aux` hung.
`lxc-attach -n 310 -- pgrep -la miloco` also worked.

This revealed:
- supervisord (PID 323)
- miloco-cli service start (PID 17163) — **stuck**
- miloco.main (PID 17174)

## Recovery
PID-targeted kill of all three → clear socket → supervisord restart → health OK at 15s.

## Takeaway
When diagnosing partial lxc-attach/pct exec hangs, try `pgrep -la <process>` **before** `ps aux`. If pgrep works, you can identify PIDs and do PID-targeted nuclear restart without needing container stop/start. Container stop/start is more disruptive and should be reserved for when pgrep also hangs.
