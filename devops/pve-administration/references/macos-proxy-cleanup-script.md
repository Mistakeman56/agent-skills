## macOS Proxy Cleanup Script

### 问题背景
v2raya退出后不清理macOS系统代理，且代理配置在系统中多层持久化。最隐蔽的是Tailscale VPN的plist配置里嵌入了代理设置。

### 三层代理残留
| 层 | 位置 | networksetup能清？ |
|---|---|---|
| ① Wi-Fi 接口 | `networksetup -getwebproxy Wi-Fi` | ✅ 能 |
| ② SystemConfiguration plist | `preferences.plist → NetworkServices.<UUID>.Proxies` | ❌ 不能 |
| ③ Tailscale VPN 嵌套 | `NetworkServices.<Tailscale-UUID>.VPN.Proxies` | ❌ 不能 |

### 根因：Tailscale VPN的两层代理
plist里Tailscale服务同时有：
- 顶层 `NetworkServices.<UUID>.Proxies` → `HTTPPort: 52345`
- VPN嵌套 `NetworkServices.<UUID>.VPN.Proxies` → `HTTPPort: 52345`

Tailscale激活时VPN层代理优先级高于Wi-Fi，scutil显示52345而非Wi-Fi的7897。

### 识别Tailscale的UUID
```python
import plistlib
with open("/Library/Preferences/SystemConfiguration/preferences.plist", "rb") as f:
    d = plistlib.load(f)
for sid, sd in d.get("NetworkServices", {}).items():
    if isinstance(sd, dict):
        name = sd.get("UserDefinedName", "?")
        if "Tailscale" in name:
            print(f"UUID: {sid}")
            print(f"  Top-level Proxies: {sd.get('Proxies', {})}")
            print(f"  VPN.Proxies: {sd.get('VPN', {}).get('Proxies', {})}")
```

### 一次性修复（plistlib + expect sudo）
```python
import plistlib
path = "/Library/Preferences/SystemConfiguration/preferences.plist"
with open(path, "rb") as f:
    d = plistlib.load(f)
for sid, sd in d.get("NetworkServices", {}).items():
    if isinstance(sd, dict):
        name = sd.get("UserDefinedName", "?")
        if "Tailscale" in name:
            for proxy_path in [sd.get("Proxies", {}), sd.get("VPN", {}).get("Proxies", {})]:
                for k in ["HTTPEnable","HTTPPort","HTTPProxy","HTTPSEnable","HTTPSPort","HTTPSProxy","SOCKSEnable"]:
                    if k in proxy_path:
                        proxy_path[k] = 0 if "Enable" in k or "Port" in k else ""
        p = sd.get("Proxies", {})
        if "ProxyAutoConfigURLString" in p and "33331" in str(p["ProxyAutoConfigURLString"]):
            del p["ProxyAutoConfigURLString"]
            p["ProxyAutoConfigEnable"] = 0
with open(path, "wb") as f:
    plistlib.dump(d, f)
```

### 持久化修复（LaunchAgent + PlistBuddy）
每次开机Tailscale会重新写入代理。用LaunchAgent在登录后5秒自动清理：
```bash
cat > ~/fix_proxy_and_start.sh << 'EOF'
#!/bin/bash
sleep 5
/usr/libexec/PlistBuddy -c "Delete :NetworkServices:<TAILSCALE_UUID>:VPN:Proxies" /Library/Preferences/SystemConfiguration/preferences.plist 2>/dev/null
/usr/libexec/PlistBuddy -c "Delete :NetworkServices:<TAILSCALE_UUID>:Proxies" /Library/Preferences/SystemConfiguration/preferences.plist 2>/dev/null
networksetup -setwebproxy "Wi-Fi" 127.0.0.1 7897
networksetup -setsecurewebproxy "Wi-Fi" 127.0.0.1 7897
networksetup -setwebproxystate "Wi-Fi" on
networksetup -setsecurewebproxystate "Wi-Fi" on
if ! pgrep -f verge-mihomo > /dev/null; then
    nohup "/Applications/Clash Verge.app/Contents/MacOS/verge-mihomo" \
      -d "$HOME/Library/Application Support/io.github.clash-verge-rev.clash-verge-rev" \
      -f "$HOME/Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/direct-config.yaml" \
      > /tmp/mihomo.log 2>&1 &
fi
EOF
```

### Safari iCloud Private Relay（2026-06-06）
即使系统代理正常，Safari可能因Private Relay无法连接：
- `defaults read com.apple.Safari WBSPrivacyProxyAvailabilityActiveOnDefaultNetwork` → 1 = 激活
- 修复：Safari → 设置 → 隐私 → 隐藏IP地址 → 关闭
- Chrome不受影响（Chrome不使用Private Relay）
- 区分：Chrome能开Safari不行 = Private Relay问题；两个都不行 = 系统代理问题

### 验证代理生效
```bash
# scutil可能有缓存残留，不要完全信任
scutil --proxy | grep -E "HTTP|nable"

# curl测试最可靠
curl -s -o /dev/null -w "YouTube: %{http_code}\n" "https://www.youtube.com" --max-time 10

# 让用户在浏览器实际打开确认（curl通过≠浏览器通过）
```
