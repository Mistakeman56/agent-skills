# Weixin (个人微信) Gateway 接入

## 概述

Hermes 原生支持个人微信接入（`gateway/platforms/weixin.py`），使用腾讯 **iLink Bot API**（`ilinkai.weixin.qq.com`）。与 WeCom（企业微信）是独立的接入方式，配置完成后用户可以在微信里跟 Hermes 对话。

## 配置项

| 环境变量 | 说明 | 来源 |
|----------|------|------|
| `WEIXIN_ACCOUNT_ID` | 微信账号标识 | QR 登录成功后自动获取 |
| `WEIXIN_TOKEN` | API 鉴权令牌 | QR 登录成功后自动获取 |

## QR 登录步骤

### 1. 请求二维码（无需 OpenClaw）

直接调用 iLink API 获取二维码信息：

```bash
curl -s 'https://ilinkai.weixin.qq.com/ilink/bot/get_bot_qrcode?bot_type=3'
```

响应示例：
```json
{
  "qrcode": "0bf5aff34c1682a4bc43fd83e7804ebc",
  "qrcode_img_content": "https://liteapp.weixin.qq.com/q/7GiQu1?qrcode=...",
  "ret": 0
}
```

- `qrcode` — hex token，用于轮询扫码状态
- `qrcode_img_content` — 微信 liteapp 可扫码完整 URL

### 2. 生成二维码图片

Python（需要 `pip install qrcode[pil]`）或在线 QR API：

```bash
curl -s 'https://api.qrserver.com/v1/create-qr-code/?size=500x500&data=<URL_ENCODED_QR_DATA>' -o /tmp/weixin_qr.png
```

### 3. 发送给用户扫码

如果通过 WeCom 对话，用 `MEDIA:/path/to/qr.png` 语法发送；用户用微信扫码后 Hermes 自动获取 credentials。

### 4. 轮询扫码状态

```bash
# 轮询，qrcode 替换为上面拿到的值
curl -s "https://ilinkai.weixin.qq.com/ilink/bot/get_qrcode_status?qrcode=<HEX_TOKEN>"
```

扫码成功后的响应包含 `WEIXIN_ACCOUNT_ID` 和 `WEIXIN_TOKEN`。

### 5. 持久化到配置

```yaml
# ~/.hermes/config.yaml
messaging:
  weixin:
    enabled: true
```

同时将获取到的 token 写入 `~/.hermes/.env` 或对应环境变量。

### 6. 重启网关

```bash
hermes gateway restart
```

## 注意事项

- **Host 需要 `aiohttp` 和 `cryptography`** — Hermes gateway 的微信适配器依赖这两个 Python 包
- **证书问题** — iLink 服务器证书在某些 macOS 系统 CA 存储中不可验证，需要 `certifi` 包提供 Mozilla CA bundle
- **`qrcode` Python 包** — 可选依赖。没有时终端二维码渲染会降级为仅打印 URL，不影响功能
- **与 OpenClaw 无关** — 微信接入是 Hermes 的原生功能，不需要安装 OpenClaw
- **网关重启生效** — 加完配置后必须重启 gateway 才能启用微信平台
- **与 WeCom 不冲突** — 可以同时启用 WeCom 和 Weixin，互不影响

## 多用户限制与解决方案

### 已知限制
iLink Bot API 的 `get_bot_qrcode` 每次调用都生成一个**全新的 bot 实例**（不同的 `ilink_bot_id`）。每个二维码只能绑定**一个微信用户**，无法让多个用户共享同一个 bot 实例。

表现：当用户 A 扫码绑定 bot_X，用户 B 扫码绑定 bot_Y，gateway 只连接 bot_X，B 的消息 gateway 收不到。

### 验证方法
```bash
# 生成二维码
curl -s 'https://ilinkai.weixin.qq.com/ilink/bot/get_bot_qrcode?bot_type=3'
# 扫码后查状态（每个返回不同的 ilink_bot_id）
curl -s 'https://ilinkai.weixin.qq.com/ilink/bot/get_qrcode_status?qrcode=<HEX>'
```

### 解决方案：侧车中继脚本
对于需要接入第二个微信用户的场景，编写独立的 Python sidecar 脚本：

```
思路：独立进程轮询第二个 bot 的 get_updates API →
      收到消息后写入 JSONL 文件或调用 Hermes API Server →
      Hermes 主进程读取并处理
```

关键点：
- 需安装 `python3-aiohttp python3-certifi`
- 每个 bot 的 token 有时效性，扫码后需尽快使用
- 中继脚本写入 `~/.hermes/logs/mom_relay.log`，消息记录到 `~/.hermes/mom_messages.jsonl`
- 用 `terminal(background=true)` 启动中继进程

### 通过侧车中继回复消息（⚠️ 必须共享 HTTP 会话）

#### 核心坑：iLink 要求 sendmessage 与 getupdates 使用同一个 HTTP 连接

