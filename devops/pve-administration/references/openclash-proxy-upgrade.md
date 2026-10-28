# OpenClash plugin + kernel upgrade (iStoreOS)

## Trigger
- User asks "is my OpenClash version too old, should I update"
- Proxy is flaky / kernel is old
- "LuCI says it's enabled but the proxy doesn't work"

## 0. Read the state first, don't touch anything yet
```sh
/etc/init.d/openclash status          # running / inactive
uci -q get openclash.config.enable    # 1 = should be running
/etc/init.d/openclash enabled && echo autostart-ON || echo autostart-OFF
uci -q get openclash.@authentication[0].enabled   # 1 = clients need a password (407)
uci -q get openclash.config.core_version          # decides which kernel asset to fetch
```

**"LuCI shows enabled, proxy still unusable" has TWO independent causes — diagnose separately:**
1. `enable=1` but service `inactive` → the process simply isn't running (autostart was never enabled,
   so it didn't come back after the last reboot).
2. Service running but clients can't connect → check `@authentication[0].enabled`; if it's on, every
   request without credentials gets `407 Proxy Authentication Required` (with `Proxy-Authenticate: Basic`).

## 1. Version comparison (give the user the verdict, then ask before upgrading)
```sh
grep '^Version:' /usr/lib/opkg/info/luci-app-openclash.control      # plugin version
cat /etc/openclash/core/clash_meta_version                          # kernel version
/etc/openclash/clash -v                                             # kernel self-report
```
Fetch latest from GitHub Releases — **download through the router's own proxy**, direct GitHub is slow
in China:
```sh
curl -s -m 20 -x http://<router>:7890 \
  'https://api.github.com/repos/MetaCubeX/mihomo/releases?per_page=8' | grep -E '"tag_name"|"prerelease"'
curl -s -m 20 -x http://<router>:7890 \
  'https://api.github.com/repos/vernesong/OpenClash/releases?per_page=3' | grep -E '"tag_name"|browser_download_url.*ipk'
```
- Take a **stable** release (`prerelease: false`); skip `Prerelease-Alpha`.
- **The asset name must match `core_version`**: `linux-amd64-v1` ↔ `mihomo-linux-amd64-v1-<ver>.gz`.
  Other variants (`-v2-`, `-v3-`, `-compatible-`, `-go120-`) exist; the wrong one may not start.
- The plugin package is `luci-app-openclash_<ver>_all.ipk`.

## 2. Download locally → scp → upgrade
```sh
# download on YOUR machine through the router proxy, not curl-on-router
curl -L -x http://<router>:7890 -o /tmp/oc-update/kernel.gz '<kernel asset url>'
curl -L -x http://<router>:7890 -o /tmp/oc-update/oc.ipk    '<ipk url>'
gzip -t /tmp/oc-update/kernel.gz          # verify before transferring
gunzip -c /tmp/oc-update/kernel.gz > /tmp/mihomo_test && chmod +x /tmp/mihomo_test && /tmp/mihomo_test -v
```
```sh
scp -P <ssh-port> /tmp/oc-update/kernel.gz root@<router>:/tmp/mihomo-new.gz
scp -P <ssh-port> /tmp/oc-update/oc.ipk    root@<router>:/tmp/openclash-new.ipk
```
On the router — **order: stop service → swap kernel → install ipk → set enable → start service**:
```sh
/etc/init.d/openclash stop
cp /etc/openclash/core/clash_meta /root/oc-backup/clash_meta.before-update
gunzip -c /tmp/mihomo-new.gz > /etc/openclash/core/clash_meta.new
chmod 755 /etc/openclash/core/clash_meta.new
/etc/openclash/core/clash_meta.new -v >/dev/null 2>&1 || exit 1   # don't swap in a kernel that won't run
mv /etc/openclash/core/clash_meta.new /etc/openclash/core/clash_meta
echo "<new version>" > /etc/openclash/core/clash_meta_version
opkg install /tmp/openclash-new.ipk
```

## 3. ★ ALWAYS CHECK: installing the ipk resets `enable` to 0
After the plugin upgrade `uci -q get openclash.config.enable` flips back to `0`, the service won't start,
and the only log line is:
```
[Warning] OpenClash Now Disabled, Need Start From Luci Page, Exit...
```
**This is not a broken config** — `clash -t -f config/9.1.yaml` passes cleanly. Just flip the switch back:
```sh
uci set openclash.config.enable='1' && uci commit openclash
/etc/init.d/openclash start
```
With `enable=0` the new version **only allows starting from the LuCI page** and rejects CLI start outright,
so don't sit in the CLI retrying it.

## 4. Acceptance (all of these)
```sh
/etc/init.d/openclash status                       # running
ps | grep -c '[c]lash'                             # process exists
netstat -lntp | grep -E '7890|9090'                # ports listening
curl -s -o /dev/null -w '%{http_code}\n' -x http://127.0.0.1:7890 https://www.google.com/generate_204
curl -s -o /dev/null -w '%{http_code}\n' -x http://127.0.0.1:7890 http://www.baidu.com
grep '^Version:' /usr/lib/opkg/info/luci-app-openclash.control   # version actually changed
```

## 5. Backup and rollback
```sh
tar czf /root/oc-backup/openclash-config-$(date +%Y%m%d-%H%M%S).tar.gz /etc/openclash
cp /etc/config/openclash /root/oc-backup/config.openclash.before-update
```
Rollback: copy the old kernel back + rewrite the version file + `uci set openclash.config.enable='1'` +
`/etc/init.d/openclash restart`; restore config with `tar xzf … -C /`.

## Pitfalls
1. **`uci commit` after every `uci set`** or the change is lost on reboot.
2. **Re-set `enable=1` after the upgrade** (section 3) — the single easiest step to miss, and it makes
   the user believe "the upgrade broke my proxy".
3. **Check who else depends on the proxy before downing it.** If a container has a global
   `HTTP_PROXY=http://…@<router>:7890`, stopping the proxy instantly breaks every proxied request in that
   container. Symptom and discriminator: `hermes-model-failover` → "SSH CLI silent while WeChat works".
4. **`enable=0` means CLI start is refused** — stop retrying, set it to 1 or use LuCI.
5. The upgrade window briefly interrupts the proxy — tell the user before you start.
6. **Confirm who stopped it if you find it off later.** An orderly stop
   (`[Tip] OpenClash Stoping...` followed by the 5-step shutdown) came from an admin action, not a crash —
   ask before "fixing" it, because re-enabling something the user deliberately turned off is worse than leaving it.
