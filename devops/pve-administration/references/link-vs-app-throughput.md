# Link bandwidth vs application throughput: who is actually the bottleneck

When the user says "I have a X-gigabit line, why am I only getting Y", **separate the link from the
application before digging into either.**

## Discriminator: pull a file from a public mirror with concurrency, on the same host
```sh
# single thread
curl -s -o /dev/null -m 12 -w "%{speed_download} B/s\n" --noproxy '*' \
  https://mirrors.cloud.tencent.com/ubuntu/ls-lR.gz
# 8 concurrent (a single stream not saturating the link is NORMAL)
for i in $(seq 8); do
  curl -s -o /dev/null -m 12 -w "%{speed_download}\n" --noproxy '*' \
    https://mirrors.cloud.tencent.com/ubuntu/ls-lR.gz &
done; wait
```
8 streams hitting the subscribed rate while one stream only manages a few hundred Mbps is **expected**
(TCP window / per-session shaping), not a fault. **If the concurrent test hits the line rate, the link is
healthy and the problem is on the application's server side.**

**Always pass `--noproxy '*'`**: containers commonly carry a global `HTTP_PROXY`, and without it you
measure the proxy, not the line.

## Read the application's own log for per-server throughput
Only the app's log tells you what each server actually granted. Steam example (Windows):
```powershell
$sp = (Get-ItemProperty 'HKCU:\Software\Valve\Steam').SteamPath
$log = Join-Path $sp 'logs\content_log.txt'
Select-String $log -Pattern 'Current download rate' | Select-Object -Last 6
Select-String $log -Pattern 'stats.*dl\.' | Select-Object -Last 6
```
- `stats: (CDN, N) <host>: N bytes, N sec (X Mbps)` gives **each CDN's individual grant**. Several CDNs at
  30–70 Mbps summing to exactly what the user reported → source-side cap; nothing local can fix it.
- `Current download rate` is sampled per minute — use it for trend.
- Historical peak by date proves what it *used to* do:
  ```powershell
  Select-String $log -Pattern 'Current download rate: ([\d.]+)' -AllMatches |
    ForEach-Object { $_.Matches } | ForEach-Object { [double]$_.Groups[1].Value } |
    Sort-Object -Descending | Select-Object -First 10
  ```
  **Anchor the conversation on the historical peak**, not on an impression.

## Pitfalls
1. **`rx_dropped` / `rx_errors` are cumulative — never alarm on the absolute value.** They are kernel
   buffer drops, not physical-layer errors (for those look at `rx_crc_errors`). Judge by the **delta
   between two samples**:
   ```sh
   a=$(cat /sys/class/net/ethX/statistics/rx_dropped); sleep 10
   b=$(cat /sys/class/net/ethX/statistics/rx_dropped); echo $((b-a))
   ```
   Tens of thousands of drops out of tens of millions of packets is a few parts per ten thousand — ignorable.
2. **A `qdisc`'s `overlimits` counter looks like shaping but is not proof of it.** Settle it with an A/B run
   (shaping off vs on); a ratio anywhere near 1.0 clears it. Don't convict a component on a counter alone.
3. **A game accelerator (UU etc.) is not automatically the culprit.** It doesn't use the system proxy (it
   redirects at the driver layer), so "no proxy configured" doesn't clear it — but **if turning it off
   changes nothing, drop it and move on.**
4. **Don't expect the app's "server region" setting to be the lever.** Download regions (e.g. Steam's
   CellID) are usually derived from the egress IP; deleting a pinned override just makes the app pick the
   same region again. Change regions from the app's UI, and verify the CDN actually changed.
5. **Stop the application under test before measuring**, or the two compete for the line and the numbers
   mean nothing.
6. **Don't skip the bridge/switch in the middle.** A link that negotiates 2.5G can still be the bottleneck
   if an intermediate switch is degrading — negotiate speed is not throughput. **But don't convict the
   switch on an app-level number either**: settle a suspect hop with an A/B ping from a host on both sides
   (direct vs through the device) before touching config — see `lan-switch-discovery-and-latency-ab.md`.
   A number produced inside a container or a browser measures that container/browser, not the link
   (NAT段 + TLS/JS/render CPU + JS timer granularity) — see the 测量陷阱 table in
   `home-network-outage-forensics.md`.