**这是最容易被忽略的问题。** 如果 `sendmessage` 使用独立的 `aiohttp.ClientSession`（或者通过 CLI 每次新建连接去调用），iLink 会把它当做不同的连接/会话处理。虽然 API 可能返回 `ret=0` 或空 `{}`，但**消息实际上不会送达对方微信**。

**正确做法：收和发必须共用一个持久 `aiohttp.ClientSession`。**

推荐架构：**轮询循环内部处理发送，使用队列机制**：

```
独立进程（cron job / your code）
    ↓ 写入 JSONL 队列文件
轮询进程（内部共享同一 aiohttp 会话）
    ↓ 用共享会话调用 sendmessage
微信用户收到消息 ✅
```

关键代码模式：

```python
# 轮询循环同时处理接收和发送
async def poll():
    connector = _make_connector()
    async with aiohttp.ClientSession(trust_env=True, connector=connector) as session:
        # ↑ 这个 session 被收和发共享 ↑
        while True:
            # 1. 收消息（getupdates）
            resp = await _api_post(session, "ilink/bot/getupdates", ...)

            # 2. 检查发送队列文件，用同一个 session 发
            for entry in read_queue():
                await send_message(session, entry["text"], ctx_token)
```

发送函数使用共享 session：

```python
async def send_message(session, text, ctx_token=None):
    message = {
        "from_user_id": "",
        "to_user_id": "<对方微信ID@im.example>",
        "client_id": f"hermes-weixin-{uuid.uuid4().hex}",
        "message_type": 2,
        "message_state": 2,
        "item_list": [{"type": 1, "text_item": {"text": text}}],
    }
    if ctx_token:
        message["context_token"] = ctx_token
    resp = await _api_post(session, "ilink/bot/sendmessage", {"msg": message}, 15000)
```

发送队列文件格式（`mom_send_queue.jsonl`），一行一个 JSON，轮询自动消费：

```json
{"text": "回复内容"}
```

#### 请求格式参考

```python
msg = {
    "from_user_id": "",
    "to_user_id": "<对方微信ID@im.example>",
    "client_id": f"hermes-weixin-{uuid.uuid4().hex}",  # 每次唯一的 client_id
    "message_type": 2,     # MSG_TYPE_BOT
    "message_state": 2,    # MSG_STATE_FINISH
    "item_list": [{"type": 1, "text_item": {"text": "回复内容"}}]
}
body = json.dumps({"msg": msg, "base_info": {"channel_version": "2.2.0"}},
                   ensure_ascii=False, separators=(",", ":"))
```

⚠️ **客户端 ID：** 每次发送应生成新的唯一 `client_id`（如 `hermes-weixin-{uuid}`），不要复用 bot 的 account_id。

#### 响应码解释

可复用的中继模板见 `templates/ilink-relay-template.py`（hermes-agent skill 内）。

| 响应 | 含义 |
|------|------|
| `{"ret": 0}` 或 `{"ret": 0, "errcode": 0}` | 发送成功 ✅ |
| `{}`（空 JSON，HTTP 200） | **连接/会话不匹配，消息可能未送达 — 检查是否用了共享 session** |
| `{"ret": -14}` 或 `{"errcode": -14}` | session 过期 — 去掉 context_token 重试 |
| `{"ret": -2, "errcode": -2, "errmsg": "unknown error"}` | 陈旧 session（同 -14） |
| `{"ret": -1}` | 参数/格式有误 |
| `{"ret": -2}`（无 errmsg 或非 "unknown error"） | 频率限制 — 等待后重试 |

#### context_token 管理

`context_token` 从收到的消息中提取并缓存。每次收到消息时保存：

```python
# 从 getupdates 响应中提取
for msg in resp.get("msgs") or []:
    ctx_token = str(msg.get("context_token") or "").strip()
    if ctx_token:
        # 保存到文件 / 内存缓存
        save_context_token(ctx_token)
```

发送时带上缓存的 context_token。如果 session 过期（-14），去掉 token 重试一次。
    "Content-Type": "application/json",
    "AuthorizationType": "ilink_bot_token",
    "Content-Length": str(len(body.encode())),
    "X-WECHAT-UIN": random_uin(),      # 每次不同的随机值
    "iLink-App-Id": "bot",
    "iLink-App-ClientVersion": str((2<<16) | (2<<8) | 0),
    "Authorization": f"Bearer {token}", # 完整token包含前缀
}

# 随机UIN生成函数
def random_uin():
    import secrets, struct, base64
    v = struct.unpack(">I", secrets.token_bytes(4))[0]
    return base64.b64encode(str(v).encode()).decode("ascii")
```

**注意：** `context_token` 可通过先调用 `getconfig`（带 `ilink_user_id` 参数）获取。若 `sendmessage` 返回 `ret=-1`，通常表示参数/格式有误而非会话过期；返回 `ret=-14` 才是 session 过期。响应 `{}`（空 JSON）可能是成功，也可能是格式错误——需结合网关日志判断。
