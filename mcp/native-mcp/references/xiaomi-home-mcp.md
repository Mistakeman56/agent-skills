# Xiaomi Home MCP Server (gehaiyi/xiaomi-home-mcp)

Control Xiaomi smart home devices (lights, sensors, locks, **XiaoAi speakers**) 
through Hermes Agent via MCP.

**GitHub:** [gehaiyi/xiaomi-home-mcp](https://github.com/gehaiyi/xiaomi-home-mcp) ⭐2355

## Capabilities

| MCP Tool | Description | For Mom's Speaker |
|----------|-------------|-------------------|
| `tts(text)` | Text-to-speech on XiaoAi speaker | ✅ Make it talk |
| `play_music(keyword?)` | Play music on speaker | ✅ |
| `pause_music()` / `resume_music()` | Control playback | ✅ |
| `set_volume(0-100)` | Adjust volume | ✅ |
| `xiaoai_command(text)` | Send voice command | ✅ |
| `get_speaker_status()` | Check playback | ✅ |
| `get_devices()` | List all devices | ✅ |
| `control_device(name, action)` | On/off, brightness, temp | ✅ |
| `get_device_status(name?)` | Query power, temp, humidity | ✅ |

## Setup Steps

### Prerequisites

```bash
# Install uv (required by the MCP server)
pip3 install uv --break-system-packages
# OR: curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Clone

```bash
mkdir -p ~/.hermes/mcps
cd ~/.hermes/mcps
git clone https://github.com/gehaiyi/xiaomi-home-mcp.git
```

### Login (QR Code)

The server uses Xiaomi account QR login. On a headless server, you can't 
use `webbrowser.open()` — use a custom script instead:

**`login_qr.py`** (save in the cloned repo dir):
```python
#!/usr/bin/env python3
"""小米 MCP 登录助手 - 生成二维码图片供扫码登录"""
import asyncio, aiohttp, json, os, time, hashlib
from urllib.parse import quote, urlencode

TOKEN_DIR = os.path.expanduser("~/.xiaomi-mcp")
TOKEN_FILE = os.path.join(TOKEN_DIR, "tokens.json")
UA = "APP/com.xiaomi.mihome APPV/6.0.103 iosPassportSDK/3.9.0 iOS/14.4 miHSTS"
SID = "xiaomiio"

def _parse_json(text):
    if text.startswith("&&&START&&&"):
        text = text[11:]
    return json.loads(text)

async def main():
    os.makedirs(TOKEN_DIR, exist_ok=True)
    device_id = hashlib.md5(f"xiaomi-mcp-qr-{int(time.time())}".encode()).hexdigest()[:16]
    async with aiohttp.ClientSession() as session:
        # 1. Get QR code URL
        qr_params = urlencode({
            "_qrsize": "480",
            "qs": "%3Fsid%3Dxiaomiio%26_json%3Dtrue",
            "callback": "https://sts.api.io.mi.com/sts",
            "_hasLogo": "false", "sid": SID, "serviceParam": "",
            "_locale": "zh_CN", "_dc": str(int(time.time() * 1000)),
        }, quote_via=quote)
        async with session.get(
            f"https://account.xiaomi.com/longPolling/loginUrl?{qr_params}",
            headers={"User-Agent": UA},
            cookies={"sdkVersion": "accountsdk-18.8.15", "deviceId": device_id},
        ) as resp:
            result = _parse_json((await resp.read()).decode("utf-8"))
        qr_url, lp_url, timeout = result["qr"], result["lp"], result.get("timeout", 300)
        
        # 2. Download QR image
        async with session.get(qr_url) as resp:
            img_data = await resp.read()
            qr_path = "~/.hermes/mcps/xiaomi-home-mcp/qr_login.png"
            with open(qr_path, "wb") as f: f.write(img_data)
            print(f"QR saved: {qr_path}")
            print("Scan with Mi Home app (Profile → scan icon)")

        # 3. Poll for scan confirmation
        start = time.time()
        login_result = None
        while time.time() - start < timeout:
            try:
                async with session.get(lp_url, headers={"User-Agent": UA},
                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        login_result = _parse_json((await resp.read()).decode("utf-8"))
                        if login_result.get("passToken"): break
                        if login_result.get("lp"): lp_url = login_result["lp"]
            except asyncio.TimeoutError: continue
            except: continue

        if not login_result or not login_result.get("passToken"):
            print("Timeout — try again"); return
        
        # 4. Save tokens
        tokens = {"userId": str(login_result["userId"]),
                  "passToken": str(login_result["passToken"]), "deviceId": device_id}
        with open(TOKEN_FILE, "w") as f: json.dump(tokens, f, indent=2)
        os.chmod(TOKEN_FILE, 0o600)
        print(f"Login OK! Token saved to {TOKEN_FILE}")

asyncio.run(main())
```

**Run it:**
```bash
cd ~/.hermes/mcps/xiaomi-home-mcp
# Start in background (it waits up to 300s for scan)
python3 login_qr.py
```

Send the generated QR image (`qr_login.png`) to the user. They scan with 
**Mi Home app → My → Scan icon** (top-right corner).

> **Note:** The QR code is a 300-second one-time session. If it times out, 
> just re-run the script for a fresh QR.

### Add to Hermes Config

```yaml
mcp_servers:
  xiaomi:
    command: "uv"
    args:
      - "run"
      - "--script"
      - "~/.hermes/mcps/xiaomi-home-mcp/mcp_server.py"
    timeout: 30
```

After adding, run `/reload-mcp` in-session. Tools appear as `mcp_xiaomi_*`.

## Usage Examples

```python
# Make XiaoAi speaker talk
mcp_xiaomi_tts(text="今天天气不错，记得带伞")

# Check all devices
mcp_xiaomi_get_devices()

# Control a light
mcp_xiaomi_control_device(name="客厅灯", action="on")

# Play music
mcp_xiaomi_play_music(keyword="周杰伦")
```

## Architecture

```
Mi Home App (scan QR) → login.py → ~/.xiaomi-mcp/tokens.json
                                         ↓
Hermes Agent ←→ MCP Protocol ←→ mcp_server.py ←→ Xiaomi Cloud API
                                                    (api.io.mi.com)
```

Control happens through Xiaomi Cloud — no LAN requirement. Works as long 
as the server can reach `api.io.mi.com`.

## Known Issues

- QR login timeout window is 300s; user must scan quickly
- Tokens are long-lived (weeks/months) but eventually expire
- If `mcp_xiaomi_*` tools stop working, re-run login
- `deviceId` in login script uses MD5 of timestamp — this is the same 
  approach as the original `login.py`
