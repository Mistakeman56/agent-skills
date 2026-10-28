# Xiaomi Home MCP — 小米智能家居控制

通过 [gehaiyi/xiaomi-home-mcp](https://github.com/gehaiyi/xiaomi-home-mcp)（⭐2355）接入小米智能家居设备，包括小爱音箱。

## 架构

```
米家App（扫码登录）→ login.py → ~/.xiaomi-mcp/tokens.json
                                     ↓
Hermes Agent ←→ MCP 协议 ←→ mcp_server.py ←→ 小米云 API (api.io.mi.com)
                                               ↓
                                          小米智能设备（音箱、灯、传感器等）
```

所有控制通过小米云 API，不需要设备与服务器在同一局域网。

## 安装

### 1. 安装 uv（Python 包管理器）

```bash
pip install uv --break-system-packages   # Debian/Ubuntu 需要 --break-system-packages
```

或者从官方脚本安装：
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. 克隆仓库

```bash
mkdir -p ~/.hermes/mcps
cd ~/.hermes/mcps
git clone https://github.com/gehaiyi/xiaomi-home-mcp.git
```

### 3. 登录（生成二维码）

仓库自带的 `login.py` 使用 `webbrowser.open()` 打开二维码图片，在**无图形界面的服务器上**需要手动保存图片。

参考 `login_qr.py`（见下方代码块）替代用法：

```python
# login_qr.py 关键改动：
# - 下载二维码图片到 ~/.hermes/mcps/xiaomi-home-mcp/qr_login.png
# - 不调用 webbrowser.open()
# - 打印文件路径供发送
```

```bash
cd ~/.hermes/mcps/xiaomi-home-mcp && python3 login_qr.py
```

用 **米家App** → 我的 → 右上角扫一扫 扫描生成的二维码。

### 4. 配置 Hermes MCP

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  xiaomi-home:
    command: uv
    args:
      - run
      - --script
      - ~/.hermes/mcps/xiaomi-home-mcp/mcp_server.py
    timeout: 30
```

### 5. 验证连接

```bash
hermes mcp test xiaomi-home
# 应看到: ✓ Connected, ✓ Tools discovered: 10
```

### 6. 加载到当前会话

在聊天中发送 `/reload-mcp`，或新开会话。

## 可用工具（10个）

| 工具 | 说明 |
|------|------|
| `get_devices()` | 列出所有小米设备及在线状态 |
| `get_device_status(name?)` | 查询设备详细状态（开关、亮度、温度等） |
| `control_device(name, action)` | 控制设备开关/亮度/色温 |
| `play_music(keyword?)` | 小爱音箱播放音乐 |
| `pause_music()` | 暂停播放 |
| `resume_music()` | 恢复播放 |
| `set_volume(volume)` | 设置音量（0-100） |
| `tts(text)` | **文字转语音，让小爱说话** |
| `xiaoai_command(command)` | 发送语音命令给小爱 |
| `get_speaker_status()` | 获取播放状态 |

## 常见问题

### 二维码扫码超时
登录脚本默认 300 秒超时。如果网络慢，重试时扫快一点。关键窗口期是 5 分钟。

### Token 有效期
Token 长期有效（数周~数月），可能过期。如果 MCP 工具开始报错，重新运行登录。

### 日志路径
Token 保存到 `~/.xiaomi-mcp/tokens.json`（权限 600）。
首次运行 `uv run --script` 会自动下载依赖到 uv 缓存，可能较慢（尤其国内网络）。

## 完整 login_qr.py（无头服务器适配版）

```python
#!/usr/bin/env python3
import asyncio, aiohttp, json, os, time, hashlib
from urllib.parse import quote, urlencode

TOKEN_DIR = os.path.expanduser("~/.xiaomi-mcp")
TOKEN_FILE = os.path.join(TOKEN_DIR, "tokens.json")
UA = "APP/com.xiaomi.mihome APPV/6.0.103 iosPassportSDK/3.9.0 iOS/14.4 miHSTS"
SID = "xiaomiio"

async def main():
    os.makedirs(TOKEN_DIR, exist_ok=True)
    device_id = hashlib.md5(f"xiaomi-mcp-qr-{int(time.time())}".encode()).hexdigest()[:16]
    async with aiohttp.ClientSession() as session:
        # 1. 获取二维码 URL
        qr_params = urlencode({"_qrsize": "480",
            "qs": "%3Fsid%3Dxiaomiio%26_json%3Dtrue",
            "callback": "https://sts.api.io.mi.com/sts",
            "_hasLogo": "false", "sid": SID, "_locale": "zh_CN"}, quote_via=quote)
        async with session.get(
            f"https://account.xiaomi.com/longPolling/loginUrl?{qr_params}",
            headers={"User-Agent": UA},
            cookies={"sdkVersion": "accountsdk-18.8.15", "deviceId": device_id},
        ) as resp:
            result = json.loads((await resp.read()).decode().removeprefix("&&&START&&&"))
        
        qr_url, lp_url = result["qr"], result["lp"]
        
        # 2. 下载二维码图片到本地文件
        async with session.get(qr_url) as resp:
            with open("~/.hermes/mcps/xiaomi-home-mcp/qr_login.png", "wb") as f:
                f.write(await resp.read())
        print("二维码已保存，请用米家App扫码")
        
        # 3. 轮询等待扫码
        start = time.time()
        while time.time() - start < 300:
            try:
                async with session.get(lp_url, headers={"User-Agent": UA},
                        timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        r = json.loads((await resp.read()).decode().removeprefix("&&&START&&&"))
                        if r.get("passToken"):
                            break
                        lp_url = r.get("lp", lp_url)
            except: continue
        
        if "passToken" not in locals():
            print("超时"); return
        
        with open(TOKEN_FILE, "w") as f:
            json.dump({"userId": str(r["userId"]), "passToken": str(r["passToken"]), "deviceId": device_id}, f)
        os.chmod(TOKEN_FILE, 0o600)
        print("登录成功")

asyncio.run(main())
```
